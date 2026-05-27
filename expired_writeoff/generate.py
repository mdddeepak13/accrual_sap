"""Initiate write-off workflow for the 35 expired pharma batches.

Produces three artifacts:

  1. ``expired_batches_extract.csv`` — MB52 + MBEW joined extract limited to
     batches with ShelfLifeExpirationDate < today (35 of 125). One row per
     batch, includes valuation + write-off amount (100% of stock value).

  2. ``blackline_accrual_je.csv`` — BlackLine import file (one JE header + one
     line per row). Accrual entry: DR Inventory Write-off Expense (P&L) per
     plant, CR Accrued Inventory Write-off (BS liability). Total of debits = total
     of credits = total stock value of expired batches.

  3. ``blackline_accrual_je.json`` — same JE in BlackLine's structured-import JSON
     shape with supporting per-batch detail for audit trail.

Re-run any time. Idempotent. Source of truth:
``tests/fixtures/inventory_batches.json``.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "inventory_batches.json"
OUT_DIR = Path(__file__).resolve().parent
EXTRACT_PATH = OUT_DIR / "expired_batches_extract.csv"
JE_CSV_PATH = OUT_DIR / "blackline_accrual_je.csv"
JE_JSON_PATH = OUT_DIR / "blackline_accrual_je.json"

TODAY = date(2026, 5, 21)
COMPANY_CODE = "1000"
CURRENCY = "USD"
JE_DOC_TYPE = "SA"  # SAP G/L Account Document
VALUATION_CLASS = "7900"

# Accrual posting:
#   DR  894500  Inventory Write-off Expense                   (P&L)
#   CR  220100  Accrued Inventory Write-off                   (BS liability)
GL_EXPENSE = "894500"
GL_EXPENSE_NAME = "Inventory Write-off Expense"
GL_ACCRUAL = "220100"
GL_ACCRUAL_NAME = "Accrued Inventory Write-off"

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


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _is_expired(batch: dict[str, Any]) -> bool:
    shelf = _parse_date(batch.get("ShelfLifeExpirationDate"))
    return shelf is not None and shelf < TODAY


def main() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    expired_batches = [b for b in payload["d"]["results"] if _is_expired(b)]

    extract_rows: list[dict[str, Any]] = []
    by_plant: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    supporting_detail: list[dict[str, Any]] = []

    for b in sorted(expired_batches, key=lambda x: (x.get("BatchIdentifyingPlant", ""), x["Material"], x["Batch"])):
        category = (b.get("TherapeuticCategory") or "").upper()
        qty = Decimal(str(b.get("Quantity") or 0))
        stprs = PRICE_BY_CATEGORY.get(category, DEFAULT_PRICE)
        verpr = _money(stprs * Decimal("0.95"))
        stock_value = _money(qty * stprs)  # 100% write-off for expired
        writeoff_amount = stock_value

        plant = b.get("BatchIdentifyingPlant", "")
        by_plant[plant] += writeoff_amount

        days_expired = (TODAY - _parse_date(b.get("ShelfLifeExpirationDate"))).days

        extract_rows.append({
            "MATNR": b["Material"],
            "MATNR_Description": b.get("MaterialDescription", ""),
            "CHARG": b["Batch"],
            "WERKS": plant,
            "PlantName": PLANT_NAMES.get(plant, ""),
            "LGORT": "0001",
            "LABST_OnHand": str(qty),
            "MEINS": b.get("BaseUnit", "EA"),
            "WAERS": CURRENCY,
            "BKLAS": VALUATION_CLASS,
            "STPRS": str(stprs),
            "PEINH": "1",
            "VERPR": str(verpr),
            "SALK3_StockValue": str(stock_value),
            "HSDAT_SLED": b.get("ShelfLifeExpirationDate", ""),
            "Days_Past_SLED": str(days_expired),
            "LGRDT_LastGR": b.get("LastGoodsReceiptDate", "") or "",
            "LIFNR_Supplier": b.get("Supplier", "") or "",
            "WGRU1_Country": b.get("CountryOfOrigin", "") or "",
            "TherapeuticCategory": category,
            "WriteoffAmount": str(writeoff_amount),
        })

        supporting_detail.append({
            "material": b["Material"],
            "batch": b["Batch"],
            "plant": plant,
            "days_expired": days_expired,
            "qty": float(qty),
            "standard_price": float(stprs),
            "writeoff_amount": float(writeoff_amount),
        })

    # Write MB52+MBEW extract
    EXTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EXTRACT_PATH.open("w", newline="", encoding="utf-8") as fh:
        if extract_rows:
            writer = csv.DictWriter(fh, fieldnames=list(extract_rows[0].keys()))
            writer.writeheader()
            writer.writerows(extract_rows)

    # Build the BlackLine accrual JE
    total_debit = _money(sum(by_plant.values(), Decimal(0)))
    je_lines: list[dict[str, Any]] = []
    line_no = 0
    for plant in sorted(by_plant):
        line_no += 1
        amount = _money(by_plant[plant])
        je_lines.append({
            "line_number": line_no * 10,
            "posting_key": "40",
            "debit_credit": "S",
            "gl_account": GL_EXPENSE,
            "gl_account_name": GL_EXPENSE_NAME,
            "company_code": COMPANY_CODE,
            "cost_center": f"CC-{plant}",
            "profit_center": f"PC-{plant}",
            "plant": plant,
            "amount_local": float(amount),
            "amount_doc": float(amount),
            "currency": CURRENCY,
            "line_item_text": f"Expired-batch write-off accrual — Plant {plant} {PLANT_NAMES.get(plant, '')}",
            "assignment": "INV-WO-EXPIRED-2026Q2",
        })
    line_no += 1
    je_lines.append({
        "line_number": line_no * 10,
        "posting_key": "50",
        "debit_credit": "H",
        "gl_account": GL_ACCRUAL,
        "gl_account_name": GL_ACCRUAL_NAME,
        "company_code": COMPANY_CODE,
        "cost_center": None,
        "profit_center": None,
        "plant": None,
        "amount_local": float(total_debit),
        "amount_doc": float(total_debit),
        "currency": CURRENCY,
        "line_item_text": "Accrual for expired pharma batch write-off (Q2 2026)",
        "assignment": "INV-WO-EXPIRED-2026Q2",
    })

    je = {
        "$schema": "https://blackline.com/schemas/journal-entry/v1",
        "header": {
            "journal_id": "BL-JE-2026-Q2-INV-WO-EXPIRED",
            "source_system": "BLACKLINE",
            "target_system": "SAP",
            "target_company_code": COMPANY_CODE,
            "currency": CURRENCY,
            "posting_date": TODAY.isoformat(),
            "document_date": TODAY.isoformat(),
            "document_type": JE_DOC_TYPE,
            "header_text": f"Q2 2026 expired-batch write-off accrual ({len(expired_batches)} batches)",
            "reference": "INV-WO-EXPIRED-Q2-2026",
            "preparer": "Deepak",
            "approver": None,
            "status": "DRAFT",
            "source_extract": str(EXTRACT_PATH.relative_to(REPO_ROOT)),
        },
        "lines": je_lines,
        "totals": {
            "total_debit": float(total_debit),
            "total_credit": float(total_debit),
            "balanced": True,
            "line_count": len(je_lines),
        },
        "supporting_documents": [{
            "type": "MB52_MBEW_EXPIRED_EXTRACT",
            "path": str(EXTRACT_PATH.relative_to(REPO_ROOT)),
            "line_count": len(extract_rows),
            "extracted_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }],
        "supporting_detail": supporting_detail,
    }
    JE_JSON_PATH.write_text(json.dumps(je, indent=2) + "\n", encoding="utf-8")

    # BlackLine import-flavored CSV — header row + one row per JE line
    csv_columns = [
        "Journal_ID", "Posting_Date", "Document_Date", "Document_Type",
        "Company_Code", "Currency", "Header_Text", "Reference",
        "Line_Number", "Posting_Key", "GL_Account", "GL_Account_Name",
        "Cost_Center", "Profit_Center", "Plant",
        "Debit_Amount", "Credit_Amount", "Line_Item_Text", "Assignment",
    ]
    with JE_CSV_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=csv_columns)
        writer.writeheader()
        for line in je_lines:
            writer.writerow({
                "Journal_ID": je["header"]["journal_id"],
                "Posting_Date": je["header"]["posting_date"],
                "Document_Date": je["header"]["document_date"],
                "Document_Type": je["header"]["document_type"],
                "Company_Code": COMPANY_CODE,
                "Currency": CURRENCY,
                "Header_Text": je["header"]["header_text"],
                "Reference": je["header"]["reference"],
                "Line_Number": line["line_number"],
                "Posting_Key": line["posting_key"],
                "GL_Account": line["gl_account"],
                "GL_Account_Name": line["gl_account_name"],
                "Cost_Center": line["cost_center"] or "",
                "Profit_Center": line["profit_center"] or "",
                "Plant": line["plant"] or "",
                "Debit_Amount": f"{line['amount_local']:.2f}" if line["debit_credit"] == "S" else "",
                "Credit_Amount": f"{line['amount_local']:.2f}" if line["debit_credit"] == "H" else "",
                "Line_Item_Text": line["line_item_text"],
                "Assignment": line["assignment"],
            })

    # Stdout summary
    print(f"Expired batches: {len(expired_batches)}  -> {EXTRACT_PATH.relative_to(REPO_ROOT)}")
    print(f"BlackLine JE   : {len(je_lines)} lines, total \${float(total_debit):,.2f} USD")
    print(f"               -> {JE_CSV_PATH.relative_to(REPO_ROOT)}  (BlackLine CSV import)")
    print(f"               -> {JE_JSON_PATH.relative_to(REPO_ROOT)} (structured JSON)")
    print("Per-plant write-off accrual:")
    for plant in sorted(by_plant):
        print(f"  {plant} {PLANT_NAMES.get(plant, ''):18s} \${float(by_plant[plant]):>13,.2f}")


if __name__ == "__main__":
    main()
