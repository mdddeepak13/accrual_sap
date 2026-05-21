"""Normalizer tests — business-shape AccrualObject from the shared fixtures."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from accrual_pipeline.models import (
    AccrualObject,
    COCostCenter,
    FIJournalEntry,
    MMPurchaseOrder,
)
from accrual_pipeline.normalizer import normalize

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> list[dict[str, Any]]:
    payload = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return payload["d"]["results"]


@pytest.fixture
def fi_records() -> list[FIJournalEntry]:
    return [FIJournalEntry.model_validate(r) for r in _load_fixture("fi_journal_entries.json")]


@pytest.fixture
def mm_records() -> list[MMPurchaseOrder]:
    return [MMPurchaseOrder.model_validate(r) for r in _load_fixture("mm_purchase_orders.json")]


@pytest.fixture
def co_records() -> list[COCostCenter]:
    return [COCostCenter.model_validate(r) for r in _load_fixture("co_cost_centers.json")]


@pytest.fixture
def accruals(
    fi_records: list[FIJournalEntry],
    mm_records: list[MMPurchaseOrder],
    co_records: list[COCostCenter],
) -> list[AccrualObject]:
    return normalize(fi_records, mm_records, co_records)


def test_normalize_emits_one_accrual_per_fi_row(accruals: list[AccrualObject]) -> None:
    assert len(accruals) == 5


def test_business_fields_match_spec(accruals: list[AccrualObject]) -> None:
    first = accruals[0]
    assert first.accrual_id == "1010/2026/0100000001/001"
    assert first.company_code == "1010"
    assert first.posting_date is not None
    assert first.posting_date.isoformat() == "2026-04-10"
    assert first.document_date is not None and first.document_date.isoformat() == "2026-04-10"
    assert first.gl_account_number == "22000000"
    assert first.gl_description == "Accrued expenses - rent"
    assert first.vendor_number == "V-100"
    assert first.vendor_name == "Pinegate Realty Partners"
    assert first.short_text == "Rent - HQ Apr 2026"
    assert first.long_text == "Office rent Apr 2026 - headquarters"
    assert first.amount_usd == Decimal("5400.00")


def test_accrual_period_derived_from_fiscal_period(accruals: list[AccrualObject]) -> None:
    a = accruals[0]
    assert a.accrual_from_period is not None and a.accrual_from_period.isoformat() == "2026-04-01"
    assert a.accrual_to_period is not None and a.accrual_to_period.isoformat() == "2026-04-30"


def test_amount_usd_prefers_global_currency_when_usd(accruals: list[AccrualObject]) -> None:
    # All fixture rows have GlobalCurrency=USD, AmountInGlobalCurrency set.
    for a in accruals:
        assert a.amount_usd is not None


def test_long_text_falls_back_when_header_text_missing() -> None:
    fi = FIJournalEntry.model_validate({
        "CompanyCode": "1010",
        "FiscalYear": "2026",
        "FiscalPeriod": "004",
        "AccountingDocument": "0100000099",
        "AccountingDocumentItem": "001",
        "AccountingDocumentType": "SA",
        "AccountingDocumentHeaderText": "",  # blank
        "GLAccount": "22000000",
        "GLAccountName": "Accrued - rent",
        "AmountInTransactionCurrency": "100.00",
        "TransactionCurrency": "USD",
        "AmountInGlobalCurrency": "100.00",
        "GlobalCurrency": "USD",
        "DebitCreditCode": "H",
    })
    out = normalize([fi], [], [])[0]
    # Falls back to GL description + derived period range.
    assert out.long_text is not None
    assert "Accrued - rent" in out.long_text
    assert "2026-04-01" in out.long_text


def test_po_context_joined(accruals: list[AccrualObject]) -> None:
    stale = next(a for a in accruals if a.accrual_id.endswith("/0100000005/001"))
    assert stale.purchase_order == "4500000003"
    assert stale.po_supplier_name == "Delta Consulting Partners"
    assert stale.po_latest_goods_receipt_date is not None
    assert stale.po_latest_goods_receipt_date.isoformat() == "2026-01-01"
    assert stale.po_is_fully_invoiced is False
    assert stale.po_purchase_order_type == "FO"


def test_service_accrual_has_null_po_context(accruals: list[AccrualObject]) -> None:
    service = next(a for a in accruals if a.accrual_id.endswith("/0100000004/001"))
    assert service.purchase_order is None
    assert service.po_latest_goods_receipt_date is None


def test_cost_center_context_joined(accruals: list[AccrualObject]) -> None:
    a = next(a for a in accruals if a.accrual_id.endswith("/0100000002/001"))
    assert a.cost_center_id == "CC-2000"
    assert a.cost_center_name == "Marketing"
    assert a.cost_center_responsible == "Matthias Weber"


def test_duplicate_pair_shares_vendor_amount_cost_center(accruals: list[AccrualObject]) -> None:
    a2 = next(a for a in accruals if a.accrual_id.endswith("/0100000002/001"))
    a3 = next(a for a in accruals if a.accrual_id.endswith("/0100000003/001"))
    assert a2.vendor_number == a3.vendor_number == "V-200"
    assert a2.amount_usd == a3.amount_usd
    assert a2.cost_center_id == a3.cost_center_id == "CC-2000"
    assert a2.accrual_id != a3.accrual_id


def test_reversed_rows_are_skipped(
    mm_records: list[MMPurchaseOrder],
    co_records: list[COCostCenter],
) -> None:
    reversed_fi = FIJournalEntry.model_validate({
        "CompanyCode": "1010",
        "FiscalYear": "2026",
        "AccountingDocument": "0100009999",
        "AccountingDocumentItem": "001",
        "AccountingDocumentType": "SA",
        "GLAccount": "22000000",
        "AmountInTransactionCurrency": "100.00",
        "TransactionCurrency": "EUR",
        "DebitCreditCode": "H",
        "IsReversed": True,
    })
    assert normalize([reversed_fi], mm_records, co_records) == []


def test_period_derivation_handles_missing_fiscal_period() -> None:
    fi = FIJournalEntry.model_validate({
        "CompanyCode": "1010",
        "FiscalYear": "2026",
        "AccountingDocument": "0100000099",
        "AccountingDocumentItem": "001",
        "AccountingDocumentType": "SA",
        "GLAccount": "22000000",
        "AmountInTransactionCurrency": "100.00",
        "TransactionCurrency": "USD",
        "AmountInGlobalCurrency": "100.00",
        "GlobalCurrency": "USD",
        "DebitCreditCode": "H",
    })
    out = normalize([fi], [], [])[0]
    assert out.accrual_from_period is None
    assert out.accrual_to_period is None
