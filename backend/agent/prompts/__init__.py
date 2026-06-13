"""按 (cc, tax_type) 动态加载系统提示。

用法:
    from backend.agent.prompts import get_system_prompt, get_multi_jurisdiction_prompt
    prompt = get_system_prompt("uk", "vat")
    multi = get_multi_jurisdiction_prompt([("uk", "vat", "/path/to/ws"), ("de", "vat", "")])
"""
from __future__ import annotations

import importlib
import logging

from backend.models.jurisdictions import (
    JURISDICTIONS, TAX_TYPES, is_valid_jurisdiction,
)

from ._generic import _GENERIC_PROMPT_HEADER
from ._fallback import _FALLBACK_PROMPT

logger = logging.getLogger(__name__)

__all__ = [
    "get_system_prompt", "get_multi_jurisdiction_prompt", "SYSTEM_PROMPT",
    "JURISDICTIONS", "TAX_TYPES",  # re-export
]


def _load_jurisdiction_prompt(jurisdiction: str, tax_type: str) -> str:
    """加载单管辖地 prompt 文本(不含 _GENERIC_PROMPT_HEADER)。

    Raises:
        KeyError: jurisdiction/tax_type 不在合法枚举
    """
    if not is_valid_jurisdiction(jurisdiction, tax_type):
        raise KeyError(
            f"Unknown jurisdiction={jurisdiction!r} or tax_type={tax_type!r}. "
            f"Valid jurisdictions: {sorted(JURISDICTIONS)}; "
            f"Valid tax_types: {sorted(TAX_TYPES)}"
        )
    try:
        mod = importlib.import_module(
            f"backend.agent.prompts.{jurisdiction}.{tax_type}"
        )
        return getattr(mod, "PROMPT", _FALLBACK_PROMPT)
    except ModuleNotFoundError:
        logger.warning(
            "No prompt file for %s:%s — using _FALLBACK_PROMPT. "
            "Consider adding backend/agent/prompts/%s/%s.py",
            jurisdiction, tax_type, jurisdiction, tax_type,
        )
        return _FALLBACK_PROMPT


def get_multi_jurisdiction_prompt(
    slots: list[tuple[str, str, str]],  # [(cc, tt, workspace_path)]
) -> str:
    """组合多管辖地系统提示。

    结构:
        1. _GENERIC_PROMPT_HEADER (共享角色定义 + 响应风格 + 税法研究)
        2. Namespace Map 表格 (动态生成,让 LLM 知道哪个 namespace 对应哪个国家)
        3. 各管辖地 prompt 段 (按 slot 顺序,每段带 namespace header)
    """
    # 1. 共享 header
    parts = [_GENERIC_PROMPT_HEADER]

    # 2. Namespace Map — 单国也标注(统一体验)
    if len(slots) > 1:
        parts.append("\n\n## Multi-Jurisdiction Namespace Map\n")
        parts.append(
            "You are operating across multiple jurisdictions. "
            "Each jurisdiction's tools are namespaced: "
            "`mcp__tax_agent_{cc}_{tt}__{tool_name}`.\n\n"
        )
        parts.append("| # | Country | Tax Type | Tool Prefix | Workspace |\n")
        parts.append("|---|---------|----------|-------------|-----------|\n")
        for i, (cc, tt, ws) in enumerate(slots, 1):
            cc_label = cc.upper()
            tt_label = tt.replace("_", " ").title()
            prefix = f"mcp__tax_agent_{cc}_{tt}__"
            ws_display = ws or "(not loaded)"
            parts.append(f"| {i} | {cc_label} | {tt_label} | `{prefix}` | `{ws_display}` |\n")
        parts.append(
            "\n**Routing:** When the user asks about a specific country/tax type, "
            "use tools from the corresponding namespace prefix. "
            "For cross-jurisdiction questions, call tools from BOTH namespaces "
            "and present results side by side.\n"
        )
    else:
        cc, tt, ws = slots[0]
        ws_note = f" (workspace: `{ws}`)" if ws else ""
        parts.append(
            f"\n\n## Jurisdiction: {cc.upper()} — "
            f"{tt.replace('_', ' ').title()} "
            f"(tools: `mcp__tax_agent_{cc}_{tt}__*`){ws_note}\n"
        )

    # 3. 各管辖地 prompt 段
    for cc, tt, ws in slots:
        header = (
            f"\n\n---\n\n"
            f"## ── {cc.upper()} {tt.replace('_', ' ').title()} "
            f"(tools: `mcp__tax_agent_{cc}_{tt}__*`) ──\n"
        )
        try:
            specific = _load_jurisdiction_prompt(cc, tt)
        except KeyError:
            # 区分: 无效的 jurisdiction/tax_type → 传播; 模块缺失 → fallback
            if not is_valid_jurisdiction(cc, tt):
                raise
            specific = _FALLBACK_PROMPT
        parts.append(header)
        parts.append(specific)

    return "".join(parts)


def get_system_prompt(jurisdiction: str, tax_type: str) -> str:
    """向后兼容: 单管辖地 prompt。新代码用 get_multi_jurisdiction_prompt。"""
    return get_multi_jurisdiction_prompt([(jurisdiction, tax_type, "")])


# 向后兼容: 旧版 `from backend.agent.prompts import SYSTEM_PROMPT` 仍可用
SYSTEM_PROMPT = get_system_prompt("uk", "vat")
