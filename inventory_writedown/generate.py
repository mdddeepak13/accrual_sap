"""Generate two artifacts from the distressed-inventory fixture:

  1. ``mb52_mbew_distressed.csv`` — mock MB52 + MBEW extract (warehouse stock
     with valuation) joined onto the SAP-style PascalCase batch fields. Limited
     to line items flagged distressed.

  2. ``blackline_je.json`` — BlackLine-importable journal entry that writes down
     the value of the distressed stock. Lines aggregate by valuation class +
     plant; offset is a single credit to the obsolescence allowance account.

Source of truth: ``tests/fixtures/inventory_batches.json`` (the same fixture the
CAP mocksap service serves). Reads it directly; doesn't go through CAP.

Run from anywhere:

    python3 inventory_writedown/generate.py

Re-run after editing the fixture or the rules below.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "inventory_batches.json"
OUT_DIR = Path(__file__).resolve().parent
EXTRACT_PATH = OUT_DIR / "mb52_mbew_distressed.csv"
JE_PATH = OUT_DIR / "blackline_je.json"

# CAP seed CSVs — picked up by the mocksap CAP service on startup.
CAP_DATA_DIR = REPO_ROOT / "mocksap" / "db" / "data"
STOCK_OVERVIEW_CSV = CAP_DATA_DIR / "sap.s4.batch-StockOverview.csv"
MATERIAL_VALUATION_CSV = CAP_DATA_DIR / "sap.s4.batch-MaterialValuation.csv"

# Posting date for the JE. Mirrors the system date used elsewhere in the demo.
TODAY = date(2026, 5, 21)
NEAR_EXPIRY_DAYS = 90
SLOW_MOVING_DAYS = 365

COMPANY_CODE = "1000"
CURRENCY = "USD"
DOC_TYPE = "SA"  # SAP "G/L Account Document"
VALUATION_CLASS = "7900"  # finished goods pharma
GL_WRITEDOWN_EXPENSE = "894500"  # COGS-side write-down expense
GL_WRITEDOWN_EXPENSE_NAME = "Inventory Write-down Expense"
GL_OBSOLESCENCE_ALLOWANCE = "139900"  # BS contra-asset
GL_OBSOLESCENCE_NAME = "Inventory Allowance — Obsolete Stock"

# Synthetic but realistic per-unit standard prices (USD), by therapeutic category.
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

# Write-down severity by primary distress reason. Higher = more aggressive impairment.
WRITEDOWN_PCT: dict[str, Decimal] = {
    "marked_for_deletion": Decimal("1.00"),
    "expired":             Decimal("1.00"),
    "quarantine":          Decimal("0.50"),
    "slow_moving":         Decimal("0.30"),
    "near_expiry":         Decimal("0.25"),
}

# Severity order — first match wins when a batch satisfies multiple rules.
SEVERITY_ORDER = ("marked_for_deletion", "expired", "quarantine", "near_expiry", "slow_moving")

PLANT_NAMES = {
    "1010": "Frankfurt DC",
    "1710": "New Jersey DC",
    "2010": "Bangalore DC",
    "3010": "Sao Paulo DC",
    "4010": "Singapore DC",
}


# ---------------------------------------------------------------------------
# distress classification
# ---------------------------------------------------------------------------


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def classify_distress(batch: dict[str, Any]) -> str | None:
    """Return the most-severe distress reason, or None if the batch is clean."""
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


# ---------------------------------------------------------------------------
# MB52 + MBEW extract row construction
# ---------------------------------------------------------------------------


@dataclass
class ExtractRow:
    matnr: str
    matnr_desc: str
    charg: str
    werks: str
    lgort: str  # storage location — synthetic; pharma typically uses 0001
    labst: Decimal  # unrestricted stock
    insme: Decimal  # quality inspection stock
    speme: Decimal  # blocked stock
    kspem: Decimal  # restricted-use stock
    meins: str  # base UoM
    waers: str
    bklas: str  # valuation class
    stprs: Decimal  # standard price
    peinh: Decimal  # price unit
    verpr: Decimal  # moving avg price
    salk3: Decimal  # total stock value
    lgrdt: str  # last GR date
    hsdat: str  # shelf life expiration date
    lifnr: str  # supplier
    wgru1: str  # country of origin
    therapeutic_category: str
    distress_reason: str
    writedown_pct: Decimal
    writedown_amt: Decimal

    def as_csv_row(self) -> dict[str, Any]:
        return {
            "MATNR": self.matnr,
            "MATNR_Description": self.matnr_desc,
            "CHARG": self.charg,
            "WERKS": self.werks,
            "LGORT": self.lgort,
            "LABST": str(self.labst),
            "INSME": str(self.insme),
            "SPEME": str(self.speme),
            "KSPEM": str(self.kspem),
            "MEINS": self.meins,
            "WAERS": self.waers,
            "BKLAS": self.bklas,
            "STPRS": str(self.stprs),
            "PEINH": str(self.peinh),
            "VERPR": str(self.verpr),
            "SALK3": str(self.salk3),
            "LGRDT": self.lgrdt,
            "HSDAT": self.hsdat,
            "LIFNR": self.lifnr,
            "WGRU1": self.wgru1,
            "Therapeutic_Category": self.therapeutic_category,
            "Distress_Reason": self.distress_reason,
            "Writedown_Pct": str(self.writedown_pct),
            "Writedown_Amount": str(self.writedown_amt),
        }


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_extract_row(batch: dict[str, Any], reason: str) -> ExtractRow:
    qty = Decimal(str(batch.get("Quantity") or 0))
    category = (batch.get("TherapeuticCategory") or "").upper()
    stprs = PRICE_BY_CATEGORY.get(category, DEFAULT_PRICE)
    verpr = _money(stprs * Decimal("0.95"))

    if reason == "marked_for_deletion":
        labst, speme, kspem = Decimal(0), qty, Decimal(0)
    elif reason == "quarantine":
        labst, speme, kspem = Decimal(0), Decimal(0), qty
    else:
        labst, speme, kspem = qty, Decimal(0), Decimal(0)

    salk3 = _money(qty * stprs)
    pct = WRITEDOWN_PCT[reason]
    writedown_amt = _money(salk3 * pct)

    return ExtractRow(
        matnr=batch["Material"],
        matnr_desc=batch.get("MaterialDescription", ""),
        charg=batch["Batch"],
        werks=batch.get("BatchIdentifyingPlant", ""),
        lgort="0001",
        labst=labst,
        insme=Decimal(0),
        speme=speme,
        kspem=kspem,
        meins=batch.get("BaseUnit", "EA"),
        waers=CURRENCY,
        bklas=VALUATION_CLASS,
        stprs=stprs,
        peinh=Decimal(1),
        verpr=verpr,
        salk3=salk3,
        lgrdt=batch.get("LastGoodsReceiptDate", "") or "",
        hsdat=batch.get("ShelfLifeExpirationDate", "") or "",
        lifnr=batch.get("Supplier", "") or "",
        wgru1=batch.get("CountryOfOrigin", "") or "",
        therapeutic_category=category,
        distress_reason=reason,
        writedown_pct=pct,
        writedown_amt=writedown_amt,
    )


# ---------------------------------------------------------------------------
# BlackLine journal entry construction
# ---------------------------------------------------------------------------


def build_blackline_je(rows: list[ExtractRow]) -> dict[str, Any]:
    # Aggregate write-down by plant (one debit line per plant) and one
    # consolidated credit to the obsolescence allowance.
    by_plant: dict[str, Decimal] = {}
    for row in rows:
        by_plant.setdefault(row.werks, Decimal(0))
        by_plant[row.werks] += row.writedown_amt

    debit_lines: list[dict[str, Any]] = []
    for index, plant in enumerate(sorted(by_plant), start=1):
        amount = _money(by_plant[plant])
        if amount == 0:
            continue
        plant_name = PLANT_NAMES.get(plant, f"Plant {plant}")
        debit_lines.append({
            "line_number": index * 10,
            "posting_key": "40",  # DR for GL postings
            "debit_credit": "S",  # Soll = debit
            "gl_account": GL_WRITEDOWN_EXPENSE,
            "gl_account_name": GL_WRITEDOWN_EXPENSE_NAME,
            "company_code": COMPANY_CODE,
            "cost_center": f"CC-{plant}",
            "profit_center": f"PC-{plant}",
            "plant": plant,
            "amount_local": float(amount),
            "amount_doc": float(amount),
            "currency": CURRENCY,
            "line_item_text": (
                f"Distressed pharma write-down — Plant {plant} {plant_name}"
            ),
            "assignment": "INV-WD-2026Q2",
        })

    total_debit = _money(sum((Decimal(str(line["amount_local"])) for line in debit_lines), Decimal(0)))

    credit_line = {
        "line_number": (len(debit_lines) + 1) * 10,
        "posting_key": "50",  # CR for GL postings
        "debit_credit": "H",  # Haben = credit
        "gl_account": GL_OBSOLESCENCE_ALLOWANCE,
        "gl_account_name": GL_OBSOLESCENCE_NAME,
        "company_code": COMPANY_CODE,
        "cost_center": None,
        "profit_center": None,
        "plant": None,
        "amount_local": float(total_debit),
        "amount_doc": float(total_debit),
        "currency": CURRENCY,
        "line_item_text": "Offset to Q2 2026 distressed inventory write-down",
        "assignment": "INV-WD-2026Q2",
    }

    lines = debit_lines + [credit_line]

    # Supporting per-batch detail kept inside the artifact for traceability;
    # BlackLine import generally ignores unknown fields but auditors will want
    # to know which lots are behind each plant-level debit.
    supporting_detail = [
        {
            "material": row.matnr,
            "batch": row.charg,
            "plant": row.werks,
            "distress_reason": row.distress_reason,
            "writedown_pct": float(row.writedown_pct),
            "writedown_amount": float(row.writedown_amt),
            "stock_value_at_standard": float(row.salk3),
        }
        for row in rows
        if row.writedown_amt > 0
    ]

    return {
        "$schema": "https://blackline.com/schemas/journal-entry/v1",
        "header": {
            "journal_id": "BL-JE-2026-Q2-INV-WD",
            "source_system": "BLACKLINE",
            "target_system": "SAP",
            "target_company_code": COMPANY_CODE,
            "currency": CURRENCY,
            "posting_date": TODAY.isoformat(),
            "document_date": TODAY.isoformat(),
            "document_type": DOC_TYPE,
            "header_text": "Q2 2026 distressed pharma inventory write-down",
            "reference": "INV-WD-Q2-2026",
            "preparer": "Deepak",
            "approver": None,
            "status": "DRAFT",
            "source_extract": "inventory_writedown/mb52_mbew_distressed.csv",
        },
        "lines": lines,
        "totals": {
            "total_debit": float(total_debit),
            "total_credit": float(total_debit),
            "balanced": True,
            "line_count": len(lines),
        },
        "supporting_documents": [
            {
                "type": "MB52_MBEW_EXTRACT",
                "path": str(EXTRACT_PATH.relative_to(REPO_ROOT)),
                "line_count": len(rows),
                "extracted_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            }
        ],
        "supporting_detail": supporting_detail,
    }


# ---------------------------------------------------------------------------
# CAP seed CSVs (StockOverview + MaterialValuation) — fed to the mocksap
# service so the BTP CF deployment serves real MB52 / MBEW shapes.
# ---------------------------------------------------------------------------


def write_stock_overview_csv(all_batches: list[dict[str, Any]]) -> int:
    """Emit one StockOverview row per batch (distressed + clean)."""
    STOCK_OVERVIEW_CSV.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "Material", "Plant", "StorageLocation", "Batch",
        "UnrestrictedStock", "QualityInspectionStock", "BlockedStock", "RestrictedStock",
        "BaseUnit", "LastGoodsReceiptDate", "ShelfLifeExpiration",
        "Supplier", "CountryOfOrigin", "DistressReason", "WritedownPercent", "WritedownAmount",
    ]
    written = 0
    with STOCK_OVERVIEW_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for batch in all_batches:
            reason = classify_distress(batch)
            qty = Decimal(str(batch.get("Quantity") or 0))
            category = (batch.get("TherapeuticCategory") or "").upper()
            stprs = PRICE_BY_CATEGORY.get(category, DEFAULT_PRICE)
            salk3 = _money(qty * stprs)

            if reason == "marked_for_deletion":
                labst, speme, kspem = Decimal(0), qty, Decimal(0)
            elif reason == "quarantine":
                labst, speme, kspem = Decimal(0), Decimal(0), qty
            else:
                labst, speme, kspem = qty, Decimal(0), Decimal(0)

            pct = WRITEDOWN_PCT.get(reason or "", Decimal(0))
            writedown_amt = _money(salk3 * pct) if reason else Decimal(0)

            writer.writerow({
                "Material": batch["Material"],
                "Plant": batch.get("BatchIdentifyingPlant", ""),
                "StorageLocation": "0001",
                "Batch": batch["Batch"],
                "UnrestrictedStock": str(labst),
                "QualityInspectionStock": "0",
                "BlockedStock": str(speme),
                "RestrictedStock": str(kspem),
                "BaseUnit": batch.get("BaseUnit", "EA"),
                "LastGoodsReceiptDate": batch.get("LastGoodsReceiptDate", "") or "",
                "ShelfLifeExpiration": batch.get("ShelfLifeExpirationDate", "") or "",
                "Supplier": batch.get("Supplier", "") or "",
                "CountryOfOrigin": batch.get("CountryOfOrigin", "") or "",
                "DistressReason": reason or "",
                "WritedownPercent": str(pct),
                "WritedownAmount": str(writedown_amt),
            })
            written += 1
    return written


def write_material_valuation_csv(all_batches: list[dict[str, Any]]) -> int:
    """Emit one MaterialValuation row per (Material, Plant) pair, aggregating
    total stock quantity and value across all batches at that location."""
    MATERIAL_VALUATION_CSV.parent.mkdir(parents=True, exist_ok=True)
    aggregates: dict[tuple[str, str], dict[str, Any]] = {}
    for batch in all_batches:
        material = batch["Material"]
        plant = batch.get("BatchIdentifyingPlant", "")
        if not plant:
            continue
        key = (material, plant)
        agg = aggregates.setdefault(key, {
            "category": (batch.get("TherapeuticCategory") or "").upper(),
            "qty": Decimal(0),
        })
        agg["qty"] += Decimal(str(batch.get("Quantity") or 0))

    columns = [
        "Material", "ValuationArea", "ValuationClass", "Currency",
        "StandardPrice", "PriceUnit", "MovingAvgPrice",
        "TotalStockQty", "TotalStockValue",
    ]
    written = 0
    with MATERIAL_VALUATION_CSV.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for (material, plant), agg in sorted(aggregates.items()):
            stprs = PRICE_BY_CATEGORY.get(agg["category"], DEFAULT_PRICE)
            verpr = _money(stprs * Decimal("0.95"))
            total_value = _money(agg["qty"] * stprs)
            writer.writerow({
                "Material": material,
                "ValuationArea": plant,
                "ValuationClass": VALUATION_CLASS,
                "Currency": CURRENCY,
                "StandardPrice": str(stprs),
                "PriceUnit": "1",
                "MovingAvgPrice": str(verpr),
                "TotalStockQty": str(agg["qty"]),
                "TotalStockValue": str(total_value),
            })
            written += 1
    return written


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    all_batches = payload["d"]["results"]

    rows: list[ExtractRow] = []
    for batch in all_batches:
        reason = classify_distress(batch)
        if not reason:
            continue
        rows.append(build_extract_row(batch, reason))

    # Sort for deterministic output: plant, then material, then batch.
    rows.sort(key=lambda r: (r.werks, r.matnr, r.charg))

    EXTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EXTRACT_PATH.open("w", newline="", encoding="utf-8") as fh:
        first = rows[0].as_csv_row() if rows else {}
        writer = csv.DictWriter(fh, fieldnames=list(first.keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row.as_csv_row())

    je = build_blackline_je(rows)
    JE_PATH.write_text(json.dumps(je, indent=2) + "\n", encoding="utf-8")

    # CAP seed CSVs for the mocksap CAP service
    stock_rows = write_stock_overview_csv(all_batches)
    valuation_rows = write_material_valuation_csv(all_batches)

    # Stdout summary
    from collections import Counter
    reasons = Counter(r.distress_reason for r in rows)
    print(f"MB52+MBEW extract: {len(rows)} distressed line items -> {EXTRACT_PATH.relative_to(REPO_ROOT)}")
    print("  breakdown:", dict(reasons))
    print(f"BlackLine JE: {je['totals']['line_count']} lines, total DR/CR ${je['totals']['total_debit']:,.2f} USD -> {JE_PATH.relative_to(REPO_ROOT)}")
    print(f"CAP seed StockOverview: {stock_rows} rows -> {STOCK_OVERVIEW_CSV.relative_to(REPO_ROOT)}")
    print(f"CAP seed MaterialValuation: {valuation_rows} rows -> {MATERIAL_VALUATION_CSV.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
