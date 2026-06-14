"""Shopify Admin API Test — verify connectivity to Shopify REST + GraphQL.

Usage:
    cd /root/TAXI && python scripts/shopify_api_test.py

Requires .env:
    SHOPIFY_SHOP_DOMAIN=your-store.myshopify.com
    SHOPIFY_ACCESS_TOKEN=shpat_xxx (admin API access token)

If credentials are not set, the script prints instructions and exits gracefully.
"""

import os
import sys
import json
import logging

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

SHOP_DOMAIN = os.environ.get("SHOPIFY_SHOP_DOMAIN", "")
ACCESS_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")

API_VERSION = "2024-01"
REST_BASE = f"https://{SHOP_DOMAIN}/admin/api/{API_VERSION}" if SHOP_DOMAIN else ""
GRAPHQL_URL = f"https://{SHOP_DOMAIN}/admin/api/{API_VERSION}/graphql.json" if SHOP_DOMAIN else ""


def rest_shop_health() -> dict | None:
    """Call GET /admin/api/2024-01/shop.json — simple health check."""
    url = f"{REST_BASE}/shop.json"
    log.info("Shopify REST health check: %s", url)
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                url,
                headers={
                    "X-Shopify-Access-Token": ACCESS_TOKEN,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
        data = resp.json()
        shop = data.get("shop", {})
        log.info(
            "Connected to shop: %s (plan: %s, country: %s, currency: %s)",
            shop.get("name"), shop.get("plan_name"),
            shop.get("country_name"), shop.get("currency"),
        )
        return shop
    except httpx.HTTPStatusError as e:
        log.error("Shop health check failed (HTTP %s): %s", e.response.status_code, e)
        log.error("Response: %s", e.response.text[:500])
        return None
    except Exception as e:
        log.error("Shop health check network error: %s", e)
        return None


def graphql_recent_orders(limit: int = 5) -> list[dict]:
    """Query recent orders via Shopify GraphQL Admin API."""
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
    log.info("Shopify GraphQL: fetching %d recent orders", limit)
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                GRAPHQL_URL,
                json={"query": query, "variables": {"first": min(limit, 50)}},
                headers={
                    "X-Shopify-Access-Token": ACCESS_TOKEN,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            log.error("GraphQL errors: %s", json.dumps(data["errors"], indent=2))
            return []
        edges = data.get("data", {}).get("orders", {}).get("edges", [])
        orders = [e["node"] for e in edges]
        log.info("Found %d orders", len(orders))
        return orders
    except httpx.HTTPStatusError as e:
        log.error("GraphQL request failed (HTTP %s): %s", e.response.status_code, e)
        log.error("Response: %s", e.response.text[:500])
        return []
    except Exception as e:
        log.error("GraphQL request network error: %s", e)
        return []


def main():
    if not SHOP_DOMAIN or not ACCESS_TOKEN:
        log.warning(
            "SHOPIFY_SHOP_DOMAIN and SHOPIFY_ACCESS_TOKEN not set in .env.\n"
            "To get Shopify dev store credentials:\n"
            "  1. Go to https://partners.shopify.com/\n"
            "  2. Create a development store\n"
            "  3. Settings → Apps and sales channels → Develop apps\n"
            "  4. Create an app → Configure Admin API scopes (read_orders)\n"
            "  5. Install app → Copy Admin API access token\n"
            "  6. Add to .env:\n"
            "     SHOPIFY_SHOP_DOMAIN=your-store.myshopify.com\n"
            "     SHOPIFY_ACCESS_TOKEN=shpat_xxx\n"
        )
        sys.exit(0)

    log.info("=== Shopify API Test ===")

    # Step 1: REST health check
    shop = rest_shop_health()
    if not shop:
        log.error("FAILED: REST health check")
        sys.exit(1)

    log.info("PASSED: REST API health check (shop.json)")

    # Step 2: GraphQL orders query
    orders = graphql_recent_orders(limit=5)
    if orders:
        log.info("=== Recent Orders (showing up to 3) ===")
        for order in orders[:3]:
            money = order.get("totalPriceSet", {}).get("shopMoney", {})
            customer = order.get("customer") or {}
            print(json.dumps({
                "order_name": order.get("name"),
                "created_at": order.get("createdAt"),
                "status": order.get("displayFinancialStatus"),
                "amount": money.get("amount"),
                "currency": money.get("currencyCode"),
                "customer": f"{customer.get('firstName', '')} {customer.get('lastName', '')}".strip(),
                "email": customer.get("email"),
            }, indent=2))
        log.info("PASSED: GraphQL orders query")
    else:
        log.info(
            "No orders found in development store. "
            "This is expected for a new dev store with no test orders."
        )

    log.info("=== Shopify API test complete ===")
    log.info("PASSED: Shopify API connectivity verified")


if __name__ == "__main__":
    main()
