"""ShopifyChannel — Shopify Admin API integration (REST + GraphQL).

Usage:
    channel = ShopifyChannel.from_env()
    health = await channel.health_check()
    orders = await channel.list_recent_orders(limit=10)

Requires env vars:
    SHOPIFY_SHOP_DOMAIN    — your-store.myshopify.com
    SHOPIFY_ACCESS_TOKEN   — shpat_xxx (Admin API access token)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional

import httpx

from backend.channels.ecommerce import (
    EcommerceChannel,
    EcommerceOrder,
    EcommerceHealth,
)

logger = logging.getLogger(__name__)

API_VERSION = "2024-01"


class ShopifyChannel(EcommerceChannel):
    """Shopify ecommerce platform integration.

    Uses Shopify Admin API access token for authentication.
    Supports both REST (health check, shop info) and GraphQL (orders query).
    """

    channel_name = "shopify"

    def __init__(
        self,
        shop_domain: str = "",
        access_token: str = "",
    ):
        self._shop_domain = shop_domain
        self._access_token = access_token
        self._rest_base = (
            f"https://{shop_domain}/admin/api/{API_VERSION}" if shop_domain else ""
        )
        self._graphql_url = (
            f"https://{shop_domain}/admin/api/{API_VERSION}/graphql.json"
            if shop_domain else ""
        )
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client

    @property
    def _headers(self) -> dict:
        return {
            "X-Shopify-Access-Token": self._access_token,
            "Content-Type": "application/json",
        }

    async def health_check(self) -> EcommerceHealth:
        """Verify connectivity by fetching shop info via REST API."""
        if not self._shop_domain or not self._access_token:
            return EcommerceHealth(
                connected=False,
                error="SHOPIFY_SHOP_DOMAIN and SHOPIFY_ACCESS_TOKEN not configured",
            )

        client = await self._get_client()
        try:
            resp = await client.get(
                f"{self._rest_base}/shop.json",
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()
            shop = data.get("shop", {})
            return EcommerceHealth(
                connected=True,
                store_name=shop.get("name", ""),
                plan_name=shop.get("plan_name", ""),
                country=shop.get("country_name", ""),
            )
        except Exception as e:
            logger.error("Shopify health check failed: %s", e)
            return EcommerceHealth(connected=False, error=str(e))

    async def list_recent_orders(self, limit: int = 10) -> list[EcommerceOrder]:
        """List recent orders via GraphQL Admin API."""
        if not self._access_token:
            logger.warning("Shopify: no access token configured, skipping")
            return []

        query = """
        query GetRecentOrders($first: Int!) {
            orders(first: $first, reverse: true) {
                edges {
                    node {
                        id
                        name
                        createdAt
                        displayFinancialStatus
                        totalPriceSet {
                            shopMoney {
                                amount
                                currencyCode
                            }
                        }
                        customer {
                            firstName
                            lastName
                            email
                        }
                    }
                }
            }
        }
        """
        client = await self._get_client()
        try:
            resp = await client.post(
                self._graphql_url,
                json={"query": query, "variables": {"first": min(limit, 50)}},
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error("Shopify GraphQL orders query failed: %s", e)
            return []

        if "errors" in data:
            logger.error("Shopify GraphQL errors: %s", data["errors"])
            return []

        edges = data.get("data", {}).get("orders", {}).get("edges", [])
        results = []
        for edge in edges:
            node = edge["node"]
            money = node.get("totalPriceSet", {}).get("shopMoney", {})
            customer = node.get("customer") or {}
            results.append(EcommerceOrder(
                order_id=node["id"],
                order_name=node.get("name", ""),
                created_at=datetime.fromisoformat(
                    node.get("createdAt", "2000-01-01T00:00:00Z")
                ),
                financial_status=node.get("displayFinancialStatus", ""),
                amount=money.get("amount", "0"),
                currency=money.get("currencyCode", ""),
                customer_name=(
                    f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip()
                ),
                customer_email=customer.get("email", ""),
                raw_data=node,
            ))
        return results

    async def get_order(self, order_id: str) -> Optional[EcommerceOrder]:
        """Get a single order by GraphQL ID."""
        query = """
        query GetOrder($id: ID!) {
            order(id: $id) {
                id
                name
                createdAt
                displayFinancialStatus
                totalPriceSet {
                    shopMoney {
                        amount
                        currencyCode
                    }
                }
                customer {
                    firstName
                    lastName
                    email
                }
            }
        }
        """
        client = await self._get_client()
        try:
            resp = await client.post(
                self._graphql_url,
                json={"query": query, "variables": {"id": order_id}},
                headers=self._headers,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error("Shopify get_order failed: %s", e)
            return None

        if "errors" in data:
            logger.error("Shopify get_order GraphQL errors: %s", data["errors"])
            return None

        node = data.get("data", {}).get("order")
        if not node:
            return None

        money = node.get("totalPriceSet", {}).get("shopMoney", {})
        customer = node.get("customer") or {}
        return EcommerceOrder(
            order_id=node["id"],
            order_name=node.get("name", ""),
            created_at=datetime.fromisoformat(
                node.get("createdAt", "2000-01-01T00:00:00Z")
            ),
            financial_status=node.get("displayFinancialStatus", ""),
            amount=money.get("amount", "0"),
            currency=money.get("currencyCode", ""),
            customer_name=(
                f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip()
            ),
            customer_email=customer.get("email", ""),
            raw_data=node,
        )

    @classmethod
    def from_env(cls) -> ShopifyChannel:
        """Factory: create ShopifyChannel from environment variables."""
        return cls(
            shop_domain=os.environ.get("SHOPIFY_SHOP_DOMAIN", ""),
            access_token=os.environ.get("SHOPIFY_ACCESS_TOKEN", ""),
        )
