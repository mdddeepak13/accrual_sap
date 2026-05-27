"""Convert tests/fixtures/inventory_batches.json -> db/data/sap.s4.batch-Batch.csv

Keeps the JSON fixture as single source of truth; rerun whenever it changes.
The fixture is already in SAP OData V2 envelope with PascalCase fields, so this
mostly drops the two extra columns the CAP schema doesn't model.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "inventory_batches.json"
OUT = Path(__file__).resolve().parents[1] / "db" / "data" / "sap.s4.batch-Batch.csv"

CAP_COLUMNS = [
    "Batch",
    "Material",
    "MaterialDescription",
    "TherapeuticCategory",
    "BatchIdentifyingPlant",
    "PlantName",
    "ShelfLifeExpirationDate",
    "ManufactureDate",
    "LastGoodsReceiptDate",
    "BatchIsMarkedForDeletion",
    "MatlBatchIsInRstrcdUseStock",
    "Supplier",
    "SupplierName",
    "CountryOfOrigin",
    "Quantity",
    "BaseUnit",
]


def cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = payload["d"]["results"]

    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(CAP_COLUMNS)
        for row in rows:
            writer.writerow([cell(row.get(col)) for col in CAP_COLUMNS])

    print(f"wrote {len(rows)} rows -> {OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
