"""红队修复回归测试 (2026-06-14)。

对应 docs/superpowers/audit/2026-06-14-prompt-redteam.md 的已修 finding:
C1 / H1 / H2 / H3 / M1 / M2 / M3 / N2 / N3 / NEW-1 / NEW-2。
"""
from __future__ import annotations

from backend.agent.prompts import get_multi_jurisdiction_prompt


# ── C1: 工具失败路径不再命令 agent 调被禁的 AskUserQuestion ──
def test_c1_no_askuserquestion_in_vat_prompt():
    vat = get_multi_jurisdiction_prompt([("uk", "vat", "")])
    assert "AskUserQuestion" not in vat


# ── M1: VAT workflow 不再反问 VRN ──
def test_m1_vat_workflow_does_not_ask_for_vrn():
    vat = get_multi_jurisdiction_prompt([("uk", "vat", "")])
    assert "Ask for their VRN" not in vat


# ── H3: testland 补齐提交前确认门 + 工具名对齐 ──
def test_h3_testland_has_presubmit_gate():
    tl = get_multi_jurisdiction_prompt([("testland", "vat", "")])
    assert "Pre-Submit Mandatory Re-Statement" in tl
    assert "submit_vat_return" in tl


# ── N3: pre-submit figures 必须取自工具输出 ──
def test_n3_figures_must_come_from_tool_output():
    vat = get_multi_jurisdiction_prompt([("uk", "vat", "")])
    assert "verbatim from the most recent successful" in vat


# ── NEW-1 / NEW-2: demo 完成标准 + 全税种主动审视 ──
def test_new1_new2_sections_present():
    prompt = get_multi_jurisdiction_prompt([("uk", "vat", "")])
    assert "Platform Status (Demo)" in prompt
    assert "Holistic Tax Review" in prompt


# ── N2: 引用走 tax_kb_researcher + 禁编造法规编号 ──
def test_n2_citation_routed_to_kb_subagent():
    prompt = get_multi_jurisdiction_prompt([("uk", "vat", "")])
    assert "do NOT invent statute" in prompt or "do NOT invent" in prompt


# ── H2 软约束: 并行 subagent ≤ 5 ──
def test_h2_soft_concurrency_constraint():
    prompt = get_multi_jurisdiction_prompt([("uk", "vat", "")])
    assert "at most 5 at once" in prompt


# ── H1 / H2: 子 agent 工具授权 + turn 预算 ──
def test_h1_h2_subagent_tools_and_maxturns():
    from backend.agent.tax_knowledge_prompts import TAX_KB_SUBAGENT_PROMPT
    # 子 agent prompt 仍声明三个工具
    for t in ("search_tax_knowledge", "list_supported_jurisdictions", "get_tax_rates"):
        assert t in TAX_KB_SUBAGENT_PROMPT
    # 留合成轮的指令存在
    assert "reserve your final turn" in TAX_KB_SUBAGENT_PROMPT


# ── M2 / M3: workspace 单一事实源,两个语气变体一致 ──
def test_m2_m3_workspace_single_source_of_truth():
    import backend.agent.engine as e
    facts_marker = "Never ask the user for VRN"
    # 事实源
    assert facts_marker in e._WORKSPACE_FACTS
    # 有 Read 变体 (SDK 路径)
    assert facts_marker in e._WORKSPACE_INSTRUCTION
    assert "MUST read" in e._WORKSPACE_INSTRUCTION
    # 无 Read 变体 (httpx 路径)
    assert facts_marker in e._WORKSPACE_INSTRUCTION_NO_READ
    assert "do not have a file-reading tool" in e._WORKSPACE_INSTRUCTION_NO_READ
    # 即时提醒也派生自事实源
    reminder = e._build_multi_workspace_reminder(
        [e.JurisdictionSlot(jurisdiction="uk", tax_type="vat",
                            workspace_path="/x/agent_workspace")]
    )
    assert facts_marker in reminder
