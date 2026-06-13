"""HMRC VAT Service — 封装 MTD for VAT API v1.0

Endpoints:
- GET  /organisations/vat/{vrn}/obligations
- POST /organisations/vat/{vrn}/returns
- GET  /organisations/vat/{vrn}/returns/{periodKey}
- GET  /organisations/vat/{vrn}/liabilities
- GET  /organisations/vat/{vrn}/payments
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

import httpx

from backend.channels.oauth import OAuth2Manager
from backend.channels.fraud_headers import FraudPreventionHeaders
from backend.jurisdictions.uk._hmrc_base import HMRCService

logger = logging.getLogger(__name__)


@dataclass
class VATObligation:
    """VAT 申报义务"""
    start: date
    end: date
    due: date
    status: str          # "O" = Open, "F" = Fulfilled
    period_key: str
    received: Optional[date] = None


@dataclass
class VATReturnView:
    """已提交的 VAT Return"""
    period_key: str
    vat_due_sales: Decimal
    vat_due_acquisitions: Decimal
    total_vat_due: Decimal
    vat_reclaimed_curr_period: Decimal
    net_vat_due: Decimal
    total_value_sales_ex_vat: int
    total_value_purchases_ex_vat: int
    total_value_goods_supplied_ex_vat: int
    total_acquisitions_ex_vat: int
    received: Optional[str] = None


class HMRCVATService(HMRCService):
    """HMRC Making Tax Digital for VAT API 客户端"""

    def __init__(
        self,
        base_url: str,
        oauth: OAuth2Manager,
        fraud_headers: FraudPreventionHeaders | None = None,
    ):
        super().__init__(
            base_url=base_url,
            oauth=oauth,
            fraud_headers=fraud_headers,
            accept_header="application/vnd.hmrc.1.0+json",
        )

    # ── Public API ──

    async def get_obligations(
        self,
        vrn: str,
        from_date: date | None = None,
        to_date: date | None = None,
        status: str | None = None,
    ) -> list[VATObligation]:
        """获取 VAT 申报义务列表

        Args:
            vrn: VAT Registration Number (如 "123456789")
            from_date: 查询起始日期（默认 366 天前）
            to_date: 查询结束日期（默认今天）
            status: "O" (Open) | "F" (Fulfilled) | None (all)
        """
        token = await self._authenticate()

        if to_date is None:
            to_date = date.today()
        if from_date is None:
            from_date = date.fromordinal(to_date.toordinal() - 366)

        params: dict[str, str] = {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
        }
        if status:
            params["status"] = status

        client = await self._get_client()
        url = f"/organisations/vat/{vrn}/obligations"
        headers = self._build_headers(user_id=vrn)
        headers["Authorization"] = f"Bearer {token}"

        try:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            self._raise_for_hmrc_error(resp, "obligations")

        data = resp.json()
        obligations = []
        for ob in data.get("obligations", []):
            obligations.append(VATObligation(
                start=date.fromisoformat(ob["start"]),
                end=date.fromisoformat(ob["end"]),
                due=date.fromisoformat(ob["due"]),
                status=ob["status"],
                period_key=ob["periodKey"],
                received=date.fromisoformat(ob["received"]) if "received" in ob else None,
            ))
        return obligations

    async def submit_return(self, vrn: str, body: dict) -> dict:
        """提交 VAT Return

        Args:
            vrn: VAT Registration Number
            body: HMRC 标准 VAT Return JSON (9 boxes + periodKey + finalised)

        Returns:
            HMRC 响应: {processingDate, paymentIndicator, formBundleNumber, chargeRefNumber}
        """
        token = await self._authenticate()

        client = await self._get_client()
        url = f"/organisations/vat/{vrn}/returns"
        headers = self._build_headers(user_id=vrn)
        headers["Authorization"] = f"Bearer {token}"

        try:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            self._raise_for_hmrc_error(resp, "submit")

        return resp.json()

    async def get_return(self, vrn: str, period_key: str) -> VATReturnView:
        """查看已提交的 VAT Return"""
        token = await self._authenticate()

        client = await self._get_client()
        url = f"/organisations/vat/{vrn}/returns/{period_key}"
        headers = self._build_headers(user_id=vrn)
        headers["Authorization"] = f"Bearer {token}"

        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            self._raise_for_hmrc_error(resp, "get return")

        data = resp.json()
        return VATReturnView(
            period_key=data.get("periodKey", ""),
            vat_due_sales=Decimal(str(data.get("vatDueSales", 0))),
            vat_due_acquisitions=Decimal(str(data.get("vatDueAcquisitions", 0))),
            total_vat_due=Decimal(str(data.get("totalVatDue", 0))),
            vat_reclaimed_curr_period=Decimal(str(data.get("vatReclaimedCurrPeriod", 0))),
            net_vat_due=Decimal(str(data.get("netVatDue", 0))),
            total_value_sales_ex_vat=int(data.get("totalValueSalesExVAT", 0)),
            total_value_purchases_ex_vat=int(data.get("totalValuePurchasesExVAT", 0)),
            total_value_goods_supplied_ex_vat=int(data.get("totalValueGoodsSuppliedExVAT", 0)),
            total_acquisitions_ex_vat=int(data.get("totalAcquisitionsExVAT", 0)),
            received=data.get("received"),
        )

    async def get_liabilities(self, vrn: str, from_date: date, to_date: date) -> list[dict]:
        """获取 VAT 负债信息"""
        token = await self._authenticate()

        client = await self._get_client()
        url = f"/organisations/vat/{vrn}/liabilities"
        params = {"from": from_date.isoformat(), "to": to_date.isoformat()}
        headers = self._build_headers(user_id=vrn)
        headers["Authorization"] = f"Bearer {token}"

        try:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            self._raise_for_hmrc_error(resp, "liabilities")

        data = resp.json()
        return data.get("liabilities", [])

    async def get_payments(self, vrn: str, from_date: date, to_date: date) -> list[dict]:
        """获取 VAT 付款信息"""
        token = await self._authenticate()

        client = await self._get_client()
        url = f"/organisations/vat/{vrn}/payments"
        params = {"from": from_date.isoformat(), "to": to_date.isoformat()}
        headers = self._build_headers(user_id=vrn)
        headers["Authorization"] = f"Bearer {token}"

        try:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            self._raise_for_hmrc_error(resp, "payments")

        data = resp.json()
        return data.get("payments", [])
