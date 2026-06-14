"""GovTalk XML Client — HMRC Transaction Engine 网关客户端

提供:
- GovTalkClient: 通用 GovTalk 消息客户端 (CT/PAYE/SDLT 共用)
- envelope 构建 (含 CRC32 IRmark)
- 异步提交 + 轮询 (submit → poll → accept/reject)

协议参考: docs/architecture/govtalk_client.md
"""

from __future__ import annotations

import asyncio
import logging
import uuid
import zlib
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import httpx

from .exceptions import GovTalkError, TransientError, PermanentError, AuthError

logger = logging.getLogger(__name__)

# ── XML 命名空间 ──

NS_GOV = "http://www.govtalk.gov.uk/CM/envelope"
NS_MAP = {"gov": NS_GOV}


class GovTalkClient:
    """GovTalk 消息客户端 — 通用,可供 CT/PAYE/SDLT 共用。

    Args:
        vendor_id: HMRC 软件开发商 Vendor ID (从 SDST 获取)
        vendor_password: Vendor Password
        base_url: Transaction Engine URL (默认测试环境)
        gateway_test: True = 测试模式 (GatewayTest=1), False = 生产
        max_poll_attempts: 轮询最大次数 (默认 60)
        poll_interval_base: 首次轮询间隔秒数 (默认 2)
        poll_interval_max: 最大轮询间隔秒数 (默认 30)
    """

    # 已知的消息 Class 标识符
    CLASS_CT600 = "HMRC-CT-CT600"
    CLASS_FPS = "HMRC-PAYE-RTI-FPS"
    CLASS_EPS = "HMRC-PAYE-RTI-EPS"
    CLASS_EYU = "HMRC-PAYE-RTI-EYU"
    CLASS_SDLT = "HMRC-SDLT-RETURN"

    def __init__(
        self,
        vendor_id: str,
        vendor_password: str,
        base_url: str = "https://test-transaction-engine.tax.service.gov.uk",
        gateway_test: bool = True,
        max_poll_attempts: int = 60,
        poll_interval_base: float = 2.0,
        poll_interval_max: float = 30.0,
    ):
        self.vendor_id = vendor_id
        self.vendor_password = vendor_password
        self.submit_url = f"{base_url.rstrip('/')}/submission"
        self.poll_url = f"{base_url.rstrip('/')}/poll"
        self.gateway_test = "1" if gateway_test else "0"
        self.max_poll_attempts = max_poll_attempts
        self.poll_interval_base = poll_interval_base
        self.poll_interval_max = poll_interval_max
        self._client: httpx.AsyncClient | None = None

    # ── HTTP client lifecycle ──

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ── Envelope building ──

    @staticmethod
    def compute_irmark(body_xml: str) -> str:
        """计算 IRmark — Body XML 内容的 CRC32 校验 (8 位大写 HEX)。

        HMRC 在收到消息后重新计算,比对一致才接受。
        """
        return format(zlib.crc32(body_xml.encode("utf-8")) & 0xFFFFFFFF, "08X")

    def build_envelope(
        self,
        class_name: str,
        body_xml: str,
        qualifier: str = "request",
        correlation_id: str | None = None,
    ) -> str:
        """构建完整的 GovTalkMessage XML envelope。

        Args:
            class_name: 消息类,如 "HMRC-CT-CT600"
            body_xml: 业务 XML (IRenvelope 内容,不含 <Body> 标签)
            qualifier: "request" (提交) | "poll" (轮询)
            correlation_id: UUID (默认自动生成)

        Returns:
            完整的 GovTalkMessage XML 字符串
        """
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        submit_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 计算 IRmark (Body 内容的 CRC32)
        irmark = self.compute_irmark(body_xml) if body_xml else ""

        # 构建 Body 段
        body_section = f"<Body>\n    {body_xml}\n  </Body>" if body_xml else "<Body />"

        # 构建 IRmark 段
        irmark_section = f"\n  <IRmark>{irmark}</IRmark>" if irmark else ""

        envelope = (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<GovTalkMessage xmlns="{NS_GOV}">\n'
            f"  <EnvelopeVersion>1.0</EnvelopeVersion>\n"
            f"  <Header>\n"
            f"    <MessageDetails>\n"
            f"      <Class>{_xml_escape(class_name)}</Class>\n"
            f"      <Qualifier>{_xml_escape(qualifier)}</Qualifier>\n"
            f"      <CorrelationID>{_xml_escape(correlation_id)}</CorrelationID>\n"
            f"      <SubmitTime>{submit_time}</SubmitTime>\n"
            f"      <GatewayTest>{self.gateway_test}</GatewayTest>\n"
            f"    </MessageDetails>\n"
            f"    <SenderDetails>\n"
            f"      <IDAuthentication>\n"
            f"        <SenderID>{_xml_escape(self.vendor_id)}</SenderID>\n"
            f"        <Authentication>\n"
            f"          <Method>clear</Method>\n"
            f"          <Value>{_xml_escape(self.vendor_password)}</Value>\n"
            f"        </Authentication>\n"
            f"      </IDAuthentication>\n"
            f"    </SenderDetails>\n"
            f"  </Header>\n"
            f"  {body_section}"
            f"{irmark_section}\n"
            f"</GovTalkMessage>"
        )
        return envelope

    # ── Submit ──

    async def submit(self, class_name: str, body_xml: str) -> dict:
        """提交 GovTalk 消息到 Transaction Engine。

        Args:
            class_name: 消息类,如 "HMRC-CT-CT600"
            body_xml: 业务 XML (IRenvelope 内部的内容)

        Returns:
            {"receipt_id": str, "poll_url": str, "correlation_id": str}

        Raises:
            PermanentError: 格式错误 / 校验失败
            AuthError: 认证失败
            TransientError: 网络问题 / HMRC 暂不可用
        """
        correlation_id = str(uuid.uuid4())
        envelope = self.build_envelope(
            class_name=class_name,
            body_xml=body_xml,
            qualifier="request",
            correlation_id=correlation_id,
        )

        client = await self._get_client()
        try:
            resp = await client.post(
                self.submit_url,
                content=envelope,
                headers={"Content-Type": "application/xml"},
            )
        except httpx.RequestError as exc:
            raise TransientError(f"Network error submitting to GovTalk: {exc}") from exc

        return self._parse_submit_response(resp, correlation_id)

    def _parse_submit_response(self, resp: httpx.Response, correlation_id: str) -> dict:
        """解析提交响应 XML,提取 receipt_id / poll_url / correlation_id。"""
        # HMRC 返回非 2xx 时的处理
        if resp.status_code == 401 or resp.status_code == 403:
            raise AuthError(f"GovTalk authentication failed (HTTP {resp.status_code})")

        if resp.status_code >= 500:
            raise TransientError(f"HMRC server error (HTTP {resp.status_code})")

        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as exc:
            raise PermanentError(f"Cannot parse GovTalk response XML: {exc}") from exc

        # 检查 GovTalk 级错误
        errors = self._extract_errors(root)
        if errors:
            error_text = "; ".join(errors)
            # 认证类错误
            if any("auth" in e.lower() or "credential" in e.lower() for e in errors):
                raise AuthError(error_text)
            raise PermanentError(error_text)

        # 提取成功字段
        receipt_id_el = root.find(".//gov:ReceiptID", NS_MAP)
        poll_url_el = root.find(".//gov:PollURL", NS_MAP)
        corr_id_el = root.find(".//gov:CorrelationID", NS_MAP)

        receipt_id = receipt_id_el.text.strip() if receipt_id_el is not None and receipt_id_el.text else ""
        poll_url = poll_url_el.text.strip() if poll_url_el is not None and poll_url_el.text else self.poll_url
        corr_id = corr_id_el.text.strip() if corr_id_el is not None and corr_id_el.text else correlation_id

        if not receipt_id and not poll_url:
            raise GovTalkError("Unexpected GovTalk submit response: no ReceiptID or PollURL found")

        return {
            "receipt_id": receipt_id,
            "poll_url": poll_url,
            "correlation_id": corr_id,
        }

    # ── Poll ──

    async def poll(self, class_name: str, correlation_id: str, poll_url: str | None = None) -> dict:
        """轮询提交结果。

        Args:
            class_name: 消息类 (与提交时一致)
            correlation_id: 提交时返回的 correlation_id
            poll_url: 提交响应返回的 Poll URL (默认使用 self.poll_url)

        Returns:
            {"status": "Pending"|"Accepted"|"Rejected", "message": str,
             "receipt_id": str, "form_bundle_number": str, "correlation_id": str}

        Raises:
            TransientError: 网络问题 / HMRC 暂不可用
            PermanentError: 被拒绝 (业务逻辑错误)
        """
        envelope = self.build_envelope(
            class_name=class_name,
            body_xml="",
            qualifier="poll",
            correlation_id=correlation_id,
        )

        target_url = poll_url or self.poll_url
        client = await self._get_client()

        try:
            resp = await client.post(
                target_url,
                content=envelope,
                headers={"Content-Type": "application/xml"},
            )
        except httpx.RequestError as exc:
            raise TransientError(f"Network error polling GovTalk: {exc}") from exc

        return self._parse_poll_response(resp, correlation_id)

    def _parse_poll_response(self, resp: httpx.Response, correlation_id: str) -> dict:
        """解析轮询响应 XML。"""
        if resp.status_code >= 500:
            raise TransientError(f"HMRC server error during poll (HTTP {resp.status_code})")

        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as exc:
            raise PermanentError(f"Cannot parse GovTalk poll response XML: {exc}") from exc

        # 检查错误
        errors = self._extract_errors(root)
        if errors:
            error_text = "; ".join(errors)
            raise PermanentError(error_text)

        # 提取 Result
        result_el = root.find(".//gov:Result", NS_MAP)
        status = result_el.text.strip() if result_el is not None and result_el.text else "Pending"

        # 提取 Message
        msg_el = root.find(".//gov:Message", NS_MAP)
        message = msg_el.text.strip() if msg_el is not None and msg_el.text else ""

        # 提取 Receipt 内详细信息 (Accepted 时)
        receipt_id = ""
        form_bundle_number = ""
        processing_date = ""

        receipt_el = root.find(".//gov:Receipt", NS_MAP)
        if receipt_el is not None:
            rid_el = receipt_el.find("gov:ReceiptID", NS_MAP)
            receipt_id = rid_el.text.strip() if rid_el is not None and rid_el.text else ""

            # ServiceSpecificMessage 里可能有 FormBundleNumber
            ssm_el = receipt_el.find(".//gov:ServiceSpecificMessage", NS_MAP)
            if ssm_el is not None:
                fbn_el = ssm_el.find("gov:FormBundleNumber", NS_MAP)
                form_bundle_number = fbn_el.text.strip() if fbn_el is not None and fbn_el.text else ""
                pd_el = ssm_el.find("gov:ProcessingDate", NS_MAP)
                processing_date = pd_el.text.strip() if pd_el is not None and pd_el.text else ""

        return {
            "status": status,
            "message": message,
            "receipt_id": receipt_id,
            "form_bundle_number": form_bundle_number,
            "processing_date": processing_date,
            "correlation_id": correlation_id,
        }

    # ── Submit + Poll until done ──

    async def submit_and_poll(self, class_name: str, body_xml: str) -> dict:
        """提交 GovTalk 消息并轮询直到最终结果。

        轮询策略: 首次 2s,指数退避到 30s,最多 60 次 (约 30 分钟)。

        Returns:
            同 poll() 的返回值 (status="Accepted"|"Rejected")
        """
        submit_result = await self.submit(class_name, body_xml)

        poll_url = submit_result["poll_url"]
        correlation_id = submit_result["correlation_id"]

        interval = self.poll_interval_base
        for attempt in range(self.max_poll_attempts):
            result = await self.poll(
                class_name=class_name,
                correlation_id=correlation_id,
                poll_url=poll_url,
            )

            if result["status"] == "Accepted":
                return result
            if result["status"] == "Rejected":
                raise PermanentError(
                    f"GovTalk submission rejected: {result['message']}"
                )

            # Pending — 等待后重试
            logger.info(
                f"GovTalk poll #{attempt+1}: Pending (correlation_id={correlation_id}), "
                f"waiting {interval:.1f}s"
            )
            await asyncio.sleep(interval)
            interval = min(interval * 1.5, self.poll_interval_max)

        raise TransientError(
            f"GovTalk polling timed out after {self.max_poll_attempts} attempts "
            f"(correlation_id={correlation_id})"
        )

    # ── Helpers ──

    @staticmethod
    def _extract_errors(root: ET.Element) -> list[str]:
        """从 GovTalk 响应 XML 提取错误信息。"""
        errors: list[str] = []
        # 尝试标准 GovTalk 错误结构
        for err_el in root.findall(".//gov:Errors/gov:Error", NS_MAP):
            text = err_el.text or ""
            if text.strip():
                errors.append(text.strip())
        # 也检查更常见的 <Error> (可能不在命名空间中)
        for err_el in root.findall(".//Error"):
            text = err_el.text or ""
            if text.strip():
                errors.append(text.strip())
        # 检查 <ErrorResponse> 结构
        for err_el in root.findall(".//gov:ErrorResponse/gov:Error", NS_MAP):
            text = err_el.text or ""
            if text.strip():
                errors.append(text.strip())
        return errors


# ── Module-level helpers ──

def _xml_escape(s: str) -> str:
    """Escape XML special characters in text content."""
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&apos;")
    )
