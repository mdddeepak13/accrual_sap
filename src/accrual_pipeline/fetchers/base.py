"""Shared httpx.AsyncClient factory and helpers for SAP sandbox calls.

All three fetchers (FI, MM, CO) share auth, transport, and the OData v2
unwrap shape, so the plumbing lives here.

Retry policy: exponential backoff on 5xx responses and transient transport
errors. 4xx raises immediately — retrying won't change an auth or input
error. Retries happen at the GET helper layer so the fetchers stay simple.

MOCK_MODE fixture loading also lives here so fetcher modules only own
the per-resource shape (endpoint path, filter params, target model).
"""
from __future__ import annotations

import asyncio
import gzip
import json
from pathlib import Path
from typing import Any

import httpx
import structlog

from accrual_pipeline.config import Settings, get_settings

log = structlog.get_logger(__name__)

# `src/accrual_pipeline/fetchers/base.py` → repo root → tests/fixtures.
FIXTURES_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures"


class SAPClientError(Exception):
    """Raised when a SAP sandbox call fails after exhausting retries."""


def create_sap_client(settings: Settings | None = None) -> httpx.AsyncClient:
    """Return an httpx.AsyncClient pre-configured for the SAP Business Accelerator Hub.

    Used by FI/MM/CO fetchers (accruals, purchase orders, cost centers).
    Caller owns the `async with` lifetime.
    """
    resolved = settings or get_settings()
    return httpx.AsyncClient(
        base_url=resolved.sap_sandbox_base_url,
        headers={
            "APIKey": resolved.sap_api_key.get_secret_value(),
            "Accept": "application/json",
            # SAP sandbox always returns gzip. httpx decompresses automatically
            # when Accept-Encoding is declared — without it the raw bytes land
            # in response.text and json() crashes.
            "Accept-Encoding": "gzip, deflate",
        },
        timeout=httpx.Timeout(30.0, connect=10.0),
    )


def create_btp_client(settings: Settings | None = None) -> httpx.AsyncClient:
    """Return an httpx.AsyncClient pre-configured for the SAP BTP CAP service.

    Used by inventory/batch/writedown fetchers (pharma distressed inventory).
    The BTP CAP service uses the same SAP API key for auth.
    Caller owns the `async with` lifetime.
    """
    resolved = settings or get_settings()
    return httpx.AsyncClient(
        base_url=resolved.sap_btp_base_url,
        headers={
            "APIKey": resolved.sap_api_key.get_secret_value(),
            "Accept": "application/json",
        },
        timeout=httpx.Timeout(30.0, connect=10.0),
    )


def _build_odata_url(path: str, params: dict[str, Any] | None) -> str:
    """Construct an OData URL with `%20`-encoded spaces.

    SAP CAP's OData parser rejects `+` as a space encoding (it requires `%20`).
    httpx's default param encoder uses `quote_plus` which produces `+`, so we
    pre-build the URL ourselves using `quote()`.
    """
    if not params:
        return path
    from urllib.parse import quote
    qs = "&".join(
        f"{quote(str(k), safe='$')}={quote(str(v), safe='')}"
        for k, v in params.items()
        if v is not None
    )
    return f"{path}?{qs}" if qs else path


def _decode_response(response: httpx.Response) -> dict[str, Any]:
    """Decode an httpx response to a JSON dict, handling gzip manually.

    The SAP Business Accelerator Hub always returns Content-Encoding: gzip.
    httpx decompresses automatically when it sends Accept-Encoding, but on
    some serverless runtimes the header gets stripped. This function falls
    back to manual gzip decompression so the response always parses cleanly.
    """
    content = response.content
    # Try manual gzip decompression first if the content looks compressed
    # (magic bytes 1f 8b) or the header says so.
    encoding = response.headers.get("content-encoding", "").lower()
    if encoding == "gzip" or (len(content) >= 2 and content[:2] == b"\x1f\x8b"):
        try:
            content = gzip.decompress(content)
        except Exception:
            pass  # already decompressed by httpx — use as-is
    return json.loads(content.decode("utf-8"))


async def get_with_retry(
    client: httpx.AsyncClient,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    max_attempts: int = 3,
) -> httpx.Response:
    """GET with exponential backoff on 5xx and transport errors.

    Returns the successful response. Raises:
      - httpx.HTTPStatusError on a 4xx (no retry).
      - SAPClientError if all retry attempts fail.
    """
    url = _build_odata_url(path, params)
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.get(url)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_exc = exc
            log.warning(
                "sap.transport_error",
                path=path, attempt=attempt, error=type(exc).__name__,
            )
        else:
            if response.status_code < 500:
                response.raise_for_status()  # raises on 4xx
                return response
            log.warning(
                "sap.server_error",
                path=path, attempt=attempt, status=response.status_code,
            )
            last_exc = httpx.HTTPStatusError(
                f"HTTP {response.status_code} on {path}",
                request=response.request,
                response=response,
            )
        if attempt < max_attempts:
            await asyncio.sleep(2 ** (attempt - 1))
    raise SAPClientError(
        f"SAP sandbox call to {path} failed after {max_attempts} attempts"
    ) from last_exc


def load_fixture(name: str) -> dict[str, Any]:
    """Load a JSON fixture from tests/fixtures/ by file name."""
    path = FIXTURES_DIR / name
    with path.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)
    return data


def unwrap_odata(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract the record array from an OData v2 or v4 JSON response.

    OData v2: ``{"d": {"results": [...]}}``
    OData v4: ``{"value": [...]}``
    """
    d = payload.get("d")
    if isinstance(d, dict):
        results = d.get("results")
        if isinstance(results, list):
            return results
    value = payload.get("value")
    if isinstance(value, list):
        return value
    raise ValueError(
        f"Unrecognized OData payload shape; top-level keys: {sorted(payload)}"
    )
