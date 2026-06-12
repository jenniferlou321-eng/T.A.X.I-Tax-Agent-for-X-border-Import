"""/api/erp/* — ERP 数据接入 REST 端点

- GET  /api/erp/cases                — 列出所有 demo case
- GET  /api/erp/cases/{case_id}      — 加载 demo case → ImportResult
- POST /api/erp/import               — multipart 上传 CSV
- POST /api/erp/reconcile            — 调 reconcile 生成差异报告
- POST /api/erp/erpnext/push         — 接收 ERPNext HMAC 签名推送
- POST /api/erp/erpnext/pull         — 手动从 ERPNext REST 拉本期内发票
- GET  /api/erp/erpnext/status       — ERPNext 连接状态
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile

from .erp.csv_parser import CsvParseError, parse_csv
from .erp.erp_samples_loader import DemoCaseNotFoundError, list_demo_cases, load_demo_case
from .erp.erpnext_connector import payload_to_import_result, validate_signature
from .erp import erpnext_pull
from .erp.reconcile import compute_taxi_nine_box, reconcile
from .models.erp_models import ImportResult
from .services.erpnext_buffer import (
    get_import_result as get_buffered_erpnext,
    store_import_result as store_erpnext_buffer,
)
from .services.imported_data_buffer import ImportHubStore


router = APIRouter(prefix="/erp", tags=["erp"])


def _to_json(model) -> dict:
    """Serialize a pydantic model to a JSON-safe dict."""
    return model.model_dump(mode="json")


def _erpnext_secret() -> str:
    """Read shared HMAC secret from env (no .env reload for dev)."""
    return os.environ.get("ERPNEXT_HMAC_SECRET", "")


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
        ir = ImportResult.model_validate(payload["import_result"])
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"invalid ImportResult: {e}") from e
    taxi_boxes = compute_taxi_nine_box(ir.sales, ir.purchases)
    delta = reconcile(ir.erp_provided_boxes, taxi_boxes, erp_source=payload.get("erp_source", "unknown"))
    return _to_json(delta)


@router.post("/erpnext/push")
async def erpnext_push(
    request: Request,
    x_taxi_signature: str = Header(..., alias="X-TAXI-Signature"),
    x_taxi_source: Optional[str] = Header(default=None, alias="X-TAXI-Source"),
):
    """接收 ERPNext 异步推送的单据数据。

    Headers:
        X-TAXI-Signature: HMAC-SHA256 of (raw body + secret)
        X-TAXI-Source:  e.g. "erpnext"

    Body: JSON payload (see erpnext_connector.payload_to_import_result).
    """
    body = await request.body()
    secret = _erpnext_secret()
    if not secret:
        raise HTTPException(status_code=500, detail="ERPNEXT_HMAC_SECRET not configured")
    if not validate_signature(body, x_taxi_signature, secret):
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        payload = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {e}") from e

    try:
        ir = payload_to_import_result(payload)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"payload error: {e}") from e

    store_erpnext_buffer(ir)
    return {
        "status": "ok",
        "docname": payload.get("docname"),
        "txn_type": payload.get("txn_type"),
        "sales": len(ir.sales),
        "purchases": len(ir.purchases),
    }


@router.get("/erpnext/status")
def erpnext_status():
    """ERPNext 连接状态：是否有推过来的数据、最近一次推送时间等。"""
    ir = get_buffered_erpnext()
    if ir is None:
        return {
            "connected": False,
            "last_push_at": None,
            "sales_count": 0,
            "purchases_count": 0,
            "docnames": [],
        }
    metadata = ir.metadata or {}
    docnames = [s.id for s in ir.sales] + [p.id for p in ir.purchases]
    return {
        "connected": True,
        "last_push_at": metadata.get("pushed_at"),
        "sales_count": len(ir.sales),
        "purchases_count": len(ir.purchases),
        "docnames": docnames,
        "company": metadata.get("company"),
        "source": metadata.get("source"),
    }


@router.post("/erpnext/pull")
async def post_erpnext_pull(payload: dict):
    """手动 Pull:从 T.A.X.I. 主动拉 ERPNext 数据。

    Body: {
      "url": "http://my.local:8000",
      "api_key": "...", "api_secret": "...",
      "period": "Q1_2026",
      "period_start": "2026-01-01", "period_end": "2026-03-31",
      "since": "2026-04-01" (optional, 增量)
    }

    拉 Sales Invoice + Purchase Invoice 两个 doctype,合并写 store。
    """
    from datetime import date
    period = payload.get("period", "")
    if not period:
        raise HTTPException(status_code=422, detail="period required")
    try:
        period_start = date.fromisoformat(payload.get("period_start", ""))
        period_end = date.fromisoformat(payload.get("period_end", ""))
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=422, detail=f"invalid date format: {e}") from e
    since = date.fromisoformat(payload["since"]) if payload.get("since") else None

    base_url = payload.get("url", "").rstrip("/")
    api_key = payload.get("api_key", "")
    api_secret = payload.get("api_secret", "")

    all_invoices = []
    for doctype in ("Sales Invoice", "Purchase Invoice"):
        try:
            invs = await erpnext_pull.pull_invoices(
                base_url=base_url, api_key=api_key, api_secret=api_secret,
                period_start=period_start, period_end=period_end,
                doctype=doctype, since=since,
            )
            all_invoices.extend(invs)
        except erpnext_pull.ErpNextPullError as e:
            raise HTTPException(
                status_code=500,
                detail={"message": str(e), "status_code": e.status_code, "doctype": doctype},
            ) from e

    ImportHubStore.add(period, all_invoices)
    summary = ImportHubStore.count(period)
    return {
        "status": "ok",
        "period": period,
        "sales": summary["sales"],
        "purchases": summary["purchases"],
        "cancelled": summary["cancelled"],
        "amends": summary["amends"],
        "count": summary,
    }


@router.get("/hub/summary")
def hub_summary(period: str):
    """取本 period 的 ImportHubStore 摘要(发票列表 + 计数)。"""
    from .models.erp_models import SalesTransaction, PurchaseTransaction
    items = ImportHubStore.list(period)
    sales = [
        SalesTransaction(
            id=i.id, txn_date=i.txn_date, counterparty=i.counterparty,
            net_amount=i.net_amount, vat_amount=i.vat_amount, gross_amount=i.gross_amount,
            vat_rate=i.vat_rate, tax_code=i.tax_code,
        )
        for i in items if not i.cancelled and i.id.startswith("S")
    ]
    purchases = [
        PurchaseTransaction(
            id=i.id, txn_date=i.txn_date, counterparty=i.counterparty,
            net_amount=i.net_amount, vat_amount=i.vat_amount, gross_amount=i.gross_amount,
            vat_rate=i.vat_rate, tax_code=i.tax_code,
        )
        for i in items if not i.cancelled and i.id.startswith("P")
    ]
    return {
        "period": period,
        "sales": [s.model_dump(mode="json") for s in sales],
        "purchases": [p.model_dump(mode="json") for p in purchases],
        "count": ImportHubStore.count(period),
        "raw": [i.model_dump(mode="json") for i in items],  # 含 cancelled / amend
    }
