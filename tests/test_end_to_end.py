"""End-to-end pipeline tests with MOCK_MODE=true.

Two flavors:
  1. Direct pipeline call with a mocked Anthropic client — exercises
     fetchers → normalize → claude_client → router → persistence.
  2. HTTP endpoint smoke tests — POST /runs returns 202, GET /runs/{id}
     returns the summary the pipeline wrote.

SAP data comes from fixtures (MOCK_MODE=true). Claude is mocked with
SimpleNamespace tool_use blocks so tests run offline and deterministically.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from accrual_pipeline import config, persistence
from accrual_pipeline.main import app
from accrual_pipeline.pipeline import run_pipeline


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SAP_API_KEY", "test-sap-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    config.get_settings.cache_clear()
    persistence.reset_db()
    persistence.init_db()
    yield
    persistence.reset_db()
    config.get_settings.cache_clear()


def _mock_claude_client() -> MagicMock:
    """Build a Claude-like client that returns realistic tool calls for fixtures.

    Two prompts go through this client per run:
      1. Accrual prompt — covers the 5 FI fixture accruals
      2. Payroll prompt — covers the 40 Workday reconciliations (20 workers × 2 bi-weekly periods)

    The mock dispatches by sniffing the system prompt; that's coarser than
    a real Claude call but stable across prompt edits.
    """
    accrual_blocks = [
        SimpleNamespace(
            type="tool_use", id="t1", name="approve_accrual",
            input={
                "accrual_id": "1010/2026/0100000001/001",
                "notes": "PO-linked, GR 2026-04-05, supplier matches, amount reasonable.",
            },
        ),
        SimpleNamespace(
            type="tool_use", id="t2", name="flag_duplicate_accrual",
            input={
                "accrual_ids": [
                    "1010/2026/0100000002/001",
                    "1010/2026/0100000003/001",
                ],
                "reason": "Same supplier V-200, amount 12500 USD, CC-2000, posted 1 day apart.",
            },
        ),
        SimpleNamespace(
            type="tool_use", id="t3", name="approve_accrual",
            input={
                "accrual_id": "1010/2026/0100000004/001",
                "notes": "Service accrual, no PO, plausible 750 EUR in IT cost center.",
            },
        ),
        SimpleNamespace(
            type="tool_use", id="t4", name="flag_stale_po_accrual",
            input={
                "accrual_id": "1010/2026/0100000005/001",
                "po_id": "4500000003",
                "reason": "PO 4500000003 SES 2026-01-01, ~113 days stale, not fully invoiced.",
                "severity": "medium",
            },
        ),
    ]

    payroll_blocks = [
        SimpleNamespace(
            type="tool_use", id="p1", name="flag_payroll_accrual_mismatch",
            input={
                "payroll_id": "WD/BIWEEKLY-US-CORP/2026-05-17/EMP-1005",
                "worker_id": "EMP-1005",
                "mismatch_type": "wrong_cost_center",
                "severity": "medium",
                "workday_amount": "",
                "fi_amount": "",
                "reason": "Workday assigns CC-1000; P1 FI posting routed to CC-9999.",
            },
        ),
        SimpleNamespace(
            type="tool_use", id="p2", name="flag_payroll_accrual_mismatch",
            input={
                "payroll_id": "WD/BIWEEKLY-US-CORP/2026-05-17/EMP-1007",
                "worker_id": "EMP-1007",
                "mismatch_type": "wrong_gl_account",
                "severity": "medium",
                "workday_amount": "4042.99",
                "fi_amount": "0",
                "reason": "Regular earnings posted to GL 50130000 (suspense) instead of 50100000.",
            },
        ),
        SimpleNamespace(
            type="tool_use", id="p3", name="flag_payroll_accrual_mismatch",
            input={
                "payroll_id": "WD/BIWEEKLY-US-CORP/2026-05-17/EMP-1012",
                "worker_id": "EMP-1012",
                "mismatch_type": "missing_in_fi",
                "severity": "high",
                "workday_amount": "6383.65",
                "fi_amount": "0",
                "reason": "PECI never delivered EMP-1012 for P1; no FI documents found.",
            },
        ),
        SimpleNamespace(
            type="tool_use", id="p4", name="flag_payroll_accrual_mismatch",
            input={
                "payroll_id": "WD/BIWEEKLY-US-CORP/2026-05-17/EMP-1017",
                "worker_id": "EMP-1017",
                "mismatch_type": "duplicate_fi_posting",
                "severity": "high",
                "workday_amount": "5447.38",
                "fi_amount": "10894.76",
                "reason": "FI has 2 PECI documents for EMP-1017 in P1; expected exactly 1.",
            },
        ),
        SimpleNamespace(
            type="tool_use", id="p5", name="flag_payroll_accrual_mismatch",
            input={
                "payroll_id": "WD/BIWEEKLY-US-CORP/2026-05-17/EMP-1019",
                "worker_id": "EMP-1019",
                "mismatch_type": "amount_mismatch",
                "severity": "low",
                "workday_amount": "7660.38",
                "fi_amount": "7585.38",
                "reason": "Employer FICA expense $75 short at GL 50200000 in P1.",
            },
        ),
        SimpleNamespace(
            type="tool_use", id="p6", name="flag_payroll_accrual_mismatch",
            input={
                "payroll_id": "",
                "worker_id": "EMP-9999",
                "mismatch_type": "missing_in_workday",
                "severity": "medium",
                "workday_amount": "0",
                "fi_amount": "3500.00",
                "reason": "Phantom worker in FI with no Workday counterpart for the pay period.",
            },
        ),
    ]

    async def _dispatch(**kwargs: Any) -> SimpleNamespace:
        system = (kwargs.get("system") or "").lower()
        blocks = payroll_blocks if "payroll" in system else accrual_blocks
        return SimpleNamespace(content=blocks, stop_reason="end_turn")

    mock = MagicMock()
    mock.messages.create = AsyncMock(side_effect=_dispatch)
    return mock


# ------------------------ direct pipeline ------------------------

async def test_pipeline_end_to_end_produces_expected_summary() -> None:
    with patch(
        "accrual_pipeline.pipeline.post_blackline_je_batch",
        new_callable=AsyncMock,
        return_value={"sap_document": "4900000001/2026/1000"},
    ):
        await run_pipeline("run-e2e-direct", anthropic_client=_mock_claude_client())

    summary = persistence.get_run_summary("run-e2e-direct")
    assert summary is not None
    assert summary["status"] == "completed"
    # 5 FI accruals + 40 Workday payroll reconciliations (20 workers × 2 bi-weekly periods).
    assert summary["accrual_count"] == 45
    assert summary["finished_at"] is not None

    # FI: 2 flagged from duplicate + 1 from stale PO.
    # Payroll: 6 mismatch flags (5 P1 anomalies + 1 orphan).
    assert len(summary["flagged"]) == 9

    tools = [r["tool_name"] for r in summary["flagged"]]
    assert tools.count("flag_duplicate_accrual") == 2
    assert tools.count("flag_stale_po_accrual") == 1
    assert tools.count("flag_payroll_accrual_mismatch") == 6

    stale = next(r for r in summary["flagged"] if r["tool_name"] == "flag_stale_po_accrual")
    assert stale["severity"] == "medium"
    assert stale["payload"]["po_id"] == "4500000003"

    payroll_mismatch_types = {
        r["payload"]["mismatch_type"]
        for r in summary["flagged"]
        if r["tool_name"] == "flag_payroll_accrual_mismatch"
    }
    assert payroll_mismatch_types == {
        "amount_mismatch",
        "wrong_cost_center",
        "missing_in_fi",
        "wrong_gl_account",
        "duplicate_fi_posting",
        "missing_in_workday",
    }


async def test_pipeline_marks_status_failed_on_error() -> None:
    broken = MagicMock()
    broken.messages.create = AsyncMock(side_effect=RuntimeError("Claude exploded"))

    with patch(
        "accrual_pipeline.pipeline.post_blackline_je_batch",
        new_callable=AsyncMock,
        return_value=None,
    ):
        with pytest.raises(RuntimeError):
            await run_pipeline("run-e2e-fail", anthropic_client=broken)

    summary = persistence.get_run_summary("run-e2e-fail")
    assert summary is not None
    assert summary["status"] == "failed"


# ------------------------ HTTP endpoints ------------------------

def test_health_reports_mock_mode() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["mock_mode"] is True


def test_get_unknown_run_returns_404() -> None:
    client = TestClient(app)
    response = client.get("/runs/run-does-not-exist")
    assert response.status_code == 404


def test_get_known_run_returns_summary_after_pipeline_completes() -> None:
    # Run the pipeline directly first so a row exists.
    with patch(
        "accrual_pipeline.pipeline.post_blackline_je_batch",
        new_callable=AsyncMock,
        return_value={"sap_document": "4900000001/2026/1000"},
    ):
        asyncio.run(run_pipeline("run-api-test", anthropic_client=_mock_claude_client()))

    client = TestClient(app)
    response = client.get("/runs/run-api-test")
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"] == "run-api-test"
    assert body["status"] == "completed"
    # 3 FI flags + 6 payroll mismatch flags.
    assert len(body["flagged"]) == 9


def test_post_runs_returns_run_id_and_status_url() -> None:
    # Patch the Anthropic factory so the background task uses our mock.
    with patch(
        "accrual_pipeline.pipeline.create_anthropic_client",
        return_value=_mock_claude_client(),
    ), patch(
        "accrual_pipeline.pipeline.post_blackline_je_batch",
        new_callable=AsyncMock,
        return_value={"sap_document": "4900000001/2026/1000"},
    ):
        client = TestClient(app)
        response = client.post("/runs")

    # POST /runs is synchronous — returns 200 with the run summary URL.
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert body["run_id"].startswith("run-")
    assert body["status_url"] == f"/runs/{body['run_id']}"
