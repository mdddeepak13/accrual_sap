"""Seed CAP CSV for the A_CostCenterPlan entity from plan_data.json.

Plan fixture is snake_case; CAP entity uses SAP-style PascalCase, so we map
field-by-field.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "plan_data.json"
OUT = REPO_ROOT / "mocksap" / "db" / "data" / "sap.s4.batch-A_CostCenterPlan.csv"

# fixture snake_case -> CAP PascalCase
MAP = {
    "company_code":         "CompanyCode",
    "fiscal_year":          "FiscalYear",
    "fiscal_period":        "FiscalPeriod",
    "cost_center":          "CostCenter",
    "gl_account":           "GLAccount",
    "cost_center_name":     "CostCenterName",
    "gl_description":       "GLAccountName",
    "planned_amount_usd":   "PlannedAmountInGlobalCurrency",
}


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
    columns = list(MAP.values()) + ["Currency"]
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        for row in rows:
            out = {pascal: row.get(snake, "") for snake, pascal in MAP.items()}
            out["Currency"] = "USD"
            w.writerow(out)
    print(f"wrote {len(rows)} rows -> {OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
