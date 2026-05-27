"""Seed CAP CSVs for MM (A_PurchaseOrderItem) and CO (A_CostCenter)."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "mocksap" / "db" / "data"

MM_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "mm_purchase_orders.json"
MM_OUT = DATA_DIR / "sap.s4.batch-A_PurchaseOrderItem.csv"
MM_COLUMNS = [
    "PurchaseOrder", "PurchaseOrderItem", "PurchaseOrderType",
    "PurchasingDocumentDate", "Supplier", "SupplierName", "Material",
    "PurchaseOrderItemText", "OrderQuantity", "OrderPriceUnit",
    "NetPriceAmount", "DocumentCurrency", "AccountAssignmentCategory",
    "CostCenter", "GLAccount", "LatestGoodsReceiptDate",
    "InvoicedQuantity", "IsFullyDelivered", "IsFullyInvoiced",
]

CO_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "co_cost_centers.json"
CO_OUT = DATA_DIR / "sap.s4.batch-A_CostCenter.csv"
CO_COLUMNS = [
    "ControllingArea", "CostCenter", "ValidityEndDate", "ValidityStartDate",
    "CostCenterName", "Department", "PersonResponsibleName",
    "CompanyCode", "CostCenterCategory", "CostCenterStandardHierArea",
]


def cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _strip_odata_date(value: str | None) -> str:
    """CO fixture uses `datetime'9999-12-31T00:00:00'` style — flatten to ISO date."""
    if not value:
        return ""
    if isinstance(value, str) and value.startswith("datetime'"):
        return value.split("'")[1].split("T")[0]
    if isinstance(value, str) and "T" in value:
        return value.split("T")[0]
    return str(value)


def write(fixture: Path, out: Path, columns: list[str], date_keys: set[str] | None = None) -> int:
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    rows = payload["d"]["results"]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        for row in rows:
            r = {}
            for col in columns:
                v = row.get(col)
                if date_keys and col in date_keys:
                    v = _strip_odata_date(v)
                r[col] = cell(v)
            w.writerow(r)
    return len(rows)


def main() -> None:
    mm = write(MM_FIXTURE, MM_OUT, MM_COLUMNS,
               date_keys={"PurchasingDocumentDate", "LatestGoodsReceiptDate"})
    co = write(CO_FIXTURE, CO_OUT, CO_COLUMNS,
               date_keys={"ValidityStartDate", "ValidityEndDate"})
    print(f"MM A_PurchaseOrderItem: {mm} rows -> {MM_OUT.relative_to(REPO_ROOT)}")
    print(f"CO A_CostCenter      : {co} rows -> {CO_OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
