"""End-to-end test: real SDK client runs the main agent, which should
activate the `tax_kb_researcher` sub-agent, which in turn calls
`mcp__tax_agent_global_tax_kb__search_tax_knowledge` to answer a UK VAT law
question.

This test exercises the full chain:
    Main Agent  →  tax_kb_researcher sub-agent  →  MCP search_tax_knowledge
        →  Markdown store  →  cited answer back to user

Skipped when ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN is not set, or when
claude-agent-sdk is not installed.
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
async def test_main_agent_uses_tax_kb_subagent_and_mcp_tool():
    """Ask about UK VAT reverse charge, verify the main agent
    delegates to tax_kb_researcher which calls search_tax_knowledge."""
    registry = JurisdictionRegistry()
    registry.register(UKJurisdictionAdapter())
    engine = TaxAgentEngine(registry=registry)

    # 收集所有 ToolUseBlock / ToolResultBlock
    from claude_agent_sdk import ToolUseBlock, ToolResultBlock, TextBlock, AssistantMessage

    captured_tools: list[dict] = []  # {name, id, input}
    captured_results: list[dict] = []  # {tool_use_id, content}
    captured_text: list[str] = []

    session_id = "e2e-kb-test-1"
    user_q = (
        "Please use the tax_kb_researcher sub-agent to look up: "
        "How does the UK VAT reverse charge work, and which boxes does "
        "it affect? Cite the source."
    )

    async for chunk in engine.chat(session_id, user_q, jurisdiction="uk"):
        # Engine yields raw text or __agui__ dicts
        if isinstance(chunk, str):
            captured_text.append(chunk)
            continue
        if isinstance(chunk, dict) and chunk.get("__agui__") == "tool_start":
            captured_tools.append(
                {"name": chunk.get("tool_name"), "id": chunk.get("tool_call_id")}
            )
        elif isinstance(chunk, dict) and chunk.get("__agui__") == "tool_result":
            captured_results.append(
                {
                    "tool_use_id": chunk.get("tool_call_id"),
                    "content": chunk.get("content"),
                }
            )

    # ── Assertions ─────────────────────────────────────────────
    tool_names = [t["name"] for t in captured_tools]
    print("\n=== Captured tool calls ===")
    for t in captured_tools:
        print(f"  - {t['name']} (id={t['id']})")
    print("=== Captured results ===")
    for r in captured_results:
        c = (r["content"] or "")[:200]
        print(f"  - {r['tool_use_id']}: {c}")
    print("=== Text response (first 800 chars) ===")
    print("".join(captured_text)[:800])

    # The sub-agent may or may not show up as a "tool call" depending on
    # SDK version (Task tool calls show the sub-agent as a Task/Agent
    # invocation).  The CRITICAL assertion is that
    # `mcp__tax_agent_global_tax_kb__search_tax_knowledge` was called.
    assert any(
        "search_tax_knowledge" in (n or "")
        for n in tool_names
    ), f"search_tax_knowledge was never called. Tools seen: {tool_names}"

    # And that the response contains "reverse charge" — proof the chain
    # produced a real answer (not just the agent refusing or erroring out).
    full_text = "".join(captured_text).lower()
    assert "reverse charge" in full_text, (
        f"Expected 'reverse charge' in agent response, got:\n"
        f"{''.join(captured_text)[:1500]}"
    )
