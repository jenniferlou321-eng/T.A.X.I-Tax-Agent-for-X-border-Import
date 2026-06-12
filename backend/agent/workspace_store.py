"""Workspace Store — case 数据落盘为多文件,让 LLM 用 Read 工具按需读取

布局: ~/.taxi/workspace/<case_id>/  →  manifest.json, sales.json, purchases.json,
      nine_box.json, warnings.json, source_meta.json, source_docs/*.json

幂等: manifest.json 已存在时跳过重写,直接返回路径+manifest dict。
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Optional

from backend.erp.erp_samples_loader import load_demo_case, SAMPLES_DIR


WORKSPACE_ROOT = Path(
    os.environ.get("TAXI_WORKSPACE_ROOT") or (Path.home() / ".taxi" / "workspace")
)


def _safe_case_id(case_id: str) -> str:
    """sanitize case_id 防止路径注入(只允许字母数字下划线中划线)"""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", case_id) or "unnamed"


def case_dir(case_id: str) -> Path:
    """返回 workspace 下某 case 的目录(mkdir -p)"""
    d = WORKSPACE_ROOT / _safe_case_id(case_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_case(case_id: str, raw_data: Optional[dict] = None) -> tuple[str, dict]:
    """确保 case 落盘到 workspace(拆多文件)

    如果目标目录已有 manifest.json,直接返回(幂等);否则从 raw_data 或 fixture 写入。
    """
    safe_id = _safe_case_id(case_id)
    target = case_dir(safe_id)

    # 快速路径: workspace 已存在 → 读 manifest 返回,不重写文件
    manifest_path = target / "manifest.json"
    if manifest_path.is_file() and raw_data is None:
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return str(target), json.load(f)
        except Exception:
            pass  # 损坏则重建

    if raw_data is None:
        loaded = load_demo_case(safe_id)
        raw_data = loaded.model_dump(mode="json") if hasattr(loaded, "model_dump") else dict(loaded)

    # 拆字段落盘(沿 ImportResult 真实 keys)
    # metadata 里常见 string 字段:company / vrn / period(dict) / currency / scenario
    # 如果 metadata 为空(如 case-a-uk-subsidiary),回退到 case_summary.json
    metadata = raw_data.get("metadata", {}) or {}
    summary: dict = {}
    # 仅在 metadata 缺少关键字段时才读 case_summary.json(避免不必要的 I/O)
    if not (metadata.get("vrn") or metadata.get("company")):
        summary_path = SAMPLES_DIR / safe_id / "case_summary.json"
        if summary_path.is_file():
            try:
                with open(summary_path, "r", encoding="utf-8") as f:
                    summary = json.load(f)
            except Exception:
                pass
    company = {
        "name": metadata.get("company") or summary.get("company") or raw_data.get("company", ""),
        "vrn": metadata.get("vrn") or summary.get("vrn") or raw_data.get("vrn", ""),
        "period": metadata.get("period") or summary.get("period") or {},
        "currency": metadata.get("currency") or summary.get("currency", "GBP"),
        "scenario": metadata.get("scenario") or summary.get("scenario", ""),
        "eori": metadata.get("eori") or summary.get("eori", ""),
        "period_key": metadata.get("period_key") or summary.get("period_key", ""),
        "group_role": summary.get("group_role", ""),
        "title": summary.get("title", ""),
    }
    # period 可能是 string 或 dict;确保 manifest 统一存 string
    if isinstance(company["period"], dict):
        company["period"] = company["period"].get("label", "") or str(company["period"])
    _write_json(target / "manifest.json", company)
    _write_json(target / "sales.json", raw_data.get("sales", []))
    _write_json(target / "purchases.json", raw_data.get("purchases", []))
    _write_json(target / "nine_box.json", raw_data.get("erp_provided_boxes", {}))
    _write_json(target / "warnings.json", raw_data.get("warnings", []))
    _write_json(
        target / "source_meta.json",
        {
            "profile": raw_data.get("source_profile"),
            "filename": raw_data.get("source_filename"),
            "hash": raw_data.get("source_hash"),
        },
    )

    # 拷 source_docs/(如果 fixture 是 directory layout,带 source_docs/ 子目录)
    src_docs = SAMPLES_DIR / safe_id / "source_docs"
    if src_docs.is_dir():
        dst_docs = target / "source_docs"
        if dst_docs.exists():
            shutil.rmtree(dst_docs)
        shutil.copytree(src_docs, dst_docs)

    return str(target), company
