"""Demo case JSON loader — 从 data/erp_samples/ 读预置案例

支持的两种 layout:
  1. flat:     data/erp_samples/{case_id}.json              (单文件 ImportResult)
  2. directory:data/erp_samples/{case_id}/erp_import.json   (目录式：含 source_docs/、case_summary.json 等)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from ..models.erp_models import ImportResult


# repo-root data/ (this file lives at backend/erp/, so go up 3 levels)
SAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "erp_samples"


class DemoCaseNotFoundError(KeyError):
    """Demo case 文件不存在"""


def _resolve_case_path(case_id: str) -> Path | None:
    """按 flat → directory 顺序解析 case 路径。返回 ImportResult JSON 路径或 None。"""
    # 1. flat: {case_id}.json
    flat = SAMPLES_DIR / f"{case_id}.json"
    if flat.is_file():
        return flat
    # 2. directory layout: {case_id}/erp_import.json
    nested = SAMPLES_DIR / case_id / "erp_import.json"
    if nested.is_file():
        return nested
    return None


def list_demo_cases() -> List[str]:
    """返回所有可用的 demo case ID。

    flat layout  → 文件 stem
    directory layout → 目录名（且包含 erp_import.json）
    """
    if not SAMPLES_DIR.exists():
        return []
    cases: set[str] = set()
    # flat
    for p in SAMPLES_DIR.glob("*.json"):
        cases.add(p.stem)
    # directory layout
    for d in SAMPLES_DIR.iterdir():
        if d.is_dir() and (d / "erp_import.json").is_file():
            cases.add(d.name)
    return sorted(cases)


def load_demo_case(case_id: str) -> ImportResult:
    """从 data/erp_samples 读 ImportResult。

    Demo case JSON 已经是 Pydantic-compatible dict，直接 ImportResult.model_validate。
    """
    file_path = _resolve_case_path(case_id)
    if file_path is None:
        available = list_demo_cases()
        raise DemoCaseNotFoundError(
            f"demo case {case_id!r} not found. available: {available}"
        )
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    return ImportResult.model_validate(raw)
