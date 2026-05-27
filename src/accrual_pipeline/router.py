"""Route Claude tool_use blocks to persistence / notification / postback.

Equivalent to CPI's Router + multi-receiver fan-out. Stage 5 of the pipeline.

Dispatch rules:
  flag_stale_po_accrual   → persist FlaggedItem (+ notify on severity=high)
  flag_duplicate_accrual  → persist ONE FlaggedItem per accrual_id in the group
  approve_accrual         → persist ApprovedItem; approved items are collected
                            and returned so the pipeline can send ONE batch
                            BlackLine JE file instead of N individual postbacks.

Unknown tool names raise ValueError — that catches prompt/schema drift
loudly rather than silently dropping calls.

The router takes the full list of accruals for the run so it can snapshot
each routed item's business fields into the persisted row. That lets the UI
render "Accruals to be posted" / "Irregularities" tables directly from DB
state without re-fetching FI/MM/CO.
"""
from __future__ import annotations

from typing import Any

import structlog

from accrual_pipeline.claude_client import ToolCall
from accrual_pipeline.models import AccrualObject, PayrollAccrualReconciliation
from accrual_pipeline.persistence import (
    persist_approved_item,
    persist_flagged_item,
)

log = structlog.get_logger(__name__)


async def route(
    tool_calls: list[ToolCall],
    accruals: list[AccrualObject],
    *,
    run_id: str,
) -> list[AccrualObject]:
    """Dispatch each tool call by name. See module docstring for rules.

    Returns the list of approved AccrualObjects so the pipeline can build
    and send a single batch BlackLine JE file rather than N individual posts.
    """
    snapshot_lookup = {a.accrual_id: a.model_dump(mode="json") for a in accruals}
    accrual_lookup = {a.accrual_id: a for a in accruals}
    stats = {"flagged": 0, "duplicates_expanded": 0, "approved": 0}
    approved_accruals: list[AccrualObject] = []

    for call in tool_calls:
        if call.tool == "flag_stale_po_accrual":
            await _handle_stale_po(call, snapshot_lookup, run_id=run_id)
            stats["flagged"] += 1
        elif call.tool == "flag_duplicate_accrual":
            n = await _handle_duplicate(call, snapshot_lookup, run_id=run_id)
            stats["flagged"] += n
            stats["duplicates_expanded"] += 1
        elif call.tool == "approve_accrual":
            accrual = await _handle_approve(call, snapshot_lookup, accrual_lookup, run_id=run_id)
            if accrual is not None:
                approved_accruals.append(accrual)
            stats["approved"] += 1
        else:
            raise ValueError(
                f"Unknown tool name from Claude: {call.tool!r}. "
                f"Known tools: flag_stale_po_accrual, flag_duplicate_accrual, approve_accrual."
            )

    log.info("router.done", run_id=run_id, **stats)
    return approved_accruals


async def _handle_stale_po(
    call: ToolCall,
    snapshot_lookup: dict[str, dict[str, Any]],
    *,
    run_id: str,
) -> None:
    accrual_id = _require(call.input, "accrual_id")
    severity = _require(call.input, "severity")
    reason = _require(call.input, "reason")

    persist_flagged_item(
        run_id=run_id,
        accrual_id=accrual_id,
        tool_name=call.tool,
        severity=severity,
        reason=reason,
        payload=call.input,
        accrual_snapshot=snapshot_lookup.get(accrual_id),
    )

    if severity == "high":
        log.warning(
            "router.notify",
            run_id=run_id,
            accrual_id=accrual_id,
            tool=call.tool,
            severity=severity,
            reason=reason,
        )


async def _handle_duplicate(
    call: ToolCall,
    snapshot_lookup: dict[str, dict[str, Any]],
    *,
    run_id: str,
) -> int:
    accrual_ids = call.input.get("accrual_ids")
    if not isinstance(accrual_ids, list) or len(accrual_ids) < 2:
        raise ValueError(
            f"flag_duplicate_accrual requires accrual_ids with >=2 items; got {accrual_ids!r}"
        )
    reason = _require(call.input, "reason")

    for aid in accrual_ids:
        persist_flagged_item(
            run_id=run_id,
            accrual_id=str(aid),
            tool_name=call.tool,
            severity=None,
            reason=reason,
            payload=call.input,
            accrual_snapshot=snapshot_lookup.get(str(aid)),
        )

    log.warning(
        "router.notify",
        run_id=run_id,
        accrual_ids=accrual_ids,
        tool=call.tool,
        reason=reason,
    )
    return len(accrual_ids)


async def _handle_approve(
    call: ToolCall,
    snapshot_lookup: dict[str, dict[str, Any]],
    accrual_lookup: dict[str, AccrualObject],
    *,
    run_id: str,
) -> AccrualObject | None:
    accrual_id = _require(call.input, "accrual_id")
    notes = _require(call.input, "notes")
    persist_approved_item(
        run_id=run_id,
        accrual_id=accrual_id,
        notes=notes,
        accrual_snapshot=snapshot_lookup.get(accrual_id),
    )
    # Return the AccrualObject so the pipeline can batch all approved items
    # into a single BlackLine JE file instead of posting one-by-one.
    return accrual_lookup.get(accrual_id)


async def route_payroll(
    tool_calls: list[ToolCall],
    reconciliations: list[PayrollAccrualReconciliation],
    *,
    run_id: str,
) -> None:
    """Dispatch payroll tool calls.

    Reuses the existing FlaggedItem / ApprovedItem tables — `tool_name`
    distinguishes payroll rows from FI/MM/CO rows for the UI. The
    reconciliation snapshot is JSON-serialized so the row is renderable
    without re-fetching Workday or FI.
    """
    snapshot_lookup = {r.payroll_id: r.model_dump(mode="json") for r in reconciliations}
    stats: dict[str, int] = {"flagged": 0}

    for call in tool_calls:
        if call.tool == "flag_payroll_accrual_mismatch":
            await _handle_payroll_flag(call, snapshot_lookup, run_id=run_id)
            stats["flagged"] += 1
        else:
            # The payroll prompt is flag-only — any other tool name is a
            # contract violation (probably stale prompt + new schema mismatch).
            raise ValueError(
                f"Unknown payroll tool from Claude: {call.tool!r}. "
                f"Known: flag_payroll_accrual_mismatch."
            )

    stats["implicitly_approved"] = len(reconciliations) - stats["flagged"]
    log.info("router.payroll_done", run_id=run_id, **stats)


async def _handle_payroll_flag(
    call: ToolCall,
    snapshot_lookup: dict[str, dict[str, Any]],
    *,
    run_id: str,
) -> None:
    worker_id = _require(call.input, "worker_id")
    severity = _require(call.input, "severity")
    reason = _require(call.input, "reason")
    mismatch_type = _require(call.input, "mismatch_type")
    # payroll_id may be empty for orphan FI postings (no Workday side); use
    # worker_id as the persistence key in that case so the UI still groups
    # the flag under the right employee.
    payroll_id = call.input.get("payroll_id") or f"orphan:{worker_id}"

    persist_flagged_item(
        run_id=run_id,
        accrual_id=payroll_id,
        tool_name=call.tool,
        severity=severity,
        reason=reason,
        payload=call.input,
        accrual_snapshot=snapshot_lookup.get(payroll_id),
    )

    log_kwargs = {
        "run_id": run_id,
        "payroll_id": payroll_id,
        "worker_id": worker_id,
        "mismatch_type": mismatch_type,
        "severity": severity,
        "reason": reason,
    }
    if severity == "high":
        log.warning("router.payroll_notify", **log_kwargs)
    else:
        log.info("router.payroll_flagged", **log_kwargs)


def _require(payload: dict[str, Any], key: str) -> str:
    """Pull a required string from a tool-call payload or raise clearly."""
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"tool call missing required field {key!r}; payload={payload!r}")
    return value
