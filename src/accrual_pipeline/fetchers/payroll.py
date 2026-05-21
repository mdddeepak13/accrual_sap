"""Payroll fetcher — Workday SOAP + the FI lines PECI is supposed to have posted.

This module spans **two external systems** intentionally: the demo needs both
sides to reconcile, and keeping them in one file makes the contract obvious.

Two functions:
  - ``fetch_workday_payroll_results`` — Workday Global Payroll Cloud SOAP API,
    operation ``Get_Payroll_Results``. Returns one ``WorkdayPayrollResult``
    per worker per pay period.
  - ``fetch_peci_fi_lines`` — SAP FI journal entries that PECI delivered into
    S/4. Queried from the same Operational Journal Entry cube the normal
    FI fetcher uses, but filtered to payroll GL accounts + AccountingDocumentType
    ``PY`` so we don't double-pull rent/services accruals.

Both honor ``MOCK_MODE``; both produce shapes that the rest of the pipeline
treats identically whether the data came from a fixture or a live call.

Live Workday path notes
-----------------------
The live SOAP path is intentionally minimal — for the demo, only the mock path
is exercised. It uses a hand-rolled WS-Security UsernameToken envelope rather
than pulling in zeep, because the response shape only needs xmltodict-style
parsing and zeep adds ~12MB to the function bundle.
"""
from __future__ import annotations

from typing import Any

import httpx
import structlog

from accrual_pipeline.config import get_settings
from accrual_pipeline.fetchers.base import (
    get_with_retry,
    load_fixture,
    unwrap_odata,
)
from accrual_pipeline.models import FIJournalEntry, WorkdayPayrollResult

log = structlog.get_logger(__name__)

WORKDAY_FIXTURE = "workday_payroll_results.json"
FI_PAYROLL_FIXTURE = "fi_payroll_lines.json"

# Payroll-side FI account ranges. PECI posts expense lines to 50xxxxxx and
# accrual liability lines to 22150000 / 22160000 — both are pulled so Claude
# can reconcile the full posting set, not just one side.
PAYROLL_EXPENSE_GL_FROM = "50100000"
PAYROLL_EXPENSE_GL_TO   = "50299999"
PAYROLL_ACCRUAL_GLS     = ("22150000", "22160000")

# Same cube as fi.py — the operational journal entry item view.
FI_PATH = (
    "/s4hanacloud/sap/opu/odata/sap/API_OPLACCTGDOCITEMCUBE_SRV"
    "/A_OperationalAcctgDocItemCube"
)
DEFAULT_COMPANY_CODE = "1010"

# Hand-rolled SOAP envelope template. Workday's Get_Payroll_Results accepts
# a Pay_Group_Reference + period filter; pagination is not modeled here
# (demo dataset is ≤50 results).
_SOAP_ENVELOPE = """\
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:wd="urn:com.workday/bsvc">
  <soapenv:Header>
    <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
      <wsse:UsernameToken>
        <wsse:Username>{username}</wsse:Username>
        <wsse:Password>{password}</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </soapenv:Header>
  <soapenv:Body>
    <wd:Get_Payroll_Results_Request wd:version="v44.0">
      <wd:Request_References>
        <wd:Pay_Group_Reference>
          <wd:ID wd:type="Pay_Group_ID">{pay_group}</wd:ID>
        </wd:Pay_Group_Reference>
      </wd:Request_References>
    </wd:Get_Payroll_Results_Request>
  </soapenv:Body>
</soapenv:Envelope>
"""


async def fetch_workday_payroll_results(
    *,
    pay_group: str | None = None,
) -> list[WorkdayPayrollResult]:
    """Fetch finalized Workday payroll results for the most recent pay period.

    MOCK_MODE: loads ``tests/fixtures/workday_payroll_results.json``.
    Live: POSTs the SOAP envelope above and parses the response.

    The live path is stubbed for the demo — flip MOCK_MODE off only after
    plugging in a real WSDL parse (xmltodict-based) and verifying the field
    names against your tenant's actual response.
    """
    settings = get_settings()
    resolved_group = pay_group or settings.workday_pay_group

    if settings.mock_mode:
        log.info("workday.mock_mode", fixture=WORKDAY_FIXTURE)
        payload = load_fixture(WORKDAY_FIXTURE)
        records = _unwrap_workday(payload)
    else:
        log.info("workday.fetch", tenant=settings.workday_tenant_url, pay_group=resolved_group)
        records = await _fetch_workday_live(settings, resolved_group)

    return [WorkdayPayrollResult.model_validate(r) for r in records]


async def fetch_peci_fi_lines(
    client: httpx.AsyncClient,
    *,
    limit: int = 500,
) -> list[FIJournalEntry]:
    """Fetch the FI journal lines PECI posted for the demo pay period.

    These are the same shape as the FI lines from ``fetch_journal_entries``;
    the GL filter is different so we don't pull the regular non-payroll
    accruals here.
    """
    settings = get_settings()
    if settings.mock_mode:
        log.info("peci_fi.mock_mode", fixture=FI_PAYROLL_FIXTURE)
        payload = load_fixture(FI_PAYROLL_FIXTURE)
    else:
        # OR-of-ranges on GLAccount: payroll expense range plus the two
        # liability accruals. SAP's OData $filter doesn't support a true
        # IN clause, so we use grouped ranges.
        filter_clause = (
            f"CompanyCode eq '{DEFAULT_COMPANY_CODE}' and ("
            f"(GLAccount ge '{PAYROLL_EXPENSE_GL_FROM}' "
            f"and GLAccount le '{PAYROLL_EXPENSE_GL_TO}') "
            f"or GLAccount eq '{PAYROLL_ACCRUAL_GLS[0]}' "
            f"or GLAccount eq '{PAYROLL_ACCRUAL_GLS[1]}'"
            f")"
        )
        log.info("peci_fi.fetch", path=FI_PATH, limit=limit)
        response = await get_with_retry(
            client,
            FI_PATH,
            params={
                "$format": "json",
                "$top": str(limit),
                "$filter": filter_clause,
            },
        )
        payload = response.json()
    records = unwrap_odata(payload)
    return [FIJournalEntry.model_validate(r) for r in records]


def _unwrap_workday(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull the Pay_Result array out of the Get_Payroll_Results envelope.

    Tolerant of both the SOAP envelope shape (``Envelope.Body.Get_...``) and
    the flat fixture shape, since live xmltodict parsing produces the former
    and the fixture writes the latter for readability.
    """
    if "Get_Payroll_Results_Response" in payload:
        body = payload["Get_Payroll_Results_Response"]
    elif "Envelope" in payload:
        body = payload["Envelope"]["Body"]["Get_Payroll_Results_Response"]
    else:
        raise ValueError(
            "Workday payload missing Get_Payroll_Results_Response root; "
            f"top-level keys: {sorted(payload)}"
        )
    response_data = body.get("Response_Data", {})
    results = response_data.get("Pay_Result", [])
    if isinstance(results, dict):
        # xmltodict collapses single-element arrays to a dict — re-wrap.
        return [results]
    return results


async def _fetch_workday_live(settings: Any, pay_group: str) -> list[dict[str, Any]]:
    """POST the SOAP envelope and return Pay_Result dicts. Demo stub.

    For a real deployment, swap the xmltodict-free fallback below for a
    proper xmltodict.parse() of response.text — this code path is not
    exercised in the demo (MOCK_MODE stays true).
    """
    if not settings.workday_tenant_url:
        raise RuntimeError(
            "MOCK_MODE is false but WORKDAY_TENANT_URL is unset. "
            "Either re-enable MOCK_MODE or configure Workday credentials."
        )
    envelope = _SOAP_ENVELOPE.format(
        username=settings.workday_isu_username,
        password=settings.workday_isu_password.get_secret_value(),
        pay_group=pay_group,
    )
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
        response = await client.post(
            settings.workday_tenant_url,
            content=envelope,
            headers={"Content-Type": "text/xml; charset=utf-8"},
        )
        response.raise_for_status()
    # Demo stub: in a real implementation, parse response.text with xmltodict.
    raise NotImplementedError(
        "Live Workday SOAP parsing not implemented for the demo — keep MOCK_MODE=true."
    )
