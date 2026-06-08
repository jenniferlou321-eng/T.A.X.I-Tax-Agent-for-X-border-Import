"""APIChannel — 基于 REST API 的提交渠道实现"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from tax_agent.channels import FilingChannel
from tax_agent.channels.oauth import OAuth2Manager, OAuth2Config
from tax_agent.channels.fraud_headers import FraudPreventionHeaders
from tax_agent.models.tax_data import ChannelType
from tax_agent.models.results import (
    AuthResult, SubmitResult, StatusResult, Receipt, FilingPayload, FilingStatus,
)

logger = logging.getLogger(__name__)


class APIChannel(FilingChannel):
    """REST API 直连提交渠道 — 用于 HMRC 等提供 API 的税务平台"""

    channel_type = ChannelType.API

    def __init__(
        self,
        base_url: str,
        oauth_config: OAuth2Config,
        submit_endpoint: str,
        status_endpoint: str | None = None,
        health_endpoint: str = "/",
        fraud_headers: bool = False,
        vendor_product: str = "TaxAgent Global",
        accept_header: str = "application/json",
    ):
        self.base_url = base_url.rstrip("/")
        self.oauth = OAuth2Manager(oauth_config)
        self._submit_endpoint = submit_endpoint
        self._status_endpoint = status_endpoint
        self._health_endpoint = health_endpoint
        self._accept_header = accept_header
        self._fraud = FraudPreventionHeaders(
            vendor_product=vendor_product,
        ) if fraud_headers else None
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30,
            )
        return self._client

    # ── FilingChannel 接口 ──

    async def authenticate(self) -> AuthResult:
        return await self.oauth.authenticate_silent()

    async def submit(self, payload: FilingPayload) -> SubmitResult:
        client = await self._get_client()
        auth = await self.oauth.authenticate_silent()
        if not auth.success:
            return SubmitResult(
                success=False,
                error_code="AUTH_FAILED",
                error_message=auth.error or "Authentication failed",
            )

        headers = {
            "Authorization": f"Bearer {auth.token}",
            "Content-Type": "application/json",
            "Accept": self._accept_header,
        }

        # 添加欺诈预防头
        if self._fraud:
            fraud_headers = self._fraud.build_headers(
                user_id=payload.taxpayer.tax_id,
            )
            headers.update(fraud_headers)

        # 构建 URL（支持路径参数替换）
        url = self._submit_endpoint.format(
            vrn=payload.taxpayer.tax_id,
            period_key=payload.period.period_key,
            **payload.body,
        )

        try:
            resp = await client.post(url, json=payload.body, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            return SubmitResult(
                success=False,
                error_code=f"HTTP_{e.response.status_code}",
                error_message=str(e),
                raw_response=e.response.json() if e.response.content else {},
            )
        except Exception as e:
            return SubmitResult(
                success=False,
                error_code="NETWORK_ERROR",
                error_message=str(e),
            )

        data = resp.json()
        return SubmitResult(
            success=True,
            receipt=Receipt(
                receipt_id=data.get("receiptID", ""),
                submitted_at=datetime.now(timezone.utc),
                raw_response=data,
            ),
            raw_response=data,
        )

    async def get_status(self, receipt: Receipt) -> StatusResult:
        """查询提交状态 — 如 HMRC 同步返回则直接标记 ACCEPTED"""
        if self._status_endpoint is None:
            # 无状态查询端点 — 认为已受理
            return StatusResult(
                status=FilingStatus.ACCEPTED,
                detail="Synchronous submission — assumed accepted",
            )

        client = await self._get_client()
        auth = await self.oauth.authenticate_silent()
        if not auth.success:
            return StatusResult(
                status=FilingStatus.SUBMITTED,
                detail="Auth failed during status check",
            )

        url = self._status_endpoint.format(receipt_id=receipt.receipt_id)
        headers = {"Authorization": f"Bearer {auth.token}"}

        try:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status", "received")
            return StatusResult(
                status=FilingStatus.ACCEPTED if status == "accepted" else FilingStatus.SUBMITTED,
                detail=data.get("message", ""),
            )
        except Exception:
            return StatusResult(
                status=FilingStatus.SUBMITTED,
                detail="Status check failed",
            )

    async def health_check(self) -> bool:
        try:
            client = await self._get_client()
            resp = await client.get(self._health_endpoint, timeout=10)
            return resp.status_code < 500
        except Exception:
            return False