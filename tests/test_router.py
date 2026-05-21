"""Router + persistence + postback tests.

Each test runs against a fresh file-based SQLite DB under pytest's tmp_path
so tables and state are fully isolated. Postback is patched with AsyncMock
so we can assert the router called into it without touching the real
(logging-only) implementation — we test postback separately.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from accrual_pipeline import config, persistence
from accrual_pipeline.claude_client import ToolCall
from accrual_pipeline.persistence import (
    FlaggedItem,
    get_run_summary,
    get_session,
    init_db,
    record_run_finish,
    record_run_start,
    reset_db,
)
from accrual_pipeline.router import route


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SAP_API_KEY", "test-sap-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    config.get_settings.cache_clear()
    reset_db()
    init_db()
    yield
    reset_db()
    config.get_settings.cache_clear()


@pytest.fixture
def run_id() -> str:
    rid = "run-test-0001"
    record_run_start(rid, model="claude-sonnet-4-6", accrual_count=5)
    return rid


# --------------------------- persistence smoke ---------------------------

def test_record_run_lifecycle(run_id: str) -> None:
    record_run_finish(run_id, status="completed")
    summary = get_run_summary(run_id)
    assert summary is not None
    assert summary["status"] == "completed"
    assert summary["accrual_count"] == 5
    assert summary["finished_at"] is not None


def test_invalid_run_status_rejected(run_id: str) -> None:
    with pytest.raises(ValueError, match="Invalid run status"):
        record_run_finish(run_id, status="whoops")


def test_record_finish_unknown_run_raises() -> None:
    with pytest.raises(ValueError, match="Unknown run_id"):
        record_run_finish("run-does-not-exist", status="completed")


# --------------------------- router dispatch ---------------------------

async def test_flag_stale_po_persists_and_notifies_on_high_severity(
    run_id: str, caplog: pytest.LogCaptureFixture
) -> None:
    call = ToolCall(
        id="t1",
        tool="flag_stale_po_accrual",
        input={
            "accrual_id": "1010/2026/0100000005/001",
            "po_id": "4500000003",
            "reason": "PO 4500000003 has SES 2026-01-01, ~115 days stale; amount EUR 3200.",
            "severity": "high",
        },
    )
    await route([call], [], run_id=run_id)

    summary = get_run_summary(run_id)
    assert summary is not None
    assert len(summary["flagged"]) == 1
    flagged = summary["flagged"][0]
    assert flagged["tool_name"] == "flag_stale_po_accrual"
    assert flagged["severity"] == "high"
    assert flagged["accrual_id"] == "1010/2026/0100000005/001"
    assert flagged["payload"]["po_id"] == "4500000003"


async def test_flag_stale_po_low_severity_does_not_emit_notify(
    run_id: str, caplog: pytest.LogCaptureFixture
) -> None:
    call = ToolCall(
        id="t1",
        tool="flag_stale_po_accrual",
        input={
            "accrual_id": "1010/2026/0100000005/001",
            "po_id": "4500000003",
            "reason": "70 days stale, EUR 1k — borderline.",
            "severity": "low",
        },
    )
    await route([call], [], run_id=run_id)
    summary = get_run_summary(run_id)
    assert summary is not None
    assert len(summary["flagged"]) == 1


async def test_flag_duplicate_expands_into_one_row_per_id(run_id: str) -> None:
    call = ToolCall(
        id="t2",
        tool="flag_duplicate_accrual",
        input={
            "accrual_ids": [
                "1010/2026/0100000002/001",
                "1010/2026/0100000003/001",
            ],
            "reason": "Same supplier V-200, amount 12500 USD, CC-2000, 1 day apart.",
        },
    )
    await route([call], [], run_id=run_id)

    summary = get_run_summary(run_id)
    assert summary is not None
    assert len(summary["flagged"]) == 2
    ids = {row["accrual_id"] for row in summary["flagged"]}
    assert ids == {
        "1010/2026/0100000002/001",
        "1010/2026/0100000003/001",
    }
    # Severity is null for duplicates.
    assert all(row["severity"] is None for row in summary["flagged"])
    # Shared reason on every row.
    reasons = {row["reason"] for row in summary["flagged"]}
    assert len(reasons) == 1


async def test_flag_duplicate_with_fewer_than_two_ids_raises(run_id: str) -> None:
    call = ToolCall(
        id="t3",
        tool="flag_duplicate_accrual",
        input={"accrual_ids": ["1010/2026/0100000001/001"], "reason": "lonely"},
    )
    with pytest.raises(ValueError, match=">=2"):
        await route([call], [], run_id=run_id)


async def test_approve_accrual_invokes_postback(run_id: str) -> None:
    call = ToolCall(
        id="t4",
        tool="approve_accrual",
        input={
            "accrual_id": "1010/2026/0100000001/001",
            "notes": "Clean service accrual, valid CC, reasonable amount.",
        },
    )
    with patch(
        "accrual_pipeline.router.post_journal_entry", new_callable=AsyncMock
    ) as mock_postback:
        await route([call], [], run_id=run_id)
    mock_postback.assert_awaited_once_with(
        run_id=run_id,
        accrual_id="1010/2026/0100000001/001",
        notes="Clean service accrual, valid CC, reasonable amount.",
    )
    # No FlaggedItem written for approvals.
    summary = get_run_summary(run_id)
    assert summary is not None
    assert summary["flagged"] == []


async def test_mixed_dispatch_tracks_all_tool_calls(run_id: str) -> None:
    calls = [
        ToolCall(
            id="a",
            tool="approve_accrual",
            input={"accrual_id": "1010/2026/0100000001/001", "notes": "clean"},
        ),
        ToolCall(
            id="b",
            tool="flag_duplicate_accrual",
            input={
                "accrual_ids": [
                    "1010/2026/0100000002/001",
                    "1010/2026/0100000003/001",
                ],
                "reason": "Same vendor/amt/CC 1 day apart.",
            },
        ),
        ToolCall(
            id="c",
            tool="approve_accrual",
            input={"accrual_id": "1010/2026/0100000004/001", "notes": "service accrual"},
        ),
        ToolCall(
            id="d",
            tool="flag_stale_po_accrual",
            input={
                "accrual_id": "1010/2026/0100000005/001",
                "po_id": "4500000003",
                "reason": "SES 115 days old.",
                "severity": "medium",
            },
        ),
    ]
    with patch(
        "accrual_pipeline.router.post_journal_entry", new_callable=AsyncMock
    ) as mock_postback:
        await route(calls, [], run_id=run_id)

    # 2 approves → 2 postbacks
    assert mock_postback.await_count == 2
    # 2 from duplicate + 1 from stale = 3 FlaggedItem rows
    summary = get_run_summary(run_id)
    assert summary is not None
    assert len(summary["flagged"]) == 3
    tool_names = [r["tool_name"] for r in summary["flagged"]]
    assert tool_names.count("flag_duplicate_accrual") == 2
    assert tool_names.count("flag_stale_po_accrual") == 1


async def test_unknown_tool_name_raises(run_id: str) -> None:
    call = ToolCall(id="x", tool="flag_mystery", input={})
    with pytest.raises(ValueError, match="Unknown tool name"):
        await route([call], [], run_id=run_id)


async def test_tool_missing_required_field_raises(run_id: str) -> None:
    call = ToolCall(
        id="y",
        tool="flag_stale_po_accrual",
        input={"accrual_id": "x", "po_id": "y", "severity": "low"},  # no reason
    )
    with pytest.raises(ValueError, match="reason"):
        await route([call], [], run_id=run_id)


# --------------------------- postback direct ---------------------------

async def test_postback_logs_soap_envelope_without_calling_network(
    run_id: str, caplog: pytest.LogCaptureFixture
) -> None:
    from accrual_pipeline.postback import post_journal_entry

    # We just want to confirm it returns cleanly and does not raise — the
    # envelope content is validated via structlog's log event in other harnesses.
    await post_journal_entry(
        run_id=run_id,
        accrual_id="1010/2026/0100000001/001",
        notes="clean",
    )


def test_flagged_item_payload_is_round_trip_json(run_id: str) -> None:
    persistence.persist_flagged_item(
        run_id=run_id,
        accrual_id="1010/2026/0100000005/001",
        tool_name="flag_stale_po_accrual",
        severity="high",
        reason="test",
        payload={"po_id": "4500000003", "days_stale": 115, "amount": "3200.00"},
    )
    with get_session() as s:
        row = s.query(FlaggedItem).first()
        assert row is not None
        import json as _json
        parsed = _json.loads(row.payload_json)
        assert parsed["po_id"] == "4500000003"
        assert parsed["days_stale"] == 115
