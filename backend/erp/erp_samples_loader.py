"""Demo case JSON loader — 从 data/erp_samples/ 读预置案例"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from ..models.erp_models import ImportResult


# repo-root data/ (this file lives at backend/erp/, so go up 3 levels)
SAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "erp_samples"


class DemoCaseNotFoundError(KeyError):
    """Demo case 文件不存在"""


def list_demo_cases() -> List[str]:
    """返回所有可用的 demo case ID（文件名去掉 .json）。"""
    if not SAMPLES_DIR.exists():
        return []
    return sorted(p.stem for p in SAMPLES_DIR.glob("*.json"))


def load_demo_case(case_id: str) -> ImportResult:
    """从 data/erp_samples/{case_id}.json 读 ImportResult。

    Demo case JSON 已经是 Pydantic-compatible dict，直接 ImportResult.model_validate。
    """
    file_path = SAMPLES_DIR / f"{case_id}.json"
    if not file_path.exists():
        available = list_demo_cases()
        raise DemoCaseNotFoundError(
            f"demo case {case_id!r} not found. available: {available}"
        )
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    # pydantic v1/v2 compat
    if hasattr(ImportResult, "model_validate"):
        return ImportResult.model_validate(raw)
    return ImportResult.parse_obj(raw)
