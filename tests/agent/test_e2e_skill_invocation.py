"""End-to-end test: the real SDK agent loads and invokes a plugin Skill.

Proves the Skill repository wiring works against a live CLI subprocess:
the `uk` local plugin is discovered (despite `setting_sources=[]`), the
`uk:vat` skill is enabled via `skills="all"`, and the main agent can invoke
the bare `Skill` tool to load the on-demand VAT procedure.

Skipped when ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN is not set, or when
claude-agent-sdk is not installed (same guard as test_e2e_kb_subagent.py).
"""
from __future__ import annotations

import os

import pytest

from backend import JurisdictionRegistry
from backend.agent.engine import TaxAgentEngine, SDK_AVAILABLE
from backend.jurisdictions.uk import UKJurisdictionAdapter


def _has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


pytestmark = pytest.mark.skipif(
    not (SDK_AVAILABLE and _has_api_key()),
    reason="End-to-end test requires claude-agent-sdk and an API key",
)


@pytest.mark.asyncio
async def test_main_agent_invokes_uk_vat_skill():
    """Ask the agent to use the uk:vat skill to compute a VAT return,
    verify it invokes the `Skill` tool (plugin skill loaded on demand)."""
    registry = JurisdictionRegistry()
    registry.register(UKJurisdictionAdapter())
    engine = TaxAgentEngine(registry=registry)

    captured_tools: list[dict] = []   # {name, id}
    captured_args: list[str] = []     # tool_args deltas
    captured_text: list[str] = []

    session_id = "e2e-skill-invocation-1"
    user_q = (
        "请使用 uk:vat 技能加载 UK VAT 的申报流程,然后用 calculate_vat_return "
        "计算一笔示例申报:VRN 123456789、期间 26A1、销项 VAT 2500.00、"
        "进项 VAT 1200.00。只需计算并向我解释 9-box 结果,先不要提交。"
    )

    async for chunk in engine.chat(session_id, user_q, jurisdiction="uk"):
        if isinstance(chunk, str):
            captured_text.append(chunk)
            continue
        if isinstance(chunk, dict):
            if chunk.get("__agui__") == "tool_start":
                captured_tools.append(
                    {"name": chunk.get("tool_name"), "id": chunk.get("tool_call_id")}
                )
            elif chunk.get("__agui__") == "tool_args":
                captured_args.append(chunk.get("delta") or "")

    tool_names = [t["name"] for t in captured_tools]
    print("\n=== Captured tool calls ===")
    for t in captured_tools:
        print(f"  - {t['name']} (id={t['id']})")
    print("=== Tool args (first 300 each) ===")
    for a in captured_args:
        print(f"  - {a[:300]}")
    print("=== Text response (first 800 chars) ===")
    print("".join(captured_text)[:800])

    # CRITICAL: the agent invoked the `Skill` tool — proof a plugin skill was
    # loaded on demand. (skills="all" adds the bare `Skill` tool; the model
    # invokes the namespaced `uk:vat`.)
    assert "Skill" in tool_names, (
        f"`Skill` tool was never invoked. Tools seen: {tool_names}. "
        f"If empty, the plugin likely failed to load (check the engine "
        f"'Skill plugins not fully loaded' warning)."
    )

    # The skill should reference uk:vat in the invocation args.
    assert any("vat" in (a or "").lower() for a in captured_args), (
        f"Skill invocation args did not reference vat: {captured_args}"
    )
