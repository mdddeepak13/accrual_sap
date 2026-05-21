"""Anthropic SDK wrapper for accrual analysis.

Uses the real SDK at runtime — Claude calls are NEVER mocked in production.
Tests inject a mock client via the `client` parameter so pytest runs offline
without spending tokens.

Stage 4 of the pipeline.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, cast

import structlog
from anthropic import AsyncAnthropic
from jinja2 import Template
from pydantic import BaseModel, ConfigDict

from accrual_pipeline.config import get_settings
from accrual_pipeline.models import (
    AccrualObject,
    FIJournalEntry,
    PayrollAccrualReconciliation,
)

log = structlog.get_logger(__name__)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "accrual_analysis.md"
_PAYROLL_PROMPT_PATH = Path(__file__).parent / "prompts" / "payroll_analysis.md"
# A plain-text line (not a Jinja tag) so the file halves are both valid
# Jinja templates in isolation.
_SYSTEM_USER_DELIM = "\n---USER---\n"


class ToolCall(BaseModel):
    """One parsed tool_use block from Claude's response."""

    model_config = ConfigDict(extra="forbid")
    id: str
    tool: str
    input: dict[str, Any]


TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "flag_stale_po_accrual",
        "description": (
            "Flag a PO-linked accrual whose most recent goods receipt / service "
            "entry is older than the stale-days threshold AND the PO is not "
            "fully invoiced."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "accrual_id": {
                    "type": "string",
                    "description": "The accrual_id of the posting being flagged.",
                },
                "po_id": {
                    "type": "string",
                    "description": "The purchase order number referenced by the accrual.",
                },
                "reason": {
                    "type": "string",
                    "description": (
                        "One- or two-sentence explanation citing concrete figures "
                        "(days stale, amount, supplier) so a human can audit quickly."
                    ),
                },
                "severity": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": (
                        "low: 60-90 days AND <5k EUR; "
                        "medium: 90-180 days OR 5-50k EUR; "
                        "high: >180 days OR >50k EUR."
                    ),
                },
            },
            "required": ["accrual_id", "po_id", "reason", "severity"],
        },
    },
    {
        "name": "flag_duplicate_accrual",
        "description": (
            "Flag a group of two or more accruals that look like duplicates "
            "(same supplier, amount, cost center, posted within 7 days)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "accrual_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "description": "All accrual_ids in the duplicate group.",
                },
                "reason": {
                    "type": "string",
                    "description": "Why these look like duplicates — cite the matching fields.",
                },
            },
            "required": ["accrual_ids", "reason"],
        },
    },
    {
        "name": "approve_accrual",
        "description": (
            "Mark an accrual as clean. The router posts approved accruals back "
            "to S/4 as confirmed entries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "accrual_id": {"type": "string"},
                "notes": {
                    "type": "string",
                    "description": "Short note on why this was approved.",
                },
            },
            "required": ["accrual_id", "notes"],
        },
    },
]


PAYROLL_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "flag_payroll_accrual_mismatch",
        "description": (
            "Flag a discrepancy between Workday's authoritative payroll result "
            "and what PECI posted to SAP FI. Use one call per reconciliation row "
            "that has at least one material issue."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "payroll_id": {
                    "type": "string",
                    "description": (
                        "The payroll_id from the reconciliation row. Empty string "
                        "if and only if this is an orphan FI posting (no Workday "
                        "counterpart)."
                    ),
                },
                "worker_id": {
                    "type": "string",
                    "description": "Worker reference / employee ID being flagged.",
                },
                "mismatch_type": {
                    "type": "string",
                    "enum": [
                        "missing_in_fi",
                        "missing_in_workday",
                        "amount_mismatch",
                        "wrong_cost_center",
                        "wrong_gl_account",
                        "duplicate_fi_posting",
                        "termination_not_prorated",
                        "other",
                    ],
                    "description": (
                        "Single best-fit category. Use 'amount_mismatch' for any "
                        "expense-side dollar difference that doesn't match a more "
                        "specific category."
                    ),
                },
                "severity": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": (
                        "low: <$100 absolute difference; "
                        "medium: $100-$1000 OR cost-center routing error; "
                        "high: >$1000 OR missing/duplicate full posting OR termination "
                        "mishandled."
                    ),
                },
                "workday_amount": {
                    "type": "string",
                    "description": "Workday-side dollar amount in dispute (decimal string). Empty if not applicable.",
                },
                "fi_amount": {
                    "type": "string",
                    "description": "SAP FI-side dollar amount in dispute (decimal string). Empty if not applicable.",
                },
                "reason": {
                    "type": "string",
                    "description": (
                        "One- to three-sentence audit-friendly explanation citing "
                        "concrete amounts, GL accounts, or cost center codes."
                    ),
                },
            },
            "required": [
                "payroll_id", "worker_id", "mismatch_type", "severity", "reason",
            ],
        },
    },
    # No `approve_payroll_accrual` here on purpose. With 50+ reconciliation rows
    # per run, asking Claude to emit a tool call for each one inflates the token
    # budget and — observed in prod — degrades focus enough that it skips
    # ambiguous rows entirely (silently). Flag-only mode keeps the model's
    # attention on the small subset of problem rows; non-flagged rows are
    # treated as implicitly clean by route_payroll.
]


def create_anthropic_client() -> AsyncAnthropic:
    """Build a real AsyncAnthropic client from Settings. Never called in tests."""
    settings = get_settings()
    return AsyncAnthropic(api_key=settings.anthropic_api_key.get_secret_value())


def load_prompt_templates() -> tuple[Template, Template]:
    """Load and split the accrual prompt file into (system, user) Jinja templates."""
    return _load_split_templates(_PROMPT_PATH)


def load_payroll_prompt_templates() -> tuple[Template, Template]:
    """Load and split the payroll reconciliation prompt file."""
    return _load_split_templates(_PAYROLL_PROMPT_PATH)


def _load_split_templates(path: Path) -> tuple[Template, Template]:
    text = path.read_text(encoding="utf-8")
    if _SYSTEM_USER_DELIM not in text:
        raise ValueError(
            f"Prompt template at {path} is missing the system/user split marker: "
            f"{_SYSTEM_USER_DELIM!r}"
        )
    system_part, user_part = text.split(_SYSTEM_USER_DELIM, 1)
    return Template(system_part.strip()), Template(user_part.strip())


async def analyze_accruals(
    client: AsyncAnthropic,
    accruals: list[AccrualObject],
    *,
    run_id: str,
    today: date | None = None,
    stale_days_threshold: int = 60,
    duplicate_days_window: int = 7,
) -> list[ToolCall]:
    """Send the accrual dataset to Claude and return parsed tool calls.

    Raises ValueError if Claude returns no tool_use blocks — a dataset this
    small should always produce at least one call, and silent no-ops would
    hide prompt regressions.
    """
    settings = get_settings()
    system_tmpl, user_tmpl = load_prompt_templates()

    resolved_today = today or date.today()
    context = {
        "run_id": run_id,
        "today": resolved_today.isoformat(),
        "stale_days_threshold": stale_days_threshold,
        "duplicate_days_window": duplicate_days_window,
        "accruals": accruals,
    }
    system_prompt = system_tmpl.render(**context)
    user_prompt = user_tmpl.render(**context)

    log.info(
        "claude.request",
        run_id=run_id,
        model=settings.claude_model,
        accrual_count=len(accruals),
        max_tokens=settings.claude_max_tokens,
    )

    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=settings.claude_max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        tools=cast(Any, TOOL_SCHEMAS),
    )

    stop_reason = getattr(response, "stop_reason", None)
    blocks = list(response.content)
    log.info(
        "claude.response",
        run_id=run_id,
        stop_reason=stop_reason,
        block_count=len(blocks),
    )

    calls: list[ToolCall] = []
    for block in blocks:
        if getattr(block, "type", None) != "tool_use":
            continue
        # The SDK's union type for content blocks includes many variants that
        # lack .name / .input; we've just narrowed by runtime `type` check so
        # Any-cast is safe here.
        b: Any = block
        raw_input = b.input
        input_dict: dict[str, Any] = (
            dict(raw_input) if isinstance(raw_input, dict) else dict(raw_input or {})
        )
        calls.append(ToolCall(id=b.id, tool=b.name, input=input_dict))

    if not calls:
        raise ValueError(
            f"Claude returned no tool_use blocks (stop_reason={stop_reason!r}). "
            f"The prompt should always produce at least one call for any non-empty dataset."
        )

    return calls


async def analyze_payroll_reconciliations(
    client: AsyncAnthropic,
    reconciliations: list[PayrollAccrualReconciliation],
    *,
    orphan_fi_lines: list[FIJournalEntry],
    run_id: str,
    today: date | None = None,
    max_tokens: int | None = None,
) -> list[ToolCall]:
    """Send the Workday↔FI reconciliation dataset to Claude.

    Mirrors ``analyze_accruals`` but uses the payroll prompt + payroll tool
    schemas. Orphan FI lines (FI postings with no Workday counterpart) are
    passed in separately so Claude can flag them as ``missing_in_workday``.
    """
    settings = get_settings()
    system_tmpl, user_tmpl = load_payroll_prompt_templates()
    resolved_today = today or date.today()

    context = {
        "run_id": run_id,
        "today": resolved_today.isoformat(),
        "reconciliations": reconciliations,
        "orphan_fi_lines": orphan_fi_lines,
    }
    system_prompt = system_tmpl.render(**context)
    user_prompt = user_tmpl.render(**context)

    # Payroll prompts emit one tool call per reconciliation row + one per orphan
    # FI line; that's easily 50+ tool calls with verbose reason strings. The
    # default 4096 budget is for the much-smaller FI prompt — payroll needs
    # more. 16k is a comfortable ceiling for the demo dataset and stays well
    # below Sonnet's per-response limit.
    resolved_max_tokens = max_tokens or max(settings.claude_max_tokens, 16384)

    log.info(
        "claude.payroll_request",
        run_id=run_id,
        model=settings.claude_model,
        reconciliation_count=len(reconciliations),
        orphan_count=len(orphan_fi_lines),
        max_tokens=resolved_max_tokens,
    )

    response = await client.messages.create(
        model=settings.claude_model,
        max_tokens=resolved_max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        tools=cast(Any, PAYROLL_TOOL_SCHEMAS),
    )

    stop_reason = getattr(response, "stop_reason", None)
    blocks = list(response.content)
    log.info(
        "claude.payroll_response",
        run_id=run_id,
        stop_reason=stop_reason,
        block_count=len(blocks),
    )

    calls: list[ToolCall] = []
    skipped_truncated = 0
    for block in blocks:
        if getattr(block, "type", None) != "tool_use":
            continue
        b: Any = block
        raw_input = b.input
        input_dict: dict[str, Any] = (
            dict(raw_input) if isinstance(raw_input, dict) else dict(raw_input or {})
        )
        # Defense against the model getting cut off mid-emission: if the
        # tool_use block has no input at all, it's a truncated call — skip and
        # log rather than letting the router crash.
        if not input_dict:
            skipped_truncated += 1
            continue
        calls.append(ToolCall(id=b.id, tool=b.name, input=input_dict))

    if skipped_truncated:
        log.warning(
            "claude.payroll_truncated",
            run_id=run_id,
            skipped=skipped_truncated,
            stop_reason=stop_reason,
        )

    if not calls:
        raise ValueError(
            f"Claude returned no payroll tool_use blocks (stop_reason={stop_reason!r})."
        )

    return calls
