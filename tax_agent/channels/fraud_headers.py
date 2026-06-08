"""FraudPreventionHeaders — HMRC Gov-Client-* 欺诈预防头"""

from __future__ import annotations

import hashlib
import platform
import socket
import uuid
from datetime import datetime, timezone
from typing import Optional


class FraudPreventionHeaders:
    """构建 HMRC 法律要求的欺诈预防 HTTP 头

    HMRC MTD APIs must include these headers:
    - Gov-Client-Connection-Method
    - Gov-Client-Device-ID
    - Gov-Client-User-IDs
    - Gov-Client-Timezone
    - Gov-Client-Local-IPs
    - Gov-Client-Public-IP
    - Gov-Client-Screens
    - Gov-Client-Window-Size
    - Gov-Vendor-Version
    - Gov-Vendor-License-ID
    - Gov-Vendor-Product-Name
    """

    def __init__(
        self,
        connection_method: str = "DESKTOP_APP_DIRECT",
        device_id: str | None = None,
        vendor_product: str = "TaxAgent Global",
        vendor_version: str = "0.1.0",
    ):
        self.connection_method = connection_method
        self.device_id = device_id or str(uuid.uuid4())
        self.vendor_product = vendor_product
        self.vendor_version = vendor_version

    def build_headers(
        self,
        user_id: str = "",
        local_ips: list[str] | None = None,
        public_ip: str | None = None,
        screen_width: int = 1920,
        screen_height: int = 1080,
        scaling_factor: float = 1.0,
        color_depth: int = 24,
        window_width: int = 1440,
        window_height: int = 900,
    ) -> dict[str, str]:
        """构建完整的欺诈预防头集合"""
        if local_ips is None:
            local_ips = self._get_local_ips()

        tz_offset = self._get_timezone_offset()

        return {
            "Gov-Client-Connection-Method": self.connection_method,
            "Gov-Client-Device-ID": self.device_id,
            "Gov-Client-User-IDs": f"user={user_id}" if user_id else "",
            "Gov-Client-Timezone": tz_offset,
            "Gov-Client-Local-IPs": ",".join(local_ips),
            "Gov-Client-Public-IP": public_ip or local_ips[0] if local_ips else "",
            "Gov-Client-Screens": (
                f"width={screen_width}&height={screen_height}"
                f"&scaling-factor={scaling_factor}"
                f"&colour-depth={color_depth}"
            ),
            "Gov-Client-Window-Size": (
                f"width={window_width}&height={window_height}"
            ),
            "Gov-Vendor-Version": self.vendor_version,
            "Gov-Vendor-License-ID": "",  # TODO: 获取 HMRC Vendor License ID
            "Gov-Vendor-Product-Name": self.vendor_product,
        }

    @staticmethod
    def _get_local_ips() -> list[str]:
        """获取本机 IP 地址"""
        try:
            hostname = socket.gethostname()
            return [socket.gethostbyname(hostname)]
        except Exception:
            return ["127.0.0.1"]

    @staticmethod
    def _get_timezone_offset() -> str:
        """获取时区偏移，格式: UTC+01:00"""
        now = datetime.now(timezone.utc)
        local = now.astimezone()
        offset = local.utcoffset()
        if offset is None:
            return "UTC+00:00"
        total_seconds = int(offset.total_seconds())
        hours, remainder = divmod(abs(total_seconds), 3600)
        minutes = remainder // 60
        sign = "+" if total_seconds >= 0 else "-"
        return f"UTC{sign}{hours:02d}:{minutes:02d}"