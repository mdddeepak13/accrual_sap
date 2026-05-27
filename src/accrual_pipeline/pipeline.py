"""End-to-end pipeline orchestration.

Fetch (FI/MM/CO in parallel) → normalize → Claude → route → persist.

Callable from both `main.py` (as a background task kicked off by POST /runs)
and `run.py` (as a synchronous CLI). A Claude client can be injected for
tests; production code creates a real one per run.
"""
from __future__ import annotations

import asyncio
from typing import Any

import structlog
from anthropic import AsyncAnthropic

from accrual_pipeline.claude_client import (
    analyze_accruals,
    analyze_payroll_reconciliations,
    create_anthropic_client,
)
from accrual_pipeline.config import get_settings
from accrual_pipeline.fetchers.base import create_sap_client
from accrual_pipeline.fetchers.co import fetch_cost_centers
from accrual_pipeline.fetchers.fi import fetch_journal_entries
from accrual_pipeline.fetchers.mm import fetch_purchase_orders
from accrual_pipeline.fetchers.payroll import (
    fetch_peci_fi_lines,
    fetch_workday_payroll_results,
)
from accrual_pipeline.normalizer import (
    find_orphaned_fi_payroll_lines,
    normalize,
    normalize_payroll,
)
from accrual_pipeline.persistence import (
    record_run_finish,
    record_run_start,
    update_run_accrual_count,
)
from accrual_pipeline.postback import post_blackline_je_batch
from accrual_pipeline.router import route, route_payroll

log = structlog.get_logger(__name__)


async def run_pipeline(
    run_id: str,
    *,
    anthropic_client: AsyncAnthropic | None = None,
) -> str:
    """Run the full pipeline once. Returns the run_id on success.

    On any exception, updates run status to "failed" and re-raises.
    Tests inject a mock `anthropic_client`; production callers pass None.
    """
    settings = get_settings()
    log.info("pipeline.start", run_id=run_id, mock_mode=settings.mock_mode)

    # Count is unknown until after normalize; start at 0 and patch.
    record_run_start(run_id, model=settings.claude_model, accrual_count=0)

    try:
        async with create_sap_client() as sap_client:
            (
                fi_records,
                mm_records,
                co_records,
                peci_fi_lines,
                workday_results,
            ) = await asyncio.gather(
                fetch_journal_entries(sap_client),
                fetch_purchase_orders(sap_client),
                fetch_cost_centers(sap_client),
                fetch_peci_fi_lines(sap_client),
                fetch_workday_payroll_results(),
            )

        accruals = normalize(fi_records, mm_records, co_records)
        payroll_reconciliations = normalize_payroll(workday_results, peci_fi_lines)
        orphan_fi_lines = find_orphaned_fi_payroll_lines(workday_results, peci_fi_lines)

        update_run_accrual_count(run_id, len(accruals) + len(payroll_reconciliations))

        if not accruals and not payroll_reconciliations:
            log.info("pipeline.empty", run_id=run_id)
            record_run_finish(run_id, status="completed")
            return run_id

        client = anthropic_client or create_anthropic_client()

        # The two analyses are independent — fan out so the function wall-clock
        # stays inside the serverless timeout. Routing still happens sequentially
        # afterwards because the sync SQLAlchemy session serializes anyway.
        analysis_jobs: list[asyncio.Task[Any]] = []
        if accruals:
            analysis_jobs.append(
                asyncio.create_task(
                    analyze_accruals(client, accruals, run_id=run_id)
                )
            )
        if payroll_reconciliations:
            analysis_jobs.append(
                asyncio.create_task(
                    analyze_payroll_reconciliations(
                        client,
                        payroll_reconciliations,
                        orphan_fi_lines=orphan_fi_lines,
                        run_id=run_id,
                    )
                )
            )

        results = await asyncio.gather(*analysis_jobs)
        result_iter = iter(results)

        approved_accruals = []
        if accruals:
            approved_accruals = await route(next(result_iter), accruals, run_id=run_id)

        if payroll_reconciliations:
            await route_payroll(
                next(result_iter),
                payroll_reconciliations,
                run_id=run_id,
            )

        # Send all approved accruals as ONE BlackLine JE file instead of
        # posting each item individually.
        await post_blackline_je_batch(approved_accruals, run_id=run_id)

        record_run_finish(run_id, status="completed")
        log.info(
            "pipeline.done",
            run_id=run_id,
            accrual_count=len(accruals),
            payroll_count=len(payroll_reconciliations),
            orphan_fi_lines=len(orphan_fi_lines),
        )
    except Exception as exc:
        log.error("pipeline.failed", run_id=run_id, error=type(exc).__name__)
        record_run_finish(run_id, status="failed")
        raise

    return run_id
