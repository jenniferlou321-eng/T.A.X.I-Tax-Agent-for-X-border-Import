"""PayPal Sandbox API Test — verify connectivity to PayPal REST API.

Usage:
    cd /root/TAXI && python scripts/paypal_sandbox_test.py

Requires .env:
    PAYPAL_CLIENT_ID=xxx
    PAYPAL_CLIENT_SECRET=xxx
    PAYPAL_MODE=sandbox  (default: sandbox)

If credentials are not set, the script prints instructions and exits gracefully.
"""

import os
import sys
import json
import logging
from datetime import date, timedelta

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "sandbox")

BASE_URL = (
    "https://api-m.sandbox.paypal.com"
    if PAYPAL_MODE == "sandbox"
    else "https://api-m.paypal.com"
)


def get_access_token(client_id: str, client_secret: str) -> str | None:
    """Get OAuth2 access token from PayPal using client credentials grant."""
    url = f"{BASE_URL}/v1/oauth2/token"
    log.info("Requesting PayPal access token from %s", url)
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                url,
                data={"grant_type": "client_credentials"},
                auth=(client_id, client_secret),
                headers={"Accept": "application/json", "Accept-Language": "en_US"},
            )
            resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token")
        log.info("Got access token (expires in %s seconds)", data.get("expires_in"))
        return token
    except httpx.HTTPStatusError as e:
        log.error("Token request failed: %s", e)
        log.error("Response body: %s", e.response.text[:500])
        return None
    except Exception as e:
        log.error("Token request network error: %s", e)
        return None


def list_transactions(access_token: str) -> list[dict]:
    """List recent transactions from PayPal reporting API."""
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    url = (
        f"{BASE_URL}/v1/reporting/transactions"
        f"?start_date={start_date.isoformat()}T00:00:00-0000"
        f"&end_date={end_date.isoformat()}T23:59:59-0000"
        f"&fields=all"
        f"&page_size=10"
    )
    log.info("Fetching transactions: %s to %s", start_date, end_date)
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
        data = resp.json()
        txn_list = data.get("transaction_details", [])
        log.info(
            "Found %d transactions (total: %s, page: %s/%s)",
            len(txn_list),
            data.get("total_items", "?"),
            data.get("page", "?"),
            data.get("total_pages", "?"),
        )
        return txn_list
    except httpx.HTTPStatusError as e:
        log.error("Transaction fetch failed: %s", e)
        log.error("Response body: %s", e.response.text[:500])
        return []
    except Exception as e:
        log.error("Transaction fetch network error: %s", e)
        return []


def main():
    if not PAYPAL_CLIENT_ID or not PAYPAL_CLIENT_SECRET:
        log.warning(
            "PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET not set in .env.\n"
            "To get sandbox credentials:\n"
            "  1. Go to https://developer.paypal.com/\n"
            "  2. Log in → Dashboard → Sandbox → Accounts\n"
            "  3. My Apps & Credentials → Create App → Sandbox\n"
            "  4. Copy Client ID and Secret to .env:\n"
            "     PAYPAL_CLIENT_ID=your_client_id\n"
            "     PAYPAL_CLIENT_SECRET=your_client_secret\n"
            "     PAYPAL_MODE=sandbox\n"
        )
        sys.exit(0)

    log.info("=== PayPal %s Connectivity Test ===", PAYPAL_MODE.upper())

    # Step 1: Authenticate
    token = get_access_token(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET)
    if not token:
        log.error("FAILED: Could not obtain access token")
        sys.exit(1)

    log.info("PASSED: OAuth2 client_credentials grant")

    # Step 2: List transactions
    transactions = list_transactions(token)
    if transactions:
        log.info("=== Recent Transactions (showing up to 3) ===")
        for t in transactions[:3]:
            txn_info = t.get("transaction_info", {})
            print(json.dumps({
                "transaction_id": txn_info.get("transaction_id"),
                "event_code": txn_info.get("transaction_event_code"),
                "amount": txn_info.get("transaction_amount", {}).get("value"),
                "currency": txn_info.get("transaction_amount", {}).get("currency_code"),
                "fee": txn_info.get("fee_amount", {}).get("value"),
                "status": txn_info.get("transaction_status"),
                "date": txn_info.get("transaction_initiation_date"),
            }, indent=2))
    else:
        log.info(
            "No transactions found in sandbox account. "
            "This is expected for a new sandbox account with no test payments. "
            "Create test payments at https://developer.paypal.com/tools/sandbox/card-testing"
        )

    log.info("=== PayPal sandbox test complete ===")
    log.info("PASSED: PayPal API connectivity verified")


if __name__ == "__main__":
    main()
