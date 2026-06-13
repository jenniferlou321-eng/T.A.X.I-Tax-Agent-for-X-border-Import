"""Shared HMRC Service base — common utilities for all UK tax-type API clients.

Provides:
- hmrc_mode() — single control point for mock vs live HMRC API calls
- tool_error() / tool_ok() — standardized MCP tool response builders
- HMRCService — abstract base class for HMRC API clients (httpx + OAuth + fraud headers)
"""

from __future__ import annotations

import logging
import os
from abc import ABC
from dataclasses import dataclass
from typing import Optional

import httpx

from backend.channels.oauth import OAuth2Manager
from backend.channels.fraud_headers import FraudPreventionHeaders

logger = logging.getLogger(__name__)


# ── Mock / Live mode ──

def hmrc_mode() -> str:
    """Single control point for all HMRC API calls across all tax types.

    Returns 'mock' (default) or 'live'. Controlled by the HMRC_MODE env var.
    Set HMRC_MODE=live to file real returns to HMRC (sandbox or production).
    """
    return os.environ.get("HMRC_MODE", "mock").lower()


# ── Standardized MCP tool response helpers ──

def tool_error(msg: str, detail: str = "") -> dict:
    """Build a standardised MCP tool error response."""
    payload: dict = {"success": False, "error": msg}
    if detail:
        payload["detail"] = detail
    return {"content": [{"type": "text", "text": __import__("json").dumps(payload)}], "is_error": True}


def tool_ok(data: dict) -> dict:
    """Build a standardised MCP tool success response."""
    return {"content": [{"type": "text", "text": __import__("json").dumps(data, indent=2)}]}


# ── HMRC error model ──

@dataclass
class HMRCError:
    """HMRC API error."""
    code: str
    message: str
    path: str = ""


# ── Abstract base class for HMRC API services ──

class HMRCService(ABC):
    """Abstract base for HMRC API clients.

    Provides:
    - httpx.AsyncClient lifecycle
    - OAuth2 bearer-token injection (via OAuth2Manager)
    - Fraud-prevention headers (HMRC Gov-Client-*)
    - HMRC error response parsing

    Subclasses:
    - HMRCVATService     (vat/hmrc_service.py)   — accept v1.0
    - HMRCCTService      (corporation_tax/...)     — accept v2.0
    - HMRCPAYEService    (paye/...)                — accept v2.0
    """

    def __init__(
        self,
        base_url: str,
        oauth: OAuth2Manager,
        fraud_headers: FraudPreventionHeaders | None = None,
        accept_header: str = "application/vnd.hmrc.1.0+json",
    ):
        self.base_url = base_url.rstrip("/")
        self.oauth = oauth
        self._fraud = fraud_headers
        self._accept_header = accept_header
        self._client: Optional[httpx.AsyncClient] = None

    # ── Client lifecycle ──

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30,
            )
        return self._client

    # ── Headers ──

    def _build_headers(self, user_id: str = "") -> dict[str, str]:
        """Build request headers including HMRC Accept header and fraud-prevention headers."""
        headers: dict[str, str] = {
            "Accept": self._accept_header,
            "Content-Type": "application/json",
        }
        if self._fraud:
            headers.update(self._fraud.build_headers(user_id=user_id))
        return headers

    # ── Authentication ──

    async def _authenticate(self) -> str:
        """Silently obtain a valid OAuth2 access token. Raises PermissionError on failure."""
        auth = await self.oauth.authenticate_silent()
        if not auth.success:
            raise PermissionError(f"HMRC auth failed: {auth.error}")
        return auth.token

    # ── Error handling ──

    def _parse_hmrc_errors(self, data: dict) -> list[HMRCError]:
        """Parse HMRC standard error response body."""
        errors: list[HMRCError] = []
        code = data.get("code", "UNKNOWN")
        message = data.get("message", "Unknown HMRC error")
        errors.append(HMRCError(code=code, message=message))

        # Field-level errors
        for err in data.get("errors", []):
            errors.append(HMRCError(
                code=err.get("code", ""),
                message=err.get("message", ""),
                path=err.get("path", ""),
            ))
        return errors

    def _raise_for_hmrc_error(self, resp: httpx.Response, operation: str) -> None:
        """Parse HMRC error response and raise ValueError with a human-readable message."""
        try:
            data = resp.json()
        except Exception:
            data = {}
        errors = self._parse_hmrc_errors(data)
        raise ValueError(
            f"HMRC {operation} error [{resp.status_code}]: "
            f"{errors[0].code} — {errors[0].message}"
        )
