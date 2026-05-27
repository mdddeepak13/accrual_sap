"""CO Cost Centers fetcher.

Source: Cost Center API (API_COSTCENTER_SRV / A_CostCenter). Master data
used to tag accrual objects with owning department and responsible person
so flagged items can be routed to the right reviewer.
"""
from __future__ import annotations

import httpx
import structlog

from accrual_pipeline.config import get_settings
from accrual_pipeline.fetchers.base import (
    _decode_response,
    get_with_retry,
    load_fixture,
    unwrap_odata,
)
from accrual_pipeline.models import COCostCenter

log = structlog.get_logger(__name__)

CO_PATH = "/s4hanacloud/sap/opu/odata/sap/API_COSTCENTER_SRV/A_CostCenter"
CO_FIXTURE = "co_cost_centers.json"


async def fetch_cost_centers(
    client: httpx.AsyncClient,
    *,
    limit: int = 500,
) -> list[COCostCenter]:
    """Fetch active cost center master records."""
    settings = get_settings()
    if settings.mock_mode:
        log.info("co.mock_mode", fixture=CO_FIXTURE)
        payload = load_fixture(CO_FIXTURE)
    else:
        log.info("co.fetch", path=CO_PATH, limit=limit)
        response = await get_with_retry(
            client,
            CO_PATH,
            params={
                "$format": "json",
                "$top": str(limit),
            },
        )
        payload = _decode_response(response)
    records = unwrap_odata(payload)
    return [COCostCenter.model_validate(r) for r in records]
