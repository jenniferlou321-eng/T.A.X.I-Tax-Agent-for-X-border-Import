"""/api/erp/* — ERP 数据接入 REST 端点

- GET  /api/erp/cases                — 列出所有 demo case
- GET  /api/erp/cases/{case_id}      — 加载 demo case → ImportResult
- POST /api/erp/import               — multipart 上传 CSV
- POST /api/erp/reconcile            — 调 reconcile 生成差异报告
- DELETE /api/erp/{import_id}        — 清 in-memory 缓存（v0）
"""
from __future__ import annotations

import hashlib
import io
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from .erp.csv_parser import CsvParseError, parse_csv
from .erp.erp_samples_loader import DemoCaseNotFoundError, list_demo_cases, load_demo_case
from .erp.reconcile import compute_taxi_nine_box, reconcile
from .models.erp_models import ImportResult


router = APIRouter(prefix="/erp", tags=["erp"])


def _to_json(model) -> dict:
    """Serialize a pydantic model to JSON-safe dict.

    Supports both pydantic v2 (model_dump) and v1 (dict). The project
    spec targets pydantic v2 (per pyproject.toml `pydantic>=2.0`); this
    helper is a fallback so the router can be exercised on environments
    that still have pydantic v1 installed.
    """
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


@router.get("/cases")
def get_cases():
    """列出所有 demo case ID。"""
    return {"cases": list_demo_cases()}


@router.get("/cases/{case_id}")
def get_case(case_id: str):
    """加载指定 demo case 返回 ImportResult。"""
    try:
        result = load_demo_case(case_id)
    except DemoCaseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _to_json(result)


@router.post("/import")
async def import_csv(file: UploadFile = File(...), profile: Optional[str] = Form(None)):
    """multipart 上传 CSV → ImportResult。

    v0 上限 10MB（spec §7 risks）。
    """
    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file exceeds 10MB limit")
    try:
        result = parse_csv(file_bytes, profile=profile)
    except CsvParseError as e:
        raise HTTPException(status_code=422, detail=f"CSV parse error: {e}") from e
    # 填充 source_filename
    result.source_filename = file.filename or "<uploaded>"
    return _to_json(result)


@router.post("/reconcile")
def post_reconcile(payload: dict):
    """接收 ImportResult dict 和 erp_source → ReconciliationDelta。

    Request body: {"import_result": {...}, "erp_source": "csv:generic"}
    """
    try:
        if hasattr(ImportResult, "model_validate"):
            ir = ImportResult.model_validate(payload["import_result"])
        else:  # pydantic v1 compat
            ir = ImportResult.parse_obj(payload["import_result"])
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"invalid ImportResult: {e}") from e
    taxi_boxes = compute_taxi_nine_box(ir.sales, ir.purchases)
    delta = reconcile(ir.erp_provided_boxes, taxi_boxes, erp_source=payload.get("erp_source", "unknown"))
    return _to_json(delta)
