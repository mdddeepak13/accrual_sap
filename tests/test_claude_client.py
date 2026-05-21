"""Claude client tests.

Mocks the AsyncAnthropic client entirely — we're testing the parser that
converts Claude's content blocks into ToolCall objects, not the model itself.
Real SDK calls happen in Phase 5 end-to-end runs.
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from accrual_pipeline import config
from accrual_pipeline.claude_client import (
    TOOL_SCHEMAS,
    analyze_accruals,
    load_prompt_templates,
)
from accrual_pipeline.models import AccrualObject


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAP_API_KEY", "test-sap-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


def _mock_client(blocks: list[SimpleNamespace], stop_reason: str = "end_turn") -> MagicMock:
    client = MagicMock()
    client.messages.create = AsyncMock(
        return_value=SimpleNamespace(content=blocks, stop_reason=stop_reason)
    )
    return client


def _make_accrual(doc: str, **overrides: object) -> AccrualObject:
    base: dict[str, object] = {
        "accrual_id": f"1010/2026/{doc}/001",
        "company_code": "1010",
        "fiscal_year": "2026",
        "accounting_document": doc,
        "accounting_document_item": "001",
        "is_reversal": False,
        "is_reversed": False,
        "gl_account_number": "22000000",
        "amount_usd": Decimal("5000.00"),
    }
    base.update(overrides)
    return AccrualObject.model_validate(base)


# -------------------------------- tool schemas --------------------------------

def test_tool_schemas_declare_three_tools() -> None:
    names = {t["name"] for t in TOOL_SCHEMAS}
    assert names == {"flag_stale_po_accrual", "flag_duplicate_accrual", "approve_accrual"}


def test_flag_stale_po_has_required_severity_enum() -> None:
    schema = next(t for t in TOOL_SCHEMAS if t["name"] == "flag_stale_po_accrual")
    props = schema["input_schema"]["properties"]
    assert props["severity"]["enum"] == ["low", "medium", "high"]
    for required in ("accrual_id", "po_id", "reason", "severity"):
        assert required in schema["input_schema"]["required"]


def test_flag_duplicate_requires_at_least_two_ids() -> None:
    schema = next(t for t in TOOL_SCHEMAS if t["name"] == "flag_duplicate_accrual")
    items = schema["input_schema"]["properties"]["accrual_ids"]
    assert items["minItems"] == 2
    assert items["items"]["type"] == "string"


def test_approve_requires_notes_for_audit_trail() -> None:
    schema = next(t for t in TOOL_SCHEMAS if t["name"] == "approve_accrual")
    required = schema["input_schema"]["required"]
    assert "notes" in required
    assert "accrual_id" in required


# -------------------------------- prompt template --------------------------------

def test_prompt_template_splits_on_system_user_marker() -> None:
    system_tmpl, user_tmpl = load_prompt_templates()
    rendered_system = system_tmpl.render(
        run_id="r-1", today="2026-04-24", stale_days_threshold=60,
        duplicate_days_window=7, accruals=[]
    )
    rendered_user = user_tmpl.render(
        run_id="r-1", today="2026-04-24", stale_days_threshold=60,
        duplicate_days_window=7, accruals=[]
    )
    assert "accounting controls assistant" in rendered_system
    assert "flag_stale_po_accrual" in rendered_system
    assert "60 days" in rendered_system
    assert "Run ID: r-1" in rendered_user
    assert "As of: 2026-04-24" in rendered_user


def test_user_prompt_embeds_accrual_json(env: None) -> None:
    _, user_tmpl = load_prompt_templates()
    a = _make_accrual("0100000001", vendor_number="V-100")
    rendered = user_tmpl.render(
        run_id="r-1", today="2026-04-24", stale_days_threshold=60,
        duplicate_days_window=7, accruals=[a]
    )
    assert "1010/2026/0100000001/001" in rendered
    assert "V-100" in rendered


# -------------------------------- analyze_accruals parsing --------------------------------

async def test_parses_single_tool_use_block(env: None) -> None:
    blocks = [
        SimpleNamespace(type="text", text="Reviewing..."),
        SimpleNamespace(
            type="tool_use",
            id="toolu_01",
            name="approve_accrual",
            input={"accrual_id": "1010/2026/0100000001/001", "notes": "clean"},
        ),
    ]
    client = _mock_client(blocks)
    calls = await analyze_accruals(
        client, [_make_accrual("0100000001")], run_id="r-1"
    )
    assert len(calls) == 1
    assert calls[0].id == "toolu_01"
    assert calls[0].tool == "approve_accrual"
    assert calls[0].input["accrual_id"] == "1010/2026/0100000001/001"


async def test_parses_multiple_tool_use_blocks_and_preserves_order(env: None) -> None:
    blocks = [
        SimpleNamespace(
            type="tool_use",
            id="t1",
            name="flag_duplicate_accrual",
            input={
                "accrual_ids": [
                    "1010/2026/0100000002/001",
                    "1010/2026/0100000003/001",
                ],
                "reason": "Same supplier, amount, cost center within 1 day.",
            },
        ),
        SimpleNamespace(
            type="tool_use",
            id="t2",
            name="flag_stale_po_accrual",
            input={
                "accrual_id": "1010/2026/0100000005/001",
                "po_id": "4500000003",
                "reason": "SES 2026-01-01 → 113 days stale, PO not fully invoiced.",
                "severity": "medium",
            },
        ),
        SimpleNamespace(
            type="tool_use",
            id="t3",
            name="approve_accrual",
            input={"accrual_id": "1010/2026/0100000001/001", "notes": "recent GR"},
        ),
    ]
    client = _mock_client(blocks)
    calls = await analyze_accruals(
        client,
        [_make_accrual(d) for d in ("0100000001", "0100000002", "0100000003", "0100000005")],
        run_id="r-1",
    )
    assert [c.tool for c in calls] == [
        "flag_duplicate_accrual",
        "flag_stale_po_accrual",
        "approve_accrual",
    ]
    assert calls[1].input["severity"] == "medium"


async def test_raises_when_no_tool_use_blocks(env: None) -> None:
    blocks = [SimpleNamespace(type="text", text="I can't decide.")]
    client = _mock_client(blocks, stop_reason="end_turn")
    with pytest.raises(ValueError, match="no tool_use blocks"):
        await analyze_accruals(client, [_make_accrual("0100000001")], run_id="r-1")


async def test_invokes_sdk_with_expected_kwargs(env: None) -> None:
    blocks = [
        SimpleNamespace(
            type="tool_use",
            id="t1",
            name="approve_accrual",
            input={"accrual_id": "1010/2026/0100000001/001"},
        ),
    ]
    client = _mock_client(blocks)
    await analyze_accruals(
        client,
        [_make_accrual("0100000001")],
        run_id="r-1",
        stale_days_threshold=90,
    )
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["model"].startswith("claude-")
    assert kwargs["max_tokens"] > 0
    assert "flag_stale_po_accrual" in kwargs["system"]
    assert "90 days" in kwargs["system"]  # threshold flowed through
    assert kwargs["tools"] == TOOL_SCHEMAS
    assert kwargs["messages"][0]["role"] == "user"
