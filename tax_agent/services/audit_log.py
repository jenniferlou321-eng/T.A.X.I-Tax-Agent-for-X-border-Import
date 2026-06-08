"""审计日志 — 全流程可追溯"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models.results import AuditEntry, FilingStatus

logger = logging.getLogger(__name__)


class AuditLog:
    """结构化审计日志记录"""

    def __init__(self, log_dir: Optional[Path] = None):
        self._log_dir = log_dir or Path("logs/audit")
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, list[AuditEntry]] = {}

    def record(
        self,
        filing_id: str,
        stage: str,
        action: str,
        detail: dict | None = None,
    ) -> AuditEntry:
        """记录一条审计日志"""
        entry = AuditEntry(
            filing_id=filing_id,
            stage=stage,
            action=action,
            detail=detail or {},
            timestamp=datetime.utcnow(),
        )
        if filing_id not in self._entries:
            self._entries[filing_id] = []
        self._entries[filing_id].append(entry)
        logger.info(f"[{filing_id}] {stage}::{action} — {detail}")
        return entry

    def get_trail(self, filing_id: str) -> list[AuditEntry]:
        """获取某个申报的完整审计轨迹"""
        return self._entries.get(filing_id, [])

    def persist(self, filing_id: str) -> None:
        """将审计日志持久化到文件"""
        trail = self.get_trail(filing_id)
        filepath = self._log_dir / f"{filing_id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {
                        "filing_id": e.filing_id,
                        "stage": e.stage,
                        "action": e.action,
                        "detail": e.detail,
                        "timestamp": e.timestamp.isoformat(),
                    }
                    for e in trail
                ],
                f,
                ensure_ascii=False,
                indent=2,
            )