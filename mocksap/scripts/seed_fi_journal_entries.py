"""Seed CAP CSV for sap.s4.batch-A_OperationalAcctgDocItemCube from the FI fixture.

Reads tests/fixtures/fi_journal_entries.json and writes the rows into the CAP
CSV that the deployed CAP service picks up at startup.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
FI_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "fi_journal_entries.json"
PAYROLL_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "fi_payroll_lines.json"
OUT = (
    REPO_ROOT
    / "mocksap"
    / "db"
    / "data"
    / "sap.s4.batch-A_OperationalAcctgDocItemCube.csv"
)

COLUMNS = [
    "CompanyCode", "FiscalYear", "AccountingDocument", "AccountingDocumentItem",
    "FiscalPeriod", "Ledger", "PostingDate", "DocumentDate",
    "AccountingDocumentType", "AccountingDocumentTypeName",
    "AccountingDocumentHeaderText", "DocumentItemText",
    "DocumentReferenceID", "ReferenceDocumentType",
    "IsReversal", "IsReversed",
    "GLAccount", "GLAccountName",
    "AmountInTransactionCurrency", "TransactionCurrency",
    "AmountInCompanyCodeCurrency", "CompanyCodeCurrency",
    "AmountInGlobalCurrency", "GlobalCurrency",
    "DebitCreditCode", "PurchasingDocument", "PurchasingDocumentItem",
    "Material", "Supplier", "SupplierName",
    "InvoiceReference", "InvoiceReferenceFiscalYear", "InvoiceReceiptDate",
    "CostCenter", "CostCenterName", "ProfitCenter",
]


def cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fi_rows = json.loads(FI_FIXTURE.read_text(encoding="utf-8"))["d"]["results"]
    payroll_rows = json.loads(PAYROLL_FIXTURE.read_text(encoding="utf-8"))
    # payroll fixture is a bare list, not wrapped in {"d":{"results":...}}
    if isinstance(payroll_rows, dict):
        payroll_rows = payroll_rows.get("d", {}).get("results", [])
    rows = list(fi_rows) + list(payroll_rows)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for row in rows:
            w.writerow({col: cell(row.get(col)) for col in COLUMNS})
    print(
        f"wrote {len(rows)} rows ({len(fi_rows)} FI + {len(payroll_rows)} payroll) -> {OUT.relative_to(REPO_ROOT)}"
    )


if __name__ == "__main__":
    main()
