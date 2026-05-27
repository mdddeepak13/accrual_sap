"""FastAPI application.

Endpoints:
  GET  /health            — liveness + config flags
  POST /runs              — kick off a pipeline run, return run_id
  GET  /runs/{run_id}     — fetch run status + flagged items

POST /runs awaits the pipeline synchronously and returns once it's done.
A serverless function instance is not guaranteed to keep running after the
response returns, so `asyncio.create_task` style background tasks would be
dropped. The pipeline takes ~20s for the fixture dataset, well under the
default 300s function timeout.
"""
from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator

import structlog
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import RedirectResponse

from fastapi.middleware.cors import CORSMiddleware

from accrual_pipeline.config import get_settings
from accrual_pipeline.fetchers.base import create_sap_client, create_btp_client
from accrual_pipeline.fetchers.co import fetch_cost_centers
from accrual_pipeline.fetchers.fi import fetch_journal_entries
from accrual_pipeline.fetchers.mm import fetch_purchase_orders
from accrual_pipeline.normalizer import normalize
from accrual_pipeline import persistence
from accrual_pipeline.persistence import (
    get_run_summary,
    init_db,
    list_runs,
    record_run_start,
)
from accrual_pipeline.fetchers.payroll import (
    fetch_peci_fi_lines,
    fetch_workday_payroll_results,
)
from accrual_pipeline.inventory import fetch_batches, filter_batches
from accrual_pipeline.normalizer import (
    find_orphaned_fi_payroll_lines,
    normalize_payroll,
)
from accrual_pipeline.pipeline import run_pipeline
from accrual_pipeline.plan import query_plan, query_plan_remote
from accrual_pipeline.writedown import (
    draft_writeoff_je,
    get_distressed_writedown_extract,
)

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize the database on app startup."""
    init_db()
    yield


app = FastAPI(
    title="Accrual Processing Pipeline",
    description="Python mirror of an SAP BTP CPI accrual iFlow.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS is permissive here because this service is dev-only and the Next.js
# UI proxies through its own server. A production deployment should restrict
# allow_origins to the known SPA host(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health() -> dict[str, Any]:
    """Liveness probe. Reports service state and pipeline config flags."""
    settings = get_settings()
    return {
        "status": "ok",
        "mock_mode": settings.mock_mode,
        "claude_model": settings.claude_model,
    }


@app.post("/runs")
async def start_run() -> dict[str, str]:
    """Run the pipeline synchronously and return when it's done.

    Returns `run_id` and `status_url` once the pipeline has finished writing
    persistence rows. Existing clients that POST then GET /runs/{run_id} keep
    working — the GET will find the completed run immediately.
    """
    run_id = f"run-{secrets.token_hex(8)}"
    settings = get_settings()
    record_run_start(run_id, model=settings.claude_model, accrual_count=0)
    log.info("api.run_started", run_id=run_id)

    await run_pipeline(run_id)
    return {"run_id": run_id, "status_url": f"/runs/{run_id}"}


@app.get("/accruals")
async def get_accruals(
    year: str | None = None,
    period: str | None = None,
    gl_account_prefix: str | None = None,
    cost_center: str | None = None,
    vendor_contains: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Fetch current accruals from SAP (FI/MM/CO), normalize, and filter.

    All filters are optional and AND together. Query-time only — no Claude
    call, no persistence. This is the tool the chat agent uses to look up
    actuals.
    """
    async with create_sap_client() as client:
        fi_records = await fetch_journal_entries(client, limit=limit)
        mm_records = await fetch_purchase_orders(client, limit=limit)
        co_records = await fetch_cost_centers(client, limit=limit)
    accruals = normalize(fi_records, mm_records, co_records)

    def keep(a: Any) -> bool:
        if year and a.fiscal_year != year:
            return False
        if period and (a.accrual_from_period is None
                       or f"{a.accrual_from_period.month:03d}" != period):
            return False
        if gl_account_prefix and not a.gl_account_number.startswith(gl_account_prefix):
            return False
        if cost_center and a.cost_center_id != cost_center:
            return False
        if vendor_contains:
            hay = (a.vendor_name or "").lower() + " " + (a.vendor_number or "").lower()
            if vendor_contains.lower() not in hay:
                return False
        return True

    filtered = [a.model_dump(mode="json") for a in accruals if keep(a)]
    return {"accruals": filtered, "count": len(filtered)}


@app.get("/inventory/batches")
async def get_batches(
    material_prefix: str | None = None,
    therapeutic_category: str | None = None,
    plant: str | None = None,
    supplier_contains: str | None = None,
    distress_signal: str | None = None,
    near_expiry_days: int = 90,
    slow_moving_days: int = 365,
    limit: int = 200,
) -> dict[str, Any]:
    """Return batch records, optionally filtered by pharma distress signals.

    `distress_signal` values: `expired`, `near_expiry`, `quarantine`,
    `marked_for_deletion`, `slow_moving`, `clean`, `any_distressed`.
    """
    async with create_btp_client() as client:
        batches = await fetch_batches(client, limit=limit)
    filtered = filter_batches(
        batches,
        material_prefix=material_prefix,
        therapeutic_category=therapeutic_category,
        plant=plant,
        supplier_contains=supplier_contains,
        distress_signal=distress_signal,
        near_expiry_days=near_expiry_days,
        slow_moving_days=slow_moving_days,
    )
    return {
        "batches": [b.model_dump(mode="json") for b in filtered],
        "count": len(filtered),
        "total_before_filter": len(batches),
    }


@app.get("/blackline/draft-writeoff")
async def draft_writeoff(reason: str = "expired") -> dict[str, Any]:
    """Build a BlackLine-shape JE for the chosen distress reason, pulling live
    data from BTP (or the fixture in MOCK_MODE). The UI calls this so the user
    doesn't have to run any local scripts.

    `reason` values: `expired`, `near_expiry`, `quarantine`, `marked_for_deletion`,
    `slow_moving`, `all_distressed`.
    """
    settings = get_settings()
    if settings.mock_mode:
        return await draft_writeoff_je(None, reason=reason)
    async with create_btp_client() as client:
        return await draft_writeoff_je(client, reason=reason)


@app.post("/blackline/post")
async def post_blackline_je(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Simulate posting a BlackLine JE to SAP S/4HANA.

    Accepts a JE in the BlackLine import shape (header + lines). Validates the
    journal balances, generates a SAP-style document number, and returns it.

    In a real deployment this would call SAP's ``BAPI_ACC_DOCUMENT_POST`` via
    OData / RFC. Here it simulates the round-trip so the BlackLine-stand-in UI
    has something to display.
    """
    lines = payload.get("lines") or []
    if not lines:
        raise HTTPException(status_code=400, detail="JE has no lines")

    total_debit = sum(
        float(line.get("amount_local") or 0)
        for line in lines
        if line.get("debit_credit") == "S"
    )
    total_credit = sum(
        float(line.get("amount_local") or 0)
        for line in lines
        if line.get("debit_credit") == "H"
    )
    if abs(total_debit - total_credit) > 0.01:
        raise HTTPException(
            status_code=400,
            detail=f"JE not balanced: debit={total_debit:.2f}, credit={total_credit:.2f}",
        )

    header = payload.get("header") or {}
    company_code = header.get("target_company_code") or header.get("company_code") or "1000"
    fiscal_year = (header.get("posting_date") or "2026-01-01")[:4]
    doc_number = f"49{secrets.randbelow(100000000):08d}"

    log.info(
        "blackline.posted_to_sap",
        sap_document=f"{doc_number}/{fiscal_year}/{company_code}",
        total_debit=total_debit,
        line_count=len(lines),
        journal_id=header.get("journal_id"),
    )

    return {
        "status": "posted",
        "sap_document": f"{doc_number}/{fiscal_year}/{company_code}",
        "doc_number": doc_number,
        "fiscal_year": fiscal_year,
        "company_code": company_code,
        "total_amount": round(total_debit, 2),
        "currency": header.get("currency", "USD"),
        "line_count": len(lines),
        "posted_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


@app.get("/inventory/writedown-extract")
async def get_writedown_extract(
    distressed_only: bool = True,
) -> dict[str, Any]:
    """Distressed inventory across all plants joined with MBEW valuation.

    Calls ``API_STOCK_OVERVIEW_SRV/StockOverview`` (MB52) and
    ``API_MATERIAL_VALUATION_SRV/MaterialValuation`` (MBEW) on the BTP CAP
    mock SAP deployment, joins per (material, plant), and returns per-batch
    detail plus a summary aggregated by plant. In MOCK_MODE computes the
    same shape from the local inventory_batches fixture.
    """
    settings = get_settings()
    if settings.mock_mode:
        return await get_distressed_writedown_extract(None, distressed_only=distressed_only)
    async with create_btp_client() as client:
        return await get_distressed_writedown_extract(client, distressed_only=distressed_only)


@app.get("/plan")
async def get_plan(
    year: str | None = None,
    period: str | None = None,
    cost_center: str | None = None,
    gl_account_prefix: str | None = None,
) -> dict[str, Any]:
    """Return plan / budget rows matching filters.

    Plan data is synthetic (see src/accrual_pipeline/plan.py). Covers
    fiscal years 2024-2026, monthly periods, 4 cost centers, 5 GL ranges.
    """
    settings = get_settings()
    if settings.mock_mode:
        rows = query_plan(
            fiscal_year=year,
            fiscal_period=period,
            cost_center=cost_center,
            gl_account_prefix=gl_account_prefix,
        )
    else:
        async with create_sap_client() as client:
            rows = await query_plan_remote(
                client,
                fiscal_year=year,
                fiscal_period=period,
                cost_center=cost_center,
                gl_account_prefix=gl_account_prefix,
            )
    return {"plan": rows, "count": len(rows)}


@app.get("/payroll/results")
async def get_payroll_results(
    worker_id: str | None = None,
    pay_group: str | None = None,
    pay_period_end: str | None = None,
    cost_center: str | None = None,
    only_mismatches: bool = False,
) -> dict[str, Any]:
    """Return the Workday↔FI payroll reconciliations for the current period.

    Query-time only — no Claude call, no persistence. Same pattern as
    ``/accruals``. The chat agent uses this to answer ad-hoc payroll
    questions like "did EMP-1010 get prorated correctly after resigning 5/20?" without needing
    to kick off a full pipeline run.
    """
    async with create_sap_client() as client:
        workday, fi_lines = await fetch_workday_payroll_results(), await fetch_peci_fi_lines(client)

    reconciliations = normalize_payroll(workday, fi_lines)
    orphan_fi_lines = find_orphaned_fi_payroll_lines(workday, fi_lines)

    def keep(r: Any) -> bool:
        if worker_id and r.worker_id != worker_id:
            return False
        if pay_group and r.pay_group != pay_group:
            return False
        if pay_period_end and r.pay_period_end.isoformat() != pay_period_end:
            return False
        if cost_center and r.cost_center != cost_center:
            return False
        if only_mismatches:
            # A row is a mismatch if FI is missing, duplicated, or any
            # expense-side total is off by more than $1.
            if r.fi_document_count != 1:
                return True
            gross_gap = abs(r.workday_gross - r.fi_total_earnings)
            er_gap = abs(
                (r.workday_total_employer_cost or 0) - r.fi_total_employer_cost
            )
            cc_mismatch = (
                r.cost_center is not None
                and r.fi_cost_centers_seen
                and r.cost_center not in r.fi_cost_centers_seen
            )
            return gross_gap > 1 or er_gap > 1 or cc_mismatch
        return True

    filtered = [r.model_dump(mode="json") for r in reconciliations if keep(r)]
    return {
        "reconciliations": filtered,
        "count": len(filtered),
        "orphan_fi_lines": [ln.model_dump(mode="json", exclude_none=True) for ln in orphan_fi_lines],
        "total_workday_records": len(workday),
        "total_fi_payroll_lines": len(fi_lines),
    }


@app.get("/runs")
async def list_runs_endpoint(limit: int = 50) -> dict[str, Any]:
    """Return the most recent runs, newest first."""
    return {"runs": list_runs(limit=limit)}


@app.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    """Return run metadata + flagged items. 404 if run_id is unknown."""
    summary = get_run_summary(run_id)
    if summary is None:
        raise HTTPException(status_code=404, detail=f"Unknown run_id: {run_id}")
    return summary

# -------------------- Posting workflow endpoints --------------------


@app.post("/postings/draft")
async def create_posting_draft(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Create a posting draft. Called by the UI / chat agent / Next.js
    server action right before starting a Workflow DevKit run.

    Request shape:
      {
        "source_type": "accrual" | "payroll",
        "source_id":   "<accrual_id or payroll_id>",
        "source_run_id": "<run id this came from>" (optional),
        "title":       "human-readable label",
        "payload":     { ... opaque JSON the workflow will push downstream ... }
      }
    """
    posting_id = body.get("id") or f"post-{secrets.token_hex(8)}"
    try:
        row = persistence.create_posting(
            posting_id=posting_id,
            source_type=str(body["source_type"]),
            source_id=str(body["source_id"]),
            source_run_id=body.get("source_run_id"),
            title=str(body.get("title", "(no title)")),
            payload=dict(body.get("payload") or {}),
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    log.info("api.posting_drafted", posting_id=posting_id, source_type=row["source_type"])
    return row


@app.post("/postings/{posting_id}/workflow")
async def attach_posting_workflow(
    posting_id: str,
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """Record the Workflow DevKit run_id once start() returns on the Next.js side."""
    workflow_run_id = body.get("workflow_run_id")
    if not workflow_run_id:
        raise HTTPException(status_code=400, detail="workflow_run_id is required")
    try:
        persistence.attach_workflow_run(posting_id, str(workflow_run_id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}


@app.post("/postings/{posting_id}/event")
async def record_posting_event_endpoint(
    posting_id: str,
    body: dict[str, Any] = Body(...),
) -> dict[str, Any]:
    """Append a workflow event to the posting (used by the workflow's `recordEvent` step)."""
    step = body.get("step")
    if not step:
        raise HTTPException(status_code=400, detail="step is required")
    payload = body.get("payload")
    try:
        return persistence.record_posting_event(
            posting_id=posting_id,
            step=str(step),
            payload=dict(payload) if isinstance(payload, dict) else None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/postings")
async def list_postings_endpoint(limit: int = 50) -> dict[str, Any]:
    """Return the most recent postings, newest first."""
    return {"postings": persistence.list_postings(limit=limit)}


@app.get("/postings/{posting_id}")
async def get_posting_endpoint(posting_id: str) -> dict[str, Any]:
    """Return one posting with its full event history."""
    row = persistence.get_posting(posting_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown posting_id: {posting_id}")
    return row


@app.post("/postback/blackline-mock")
async def blackline_mock_receiver(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Mock BlackLine /journals POST receiver.

    Accepts a posting payload, returns a simulated BlackLine receipt. The
    Workflow runtime POSTs to this URL as a real HTTP request so the
    workflow's `fetch` step is exercised end-to-end without a real BlackLine
    tenant.
    """
    receipt = {
        "system": "BlackLine",
        "blackline_journal_id": f"BLN-{secrets.token_hex(6).upper()}",
        "received_at": datetime.utcnow().isoformat() + "Z",
        "echo": {k: body.get(k) for k in ("source_type", "source_id", "title") if k in body},
    }
    log.info("postback.blackline_mock", **{k: v for k, v in receipt.items() if k != "echo"})
    return receipt


@app.post("/postback/cap-mock")
async def cap_mock_receiver(body: dict[str, Any] = Body(...)) -> dict[str, Any]:
    """Mock SAP BTP CAP /odata/v4/postings POST receiver.

    Same intent as the BlackLine mock — gives the workflow a real HTTP
    endpoint to POST to without requiring the CAP service to expose a
    write-capable posting entity.
    """
    receipt = {
        "system": "SAP BTP CAP",
        "cap_document_id": f"CAP-{secrets.token_hex(6).upper()}",
        "received_at": datetime.utcnow().isoformat() + "Z",
        "echo": {k: body.get(k) for k in ("source_type", "source_id", "title") if k in body},
    }
    log.info("postback.cap_mock", **{k: v for k, v in receipt.items() if k != "echo"})
    return receipt
