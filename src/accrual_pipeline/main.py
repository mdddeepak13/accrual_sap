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
from typing import Any, AsyncIterator

import structlog
from fastapi import FastAPI, HTTPException

from fastapi.middleware.cors import CORSMiddleware

from accrual_pipeline.config import get_settings
from accrual_pipeline.fetchers.base import create_sap_client
from accrual_pipeline.fetchers.co import fetch_cost_centers
from accrual_pipeline.fetchers.fi import fetch_journal_entries
from accrual_pipeline.fetchers.mm import fetch_purchase_orders
from accrual_pipeline.normalizer import normalize
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
from accrual_pipeline.plan import query_plan

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
    async with create_sap_client() as client:
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
    rows = query_plan(
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
    questions like "did EMP-1045 get prorated correctly?" without needing
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
