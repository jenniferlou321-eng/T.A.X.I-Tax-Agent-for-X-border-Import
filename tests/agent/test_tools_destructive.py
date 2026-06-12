"""Test: tools whose meta['name'] starts with submit_ get ToolAnnotations(destructiveHint=True).

Validates PR-1 C2.
"""
from __future__ import annotations

import pytest

mcp_types = pytest.importorskip("mcp").types
claude_agent_sdk = pytest.importorskip("claude_agent_sdk")

from backend.agent.tools import _make_tool_wrapper, SDK_AVAILABLE  # noqa: E402


pytestmark = pytest.mark.skipif(
    not SDK_AVAILABLE, reason="claude-agent-sdk not installed"
)


class _StubToolSet:
    """Minimal AgentToolSet-shaped object to satisfy _make_tool_wrapper."""
    country_code = "uk"
    tax_type = "vat"

    def get_tool_metadata(self):
        return []

    def get_allowlist(self):
        return []

    async def submit_vat_return(self, **kw):
        return {}

    async def get_vat_obligations(self, **kw):
        return {}


def _make_meta(name: str) -> dict:
    return {"name": name, "description": f"test {name}", "input_schema": {}}


def test_submit_tools_get_destructive_annotation():
    inst = _StubToolSet()
    wrapped = _make_tool_wrapper(
        inst, "submit_vat_return", _make_meta("submit_vat_return")
    )
    ann = getattr(wrapped, "annotations", None)
    assert ann is not None, "submit_* tool should carry ToolAnnotations"
    assert ann.destructiveHint is True
    assert ann.readOnlyHint in (None, False)
    assert ann.openWorldHint in (None, False)
    assert ann.title in (None, "")


def test_non_submit_tools_get_no_annotation():
    inst = _StubToolSet()
    wrapped = _make_tool_wrapper(
        inst, "get_vat_obligations", _make_meta("get_vat_obligations")
    )
    ann = getattr(wrapped, "annotations", None)
    assert ann is None, "Non-submit tool should have annotations=None"
