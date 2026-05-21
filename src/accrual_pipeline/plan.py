"""Synthetic plan / budget data.

SAP's sandbox tenant exposes actuals via the Operational Journal Entry
cube but no corresponding plan data that matches our demo's cost centers
and GL ranges. This module serves a hand-curated fixture so chat queries
like "compare actuals vs plan for Q1 2026" have something to compare
against.

For a production deploy, swap `_load_plan_records` to hit one of SAP's
plan APIs (e.g. API_COSTCENTERPLAN_SRV) and drop the fixture.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "plan_data.json"


def _load_plan_records() -> list[dict[str, Any]]:
    with _FIXTURE_PATH.open(encoding="utf-8") as f:
        data: list[dict[str, Any]] = json.load(f)
    return data


def query_plan(
    *,
    fiscal_year: str | None = None,
    fiscal_period: str | None = None,
    cost_center: str | None = None,
    gl_account_prefix: str | None = None,
    company_code: str | None = None,
) -> list[dict[str, Any]]:
    """Return plan rows matching all non-None filters.

    Each row has: company_code, fiscal_year, fiscal_period, cost_center,
    cost_center_name, gl_account, gl_description, planned_amount_usd.
    """
    records = _load_plan_records()

    def matches(r: dict[str, Any]) -> bool:
        if fiscal_year is not None and r.get("fiscal_year") != fiscal_year:
            return False
        if fiscal_period is not None and r.get("fiscal_period") != fiscal_period:
            return False
        if cost_center is not None and r.get("cost_center") != cost_center:
            return False
        if company_code is not None and r.get("company_code") != company_code:
            return False
        if gl_account_prefix is not None and not str(r.get("gl_account", "")).startswith(gl_account_prefix):
            return False
        return True

    return [r for r in records if matches(r)]


def plan_totals(
    rows: list[dict[str, Any]],
    group_by: str = "gl_account",
) -> list[dict[str, Any]]:
    """Aggregate planned_amount_usd by the given field."""
    totals: dict[str, Decimal] = {}
    labels: dict[str, str] = {}
    for r in rows:
        key = str(r.get(group_by, ""))
        totals[key] = totals.get(key, Decimal("0")) + Decimal(str(r.get("planned_amount_usd", "0")))
        # Capture a human label if a parallel `*_description` field exists.
        label_key = f"{group_by}_description" if group_by == "gl_account" else f"{group_by}_name"
        if label_key in r:
            labels[key] = str(r[label_key])
    return [
        {group_by: k, "total_planned_usd": str(v), "label": labels.get(k)}
        for k, v in sorted(totals.items())
    ]
