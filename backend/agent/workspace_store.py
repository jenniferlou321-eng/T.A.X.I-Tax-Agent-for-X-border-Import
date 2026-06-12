"""Workspace Store — case 数据落盘为多文件,让 LLM 用 Read 工具按需读取

设计动机:
    - 之前 session.raw_business_data 把整本数据灌进 prompt,LLM 失忆 + token 浪费
    - 现在:每个 case 落盘到 ~/.taxi/workspace/<case_id>/,按字段拆为多个文件
    - 后端 SDK 配 add_dirs 把这个根目录暴露给 Read 工具
    - LLM 按需 Read 单文件拿数据,不重复灌 prompt

文件布局(以 case-x-uk-standard 为例):
    ~/.taxi/workspace/case-x-uk-standard/
        manifest.json          # 公司元信息(name / vrn / period / ...)
        sales.json             # 销售发票数组
        purchases.json         # 采购发票数组
        nine_box.json          # ERP 自报的 9-Box
        warnings.json          # 解析警告
        source_meta.json       # 数据源元信息
        source_docs/           # 发票级 JSON(从 erp_samples 拷过来)
            *.json

注意:
    - workspace 是 append-only:切换 case 不删旧文件(LLM 可列表查看)
    - case_id sanitize:防止路径注入
    - 文件拆法:沿 ImportResult 真实 keys(sales/purchases/erp_provided_boxes/...)；
      engine 旧代码期望的 keys(sales_invoices/purchase_invoices/company)不强造,
      由 business_analyzer 的 translator 翻译
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

    Args:
        case_id: 案例 ID
        raw_data: 如果调用方有原始数据(ImportResult dict),直接用;
                  否则从 fixture (data/erp_samples/<id>/) 加载 + 拆

    Returns:
        (落盘目录路径, manifest dict) — manifest 包含 name/vrn/period/currency/scenario,
        调用方据此填充 session.taxpayer_id 等,无需再读文件。
    """
    safe_id = _safe_case_id(case_id)
    target = case_dir(safe_id)

    if raw_data is None:
        loaded = load_demo_case(safe_id)
        raw_data = loaded.model_dump(mode="json") if hasattr(loaded, "model_dump") else dict(loaded)

    # 拆字段落盘(沿 ImportResult 真实 keys)
    # metadata 里常见 string 字段:company / vrn / period(dict) / currency / scenario
    # 如果 metadata 为空(如 case-a-uk-subsidiary),回退到 case_summary.json
    metadata = raw_data.get("metadata", {}) or {}
    summary: dict = {}
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
