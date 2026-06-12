"""ERPNext REST API 客户端 — 手动 Pull 拉本期内已 Submit 的发票。

调用方:backend/erp_router.py::POST /erpnext/pull
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import List, Optional

import httpx

from ..models.erp_models import HubInvoice


class ErpNextPullError(Exception):
    """ERPNext Pull 失败(网络/凭证/解析)。"""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def json_fields(doctype: str) -> str:
    fields = [
        "name", "posting_date", "net_total", "total_taxes_and_charges",
        "grand_total", "docstatus", "is_return", "return_against",
    ]
    if doctype == "Sales Invoice":
        fields.append("customer_name")
    else:
        fields.append("supplier_name")
    return json.dumps(fields)


async def pull_invoices(
    base_url: str, api_key: str, api_secret: str,
    period_start: date, period_end: date,
    doctype: str = "Sales Invoice",
    since: Optional[date] = None,
) -> List[HubInvoice]:
    """拉 ERPNext 列表 + 转换 → list[HubInvoice]。

    Args:
        base_url: e.g. "http://my.local:8000"
        api_key/api_secret: ERPNext API 凭证
        period_start/period_end: posting_date 范围
        doctype: "Sales Invoice" 或 "Purchase Invoice"
        since: modified >= since(增量);None = 全量
    """
    headers = {
        "Authorization": f"token {api_key}:{api_secret}",
    }
    # ERPNext filter syntax: [["posting_date", "Between", [start, end]]]
    filters = [["posting_date", "Between", [period_start.isoformat(), period_end.isoformat()]]]
    if since is not None:
        filters.append(["modified", ">=", since.isoformat()])
    # docstatus ∈ {1, 2} = submitted + cancelled
    filters.append(["docstatus", "in", [1, 2]])

    params = {
        "filters": json.dumps(filters),  # ERPNext 期望 JSON 字符串
        "limit_page_length": 500,
        "fields": json_fields(doctype),
    }

    url = f"{base_url.rstrip('/')}/api/resource/{doctype.replace(' ', '%20')}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.get(url, headers=headers, params=params)
        except httpx.RequestError as e:
            raise ErpNextPullError(f"network error: {e}") from e

    if resp.status_code in (401, 403):
        raise ErpNextPullError(
            f"ERPNext returned {resp.status_code}",
            status_code=resp.status_code,
        )
    if resp.status_code != 200:
        raise ErpNextPullError(
            f"ERPNext returned {resp.status_code}: {resp.text[:200]}",
            status_code=resp.status_code,
        )

    try:
        payload = resp.json()
    except ValueError as e:
        raise ErpNextPullError(
            f"ERPNext returned invalid JSON: {resp.text[:200]}",
            status_code=resp.status_code,
        ) from e
    docs = payload.get("data", [])
    return [_to_hub_invoice(d, doctype) for d in docs]


def _to_hub_invoice(doc: dict, doctype: str) -> HubInvoice:
    counterparty = doc.get("customer_name") or doc.get("supplier_name") or ""
    net = Decimal(str(doc.get("net_total", 0)))
    vat = Decimal(str(doc.get("total_taxes_and_charges", 0)))
    vat_rate = (vat / net).quantize(Decimal("0.0001")) if net != 0 else Decimal("0")
    is_amend = bool(doc.get("is_return", 0))
    parent = doc.get("return_against") if is_amend else None
    return HubInvoice(
        id=doc.get("name", ""),
        txn_date=date.fromisoformat(doc["posting_date"]),
        counterparty=counterparty,
        net_amount=net,
        vat_amount=vat,
        gross_amount=Decimal(str(doc.get("grand_total", 0))),
        vat_rate=vat_rate,
        tax_code="T1",
        cancelled=(doc.get("docstatus") == 2),
        is_amend=is_amend,
        parent=parent,
        source="erpnext_pull",
    )
