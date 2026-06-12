"""ImportHubStore — 按 period 隔离的 in-memory store。

去重规则:同一 (period, id) 后写覆盖前;Cancel 事件 = 同 id 再 add 并标 cancelled。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from ..models.erp_models import HubInvoice


class _Store:
    """Module-level singleton (process-local)."""

    _data: Dict[str, Dict[str, HubInvoice]] = {}

    @classmethod
    def add(cls, period: str, invoices: List[HubInvoice]) -> None:
        bucket = cls._data.setdefault(period, {})
        for inv in invoices:
            bucket[inv.id] = inv  # dedup by (period, id) — 后写覆盖

    @classmethod
    def list(cls, period: str) -> List[HubInvoice]:
        return list(cls._data.get(period, {}).values())

    @classmethod
    def count(cls, period: str) -> dict:
        items = cls.list(period)
        return {
            "sales": sum(1 for x in items if x.id.startswith("S") and not x.cancelled and not x.is_amend),
            "purchases": sum(1 for x in items if x.id.startswith("P") and not x.cancelled and not x.is_amend),
            "cancelled": sum(1 for x in items if x.cancelled),
            "amends": sum(1 for x in items if x.is_amend),
            "total": len(items),
        }

    @classmethod
    def clear(cls, period: Optional[str] = None) -> None:
        if period is None:
            cls._data.clear()
        else:
            cls._data.pop(period, None)


# Public API (module-level convenience)
ImportHubStore = _Store  # 暴露类, 调用方写 ImportHubStore.add(...) 即可
