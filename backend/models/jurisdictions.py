"""国家 / 税种枚举 — 单一事实源

被 backend/agent/prompts/__init__.py、backend/channels/registry.py、
backend/registry.py 共同 import。**修改这里需要同时改 3 个 import 方的测试**。
"""
from __future__ import annotations

JURISDICTIONS: frozenset[str] = frozenset({"uk", "de", "cn", "fr", "testland"})

TAX_TYPES: frozenset[str] = frozenset({
    "vat", "self_assessment", "corporation_tax", "paye", "stamp_duty",
})


def is_valid_jurisdiction(jurisdiction: str, tax_type: str) -> bool:
    """检查 (cc, tt) 是否在合法枚举里。

    大小写敏感: 不接受 'UK' / 'VAT'。
    """
    return jurisdiction in JURISDICTIONS and tax_type in TAX_TYPES
