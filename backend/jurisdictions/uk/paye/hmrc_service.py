"""HMRC PAYE (RTI) Service — 通过 GovTalk XML 提交 FPS/EPS/EYU

PAYE/RTI 通过 HMRC Transaction Engine (GovTalk XML) 提交,不是 REST JSON API。
Class 标识:
- FPS: "HMRC-PAYE-RTI-FPS"
- EPS: "HMRC-PAYE-RTI-EPS"
- EYU: "HMRC-PAYE-RTI-EYU"

本服务:
- get_obligations: 仍走 REST API (HMRC 有此 endpoint)
- submit_fps/eps/eyu: 改走 GovTalk XML (之前用的是不存在的假 REST 路径)
- get_fps: 通过 GovTalk poll 查询提交状态
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

from .govtalk_body import build_fps_body, build_eps_body, build_eyu_body

logger = logging.getLogger(__name__)


@dataclass
class PAYEObligation:
    """PAYE 申报义务"""
    start: date
    end: date
    due: date
    status: str          # "O" = Open, "F" = Fulfilled
    period_key: str
    submission_type: str = "FPS"   # "FPS" or "EPS"
    received: Optional[date] = None


@dataclass
class PAYEReturnView:
    """已提交的 PAYE FPS/EPS"""
    submission_id: str
    transaction_id: str
    processing_date: str
    submission_type: str = "FPS"
    correlation_id: str = ""


class HMRCPAYEService(HMRCService):
    """HMRC Real Time Information (RTI) for PAYE — 混合模式

    - get_obligations: REST JSON (HMRC 有此 endpoint)
    - submit_fps/eps/eyu: GovTalk XML (走 Transaction Engine)
    - get_fps: GovTalk poll 查询
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
        empref: str,
        from_date: date | None = None,
        to_date: date | None = None,
        status: str | None = None,
    ) -> list[PAYEObligation]:
        """获取 PAYE 申报义务列表 (REST API)

        Args:
            empref: Employer PAYE Reference (如 "123/AB45678")
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
        url = f"/employers/paye/employer/{empref}/obligations"
        headers = self._build_headers(user_id=empref)
        headers["Authorization"] = f"Bearer {token}"

        try:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError:
            self._raise_for_hmrc_error(resp, "obligations")

        data = resp.json()
        obligations = []
        for ob in data.get("obligations", []):
            obligations.append(PAYEObligation(
                start=date.fromisoformat(ob["start"]),
                end=date.fromisoformat(ob["end"]),
                due=date.fromisoformat(ob["due"]),
                status=ob["status"],
                period_key=ob.get("periodKey", ""),
                submission_type=ob.get("type", "FPS"),
                received=date.fromisoformat(ob["received"]) if "received" in ob else None,
            ))
        return obligations

    # ── GovTalk XML: submit FPS ──

    async def submit_fps(
        self,
        empref: str,
        body: dict,
        tax_year: str = "",
        period_start: str = "",
        period_end: str = "",
    ) -> dict:
        """提交 Full Payment Submission (FPS) via GovTalk XML。

        之前用假 REST 路径 `/employers/paye/employer/{empref}/fps`(不存在)。
        现在走真正的 HMRC Transaction Engine GovTalk 通道。

        Args:
            empref: Employer PAYE Reference
            body: FPS 数据 dict
            tax_year: 税年 (如 "2024-25")
            period_start: 期间开始 (YYYY-MM-DD)
            period_end: 期间结束 (YYYY-MM-DD)

        Returns:
            {"submissionId", "transactionId", "processingDate", "correlationId"}
        """
        body_xml = build_fps_body(
            empref=empref,
            tax_year=tax_year or body.get("tax_year", ""),
            period_start=period_start or body.get("period_start", ""),
            period_end=period_end or body.get("period_end", ""),
            line_map=body,
        )

        govtalk = self._get_govtalk()
        try:
            result = await govtalk.submit_and_poll(
                class_name=GovTalkClient.CLASS_FPS,
                body_xml=body_xml,
            )
        except GovTalkAuthError as exc:
            raise PermissionError(f"GovTalk authentication failed: {exc}") from exc
        except PermanentError as exc:
            raise ValueError(f"FPS submission rejected by HMRC: {exc}") from exc

        return {
            "submissionId": result.get("receipt_id", ""),
            "transactionId": result.get("form_bundle_number", ""),
            "processingDate": result.get("processing_date", ""),
            "correlationId": result.get("correlation_id", ""),
        }

    # ── GovTalk XML: submit EPS ──

    async def submit_eps(
        self,
        empref: str,
        body: dict,
        tax_year: str = "",
        period_start: str = "",
        period_end: str = "",
    ) -> dict:
        """提交 Employer Payment Summary (EPS) via GovTalk XML。

        EPS 用于报告调整项：CIS 扣减、学徒税、雇佣津贴等。

        Args:
            empref: Employer PAYE Reference
            body: EPS 数据 dict
            tax_year: 税年
            period_start: 期间开始
            period_end: 期间结束

        Returns:
            同 submit_fps
        """
        body_xml = build_eps_body(
            empref=empref,
            tax_year=tax_year or body.get("tax_year", ""),
            period_start=period_start or body.get("period_start", ""),
            period_end=period_end or body.get("period_end", ""),
            line_map=body,
        )

        govtalk = self._get_govtalk()
        try:
            result = await govtalk.submit_and_poll(
                class_name=GovTalkClient.CLASS_EPS,
                body_xml=body_xml,
            )
        except GovTalkAuthError as exc:
            raise PermissionError(f"GovTalk authentication failed: {exc}") from exc
        except PermanentError as exc:
            raise ValueError(f"EPS submission rejected by HMRC: {exc}") from exc

        return {
            "submissionId": result.get("receipt_id", ""),
            "transactionId": result.get("form_bundle_number", ""),
            "processingDate": result.get("processing_date", ""),
            "correlationId": result.get("correlation_id", ""),
        }

    # ── GovTalk XML: submit EYU ──

    async def submit_eyu(
        self,
        empref: str,
        body: dict,
        tax_year: str = "",
        period_start: str = "",
        period_end: str = "",
    ) -> dict:
        """提交 Earlier Year Update (EYU) via GovTalk XML。

        用于更正上一税务年度的 FPS 数据。

        Args:
            empref: Employer PAYE Reference
            body: EYU 数据 dict
            tax_year: 被更正的税年
            period_start: 期间开始
            period_end: 期间结束

        Returns:
            同 submit_fps
        """
        body_xml = build_eyu_body(
            empref=empref,
            tax_year=tax_year or body.get("tax_year", ""),
            period_start=period_start or body.get("period_start", ""),
            period_end=period_end or body.get("period_end", ""),
            line_map=body,
        )

        govtalk = self._get_govtalk()
        try:
            result = await govtalk.submit_and_poll(
                class_name=GovTalkClient.CLASS_EYU,
                body_xml=body_xml,
            )
        except GovTalkAuthError as exc:
            raise PermissionError(f"GovTalk authentication failed: {exc}") from exc
        except PermanentError as exc:
            raise ValueError(f"EYU submission rejected by HMRC: {exc}") from exc

        return {
            "submissionId": result.get("receipt_id", ""),
            "transactionId": result.get("form_bundle_number", ""),
            "processingDate": result.get("processing_date", ""),
            "correlationId": result.get("correlation_id", ""),
        }

    # ── GovTalk XML: get_fps (poll) ──

    async def get_fps(
        self,
        empref: str,
        submission_id: str,
        correlation_id: str = "",
    ) -> PAYEReturnView:
        """查看已提交的 FPS/EPS。

        如果有 correlation_id,通过 GovTalk poll 查询最新状态。

        Args:
            empref: Employer PAYE Reference
            submission_id: 提交时返回的 receipt_id
            correlation_id: 提交时返回的 correlation_id
        """
        if correlation_id:
            govtalk = self._get_govtalk()
            poll_result: dict = {}
            try:
                poll_result = await govtalk.poll(
                    class_name=GovTalkClient.CLASS_FPS,
                    correlation_id=correlation_id,
                )
            except (PermanentError, GovTalkAuthError) as exc:
                logger.warning(f"GovTalk poll failed for PAYE {empref}: {exc}")

            return PAYEReturnView(
                submission_id=submission_id,
                transaction_id=poll_result.get("form_bundle_number", ""),
                processing_date=poll_result.get("processing_date", ""),
                correlation_id=correlation_id,
            )

        # 无 correlation_id — 返回基本视图
        return PAYEReturnView(
            submission_id=submission_id,
            transaction_id="",
            processing_date="",
        )
