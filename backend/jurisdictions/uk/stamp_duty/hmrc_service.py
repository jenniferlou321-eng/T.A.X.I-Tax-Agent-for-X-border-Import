"""HMRC SDLT Service — 通过 GovTalk XML 提交 SDLT Return

SDLT 通过 HMRC Transaction Engine (GovTalk XML) 提交,不是 REST JSON API。
Class = "HMRC-SDLT-RETURN"
Endpoint = https://transaction-engine.tax.service.gov.uk/submission

SDLT 是基于交易的税种 (transaction-based),没有周期性申报义务。
每次房产交易单独提交一份 SDLT Return。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from backend.channels.govtalk import GovTalkClient, PermanentError, AuthError as GovTalkAuthError

from .govtalk_body import build_sdlt_body

logger = logging.getLogger(__name__)


@dataclass
class SDLTReturnView:
    """已提交的 SDLT Return"""
    submission_id: str
    processing_date: str
    form_bundle_number: str
    correlation_id: str = ""


class HMRCSDLTService:
    """HMRC SDLT API 客户端 — 通过 GovTalk XML 提交。

    SDLT 没有周期性义务 (get_obligations 不适用),只有:
    - submit_return: 提交 SDLT Return
    - get_return: 查询提交状态 (via GovTalk poll)
    """

    def __init__(
        self,
        govtalk_client: GovTalkClient | None = None,
    ):
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

    async def submit_return(
        self,
        utr: str,
        body: dict,
        effective_date: str = "",
        transaction_id: str = "",
    ) -> dict:
        """提交 SDLT Return via GovTalk XML。

        Args:
            utr: SDLT Unique Transaction Reference (13-17 位)
            body: SDLT 数据 dict (from to_filing_format)
            effective_date: 交易生效日期 (YYYY-MM-DD)
            transaction_id: 交易 ID (默认自动生成)

        Returns:
            {"processingDate", "formBundleNumber", "submissionId", "correlationId"}
        """
        import uuid
        if not transaction_id:
            transaction_id = f"SDLT-{utr}-{uuid.uuid4().hex[:8]}"

        body_xml = build_sdlt_body(
            utr=utr,
            transaction_id=transaction_id,
            effective_date=effective_date or body.get("effective_date", ""),
            line_map=body,
        )

        govtalk = self._get_govtalk()
        try:
            result = await govtalk.submit_and_poll(
                class_name=GovTalkClient.CLASS_SDLT,
                body_xml=body_xml,
            )
        except GovTalkAuthError as exc:
            raise PermissionError(f"GovTalk authentication failed: {exc}") from exc
        except PermanentError as exc:
            raise ValueError(f"SDLT submission rejected by HMRC: {exc}") from exc

        return {
            "processingDate": result.get("processing_date", ""),
            "formBundleNumber": result.get("form_bundle_number", ""),
            "submissionId": result.get("receipt_id", ""),
            "correlationId": result.get("correlation_id", ""),
        }

    async def get_return(
        self,
        utr: str,
        submission_id: str,
        correlation_id: str = "",
    ) -> SDLTReturnView:
        """查询已提交的 SDLT Return 状态。

        Args:
            utr: SDLT UTR
            submission_id: 提交时返回的 receipt_id
            correlation_id: 提交时返回的 correlation_id
        """
        if correlation_id:
            govtalk = self._get_govtalk()
            poll_result: dict = {}
            try:
                poll_result = await govtalk.poll(
                    class_name=GovTalkClient.CLASS_SDLT,
                    correlation_id=correlation_id,
                )
            except (PermanentError, GovTalkAuthError) as exc:
                logger.warning(f"GovTalk poll failed for SDLT {utr}: {exc}")

            return SDLTReturnView(
                submission_id=submission_id,
                processing_date=poll_result.get("processing_date", ""),
                form_bundle_number=poll_result.get("form_bundle_number", ""),
                correlation_id=correlation_id,
            )

        return SDLTReturnView(
            submission_id=submission_id,
            processing_date="",
            form_bundle_number="",
        )
