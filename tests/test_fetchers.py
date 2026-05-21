"""FI / MM / CO fetcher tests.

Covers both branches:
  - MOCK_MODE=true   → fixture JSON is loaded from tests/fixtures/
  - MOCK_MODE=false  → httpx calls go through respx mocks

Both are exercised so real-path bugs aren't masked by fixture-only tests.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from accrual_pipeline import config
from accrual_pipeline.fetchers import co as co_fetcher
from accrual_pipeline.fetchers import fi as fi_fetcher
from accrual_pipeline.fetchers import mm as mm_fetcher
from accrual_pipeline.fetchers.base import SAPClientError, create_sap_client

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict[str, Any]:
    with (FIXTURES_DIR / name).open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data


@pytest.fixture
def base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAP_API_KEY", "test-sap-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("SAP_SANDBOX_BASE_URL", "https://sandbox.api.sap.com")


@pytest.fixture
def mock_env(base_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "true")
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


@pytest.fixture
def live_env(base_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_MODE", "false")
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


@pytest.fixture
def nosleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralize asyncio.sleep so retry tests don't waste wall time."""
    async def _noop(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _noop)


# -------------------------- MOCK_MODE branch --------------------------

@pytest.mark.usefixtures("mock_env")
class TestMockMode:
    async def test_fi_returns_five_typed_accruals(self) -> None:
        async with create_sap_client() as client:
            entries = await fi_fetcher.fetch_journal_entries(client)
        assert len(entries) == 5
        assert entries[0].CompanyCode == "1010"
        assert entries[0].AmountInTransactionCurrency.is_finite()
        # Duplicate-of-#2 fixture.
        assert entries[2].DocumentReferenceID == "ACC-APR-002-DUP"
        # Stale-PO fixture — SAP's cube names the PO ref PurchasingDocument.
        assert entries[4].PurchasingDocument == "4500000003"
        assert entries[4].Supplier == "V-400"

    async def test_mm_returns_three_line_items_with_ses_dates(self) -> None:
        async with create_sap_client() as client:
            pos = await mm_fetcher.fetch_purchase_orders(client)
        assert len(pos) == 3
        stale = next(po for po in pos if po.PurchaseOrder == "4500000003")
        assert stale.LatestGoodsReceiptDate is not None
        assert stale.LatestGoodsReceiptDate.isoformat() == "2026-01-01"
        assert stale.IsFullyInvoiced is False

    async def test_co_returns_three_cost_centers(self) -> None:
        async with create_sap_client() as client:
            centers = await co_fetcher.fetch_cost_centers(client)
        assert {c.CostCenter for c in centers} == {"CC-1000", "CC-2000", "CC-3000"}
        assert next(c for c in centers if c.CostCenter == "CC-2000").CostCenterName == "Marketing"


# -------------------------- live-HTTP branch --------------------------

@pytest.mark.usefixtures("live_env")
class TestLiveMode:
    @respx.mock
    async def test_fi_injects_apikey_and_parses_response(self) -> None:
        url = (
            "https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap/"
            "API_OPLACCTGDOCITEMCUBE_SRV/A_OperationalAcctgDocItemCube"
        )
        route = respx.get(url).mock(
            return_value=httpx.Response(200, json=_load("fi_journal_entries.json"))
        )
        async with create_sap_client() as client:
            entries = await fi_fetcher.fetch_journal_entries(client)
        assert route.called
        assert route.calls.last.request.headers["APIKey"] == "test-sap-key"
        assert route.calls.last.request.headers["Accept"] == "application/json"
        # Cube requires a CompanyCode filter — confirm the fetcher sends one.
        query = dict(route.calls.last.request.url.params)
        assert "CompanyCode eq '1010'" in query["$filter"]
        assert len(entries) == 5

    @respx.mock
    async def test_mm_sends_filter_for_open_items(self) -> None:
        url = (
            "https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap/"
            "API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrderItem"
        )
        route = respx.get(url).mock(
            return_value=httpx.Response(200, json=_load("mm_purchase_orders.json"))
        )
        async with create_sap_client() as client:
            pos = await mm_fetcher.fetch_purchase_orders(client)
        assert route.called
        query = dict(route.calls.last.request.url.params)
        assert query["$filter"] == "IsFullyInvoiced eq false"
        assert len(pos) == 3

    @respx.mock
    async def test_co_returns_cost_centers_from_mocked_endpoint(self) -> None:
        url = (
            "https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap/"
            "API_COSTCENTER_SRV/A_CostCenter"
        )
        respx.get(url).mock(
            return_value=httpx.Response(200, json=_load("co_cost_centers.json"))
        )
        async with create_sap_client() as client:
            centers = await co_fetcher.fetch_cost_centers(client)
        assert len(centers) == 3

    @respx.mock
    async def test_retries_on_503_then_succeeds(
        self, nosleep: None
    ) -> None:
        url = (
            "https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap/"
            "API_COSTCENTER_SRV/A_CostCenter"
        )
        route = respx.get(url).mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json=_load("co_cost_centers.json")),
            ]
        )
        async with create_sap_client() as client:
            centers = await co_fetcher.fetch_cost_centers(client)
        assert len(route.calls) == 2
        assert len(centers) == 3

    @respx.mock
    async def test_exhausted_5xx_raises_sap_client_error(
        self, nosleep: None
    ) -> None:
        url = (
            "https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap/"
            "API_COSTCENTER_SRV/A_CostCenter"
        )
        route = respx.get(url).mock(return_value=httpx.Response(500))
        async with create_sap_client() as client:
            with pytest.raises(SAPClientError):
                await co_fetcher.fetch_cost_centers(client)
        assert len(route.calls) == 3  # max_attempts=3

    @respx.mock
    async def test_4xx_raises_immediately_without_retry(self) -> None:
        url = (
            "https://sandbox.api.sap.com/s4hanacloud/sap/opu/odata/sap/"
            "API_PURCHASEORDER_PROCESS_SRV/A_PurchaseOrderItem"
        )
        route = respx.get(url).mock(
            return_value=httpx.Response(401, json={"error": {"message": "unauthorized"}})
        )
        async with create_sap_client() as client:
            with pytest.raises(httpx.HTTPStatusError):
                await mm_fetcher.fetch_purchase_orders(client)
        assert len(route.calls) == 1


# -------------------------- unit helpers --------------------------

def test_odata_date_coercion_handles_sap_ms_format() -> None:
    from accrual_pipeline.models import FIJournalEntry

    raw = {
        "CompanyCode": "1000",
        "AccountingDocument": "0100000099",
        "AccountingDocumentItem": "001",
        "FiscalYear": "2026",
        "PostingDate": "/Date(1712707200000)/",
        "AccountingDocumentType": "SA",
        "GLAccount": "2210000",
        "AmountInTransactionCurrency": "100.00",
        "TransactionCurrency": "EUR",
        "DebitCreditCode": "H",
    }
    entry = FIJournalEntry.model_validate(raw)
    assert entry.PostingDate.isoformat() == "2024-04-10"
