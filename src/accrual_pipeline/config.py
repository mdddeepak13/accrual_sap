"""Runtime configuration loaded from environment / .env.

Single source of truth for pipeline settings. Secrets are wrapped in
SecretStr so they never leak into repr(), structlog output, or tracebacks.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# /tmp is the only writable path on serverless functions and works fine on
# local dev too. Tests + production HANA override via DATABASE_URL.
_DEFAULT_DB_URL = "sqlite:////tmp/accrual.db"


class Settings(BaseSettings):
    """Pipeline settings sourced from env vars and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Required secrets ---
    sap_api_key: SecretStr = Field(
        ..., description="SAP Business Accelerator Hub API key"
    )
    anthropic_api_key: SecretStr = Field(
        ..., description="Anthropic SDK API key"
    )

    # --- Claude settings ---
    claude_model: str = Field(
        default="claude-sonnet-4-6",
        description="Claude model ID — sonnet for dev, opus for prod",
    )
    claude_max_tokens: int = Field(default=4096, ge=256, le=32768)

    # --- Pipeline behavior ---
    mock_mode: bool = Field(
        default=True,
        description="When true, fetchers return fixtures instead of calling sandbox",
    )
    sap_sandbox_base_url: str = Field(default="https://sandbox.api.sap.com")

    # --- Workday Global Payroll Cloud ---
    # In MOCK_MODE the payroll fetcher reads tests/fixtures/ and never touches
    # these. Live mode posts a SOAP envelope against Workday's
    # Payroll/$VERSION endpoint with WS-Security headers built from the ISU
    # credentials below. Leaving them blank in MOCK_MODE is fine.
    workday_tenant_url: str = Field(
        default="",
        description="Workday tenant SOAP endpoint, e.g. https://wd2-impl-services1.workday.com/ccx/service/<tenant>/Payroll/v44.0",
    )
    workday_isu_username: str = Field(default="")
    workday_isu_password: SecretStr = SecretStr("")
    workday_pay_group: str = Field(
        default="BIWEEKLY-US-CORP",
        description="Pay group ID to pull results for (matches Workday Pay_Group_Reference.ID)",
    )

    # --- Persistence ---
    database_url: str = Field(default=_DEFAULT_DB_URL)

    # --- Observability ---
    log_level: str = Field(default="INFO")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance. Re-reads env on process restart only."""
    return Settings()
