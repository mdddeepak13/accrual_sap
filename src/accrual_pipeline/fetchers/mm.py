"""MM Purchase Orders fetcher.

Source: Purchase Order API (A_PurchaseOrderItem). Line-level rather than
header-level because SES and invoice state hang off the item, which is
what accrual reconciliation actually needs.
"""
from __future__ import annotations

import httpx
import structlog

from accrual_pipeline.config import get_settings
from accrual_pipeline.fetchers.base import (
    get_with_retry,
    load_fixture,
    unwrap_odata,
)
from accrual_pipeline.models import MMPurchaseOrder

log = structlog.get_logger(__name__)

MM_PATH = (
    "/s4hanacloud/sap/opu/odata/sap/API_PURCHASEORDER_PROCESS_SRV"
    "/A_PurchaseOrderItem"
)
MM_FIXTURE = "mm_purchase_orders.json"


async def fetch_purchase_orders(
    client: httpx.AsyncClient,
    *,
    limit: int = 100,
) -> list[MMPurchaseOrder]:
    """Fetch open PO line items with supplier, cost center, and SES data."""
    settings = get_settings()
    if settings.mock_mode:
        log.info("mm.mock_mode", fixture=MM_FIXTURE)
        payload = load_fixture(MM_FIXTURE)
    else:
        log.info("mm.fetch", path=MM_PATH, limit=limit)
        response = await get_with_retry(
            client,
            MM_PATH,
            params={
                "$format": "json",
                "$top": str(limit),
                "$filter": "IsFullyInvoiced eq false",
            },
        )
        payload = response.json()
    records = unwrap_odata(payload)
    return [MMPurchaseOrder.model_validate(r) for r in records]
