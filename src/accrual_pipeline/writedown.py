"""Distressed-inventory write-down extract.

Joins MB52 stock data (per material × plant × batch) with MBEW valuation data
(per material × valuation area) and emits a per-batch view that includes
distress reason, write-down percentage, and write-down amount.

Live mode calls two OData services on the BTP CAP mock SAP deployment:
- ``API_STOCK_OVERVIEW_SRV/StockOverview`` (MB52 shape)
- ``API_MATERIAL_VALUATION_SRV/MaterialValuation`` (MBEW shape)

MOCK_MODE reads the same inventory_batches fixture used by inventory.py and
applies the distress + pricing logic in-process so tests stay offline. Logic
intentionally mirrors ``inventory_writedown/generate.py`` so the BlackLine
artifact and the live endpoint surface identical numbers.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import structlog
from pydantic import BaseModel, ConfigDict

from accrual_pipeline.config import get_settings
from accrual_pipeline.fetchers.base import get_with_retry, unwrap_odata
from accrual_pipeline.models import ODataDate

log = structlog.get_logger(__name__)

STOCK_OVERVIEW_PATH = "/s4hanacloud/sap/opu/odata/sap/API_STOCK_OVERVIEW_SRV/StockOverview"
MATERIAL_VALUATION_PATH = "/s4hanacloud/sap/opu/odata/sap/API_MATERIAL_VALUATION_SRV/MaterialValuation"

# Shared with inventory.py / inventory_writedown/generate.py.
BATCH_FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "inventory_batches.json"
TODAY = date(2026, 5, 21)
NEAR_EXPIRY_DAYS = 90
SLOW_MOVING_DAYS = 365

PRICE_BY_CATEGORY: dict[str, Decimal] = {
    "ANTIBIOTIC":   Decimal("4.50"),
    "ANTIVIRAL":    Decimal("18.00"),
    "BIOLOGIC":     Decimal("850.00"),
    "CHRONIC":      Decimal("0.80"),
    "CONTROLLED":   Decimal("5.00"),
    "IMMUNO":       Decimal("150.00"),
    "INJECTABLE":   Decimal("25.00"),
    "ONCOLOGY":     Decimal("250.00"),
    "OTC":          Decimal("0.30"),
    "RESPIRATORY":  Decimal("2.50"),
    "VACCINE":      Decimal("35.00"),
}
DEFAULT_PRICE = Decimal("5.00")
PLANT_NAMES = {
    "1010": "Frankfurt DC",
    "1710": "New Jersey DC",
    "2010": "Bangalore DC",
    "3010": "Sao Paulo DC",
    "4010": "Singapore DC",
}
WRITEDOWN_PCT: dict[str, Decimal] = {
    "marked_for_deletion": Decimal("1.00"),
    "expired":             Decimal("1.00"),
    "quarantine":          Decimal("0.50"),
    "slow_moving":         Decimal("0.30"),
    "near_expiry":         Decimal("0.25"),
}


class WritedownItem(BaseModel):
    """Per-batch row joining MB52 stock + MBEW valuation + distress signals."""

    model_config = ConfigDict(extra="ignore")

    material: str
    material_description: str | None = None
    batch: str
    plant: str
    plant_name: str | None = None
    storage_location: str | None = None
    unrestricted_stock: float = 0.0
    blocked_stock: float = 0.0
    restricted_stock: float = 0.0
    base_unit: str | None = None
    last_goods_receipt_date: ODataDate | None = None
    shelf_life_expiration_date: ODataDate | None = None
    supplier: str | None = None
    supplier_name: str | None = None
    country_of_origin: str | None = None
    therapeutic_category: str | None = None
    standard_price: float = 0.0
    moving_avg_price: float = 0.0
    valuation_class: str | None = None
    currency: str = "USD"
    stock_value_at_standard: float = 0.0
    distress_reason: str | None = None
    writedown_percent: float = 0.0
    writedown_amount: float = 0.0


# ---------------------------------------------------------------------------
# field maps + remappers
# ---------------------------------------------------------------------------

_STOCK_FIELD_MAP = {
    "Material": "material",
    "Plant": "plant",
    "StorageLocation": "storage_location",
    "Batch": "batch",
    "UnrestrictedStock": "unrestricted_stock",
    "BlockedStock": "blocked_stock",
    "RestrictedStock": "restricted_stock",
    "BaseUnit": "base_unit",
    "LastGoodsReceiptDate": "last_goods_receipt_date",
    "ShelfLifeExpiration": "shelf_life_expiration_date",
    "Supplier": "supplier",
    "CountryOfOrigin": "country_of_origin",
    "DistressReason": "distress_reason",
    "WritedownPercent": "writedown_percent",
    "WritedownAmount": "writedown_amount",
}

_VALUATION_FIELD_MAP = {
    "Material": "material",
    "ValuationArea": "plant",
    "ValuationClass": "valuation_class",
    "Currency": "currency",
    "StandardPrice": "standard_price",
    "MovingAvgPrice": "moving_avg_price",
}


def _remap(raw: dict[str, Any], field_map: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for sap_key, our_key in field_map.items():
        if sap_key in raw and raw[sap_key] not in ("", None):
            out[our_key] = raw[sap_key]
    return out


# ---------------------------------------------------------------------------
# live fetchers (BTP CAP service)
# ---------------------------------------------------------------------------


def _odata_url(path: str, params: dict[str, str]) -> str:
    """Build an OData URL with %20 spaces. CAP's parser rejects '+' as space."""
    qs = "&".join(f"{quote(k, safe='$')}={quote(v, safe='')}" for k, v in params.items())
    return f"{path}?{qs}"


async def fetch_stock_overview(
    client: httpx.AsyncClient,
    *,
    distressed_only: bool = True,
    limit: int = 500,
) -> list[dict[str, Any]]:
    params: dict[str, str] = {"$format": "json", "$top": str(limit)}
    if distressed_only:
        params["$filter"] = "WritedownAmount gt 0"
    url = _odata_url(STOCK_OVERVIEW_PATH, params)
    log.info("writedown.fetch_stock_overview", url=url, distressed_only=distressed_only)
    try:
        response = await get_with_retry(client, url)
        return unwrap_odata(response.json())
    except Exception as exc:
        log.warning("writedown.btp_stock_unavailable", error=type(exc).__name__, detail=str(exc))
        raise


async def fetch_material_valuation(
    client: httpx.AsyncClient,
    *,
    limit: int = 500,
) -> list[dict[str, Any]]:
    url = _odata_url(MATERIAL_VALUATION_PATH, {"$format": "json", "$top": str(limit)})
    log.info("writedown.fetch_material_valuation", url=url)
    try:
        response = await get_with_retry(client, url)
        return unwrap_odata(response.json())
    except Exception as exc:
        log.warning("writedown.btp_valuation_unavailable", error=type(exc).__name__, detail=str(exc))
        raise


# ---------------------------------------------------------------------------
# mock-mode: compute from inventory_batches fixture in-process
# ---------------------------------------------------------------------------


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _classify_distress(batch: dict[str, Any]) -> str | None:
    if batch.get("BatchIsMarkedForDeletion"):
        return "marked_for_deletion"
    shelf = _parse_date(batch.get("ShelfLifeExpirationDate"))
    if shelf and shelf < TODAY:
        return "expired"
    if batch.get("MatlBatchIsInRstrcdUseStock"):
        return "quarantine"
    if shelf and (shelf - TODAY).days <= NEAR_EXPIRY_DAYS:
        return "near_expiry"
    last_gr = _parse_date(batch.get("LastGoodsReceiptDate"))
    if last_gr and (TODAY - last_gr).days > SLOW_MOVING_DAYS:
        return "slow_moving"
    return None


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _mock_writedown_items(*, distressed_only: bool = True) -> list[WritedownItem]:
    payload = json.loads(BATCH_FIXTURE.read_text(encoding="utf-8"))
    items: list[WritedownItem] = []
    for batch in payload["d"]["results"]:
        reason = _classify_distress(batch)
        if distressed_only and not reason:
            continue
        category = (batch.get("TherapeuticCategory") or "").upper()
        qty = Decimal(str(batch.get("Quantity") or 0))
        stprs = PRICE_BY_CATEGORY.get(category, DEFAULT_PRICE)
        verpr = _money(stprs * Decimal("0.95"))
        salk3 = _money(qty * stprs)
        pct = WRITEDOWN_PCT.get(reason or "", Decimal(0))
        writedown_amt = _money(salk3 * pct) if reason else Decimal(0)

        items.append(
            WritedownItem(
                material=batch["Material"],
                material_description=batch.get("MaterialDescription"),
                batch=batch["Batch"],
                plant=batch.get("BatchIdentifyingPlant", ""),
                plant_name=batch.get("PlantName"),
                storage_location="0001",
                unrestricted_stock=float(qty) if reason not in {"marked_for_deletion", "quarantine"} else 0.0,
                blocked_stock=float(qty) if reason == "marked_for_deletion" else 0.0,
                restricted_stock=float(qty) if reason == "quarantine" else 0.0,
                base_unit=batch.get("BaseUnit"),
                last_goods_receipt_date=batch.get("LastGoodsReceiptDate"),
                shelf_life_expiration_date=batch.get("ShelfLifeExpirationDate"),
                supplier=batch.get("Supplier"),
                supplier_name=batch.get("SupplierName"),
                country_of_origin=batch.get("CountryOfOrigin"),
                therapeutic_category=category or None,
                standard_price=float(stprs),
                moving_avg_price=float(verpr),
                valuation_class="7900",
                currency="USD",
                stock_value_at_standard=float(salk3),
                distress_reason=reason,
                writedown_percent=float(pct),
                writedown_amount=float(writedown_amt),
            )
        )
    return items


# ---------------------------------------------------------------------------
# join + summarize
# ---------------------------------------------------------------------------


def join_stocks_with_valuations(
    stocks: list[dict[str, Any]],
    valuations: list[dict[str, Any]],
) -> list[WritedownItem]:
    val_index: dict[tuple[str, str], dict[str, Any]] = {}
    for v in valuations:
        mapped = _remap(v, _VALUATION_FIELD_MAP)
        key = (mapped.get("material", ""), mapped.get("plant", ""))
        val_index[key] = mapped

    items: list[WritedownItem] = []
    for s in stocks:
        stock = _remap(s, _STOCK_FIELD_MAP)
        val = val_index.get((stock.get("material", ""), stock.get("plant", "")), {})
        merged = {**stock, **val}
        labst = float(stock.get("unrestricted_stock") or 0)
        spepm = float(stock.get("blocked_stock") or 0)
        kspem = float(stock.get("restricted_stock") or 0)
        total_qty = labst + spepm + kspem
        price = float(val.get("standard_price") or 0)
        merged["stock_value_at_standard"] = round(total_qty * price, 2)
        merged.setdefault("plant_name", PLANT_NAMES.get(stock.get("plant", "")))
        items.append(WritedownItem.model_validate(merged))
    return items


def summarize_by_plant(items: list[WritedownItem]) -> list[dict[str, Any]]:
    by_plant: dict[str, dict[str, Any]] = {}
    for it in items:
        bucket = by_plant.setdefault(it.plant, {
            "plant": it.plant,
            "plant_name": it.plant_name,
            "line_count": 0,
            "total_stock_value": 0.0,
            "total_writedown": 0.0,
            "by_reason": {},
        })
        bucket["line_count"] += 1
        bucket["total_stock_value"] += it.stock_value_at_standard
        bucket["total_writedown"] += it.writedown_amount
        if it.distress_reason:
            bucket["by_reason"][it.distress_reason] = bucket["by_reason"].get(it.distress_reason, 0) + 1
    for b in by_plant.values():
        b["total_stock_value"] = round(b["total_stock_value"], 2)
        b["total_writedown"] = round(b["total_writedown"], 2)
    return sorted(by_plant.values(), key=lambda b: b["plant"])


# ---------------------------------------------------------------------------
# public entrypoint
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# BlackLine JE drafting
# ---------------------------------------------------------------------------

PLANT_NAMES_FOR_JE = PLANT_NAMES  # alias for readability
GL_WRITEOFF_EXPENSE = "894500"
GL_WRITEOFF_EXPENSE_NAME = "Inventory Write-off Expense"
GL_WRITEOFF_ACCRUAL = "220100"
GL_WRITEOFF_ACCRUAL_NAME = "Accrued Inventory Write-off"


def _build_writeoff_je(
    items: list[WritedownItem],
    *,
    reason: str,
    posting_date: date | None = None,
) -> dict[str, Any]:
    """Aggregate per-batch write-offs by plant and emit a BlackLine JE payload.

    Mirrors ``expired_writeoff/generate.py`` so the live-drafted JE on the page
    matches the offline-generated artifact byte-for-byte (modulo IDs/timestamps).
    """
    pd_date = posting_date or TODAY
    by_plant: dict[str, Decimal] = {}
    supporting_detail: list[dict[str, Any]] = []

    for it in items:
        amt = Decimal(str(it.writedown_amount))
        if amt <= 0:
            continue
        by_plant[it.plant] = by_plant.get(it.plant, Decimal(0)) + amt
        days_expired: int | None = None
        shelf = it.shelf_life_expiration_date
        if isinstance(shelf, str):
            try:
                shelf = datetime.strptime(shelf, "%Y-%m-%d").date()
            except ValueError:
                shelf = None
        if isinstance(shelf, date):
            days_expired = (pd_date - shelf).days
        supporting_detail.append({
            "material": it.material,
            "batch": it.batch,
            "plant": it.plant,
            "days_expired": days_expired,
            "qty": float(
                (it.unrestricted_stock or 0)
                + (it.blocked_stock or 0)
                + (it.restricted_stock or 0)
            ),
            "standard_price": float(it.standard_price or 0),
            "writeoff_amount": float(amt),
        })

    lines: list[dict[str, Any]] = []
    line_no = 0
    for plant in sorted(by_plant):
        line_no += 1
        amount = _money(by_plant[plant])
        lines.append({
            "line_number": line_no * 10,
            "posting_key": "40",
            "debit_credit": "S",
            "gl_account": GL_WRITEOFF_EXPENSE,
            "gl_account_name": GL_WRITEOFF_EXPENSE_NAME,
            "company_code": "1000",
            "cost_center": f"CC-{plant}",
            "profit_center": f"PC-{plant}",
            "plant": plant,
            "amount_local": float(amount),
            "amount_doc": float(amount),
            "currency": "USD",
            "line_item_text": f"{reason.replace('_', ' ').title()} pharma write-off — Plant {plant} {PLANT_NAMES.get(plant, '')}",
            "assignment": f"INV-WO-{reason.upper()}-2026Q2",
        })

    total = _money(sum(by_plant.values(), Decimal(0)))
    line_no += 1
    lines.append({
        "line_number": line_no * 10,
        "posting_key": "50",
        "debit_credit": "H",
        "gl_account": GL_WRITEOFF_ACCRUAL,
        "gl_account_name": GL_WRITEOFF_ACCRUAL_NAME,
        "company_code": "1000",
        "cost_center": None,
        "profit_center": None,
        "plant": None,
        "amount_local": float(total),
        "amount_doc": float(total),
        "currency": "USD",
        "line_item_text": f"Accrual for {reason.replace('_', ' ')} pharma batch write-off (Q2 2026)",
        "assignment": f"INV-WO-{reason.upper()}-2026Q2",
    })

    return {
        "$schema": "https://blackline.com/schemas/journal-entry/v1",
        "header": {
            "journal_id": f"BL-JE-2026-Q2-INV-WO-{reason.upper()}",
            "source_system": "BLACKLINE",
            "target_system": "SAP",
            "target_company_code": "1000",
            "currency": "USD",
            "posting_date": pd_date.isoformat(),
            "document_date": pd_date.isoformat(),
            "document_type": "SA",
            "header_text": f"Q2 2026 {reason.replace('_', ' ')} batch write-off accrual ({len(supporting_detail)} batches)",
            "reference": f"INV-WO-{reason.upper()}-Q2-2026",
            "preparer": "Deepak",
            "approver": None,
            "status": "DRAFT",
            "source": "live SAP via BTP CAP",
        },
        "lines": lines,
        "totals": {
            "total_debit": float(total),
            "total_credit": float(total),
            "balanced": True,
            "line_count": len(lines),
        },
        "supporting_detail": supporting_detail,
    }


async def draft_writeoff_je(
    client: httpx.AsyncClient | None,
    *,
    reason: str = "expired",
) -> dict[str, Any]:
    """Pull live distressed data, filter to one reason, return a BlackLine JE."""
    settings = get_settings()
    if settings.mock_mode or client is None:
        items = _mock_writedown_items(distressed_only=True)
    else:
        stocks = await fetch_stock_overview(client, distressed_only=True)
        valuations = await fetch_material_valuation(client)
        items = join_stocks_with_valuations(stocks, valuations)

    if reason != "all_distressed":
        items = [it for it in items if it.distress_reason == reason]

    log.info("writedown.draft_writeoff_je", reason=reason, items=len(items))
    return _build_writeoff_je(items, reason=reason)


async def get_distressed_writedown_extract(
    client: httpx.AsyncClient | None,
    *,
    distressed_only: bool = True,
) -> dict[str, Any]:
    """Return per-batch distress + valuation + write-down for the chat agent.

    In MOCK_MODE the data is computed from the fixture. Otherwise we call the
    two OData services on the BTP CAP mock SAP and join in memory.
    """
    settings = get_settings()
    if settings.mock_mode or client is None:
        log.info("writedown.mock_mode")
        items = _mock_writedown_items(distressed_only=distressed_only)
    else:
        stocks = await fetch_stock_overview(client, distressed_only=distressed_only)
        valuations = await fetch_material_valuation(client)
        items = join_stocks_with_valuations(stocks, valuations)

    summary = summarize_by_plant(items)
    return {
        "items": [it.model_dump(mode="json") for it in items],
        "summary_by_plant": summary,
        "total_writedown": round(sum(it.writedown_amount for it in items), 2),
        "total_stock_value_at_standard": round(sum(it.stock_value_at_standard for it in items), 2),
        "currency": "USD",
        "line_count": len(items),
    }
