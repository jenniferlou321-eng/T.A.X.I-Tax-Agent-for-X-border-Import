"""Workspace Store — 把当前 case 投影到 Agent 固定工作目录。

Active layout:
    ~/.taxi/agent_workspace/
      manifest.json, sales.json, purchases.json, nine_box.json, warnings.json,
      source_meta.json, source_docs/*.json
      related_cases/<case_id>/...   # 多实体/跨境 case 的关联实体

默认目录为空;选择 case 时先清空再复制当前 case;前端清空数据时也清空。
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

# Agent 只看这个固定 active workspace。默认空;选择 case 后把该 case 投影进来;
# 前端清空数据时清空该目录。保留 WORKSPACE_ROOT 仅作旧数据兼容/人工排查。
AGENT_WORKSPACE_ROOT = Path(
    os.environ.get("TAXI_AGENT_WORKSPACE_ROOT") or (Path.home() / ".taxi" / "agent_workspace")
)


def _safe_case_id(case_id: str) -> str:
    """sanitize case_id 防止路径注入(只允许字母数字下划线中划线)"""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", case_id) or "unnamed"


def case_dir(case_id: str) -> Path:
    """返回 legacy workspace 下某 case 的目录(mkdir -p)。"""
    d = WORKSPACE_ROOT / _safe_case_id(case_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clear_agent_workspace() -> str:
    """清空 Agent 固定工作目录,并保持目录本身存在。"""
    if AGENT_WORKSPACE_ROOT.exists():
        shutil.rmtree(AGENT_WORKSPACE_ROOT)
    AGENT_WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    return str(AGENT_WORKSPACE_ROOT)


def _write_case_to_dir(case_id: str, target: Path, raw_data: Optional[dict] = None) -> dict:
    """把一个 case 拆成 manifest/sales/purchases/... 写到 target。"""
    safe_id = _safe_case_id(case_id)
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
        "case_id": safe_id,
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

    target.mkdir(parents=True, exist_ok=True)
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

    return company


def mount_cases(case_ids: list[str], raw_data: Optional[dict] = None) -> list[tuple[str, dict]]:
    """把当前选择的 case 投影到 Agent 固定工作目录。

    - 第一个 case 写到 `~/.taxi/agent_workspace/` 根目录,Agent 默认先读这里。
    - 其余 case(跨境相关实体)写到 `related_cases/<case_id>/`。
    - 每次 mount 都先清空固定目录,所以不会残留上一个 case 的数据。
    """
    clear_agent_workspace()
    mounted: list[tuple[str, dict]] = []
    for i, cid in enumerate(case_ids):
        target = AGENT_WORKSPACE_ROOT if i == 0 else AGENT_WORKSPACE_ROOT / "related_cases" / _safe_case_id(cid)
        manifest = _write_case_to_dir(cid, target, raw_data if i == 0 else None)
        mounted.append((str(target), manifest))
    return mounted


def ensure_case(case_id: str, raw_data: Optional[dict] = None) -> tuple[str, dict]:
    """兼容旧调用:把单个 case mount 到固定 Agent workspace。"""
    mounted = mount_cases([case_id], raw_data)
    return mounted[0]
