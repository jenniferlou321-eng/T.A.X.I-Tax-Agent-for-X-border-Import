"""HMRC Corporation Tax Service — 通过 GovTalk XML 提交 CT600

CT600 通过 HMRC Transaction Engine (GovTalk XML) 提交,不是 REST JSON API。
Class = "HMRC-CT-CT600"
Endpoint = https://transaction-engine.tax.service.gov.uk/submission

本服务:
- get_obligations: 仍走 REST API (HMRC 有此 endpoint)
- submit_return: 改走 GovTalk XML (之前用的是不存在的假 REST 路径)
- get_return: 通过 GovTalk poll 查询提交状态
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date
from typing import Optional

import httpx

from backend.channels.oauth import OAuth2Manager
from backend.channels.fraud_headers import FraudPreventionHeaders
from backend.channels.govtalk import GovTalkClient, PermanentError, AuthError as GovTalkAuthError
from backend.jurisdictions.uk._hmrc_base import HMRCService

from .govtalk_body import build_ct600_body

logger = logging.getLogger(__name__)


@dataclass
class CTObligation:
    """Corporation Tax 申报义务"""
    start: date
    end: date
    due: date
    status: str          # "O" = Open, "F" = Fulfilled
    period_key: str
    received: Optional[date] = None


@dataclass
class CTReturnView:
    """已提交的 Corporation Tax Return"""
    submission_id: str
    processing_date: str
    form_bundle_number: str
    charge_ref_number: str
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    correlation_id: str = ""


class HMRCCTService(HMRCService):
    """HMRC Corporation Tax API 客户端 — 混合模式

    - get_obligations: REST JSON (HMRC 有此 endpoint)
    - submit_return: GovTalk XML (CT600 走 Transaction Engine)
    - get_return: GovTalk poll 查询
    """

    def __init__(
        self,
        base_url: str,
        oauth: OAuth2Manager,
        fraud_headers: FraudPreventionHeaders | None = None,
        govtalk_client: GovTalkClient | None = None,
    ):
        super().__init__(
            base_url=base_url,
            oauth=oauth,
            fraud_headers=fraud_headers,
            accept_header="application/vnd.hmrc.2.0+json",
        )
        self._govtalk = govtalk_client

    def _get_govtalk(self) -> GovTalkClient:
        """获取或懒初始化 GovTalkClient。"""
        if self._govtalk is None:
            vendor_id = os.environ.get("HMRC_GOVTLAK_VENDOR_ID", os.environ.get("HMRC_VENDOR_ID", ""))
            vendor_password = os.environ.get("HMRC_GOVTLAK_VENDOR_PASSWORD", os.environ.get("HMRC_VENDOR_PASSWORD", ""))
            gateway_test = os.environ.get("HMRC_GOVTLAK_GATEWAY_TEST", "1")
            base_url = os.environ.get(
                "HMRC_GOVTLAK_BASE_URL",
                "https://test-transaction-engine.tax.service.gov.uk",
            )
            self._govtalk = GovTalkClient(
                vendor_id=vendor_id,
                vendor_password=vendor_password,
                base_url=base_url,
                gateway_test=gateway_test != "0",
            )
        return self._govtalk

    # ── REST: get_obligations (HMRC 有此 REST endpoint) ──

    async def get_obligations(
        self,
        ctref: str,
        from_date: date | None = None,
        to_date: date | None = None,
        status: str | None = None,
    ) -> list[CTObligation]:
        """获取 Corporation Tax 申报义务列表 (REST API)

        Args:
            ctref: Corporation Tax Reference (10 位数字)
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
        url = f"/company/corporation-tax/obligations/{ctref}"
        headers = self._build_headers(user_id=ctref)
        headers["Authorization"] = f"Bearer {token}"

        try:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            self._raise_for_hmrc_error(resp, "obligations")

        data = resp.json()
        obligations = []
        for ob in data.get("obligations", []):
            obligations.append(CTObligation(
                start=date.fromisoformat(ob["start"]),
                end=date.fromisoformat(ob["end"]),
                due=date.fromisoformat(ob["due"]),
                status=ob["status"],
                period_key=ob.get("periodKey", ""),
                received=date.fromisoformat(ob["received"]) if "received" in ob else None,
            ))
        return obligations

    # ── GovTalk XML: submit_return ──

    async def submit_return(
        self,
        ctref: str,
        body: dict,
        company_name: str = "",
        period_start: str = "",
        period_end: str = "",
    ) -> dict:
        """提交 Corporation Tax Return via GovTalk XML。

        之前用假 REST 路径 `/company/corporation-tax/returns`(不存在)。
        现在走真正的 HMRC Transaction Engine GovTalk 通道。

        如 body 包含 `wht_supplementary` 字段(由 UKCTAdapter.to_filing_format 自动附加),
        会在 CT600 XML 中嵌入 WHT supplementary entries (利息/特许权/股息预提税披露)。

        Args:
            ctref: Corporation Tax Reference
            body: CT600 数据 dict (line items from to_filing_format)
            company_name: 公司名称
            period_start: 会计期间开始 (YYYY-MM-DD)
            period_end: 会计期间结束 (YYYY-MM-DD)

        Returns:
            {"processingDate", "formBundleNumber", "chargeRefNumber", "correlationId"}
        """
        # 提取 WHT supplementary entries (可选)
        wht_entries = body.pop("wht_supplementary", None) or body.get("wht_supplementary")

        # 构建 CT600 body XML
        body_xml = build_ct600_body(
            ctref=ctref,
            company_name=company_name or body.get("company_name", ctref),
            period_start=period_start or body.get("period_start", ""),
            period_end=period_end or body.get("period_end", ""),
            line_map=body,
            wht_entries=wht_entries,
        )

        govtalk = self._get_govtalk()
        try:
            result = await govtalk.submit_and_poll(
                class_name=GovTalkClient.CLASS_CT600,
                body_xml=body_xml,
            )
        except GovTalkAuthError as exc:
            raise PermissionError(f"GovTalk authentication failed: {exc}") from exc
        except PermanentError as exc:
            raise ValueError(f"CT600 submission rejected by HMRC: {exc}") from exc

        return {
            "processingDate": result.get("processing_date", ""),
            "formBundleNumber": result.get("form_bundle_number", ""),
            "chargeRefNumber": result.get("receipt_id", ""),
            "correlationId": result.get("correlation_id", ""),
        }

    # ── GovTalk XML: get_return (poll) ──

    async def get_return(
        self,
        ctref: str,
        submission_id: str,
        correlation_id: str = "",
    ) -> CTReturnView:
        """查看已提交的 Corporation Tax Return。

        如果有 correlation_id,通过 GovTalk poll 查询最新状态。
        否则返回基本信息 (REST API 目前不支持查询已提交 CT return)。

        Args:
            ctref: Corporation Tax Reference
            submission_id: 提交时返回的 receipt_id
            correlation_id: 提交时返回的 correlation_id
        """
        if correlation_id:
            govtalk = self._get_govtalk()
            poll_result: dict = {}
            try:
                poll_result = await govtalk.poll(
                    class_name=GovTalkClient.CLASS_CT600,
                    correlation_id=correlation_id,
                )
            except (PermanentError, GovTalkAuthError) as exc:
                logger.warning(f"GovTalk poll failed for CT {ctref}: {exc}")

            return CTReturnView(
                submission_id=submission_id,
                processing_date=poll_result.get("processing_date", ""),
                form_bundle_number=poll_result.get("form_bundle_number", ""),
                charge_ref_number=poll_result.get("receipt_id", ""),
                correlation_id=correlation_id,
            )

        # 无 correlation_id — 无法 poll,返回基本视图
        return CTReturnView(
            submission_id=submission_id,
            processing_date="",
            form_bundle_number="",
            charge_ref_number="",
        )
