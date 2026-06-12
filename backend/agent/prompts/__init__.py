"""按 (cc, tax_type) 动态加载系统提示。

用法:
    from backend.agent.prompts import get_system_prompt
    prompt = get_system_prompt("uk", "vat")
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
    "get_system_prompt", "SYSTEM_PROMPT",
    "JURISDICTIONS", "TAX_TYPES",  # re-export
]


def get_system_prompt(jurisdiction: str, tax_type: str) -> str:
    """加载 (jurisdiction, tax_type) 的系统提示。

    错误分层:
    - 枚举层 (cc / tt 不在 JURISDICTIONS / TAX_TYPES): KeyError(严)
    - 模块层 (cc 已注册但子包无该 tax 文件): fallback + warning log(软)

    Raises:
        KeyError: jurisdiction 不在 JURISDICTIONS 或 tax_type 不在 TAX_TYPES
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
        specific = getattr(mod, "PROMPT", _FALLBACK_PROMPT)
    except ModuleNotFoundError:
        logger.warning(
            "No prompt file for %s:%s — using _FALLBACK_PROMPT. "
            "Consider adding backend/agent/prompts/%s/%s.py",
            jurisdiction, tax_type, jurisdiction, tax_type,
        )
        specific = _FALLBACK_PROMPT
    return _GENERIC_PROMPT_HEADER + specific


# 向后兼容: 旧版 `from backend.agent.prompts import SYSTEM_PROMPT` 仍可用
SYSTEM_PROMPT = get_system_prompt("uk", "vat")
