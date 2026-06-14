"""PayPalChannel — PayPal REST API integration via client credentials grant.

Usage:
    channel = PayPalChannel.from_env()
    if await channel.health_check():
        txns = await channel.list_transactions("2026-01-01", "2026-03-31")

Requires env vars:
    PAYPAL_CLIENT_ID      — from PayPal Developer Dashboard
    PAYPAL_CLIENT_SECRET  — from PayPal Developer Dashboard
    PAYPAL_MODE           — "sandbox" (default) or "live"
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from backend.channels.payment import (
    PaymentChannel,
    PaymentAuthResult,
    PaymentTransaction,
)

logger = logging.getLogger(__name__)


class PayPalChannel(PaymentChannel):
    """PayPal payment gateway integration.

    Uses client_credentials grant for server-to-server API access.
    Auto-caches access token until expiry (with 60s safety buffer).

    Sandbox: https://api-m.sandbox.paypal.com
    Live:    https://api-m.paypal.com
    """

    channel_name = "paypal"

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        mode: str = "sandbox",
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._mode = mode
        self._base_url = (
            "https://api-m.sandbox.paypal.com"
            if mode == "sandbox"
            else "https://api-m.paypal.com"
        )
        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=30,
            )
        return self._client

    async def authenticate(self) -> PaymentAuthResult:
        """Obtain OAuth2 access token via client_credentials grant.

        Returns cached token if still valid (60s buffer before expiry).
        """
        if not self._client_id or not self._client_secret:
            return PaymentAuthResult(
                success=False,
                error="PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET not configured",
            )

        # Return cached token if still valid (60s buffer)
        if self._access_token and time.time() < self._expires_at - 60:
            return PaymentAuthResult(
                success=True,
                access_token=self._access_token,
                expires_at=datetime.fromtimestamp(self._expires_at, tz=timezone.utc),
            )

        client = await self._get_client()
        try:
            resp = await client.post(
                "/v1/oauth2/token",
                data={"grant_type": "client_credentials"},
                auth=(self._client_id, self._client_secret),
                headers={"Accept": "application/json", "Accept-Language": "en_US"},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("PayPal auth failed (HTTP %s): %s", e.response.status_code, e)
            return PaymentAuthResult(success=False, error=str(e))
        except Exception as e:
            logger.error("PayPal auth network error: %s", e)
            return PaymentAuthResult(success=False, error=str(e))

        self._access_token = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 32400)
        return PaymentAuthResult(
            success=True,
            access_token=self._access_token,
            expires_at=datetime.fromtimestamp(self._expires_at, tz=timezone.utc),
        )

    async def list_transactions(
        self, start_date: str, end_date: str, page_size: int = 50
    ) -> list[PaymentTransaction]:
        """List transactions from PayPal reporting API.

        Args:
            start_date: ISO format datetime string, e.g. "2026-01-01T00:00:00-0000"
            end_date: ISO format datetime string, e.g. "2026-03-31T23:59:59-0000"
            page_size: Max 100 per PayPal API limit.
        """
        auth = await self.authenticate()
        if not auth.success:
            logger.warning("PayPal list_transactions: auth failed — %s", auth.error)
            return []

        client = await self._get_client()
        try:
            resp = await client.get(
                "/v1/reporting/transactions",
                params={
                    "start_date": start_date,
                    "end_date": end_date,
                    "fields": "all",
                    "page_size": min(page_size, 100),
                },
                headers={
                    "Authorization": f"Bearer {auth.access_token}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error("PayPal transaction fetch failed: %s", e)
            return []

        results = []
        for detail in data.get("transaction_details", []):
            info = detail.get("transaction_info", {})
            amount_info = info.get("transaction_amount", {})
            results.append(PaymentTransaction(
                transaction_id=info.get("transaction_id", ""),
                amount=amount_info.get("value", "0"),
                currency=amount_info.get("currency_code", ""),
                status=info.get("transaction_status", "unknown"),
                timestamp=datetime.fromisoformat(
                    info.get("transaction_initiation_date", "2000-01-01T00:00:00+0000")
                ),
                payer_email=detail.get("payer_info", {}).get("payer_email", ""),
                raw_data=detail,
            ))
        return results

    async def health_check(self) -> bool:
        """Verify PayPal API is reachable and credentials are valid."""
        auth = await self.authenticate()
        return auth.success

    @classmethod
    def from_env(cls) -> PayPalChannel:
        """Factory: create PayPalChannel from environment variables."""
        return cls(
            client_id=os.environ.get("PAYPAL_CLIENT_ID", ""),
            client_secret=os.environ.get("PAYPAL_CLIENT_SECRET", ""),
            mode=os.environ.get("PAYPAL_MODE", "sandbox"),
        )
