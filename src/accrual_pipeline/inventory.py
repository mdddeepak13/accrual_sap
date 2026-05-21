"""Inventory / batch data access for pharma distressed-inventory analysis.

Source (prod): SAP API_BATCH_SRV / Batch. Probe confirmed 30 fields exposed
in sandbox including ShelfLifeExpirationDate, BatchIsMarkedForDeletion,
MatlBatchIsInRstrcdUseStock, LastGoodsReceiptDate — but sandbox demo data
has most pharma-relevant fields unpopulated.

For MOCK_MODE, we serve a synthetic 25-batch pharma dataset (see
tests/fixtures/inventory_batches.json) with realistic distress signals:
expired, near-expiry, marked-for-deletion, quarantined, slow-moving, clean.

In live mode we hit the real SAP endpoint and accept nulls — Claude
handles missing fields gracefully in the prompt.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, ConfigDict

from accrual_pipeline.config import get_settings
from accrual_pipeline.fetchers.base import (
    get_with_retry,
    unwrap_odata,
)
from accrual_pipeline.models import ODataDate

log = structlog.get_logger(__name__)

BATCH_PATH = "/s4hanacloud/sap/opu/odata/sap/API_BATCH_SRV/Batch"
BATCH_FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "inventory_batches.json"


class BatchRecord(BaseModel):
    """Business-shaped batch record for the chat agent.

    Field names are snake_case (agent-facing); the upstream SAP payload
    uses PascalCase and gets mapped at load time.
    """

    model_config = ConfigDict(extra="ignore")

    batch: str
    material: str | None = None
    material_description: str | None = None
    therapeutic_category: str | None = None
    plant: str | None = None
    plant_name: str | None = None
    shelf_life_expiration_date: ODataDate | None = None
    manufacture_date: ODataDate | None = None
    last_goods_receipt_date: ODataDate | None = None
    is_marked_for_deletion: bool = False
    is_restricted_use: bool = False
    supplier: str | None = None
    supplier_name: str | None = None
    country_of_origin: str | None = None
    quantity: float | None = None
    base_unit: str | None = None


_FIELD_MAP = {
    "Batch": "batch",
    "Material": "material",
    "MaterialDescription": "material_description",
    "TherapeuticCategory": "therapeutic_category",
    "BatchIdentifyingPlant": "plant",
    "PlantName": "plant_name",
    "ShelfLifeExpirationDate": "shelf_life_expiration_date",
    "ManufactureDate": "manufacture_date",
    "LastGoodsReceiptDate": "last_goods_receipt_date",
    "BatchIsMarkedForDeletion": "is_marked_for_deletion",
    "MatlBatchIsInRstrcdUseStock": "is_restricted_use",
    "Supplier": "supplier",
    "SupplierName": "supplier_name",
    "CountryOfOrigin": "country_of_origin",
    "Quantity": "quantity",
    "BaseUnit": "base_unit",
}


def _remap(raw: dict[str, Any]) -> dict[str, Any]:
    """Translate SAP PascalCase fields onto our snake_case business shape."""
    out: dict[str, Any] = {}
    for sap_key, our_key in _FIELD_MAP.items():
        if sap_key in raw and raw[sap_key] not in ("", None):
            out[our_key] = raw[sap_key]
    return out


async def fetch_batches(
    client: httpx.AsyncClient,
    *,
    limit: int = 100,
) -> list[BatchRecord]:
    """Fetch batch records from SAP (or fixture in MOCK_MODE)."""
    settings = get_settings()
    if settings.mock_mode:
        log.info("inventory.mock_mode", fixture=str(BATCH_FIXTURE.name))
        payload = json.loads(BATCH_FIXTURE.read_text(encoding="utf-8"))
    else:
        log.info("inventory.fetch", path=BATCH_PATH, limit=limit)
        response = await get_with_retry(
            client, BATCH_PATH, params={"$format": "json", "$top": str(limit)}
        )
        payload = response.json()
    records = unwrap_odata(payload)
    return [BatchRecord.model_validate(_remap(r)) for r in records]


def filter_batches(
    batches: list[BatchRecord],
    *,
    material_prefix: str | None = None,
    therapeutic_category: str | None = None,
    plant: str | None = None,
    supplier_contains: str | None = None,
    distress_signal: str | None = None,  # expired | near_expiry | quarantine | marked_for_deletion | slow_moving | clean
    near_expiry_days: int = 90,
    slow_moving_days: int = 365,
    today: date | None = None,
) -> list[BatchRecord]:
    """Filter a batch list. `distress_signal` encodes the pharma rules."""
    resolved_today = today or date.today()

    def keep(b: BatchRecord) -> bool:
        if material_prefix and (not b.material or not b.material.startswith(material_prefix)):
            return False
        if therapeutic_category and (b.therapeutic_category or "").upper() != therapeutic_category.upper():
            return False
        if plant and b.plant != plant:
            return False
        if supplier_contains:
            hay = (b.supplier or "") + " " + (b.supplier_name or "")
            if supplier_contains.lower() not in hay.lower():
                return False
        if distress_signal:
            ds = distress_signal.lower()
            sled = b.shelf_life_expiration_date
            days_to_expiry = (sled - resolved_today).days if sled else None
            last_gr = b.last_goods_receipt_date
            days_since_gr = (resolved_today - last_gr).days if last_gr else None
            if ds == "expired":
                if days_to_expiry is None or days_to_expiry >= 0:
                    return False
            elif ds == "near_expiry":
                if days_to_expiry is None or not (0 <= days_to_expiry <= near_expiry_days):
                    return False
            elif ds == "quarantine":
                if not b.is_restricted_use:
                    return False
            elif ds == "marked_for_deletion":
                if not b.is_marked_for_deletion:
                    return False
            elif ds == "slow_moving":
                if days_since_gr is None or days_since_gr < slow_moving_days:
                    return False
            elif ds == "clean":
                if b.is_marked_for_deletion or b.is_restricted_use:
                    return False
                if days_to_expiry is not None and days_to_expiry <= near_expiry_days:
                    return False
                if days_since_gr is not None and days_since_gr >= slow_moving_days:
                    return False
            elif ds == "any_distressed":
                expired = days_to_expiry is not None and days_to_expiry < 0
                near = days_to_expiry is not None and 0 <= days_to_expiry <= near_expiry_days
                slow = days_since_gr is not None and days_since_gr >= slow_moving_days
                if not (expired or near or b.is_marked_for_deletion or b.is_restricted_use or slow):
                    return False
        return True

    return [b for b in batches if keep(b)]
