"""Merge FI / MM / CO fetcher outputs into business-shaped AccrualObject records.

Equivalent to CPI's Groovy script + Content Modifier. Each non-reversed FI
journal entry item becomes one AccrualObject with SAP's PascalCase OData
fields translated to plain business language per the finance-team spec:

    Company code, Posting Date, Document date, GL Account Number,
    GL Description, Vendor Number, Vendor Name, Short text, Long text,
    Accrual From period, Accrual to period, Amount (USD).

Derived values
--------------
- `short_text` ← DocumentItemText, falling back to GLAccountName.
- `long_text` ← AccountingDocumentHeaderText, falling back to a composed
  string describing the GL account + fiscal period.
- `accrual_from_period` / `accrual_to_period` ← derived from FiscalPeriod +
  FiscalYear assuming calendar-month periods. If FiscalPeriod is missing,
  both stay None.
- `amount_usd` ← AmountInGlobalCurrency when GlobalCurrency == "USD"
  (sandbox convention). Falls back to company-code amount if USD isn't
  available; None if neither is present.
"""
from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

import structlog

from accrual_pipeline.models import (
    AccrualObject,
    COCostCenter,
    FIJournalEntry,
    MMPurchaseOrder,
    PayrollAccrualReconciliation,
    WorkdayPayrollResult,
)


# GL ranges used to bucket the FI side of payroll postings. These mirror the
# generator in tests/fixtures and the live SAP COA convention: 50100000-
# 50199999 are earnings expense, 50200000-50299999 are employer costs.
_EARNINGS_GL_FROM, _EARNINGS_GL_TO = "50100000", "50199999"
_EMPLOYER_GL_FROM, _EMPLOYER_GL_TO = "50200000", "50299999"

log = structlog.get_logger(__name__)


def normalize(
    journal_entries: list[FIJournalEntry],
    purchase_orders: list[MMPurchaseOrder],
    cost_centers: list[COCostCenter],
) -> list[AccrualObject]:
    """Produce AccrualObjects from the three fetcher payloads."""
    po_lookup = {
        (po.PurchaseOrder, po.PurchaseOrderItem): po for po in purchase_orders
    }
    cc_lookup = {cc.CostCenter: cc for cc in cost_centers}

    log.info(
        "normalizer.start",
        fi_count=len(journal_entries),
        mm_count=len(purchase_orders),
        co_count=len(cost_centers),
    )

    accruals: list[AccrualObject] = []
    skipped_reversed = 0

    for fi in journal_entries:
        if fi.IsReversal or fi.IsReversed:
            skipped_reversed += 1
            continue
        po = _match_po(fi, po_lookup)
        cc = cc_lookup.get(fi.CostCenter or "")
        accruals.append(_build_accrual(fi, po, cc))

    log.info(
        "normalizer.done",
        produced=len(accruals),
        skipped_reversed=skipped_reversed,
    )
    return accruals


def _match_po(
    fi: FIJournalEntry,
    po_lookup: dict[tuple[str, str], MMPurchaseOrder],
) -> MMPurchaseOrder | None:
    if not fi.PurchasingDocument:
        return None
    item = fi.PurchasingDocumentItem or ""
    direct = po_lookup.get((fi.PurchasingDocument, item))
    if direct is not None:
        return direct
    try:
        normalized_item = str(int(item))
    except (ValueError, TypeError):
        return None
    return po_lookup.get((fi.PurchasingDocument, normalized_item))


def _build_accrual(
    fi: FIJournalEntry,
    po: MMPurchaseOrder | None,
    cc: COCostCenter | None,
) -> AccrualObject:
    from_period, to_period = _period_range(fi.FiscalYear, fi.FiscalPeriod)
    return AccrualObject(
        accrual_id=fi.accrual_id,
        company_code=fi.CompanyCode,
        posting_date=fi.PostingDate,
        document_date=fi.DocumentDate,
        gl_account_number=fi.GLAccount,
        gl_description=_clean(fi.GLAccountName),
        vendor_number=_clean(fi.Supplier),
        vendor_name=_clean(fi.SupplierName),
        short_text=_short_text(fi),
        long_text=_long_text(fi, from_period, to_period),
        accrual_from_period=from_period,
        accrual_to_period=to_period,
        amount_usd=_amount_usd(fi),
        fiscal_year=fi.FiscalYear,
        accounting_document=fi.AccountingDocument,
        accounting_document_item=fi.AccountingDocumentItem,
        is_reversal=fi.IsReversal,
        is_reversed=fi.IsReversed,
        purchase_order=_clean(fi.PurchasingDocument),
        purchase_order_item=_clean(fi.PurchasingDocumentItem),
        po_supplier_name=_clean(po.SupplierName) if po else None,
        po_latest_goods_receipt_date=po.LatestGoodsReceiptDate if po else None,
        po_is_fully_invoiced=po.IsFullyInvoiced if po else None,
        po_purchase_order_type=_clean(po.PurchaseOrderType) if po else None,
        cost_center_id=_clean(fi.CostCenter),
        cost_center_name=_clean(cc.CostCenterName) if cc else _clean(fi.CostCenterName),
        cost_center_responsible=_clean(cc.PersonResponsibleName) if cc else None,
    )


def _short_text(fi: FIJournalEntry) -> str | None:
    """Short text: item-level free text, fallback to GL name."""
    return _clean(fi.DocumentItemText) or _clean(fi.GLAccountName)


def _long_text(
    fi: FIJournalEntry,
    from_period: date | None,
    to_period: date | None,
) -> str | None:
    """Long text: header text if set; otherwise a composed description."""
    header = _clean(fi.AccountingDocumentHeaderText)
    if header:
        return header
    parts: list[str] = []
    gl_name = _clean(fi.GLAccountName)
    if gl_name:
        parts.append(gl_name)
    if from_period and to_period:
        parts.append(
            f"for period {from_period.isoformat()} to {to_period.isoformat()}"
        )
    return " ".join(parts) or None


def _amount_usd(fi: FIJournalEntry) -> Decimal | None:
    """Pick the USD-equivalent amount. Prefer GlobalCurrency=USD on the
    cube (sandbox convention); fall back to company-code amount if it's
    already in USD; else fall back to the global amount regardless of code
    so users see *some* number rather than None."""
    if fi.GlobalCurrency == "USD" and fi.AmountInGlobalCurrency is not None:
        return fi.AmountInGlobalCurrency
    if fi.CompanyCodeCurrency == "USD" and fi.AmountInCompanyCodeCurrency is not None:
        return fi.AmountInCompanyCodeCurrency
    if fi.AmountInGlobalCurrency is not None:
        return fi.AmountInGlobalCurrency
    return fi.AmountInCompanyCodeCurrency


def _period_range(
    fiscal_year: str,
    fiscal_period: str | None,
) -> tuple[date | None, date | None]:
    """Derive calendar-month accrual period from SAP fiscal year + period.

    Assumes calendar fiscal year (fiscal period = calendar month). Sandbox
    demo tenants uniformly use this variant; real tenants may need the
    fiscal year variant looked up and mapped, left as a future enhancement.
    """
    if not fiscal_period:
        return None, None
    try:
        year = int(fiscal_year)
        month = int(fiscal_period)
    except (ValueError, TypeError):
        return None, None
    if not 1 <= month <= 12:
        return None, None
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def normalize_payroll(
    workday_results: list[WorkdayPayrollResult],
    peci_fi_lines: list[FIJournalEntry],
) -> list[PayrollAccrualReconciliation]:
    """Join Workday pay results with the FI payroll lines PECI delivered.

    One reconciliation row per Workday result. FI lines with no matching
    Workday record are dropped here — they're surfaced separately via
    ``find_orphaned_fi_payroll_lines``.

    Match key
    ---------
    Workday: ``(Pay_Group_Reference, Pay_Period_End_Date, Worker_Reference)``
    FI:      same triple read from the custom PayGroupReference /
             PayPeriodEndDate / WorkerReference fields that PECI populates.

    Aggregation
    -----------
    FI debit lines (DC="S") are bucketed by GL into earnings vs. employer
    costs based on the 50100000 vs 50200000 ranges. Credits (the accrual
    liabilities on 22xxxxxx) are intentionally ignored — the reconciliation
    is on expense recognition, not balance sheet posting.
    """
    fi_by_key: dict[tuple[str, str, str], list[FIJournalEntry]] = {}
    for line in peci_fi_lines:
        key = _fi_payroll_key(line)
        if key is None:
            continue
        fi_by_key.setdefault(key, []).append(line)

    log.info(
        "payroll_normalizer.start",
        workday_count=len(workday_results),
        fi_line_count=len(peci_fi_lines),
        fi_keyed_workers=len(fi_by_key),
    )

    reconciliations: list[PayrollAccrualReconciliation] = []
    for wd in workday_results:
        key = (
            wd.Pay_Group_Reference,
            wd.Pay_Period_End_Date.isoformat(),
            wd.Worker_Reference,
        )
        fi_lines = fi_by_key.get(key, [])
        reconciliations.append(_build_payroll_reconciliation(wd, fi_lines))

    log.info("payroll_normalizer.done", produced=len(reconciliations))
    return reconciliations


def find_orphaned_fi_payroll_lines(
    workday_results: list[WorkdayPayrollResult],
    peci_fi_lines: list[FIJournalEntry],
) -> list[FIJournalEntry]:
    """Return FI payroll lines that have no matching Workday record.

    Helpful for the prompt: phantom FI postings (worker present in FI but
    not in Workday) are an unambiguous PECI bug and Claude should flag them.
    """
    workday_keys = {
        (wd.Pay_Group_Reference, wd.Pay_Period_End_Date.isoformat(), wd.Worker_Reference)
        for wd in workday_results
    }
    orphans: list[FIJournalEntry] = []
    for line in peci_fi_lines:
        key = _fi_payroll_key(line)
        if key is None or key not in workday_keys:
            orphans.append(line)
    return orphans


def _fi_payroll_key(line: FIJournalEntry) -> tuple[str, str, str] | None:
    """Pull the (pay_group, period_end, worker) key out of an FI payroll line.

    These three fields live in custom OData properties that PECI populates
    when delivering to S/4. Lines that don't carry them aren't payroll —
    skip silently.
    """
    if not (line.PayGroupReference and line.PayPeriodEndDate and line.WorkerReference):
        return None
    return (line.PayGroupReference, line.PayPeriodEndDate.isoformat(), line.WorkerReference)


def _build_payroll_reconciliation(
    wd: WorkdayPayrollResult,
    fi_lines: list[FIJournalEntry],
) -> PayrollAccrualReconciliation:
    earnings_by_code: dict[str, Decimal] = {
        e.Code: e.Amount for e in wd.Earnings
    }
    employer_costs_by_code: dict[str, Decimal] = {
        ec.Code: ec.Amount for ec in wd.Employer_Costs
    }

    fi_earnings_by_gl: dict[str, Decimal] = {}
    fi_employer_by_gl: dict[str, Decimal] = {}
    fi_total_earnings = Decimal("0")
    fi_total_employer = Decimal("0")
    cost_centers_seen: set[str] = set()
    doc_numbers: set[str] = set()

    for ln in fi_lines:
        if ln.DebitCreditCode != "S":
            # Skip the liability credits — reconciliation is on expense side.
            continue
        amount = ln.AmountInGlobalCurrency or ln.AmountInTransactionCurrency
        if amount is None:
            continue
        gl = ln.GLAccount
        if _EARNINGS_GL_FROM <= gl <= _EARNINGS_GL_TO:
            fi_earnings_by_gl[gl] = fi_earnings_by_gl.get(gl, Decimal("0")) + amount
            fi_total_earnings += amount
        elif _EMPLOYER_GL_FROM <= gl <= _EMPLOYER_GL_TO:
            fi_employer_by_gl[gl] = fi_employer_by_gl.get(gl, Decimal("0")) + amount
            fi_total_employer += amount
        if ln.CostCenter:
            cost_centers_seen.add(ln.CostCenter)
        doc_numbers.add(ln.AccountingDocument)

    return PayrollAccrualReconciliation(
        payroll_id=wd.payroll_id,
        worker_id=wd.Worker_Reference,
        worker_name=wd.Worker_Name,
        worker_status=wd.Worker_Status,
        pay_group=wd.Pay_Group_Reference,
        pay_period_start=wd.Pay_Period_Start_Date,
        pay_period_end=wd.Pay_Period_End_Date,
        pay_date=wd.Pay_Date,
        cost_center=wd.Cost_Center_Reference,
        termination_date=wd.Termination_Date,
        days_worked=wd.Days_Worked,
        workday_gross=wd.Gross_Pay,
        workday_net=wd.Net_Pay,
        workday_total_employer_cost=wd.Total_Employer_Cost,
        workday_earnings_by_code=earnings_by_code,
        workday_employer_costs_by_code=employer_costs_by_code,
        fi_total_earnings=fi_total_earnings,
        fi_total_employer_cost=fi_total_employer,
        fi_earnings_by_gl=fi_earnings_by_gl,
        fi_employer_cost_by_gl=fi_employer_by_gl,
        fi_cost_centers_seen=sorted(cost_centers_seen),
        fi_document_count=len(doc_numbers),
        fi_line_count=len(fi_lines),
        fi_document_numbers=sorted(doc_numbers),
    )


def _clean(value: str | None) -> str | None:
    """Collapse SAP's empty-string convention to None."""
    if value is None:
        return None
    stripped = value.strip()
    if stripped in ("", "0"):
        return None
    return stripped
