"""HMRC Sandbox OAuth Full Automation

Steps:
1. Open authorize URL in browser
2. Login with test user credentials
3. Grant authority
4. Capture redirect code
5. Exchange code for token via backend
6. Test obligations
7. Test VAT Return submit
"""

import time
import requests
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright

# Config
BACKEND_URL = "http://localhost:8765"
TEST_USER_ID = "664155084356"
TEST_PASSWORD = "6ah0eYT1NlJ4"
TEST_VRN = "960606228"


def get_auth_url():
    r = requests.get(f"{BACKEND_URL}/api/channel/uk/vat/auth-url")
    r.raise_for_status()
    return r.json()["auth_url"]


def automate_oauth():
    auth_url = get_auth_url()
    print("=" * 70)
    print("HMRC Sandbox OAuth Automation")
    print("=" * 70)
    print(f"\nAuthorize URL: {auth_url[:120]}...")

    captured_code = {"value": None}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context()
        page = context.new_page()

        # Capture navigation to localhost:8080
        def on_navigate(frame):
            url = frame.url
            if "localhost:8080" in url and "code=" in url:
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                code = params.get("code", [None])[0]
                if code:
                    captured_code["value"] = code
                    print(f"\n✅ Captured authorization code: {code[:20]}...")

        page.on("framenavigated", on_navigate)

        try:
            # Step 1: Open authorize URL
            print("\n→ Opening authorize URL...")
            page.goto(auth_url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(2)

            current_url = page.url
            print(f"  Current URL: {current_url[:100]}")

            # Step 2: Handle login page
            if "sign-in" in current_url or "bas-gateway" in current_url:
                print("\n→ On Government Gateway sign-in page")

                # Fill credentials
                try:
                    page.fill('input[name="userId"], input[name="username"], #userId', TEST_USER_ID)
                    page.fill('input[name="password"], #password', TEST_PASSWORD)
                    time.sleep(0.5)
                    page.click('button[type="submit"], input[type="submit"], #signin')
                    print("  Submitted login credentials")
                    time.sleep(3)
                except Exception as e:
                    print(f"  Login form error: {e}")
                    # Try alternative selectors
                    try:
                        page.fill('input#userId', TEST_USER_ID)
                        page.fill('input#password', TEST_PASSWORD)
                        page.click('button.govuk-button')
                        time.sleep(3)
                    except Exception as e2:
                        print(f"  Alternative login error: {e2}")

                current_url = page.url
                print(f"  After login URL: {current_url[:120]}")

            # Step 3: Handle grant authority page
            page_content = page.content()
            if "grant" in page_content.lower() or "authority" in page_content.lower() or "authorise" in page_content.lower():
                print("\n→ On grant authority page")
                try:
                    # Click grant/authorise button
                    page.click('button[type="submit"], input[type="submit"]')
                    print("  Clicked grant authority")
                    time.sleep(3)
                except Exception as e:
                    print(f"  Grant button error: {e}")

            # Step 4: Check for code in URL or page
            current_url = page.url
            print(f"\n  Final URL: {current_url[:150]}")

            if "localhost:8080" in current_url and "code=" in current_url:
                parsed = urlparse(current_url)
                params = parse_qs(parsed.query)
                captured_code["value"] = params.get("code", [None])[0]

            # If code not in URL, check page content
            if not captured_code["value"]:
                body_text = page.inner_text("body") if page.locator("body").count() else ""
                if "code" in body_text.lower():
                    import re
                    m = re.search(r'\b([A-Za-z0-9_-]{20,})\b', body_text)
                    if m:
                        captured_code["value"] = m.group(1)
                        print(f"  Found code in page text")

            # Check for errors
            body_text = page.inner_text("body") if page.locator("body").count() else ""
            if "invalid_request" in body_text or "error" in body_text.lower():
                print(f"\n⚠️  Error page detected:")
                print(f"  {body_text[:300]}")

        except Exception as e:
            print(f"\n❌ Browser automation error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

    return captured_code["value"]


def exchange_code(code: str):
    print("\n→ Exchanging code for token...")
    r = requests.post(
        f"{BACKEND_URL}/api/channel/uk/vat/callback",
        json={"code": code, "state": ""}
    )
    print(f"  Status: {r.status_code}")
    return r.json()


def test_obligations():
    print("\n→ Testing obligations endpoint...")
    r = requests.get(
        f"{BACKEND_URL}/api/filings/obligations/uk/vat?vrn={TEST_VRN}",
        timeout=30
    )
    print(f"  Status: {r.status_code}")
    try:
        data = r.json()
        if "obligations" in data:
            print(f"  ✅ Found {len(data['obligations'])} obligations")
            for ob in data["obligations"]:
                print(f"     {ob['period_key']}: {ob['start']} - {ob['end']} ({ob['status']})")
        else:
            print(f"  Response: {data}")
    except:
        print(f"  Body: {r.text[:300]}")
    return r.json() if r.status_code == 200 else None


def test_submit():
    print("\n→ Testing VAT Return submit...")
    payload = {
        "jurisdiction": "uk",
        "tax_type": "vat",
        "period": {
            "year": 2026,
            "period_type": "quarterly",
            "period_key": "24A1",
            "start_date": "2026-01-01",
            "end_date": "2026-03-31"
        },
        "taxpayer": {
            "name": "Company I4NLA6",
            "tax_id": TEST_VRN,
            "tax_id_type": "vrn"
        },
        "data": [
            {"category": "vat_due_sales", "amount": 200.00, "currency": "GBP"},
            {"category": "vat_reclaimed_purchases", "amount": 100.00, "currency": "GBP"},
            {"category": "total_sales_ex_vat", "amount": 1000, "currency": "GBP"},
            {"category": "total_purchases_ex_vat", "amount": 500, "currency": "GBP"}
        ]
    }
    r = requests.post(
        f"{BACKEND_URL}/api/filings/submit",
        json=payload,
        timeout=60
    )
    print(f"  Status: {r.status_code}")
    data = r.json()
    print(f"  Filing ID: {data.get('filing_id')}")
    print(f"  Status: {data.get('status')}")
    if data.get('errors'):
        for e in data['errors']:
            print(f"  Error: [{e['code']}] {e['message']}")
    if data.get('receipt'):
        print(f"  Receipt: {data['receipt']}")
    return data


if __name__ == "__main__":
    code = automate_oauth()
    if not code:
        print("\n❌ Failed to get authorization code")
        exit(1)

    print(f"\n{'=' * 70}")
    print("Step 2: Exchange code for token")
    print("=" * 70)
    token_result = exchange_code(code)
    print(f"Token result: {token_result}")

    if not token_result.get("success"):
        print("\n❌ Token exchange failed")
        exit(1)

    print(f"\n{'=' * 70}")
    print("Step 3: Test HMRC API calls")
    print("=" * 70)

    obligations = test_obligations()

    print(f"\n{'=' * 70}")
    print("Step 4: Test VAT Return submission")
    print("=" * 70)

    submit_result = test_submit()

    print(f"\n{'=' * 70}")
    print("Test Complete!")
    print("=" * 70)
