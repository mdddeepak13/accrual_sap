"""FI Journal Entries fetcher.

Source: Operational Journal Entry Item (A2X) API on api.sap.com.
Filters to accrued-expense GL accounts so the prompt stays focused.

Confirm the endpoint path at `api.sap.com` before the first live call —
SAP occasionally renames sandbox routes.
"""
from __future__ import annotations

import httpx
import structlog

from accrual_pipeline.config import get_settings
from accrual_pipeline.fetchers.base import (
    get_with_retry,
    load_fixture,
    unwrap_odata,
)
from accrual_pipeline.models import FIJournalEntry

log = structlog.get_logger(__name__)

FI_PATH = (
    "/s4hanacloud/sap/opu/odata/sap/API_OPLACCTGDOCITEMCUBE_SRV"
    "/A_OperationalAcctgDocItemCube"
)
FI_FIXTURE = "fi_journal_entries.json"
# Company code we target on the sandbox tenant — the "Operational" cube
# rejects unfiltered queries with DBSQL_SQL_INTERNAL_DB_ERROR, so we always
# scope by company code. "1010" is the BestRun DE demo tenant.
DEFAULT_COMPANY_CODE = "1010"
# Accrued-expense GL account range. SAP demo data uses 22000000-series for
# various accrual/liability accounts.
ACCRUAL_GL_FROM = "22000000"
ACCRUAL_GL_TO = "22999999"


async def fetch_journal_entries(
    client: httpx.AsyncClient,
    *,
    limit: int = 100,
) -> list[FIJournalEntry]:
    """Fetch accrual-bearing journal entry items.

    In MOCK_MODE returns fixtures; otherwise GETs the sandbox endpoint.
    """
    settings = get_settings()
    if settings.mock_mode:
        log.info("fi.mock_mode", fixture=FI_FIXTURE)
        payload = load_fixture(FI_FIXTURE)
    else:
        log.info("fi.fetch", path=FI_PATH, limit=limit)
        response = await get_with_retry(
            client,
            FI_PATH,
            params={
                "$format": "json",
                "$top": str(limit),
                # Cube requires a CompanyCode filter; the GL range narrows to
                # accrual-style liability accounts.
                "$filter": (
                    f"CompanyCode eq '{DEFAULT_COMPANY_CODE}' "
                    f"and GLAccount ge '{ACCRUAL_GL_FROM}' "
                    f"and GLAccount le '{ACCRUAL_GL_TO}'"
                ),
            },
        )
        payload = response.json()
    records = unwrap_odata(payload)
    return [FIJournalEntry.model_validate(r) for r in records]
