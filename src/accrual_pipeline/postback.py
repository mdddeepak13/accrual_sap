"""Postback to BlackLine / SAP S/4.

Instead of posting each approved accrual individually, the pipeline collects
all approved items and calls ``post_blackline_je_batch`` once at the end of
the run. That function:

  1. Builds a single BlackLine JE file (header + one debit line per approved
     accrual + one consolidated credit line) in the same schema used by
     ``expired_writeoff/blackline_accrual_je.json``.
  2. POSTs the file to the ``/blackline/post`` endpoint (which simulates the
     BlackLine Web Services Connector → SAP BAPI_ACC_DOCUMENT_POST round-trip).
  3. Logs the SAP document number returned.

In dev the ``/blackline/post`` endpoint is the mock receiver on the FastAPI
app itself. In production, swap ``BLACKLINE_POST_URL`` to the real BlackLine
tenant URL.
"""
from __future__ import annotations

import json
import secrets
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import httpx
import structlog

from accrual_pipeline.config import get_settings
from accrual_pipeline.models import AccrualObject

log = structlog.get_logger(__name__)

# GL accounts used for the batch accrual JE.
_GL_ACCRUAL_EXPENSE = "220100"   # Accrued Expenses (debit per item)
_GL_ACCRUAL_OFFSET  = "220199"   # Accrued Expenses Clearing (single credit)
_COMPANY_CODE       = "1000"
_CURRENCY           = "USD"
_DOC_TYPE           = "SA"       # SAP G/L Account Document


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def build_blackline_je(
    approved: list[AccrualObject],
    *,
    run_id: str,
    posting_date: date | None = None,
) -> dict[str, Any]:
    """Build a single BlackLine JE payload from all approved accruals.

    Structure:
      - One debit line (posting_key=40, debit_credit=S) per approved accrual,
        using the accrual's own GL account and cost center.
      - One consolidated credit line (posting_key=50, debit_credit=H) to the
        accrued-expenses clearing account for the total amount.

    The resulting file is balanced (total_debit == total_credit) and matches
    the ``https://blackline.com/schemas/journal-entry/v1`` shape.
    """
    today = posting_date or date.today()
    journal_id = f"BL-JE-{run_id}"

    debit_lines: list[dict[str, Any]] = []
    total = Decimal("0")

    for idx, accrual in enumerate(approved, start=1):
        amount = accrual.amount_usd or Decimal("0")
        total += amount
        debit_lines.append({
            "line_number": idx * 10,
            "posting_key": "40",
            "debit_credit": "S",
            "gl_account": accrual.gl_account_number,
            "gl_account_name": accrual.gl_description or "",
            "company_code": accrual.company_code,
            "cost_center": accrual.cost_center_id,
            "profit_center": None,
            "plant": None,
            "amount_local": _money(amount),
            "amount_doc": _money(amount),
            "currency": _CURRENCY,
            "line_item_text": (
                accrual.short_text
                or accrual.long_text
                or accrual.accrual_id
            ),
            "assignment": run_id,
        })

    credit_line: dict[str, Any] = {
        "line_number": (len(debit_lines) + 1) * 10,
        "posting_key": "50",
        "debit_credit": "H",
        "gl_account": _GL_ACCRUAL_OFFSET,
        "gl_account_name": "Accrued Expenses Clearing",
        "company_code": _COMPANY_CODE,
        "cost_center": None,
        "profit_center": None,
        "plant": None,
        "amount_local": _money(total),
        "amount_doc": _money(total),
        "currency": _CURRENCY,
        "line_item_text": f"Batch accrual posting — run {run_id}",
        "assignment": run_id,
    }

    lines = debit_lines + [credit_line]
    total_float = _money(total)

    return {
        "$schema": "https://blackline.com/schemas/journal-entry/v1",
        "header": {
            "journal_id": journal_id,
            "source_system": "ACCRUAL_PIPELINE",
            "target_system": "SAP",
            "target_company_code": _COMPANY_CODE,
            "currency": _CURRENCY,
            "posting_date": today.isoformat(),
            "document_date": today.isoformat(),
            "document_type": _DOC_TYPE,
            "header_text": f"Accrual pipeline batch posting — run {run_id}",
            "reference": run_id,
            "preparer": "accrual_pipeline",
            "approver": None,
            "status": "APPROVED",
        },
        "lines": lines,
        "totals": {
            "total_debit": total_float,
            "total_credit": total_float,
            "balanced": True,
            "line_count": len(lines),
        },
        "supporting_detail": [
            {
                "accrual_id": a.accrual_id,
                "gl_account": a.gl_account_number,
                "cost_center": a.cost_center_id,
                "vendor": a.vendor_name,
                "amount_usd": _money(a.amount_usd or Decimal("0")),
                "posting_date": a.posting_date.isoformat() if a.posting_date else None,
            }
            for a in approved
        ],
    }


async def post_blackline_je_batch(
    approved: list[AccrualObject],
    *,
    run_id: str,
) -> dict[str, Any] | None:
    """Build one BlackLine JE file from all approved accruals and POST it once.

    Returns the SAP document receipt dict on success, or None if the list is
    empty. Logs the outcome either way — never raises (pipeline should not
    fail just because the postback mock is down).
    """
    if not approved:
        log.info("postback.blackline_batch_skipped", run_id=run_id, reason="no_approved_items")
        return None

    je = build_blackline_je(approved, run_id=run_id)

    log.info(
        "postback.blackline_batch_sending",
        run_id=run_id,
        approved_count=len(approved),
        total_amount=je["totals"]["total_debit"],
        journal_id=je["header"]["journal_id"],
        line_count=je["totals"]["line_count"],
    )

    settings = get_settings()
    # In dev the FastAPI app itself hosts the mock receiver.
    # Override via BLACKLINE_POST_URL env var for a real tenant.
    base_url = getattr(settings, "blackline_post_url", None) or "http://localhost:8000"
    url = f"{base_url.rstrip('/')}/blackline/post"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                content=json.dumps(je).encode(),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            receipt: dict[str, Any] = response.json()

        log.info(
            "postback.blackline_batch_done",
            run_id=run_id,
            sap_document=receipt.get("sap_document"),
            total_amount=receipt.get("total_amount"),
            line_count=receipt.get("line_count"),
        )
        return receipt

    except Exception as exc:
        log.error(
            "postback.blackline_batch_failed",
            run_id=run_id,
            error=type(exc).__name__,
            detail=str(exc),
        )
        return None
