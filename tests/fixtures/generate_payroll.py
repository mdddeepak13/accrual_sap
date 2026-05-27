"""Regenerate the bi-weekly May 2026 payroll fixtures (Workday + SAP FI).

Scenario
--------
- Pay group: ``BIWEEKLY-US-CORP`` (20 US employees, EMP-1001 .. EMP-1020).
- May 2026 contains two complete bi-weekly periods:
    * Period 1: 2026-05-04 → 2026-05-17 (pay date 2026-05-22) — **POSTED to SAP FI**.
    * Period 2: 2026-05-18 → 2026-05-31 (pay date 2026-06-05) — **NOT POSTED**;
      this is the accrual the close team needs to book as of 2026-05-25.

Workday returns one ``Pay_Result`` record per (worker, period) for every worker
who was active during the period. The accrual equals the sum of every Period 2
``workday_total_cost`` (gross + employer cost), since SAP has nothing posted
for that period yet.

Special workers
---------------
- **EMP-1003** — new hire on 2026-05-10. Works 5/11–5/15 of Period 1 (5 days),
  full 10 days of Period 2.
- **EMP-1010** — resigns on 2026-05-20. Full 10 days of Period 1; works
  5/18–5/20 of Period 2 (3 days), then status="Terminated".
- **EMP-1015** — takes 3 days unpaid leave during Period 1. 7 paid days in P1,
  full 10 in P2.

Anomalies seeded on the SAP FI side (Period 1 only — Period 2 isn't posted yet)
-------------------------------------------------------------------------------
- **EMP-1005** — first-period FI lines posted to **CC-9999** instead of the
  worker's true cost center (wrong_cost_center).
- **EMP-1007** — regular earnings posted to GL **50130000** (misc/suspense)
  instead of 50100000 (wrong_gl_account).
- **EMP-1012** — no FI posting at all for Period 1 (missing_in_fi).
- **EMP-1017** — duplicate FI posting (every line emitted twice under separate
  document numbers).
- **EMP-1019** — employer FICA under-posted by $75 (amount_mismatch).
- Phantom worker **EMP-9999** appears in FI but not in Workday
  (orphan / missing_in_workday).

Reproducibility
---------------
``random.seed(42)`` keeps annual salaries / cost-center assignments stable so
the demo narrative doesn't drift.
"""
from __future__ import annotations

import json
import random
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent

PAY_GROUP = "BIWEEKLY-US-CORP"
COMPANY_CODE = "1010"
FISCAL_YEAR = "2026"
FISCAL_PERIOD = "005"  # May

# Two complete bi-weekly periods within May 2026. Period 1 is posted to FI;
# Period 2 is the accrual (Workday has the data, PECI hasn't posted yet).
PERIODS: list[dict] = [
    {
        "id": "P1",
        "start": "2026-05-04",
        "end": "2026-05-17",
        "pay_date": "2026-05-22",
        "run_id": "WD-PRRUN-2026-BW-USCORP-P1",
        "fi_posting_date": "2026-05-22",
        "posted_to_fi": True,
    },
    {
        "id": "P2",
        "start": "2026-05-18",
        "end": "2026-05-31",
        "pay_date": "2026-06-05",
        "run_id": "WD-PRRUN-2026-BW-USCORP-P2",
        "fi_posting_date": None,
        "posted_to_fi": False,
    },
]
STANDARD_DAYS = 10  # paid days per bi-weekly period for full attendance

WORKER_FIRST_NAMES = [
    "Alex", "Jamie", "Taylor", "Jordan", "Casey", "Riley", "Morgan", "Avery",
    "Quinn", "Skyler", "Drew", "Reese", "Hayden", "Cameron", "Rowan", "Sage",
    "Emerson", "Finley", "Harper", "Sawyer",
]
WORKER_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
]
COST_CENTERS = ["CC-1000", "CC-2000", "CC-3000", "CC-4000"]
COST_CENTER_NAMES = {
    "CC-1000": "Production Operations",
    "CC-2000": "Quality Assurance",
    "CC-3000": "R&D",
    "CC-4000": "Corporate Functions",
    "CC-9999": "Unassigned / Default Bucket",
}

GL_REGULAR = "50100000"
GL_OVERTIME = "50110000"
GL_BONUS = "50120000"
GL_MISC_SUSPENSE = "50130000"  # used as the wrong-GL anomaly target
GL_FICA_ER = "50200000"
GL_MEDICARE_ER = "50210000"
GL_401K_MATCH = "50220000"
GL_DESCRIPTIONS = {
    GL_REGULAR: "Regular salaries expense",
    GL_OVERTIME: "Overtime expense",
    GL_BONUS: "Bonus expense",
    GL_MISC_SUSPENSE: "Miscellaneous earnings (suspense)",
    GL_FICA_ER: "Employer FICA expense",
    GL_MEDICARE_ER: "Employer Medicare expense",
    GL_401K_MATCH: "Employer 401(k) match expense",
}

# Workforce events
NEW_HIRE_WORKER = "EMP-1003"
NEW_HIRE_DATE = "2026-05-10"   # Sunday → first working day Monday 5/11
NEW_HIRE_P1_DAYS = 5            # 5/11, 5/12, 5/13, 5/14, 5/15

RESIGNATION_WORKER = "EMP-1010"
RESIGNATION_DATE = "2026-05-20"  # Wednesday
RESIGNATION_P2_DAYS = 3          # 5/18, 5/19, 5/20

LEAVE_WORKER = "EMP-1015"
LEAVE_DAYS = 3                   # taken during Period 1

# FI-side anomalies (Period 1 only — Period 2 isn't posted yet)
WRONG_CC_WORKER = "EMP-1005"
WRONG_GL_WORKER = "EMP-1007"
MISSING_FI_WORKER = "EMP-1012"
DUPLICATE_FI_WORKER = "EMP-1017"
FICA_OFF_WORKER = "EMP-1019"
FICA_UNDER_BY = Decimal("75.00")
ORPHAN_FI_WORKER = "EMP-9999"


def money(value: float | Decimal) -> Decimal:
    """Round to 2dp using half-up rounding."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def make_workers(rng: random.Random) -> list[dict]:
    """Generate 20 synthetic workers with stable salaries and cost centers."""
    workers: list[dict] = []
    for i in range(20):
        emp_id = f"EMP-{1001 + i}"
        first = WORKER_FIRST_NAMES[i % len(WORKER_FIRST_NAMES)]
        last = WORKER_LAST_NAMES[(i * 7) % len(WORKER_LAST_NAMES)]
        annual = rng.choice(
            [60_000, 72_000, 85_000, 95_000, 110_000, 128_000, 150_000, 180_000]
        )
        worker_type = "Hourly" if annual < 80_000 else "Salaried"
        cost_center = rng.choice(COST_CENTERS)
        workers.append(
            {
                "worker_id": emp_id,
                "name": f"{first} {last}",
                "type": worker_type,
                "annual_salary": Decimal(annual),
                "biweekly_gross": money(Decimal(annual) / Decimal(26)),
                "cost_center": cost_center,
            }
        )
    return workers


def attendance_for(worker: dict, period: dict) -> dict | None:
    """Return attendance for this worker/period, or None if not active.

    Returned dict carries ``days_worked``, ``gross``, ``status``, and an
    optional ``termination_date``.
    """
    wid = worker["worker_id"]
    base = worker["biweekly_gross"]

    if wid == NEW_HIRE_WORKER:
        if period["end"] < NEW_HIRE_DATE:
            return None
        if period["start"] <= NEW_HIRE_DATE <= period["end"]:
            days = NEW_HIRE_P1_DAYS
            return {
                "days_worked": days,
                "gross": money(base * Decimal(days) / Decimal(STANDARD_DAYS)),
                "status": "Active",
            }
        return {"days_worked": STANDARD_DAYS, "gross": base, "status": "Active"}

    if wid == RESIGNATION_WORKER:
        if period["end"] < RESIGNATION_DATE:
            return {"days_worked": STANDARD_DAYS, "gross": base, "status": "Active"}
        if period["start"] <= RESIGNATION_DATE <= period["end"]:
            days = RESIGNATION_P2_DAYS
            return {
                "days_worked": days,
                "gross": money(base * Decimal(days) / Decimal(STANDARD_DAYS)),
                "status": "Terminated",
                "termination_date": RESIGNATION_DATE,
            }
        return None  # period entirely after termination

    if wid == LEAVE_WORKER and period["id"] == "P1":
        days = STANDARD_DAYS - LEAVE_DAYS
        return {
            "days_worked": days,
            "gross": money(base * Decimal(days) / Decimal(STANDARD_DAYS)),
            "status": "Active",
        }

    return {"days_worked": STANDARD_DAYS, "gross": base, "status": "Active"}


def workday_record(worker: dict, period: dict, att: dict) -> dict:
    """Build one Workday Pay_Result for a worker / period / attendance."""
    gross = att["gross"]
    days = att["days_worked"]

    fed_tax = money(gross * Decimal("0.12"))
    state_tax = money(gross * Decimal("0.05"))
    fica_ee = money(gross * Decimal("0.062"))
    medicare_ee = money(gross * Decimal("0.0145"))
    contrib_401k = money(gross * Decimal("0.05"))
    medical = money(Decimal("92.00"))  # bi-weekly portion of ~$200/mo premium
    deductions_total = fed_tax + state_tax + fica_ee + medicare_ee + contrib_401k + medical
    net = money(gross - deductions_total)

    fica_er = money(gross * Decimal("0.062"))
    medicare_er = money(gross * Decimal("0.0145"))
    match_401k = money(gross * Decimal("0.03"))
    employer_total = money(fica_er + medicare_er + match_401k)

    record = {
        "Worker_Reference": {"ID": worker["worker_id"], "Type": "Employee_ID"},
        "Worker_Name": worker["name"],
        "Worker_Type": worker["type"],
        "Worker_Status": att["status"],
        "Pay_Group_Reference": {"ID": PAY_GROUP},
        "Pay_Period_Start_Date": period["start"],
        "Pay_Period_End_Date": period["end"],
        "Pay_Date": period["pay_date"],
        "Cost_Center_Reference": {"ID": worker["cost_center"]},
        "Currency": "USD",
        "Days_Worked": str(days),
        "Gross_Pay": str(gross),
        "Net_Pay": str(net),
        "Total_Employer_Cost": str(employer_total),
        "Earnings": [
            {"Code": "REGULAR", "Hours": str(days * 8), "Amount": str(gross),
             "GL_Account": GL_REGULAR}
        ],
        "Deductions": [
            {"Code": "TAX_FED", "Amount": str(fed_tax)},
            {"Code": "TAX_STATE", "Amount": str(state_tax)},
            {"Code": "FICA", "Amount": str(fica_ee)},
            {"Code": "MEDICARE", "Amount": str(medicare_ee)},
            {"Code": "401K", "Amount": str(contrib_401k)},
            {"Code": "MEDICAL", "Amount": str(medical)},
        ],
        "Employer_Costs": [
            {"Code": "FICA_ER", "Amount": str(fica_er), "GL_Account": GL_FICA_ER},
            {"Code": "MEDICARE_ER", "Amount": str(medicare_er),
             "GL_Account": GL_MEDICARE_ER},
            {"Code": "401K_MATCH", "Amount": str(match_401k),
             "GL_Account": GL_401K_MATCH},
        ],
    }
    if att.get("termination_date"):
        record["Termination_Date"] = att["termination_date"]
    return record


def fi_line(
    doc: str,
    item_seq: int,
    *,
    worker_id: str,
    worker_name: str,
    period: dict,
    gl: str,
    amount: Decimal,
    description: str,
    cost_center: str,
) -> dict:
    """Build one FI A_OperationalAcctgDocItemCube row for a payroll posting."""
    item = f"{item_seq:03d}"
    return {
        "__metadata": {
            "id": (
                f"API_OPLACCTGDOCITEMCUBE_SRV/A_OperationalAcctgDocItemCube("
                f"CompanyCode='{COMPANY_CODE}',FiscalYear='{FISCAL_YEAR}',"
                f"AccountingDocument='{doc}',AccountingDocumentItem='{item}')"
            ),
            "type": "API_OPLACCTGDOCITEMCUBE_SRV.A_OperationalAcctgDocItemCubeType",
        },
        "CompanyCode": COMPANY_CODE,
        "FiscalYear": FISCAL_YEAR,
        "FiscalPeriod": FISCAL_PERIOD,
        "AccountingDocument": doc,
        "AccountingDocumentItem": item,
        "Ledger": "",
        "PostingDate": period["fi_posting_date"],
        "DocumentDate": period["fi_posting_date"],
        "AccountingDocumentType": "PY",
        "AccountingDocumentTypeName": "Payroll Posting",
        "AccountingDocumentHeaderText": (
            f"PECI payroll {PAY_GROUP} period {period['start']}–{period['end']} "
            f"(pay date {period['pay_date']})"
        ),
        "DocumentItemText": (
            f"{description} - {worker_name} - period {period['start']}–{period['end']}"
        ),
        "DocumentReferenceID": (
            f"PECI-{PAY_GROUP}-{period['end']}-{worker_id}"
        ),
        "ReferenceDocumentType": "PECI",
        "IsReversal": False,
        "IsReversed": False,
        "GLAccount": gl,
        "GLAccountName": GL_DESCRIPTIONS.get(gl, gl),
        "AmountInTransactionCurrency": str(amount),
        "TransactionCurrency": "USD",
        "AmountInCompanyCodeCurrency": str(amount),
        "CompanyCodeCurrency": "USD",
        "AmountInGlobalCurrency": str(amount),
        "GlobalCurrency": "USD",
        "DebitCreditCode": "S",
        "PurchasingDocument": "",
        "PurchasingDocumentItem": "",
        "Material": "",
        "Supplier": "",
        "SupplierName": "",
        "InvoiceReference": "",
        "InvoiceReferenceFiscalYear": "0",
        "InvoiceReceiptDate": None,
        "CostCenter": cost_center,
        "CostCenterName": COST_CENTER_NAMES.get(cost_center, ""),
        "ProfitCenter": "PC-100",
        "WorkerReference": worker_id,
        "PayGroupReference": PAY_GROUP,
        "PayPeriodStartDate": period["start"],
        "PayPeriodEndDate": period["end"],
    }


def build_period1_fi_lines(
    workers: list[dict],
    p1_attendance: dict[str, dict],
) -> list[dict]:
    """Build the SAP FI Period 1 posting set, with anomalies seeded in."""
    period = PERIODS[0]
    rows: list[dict] = []
    doc_counter = 1

    for w in workers:
        wid = w["worker_id"]
        att = p1_attendance.get(wid)
        if att is None or wid == MISSING_FI_WORKER:
            # Either the worker wasn't active in P1 (e.g., EMP-1003 before hire
            # date wouldn't apply here — they ARE active in P1) OR they're the
            # missing_in_fi anomaly worker.
            continue

        fi_cc = "CC-9999" if wid == WRONG_CC_WORKER else w["cost_center"]
        gross = att["gross"]
        regular_gl = GL_MISC_SUSPENSE if wid == WRONG_GL_WORKER else GL_REGULAR
        fica = money(gross * Decimal("0.062"))
        if wid == FICA_OFF_WORKER:
            fica = money(fica - FICA_UNDER_BY)
        medicare = money(gross * Decimal("0.0145"))
        match_401k = money(gross * Decimal("0.03"))

        doc_id = f"P{doc_counter:08d}"
        lines: list[dict] = [
            fi_line(doc_id, 1, worker_id=wid, worker_name=w["name"], period=period,
                    gl=regular_gl, amount=gross,
                    description="Payroll regular", cost_center=fi_cc),
            fi_line(doc_id, 2, worker_id=wid, worker_name=w["name"], period=period,
                    gl=GL_FICA_ER, amount=fica,
                    description="Employer FICA", cost_center=fi_cc),
            fi_line(doc_id, 3, worker_id=wid, worker_name=w["name"], period=period,
                    gl=GL_MEDICARE_ER, amount=medicare,
                    description="Employer Medicare", cost_center=fi_cc),
            fi_line(doc_id, 4, worker_id=wid, worker_name=w["name"], period=period,
                    gl=GL_401K_MATCH, amount=match_401k,
                    description="Employer 401(k) match", cost_center=fi_cc),
        ]
        rows.extend(lines)
        doc_counter += 1

        if wid == DUPLICATE_FI_WORKER:
            dup_doc = f"P{doc_counter:08d}"
            for seq, src in enumerate(lines, start=1):
                rows.append(
                    fi_line(
                        dup_doc, seq, worker_id=wid, worker_name=w["name"],
                        period=period, gl=src["GLAccount"],
                        amount=Decimal(src["AmountInGlobalCurrency"]),
                        description=src["DocumentItemText"].split(" - ")[0]
                        + " (duplicate)",
                        cost_center=src["CostCenter"],
                    )
                )
            doc_counter += 1

    # Phantom orphan worker — present in FI but not in Workday.
    orphan_doc = f"P{doc_counter:08d}"
    rows.append(
        fi_line(
            orphan_doc, 1, worker_id=ORPHAN_FI_WORKER,
            worker_name="Unknown (phantom)", period=period, gl=GL_REGULAR,
            amount=money(Decimal("3500.00")),
            description="Payroll regular", cost_center="CC-4000",
        )
    )
    return rows


def main() -> None:
    rng = random.Random(42)
    workers = make_workers(rng)

    workday_records: list[dict] = []
    p1_attendance: dict[str, dict] = {}

    for period in PERIODS:
        for w in workers:
            att = attendance_for(w, period)
            if att is None:
                continue
            workday_records.append(workday_record(w, period, att))
            if period["id"] == "P1":
                p1_attendance[w["worker_id"]] = att

    workday_payload = {
        "Get_Payroll_Results_Response": {
            "Response_Data": {
                "Pay_Group_Reference": {"ID": PAY_GROUP},
                "Pay_Period_Range": {
                    "Start_Date": PERIODS[0]["start"],
                    "End_Date": PERIODS[-1]["end"],
                },
                "Currency": "USD",
                "Pay_Result": workday_records,
            }
        }
    }

    fi_rows = build_period1_fi_lines(workers, p1_attendance)
    fi_payload = {"d": {"results": fi_rows}}

    workday_path = OUT_DIR / "workday_payroll_results.json"
    fi_path = OUT_DIR / "fi_payroll_lines.json"
    workday_path.write_text(json.dumps(workday_payload, indent=2), encoding="utf-8")
    fi_path.write_text(json.dumps(fi_payload, indent=2), encoding="utf-8")

    print(f"wrote {len(workday_records)} Workday Pay_Result records → {workday_path.name}")
    print(f"  - Period 1 ({PERIODS[0]['start']}–{PERIODS[0]['end']}): "
          f"{sum(1 for r in workday_records if r['Pay_Period_End_Date'] == PERIODS[0]['end'])} records")
    print(f"  - Period 2 ({PERIODS[1]['start']}–{PERIODS[1]['end']}): "
          f"{sum(1 for r in workday_records if r['Pay_Period_End_Date'] == PERIODS[1]['end'])} records")
    print(f"wrote {len(fi_rows)} SAP FI lines → {fi_path.name} (Period 1 only)")
    print("Workforce events:")
    print(f"  - New hire ({NEW_HIRE_DATE}): {NEW_HIRE_WORKER}")
    print(f"  - Resignation ({RESIGNATION_DATE}): {RESIGNATION_WORKER}")
    print(f"  - 3 days leave in P1: {LEAVE_WORKER}")
    print("Anomalies seeded in P1 FI posting:")
    print(f"  - Wrong CC (CC-9999): {WRONG_CC_WORKER}")
    print(f"  - Wrong GL ({GL_MISC_SUSPENSE} instead of {GL_REGULAR}): {WRONG_GL_WORKER}")
    print(f"  - Missing FI posting: {MISSING_FI_WORKER}")
    print(f"  - Duplicate FI posting: {DUPLICATE_FI_WORKER}")
    print(f"  - Employer FICA under by ${FICA_UNDER_BY}: {FICA_OFF_WORKER}")
    print(f"  - Phantom worker in FI (no Workday match): {ORPHAN_FI_WORKER}")


if __name__ == "__main__":
    main()
