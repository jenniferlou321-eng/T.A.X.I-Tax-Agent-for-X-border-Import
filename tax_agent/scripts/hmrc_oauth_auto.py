"""HMRC Sandbox OAuth Automation — 使用 Playwright 自动完成授权流程

Test User Credentials (sandbox):
  User ID:  664155084356
  Password:  6ah0eYT1NlJ4
  VRN:       960606228

Application:
  Client ID:     2U9ktG6rDRDpxUG1kNJ4Mld8y6Fl
  Client Secret: ef505ced-ee2c-4797-85b6-c673de1e9121
  Sandbox:       true
  Redirect URI:  urn:ietf:wg:oauth:2.0:oob  (在沙盒中已废弃 - 但尝试)
"""

import sys
import time
import requests
from playwright.sync_api import sync_playwright

CLIENT_ID = "2U9ktG6rDRDpxUG1kNJ4Mld8y6Fl"
CLIENT_SECRET = "ef505ced-ee2c-4797-85b6-c673de1e9121"
TEST_USER_ID = "664155084356"
TEST_PASSWORD = "6ah0eYT1NlJ4"
TEST_VRN = "960606228"
BACKEND_URL = "http://localhost:8765"


def get_auth_url_via_backend():
    """通过后端获取 OAuth authorize URL"""
    r = requests.get(f"{BACKEND_URL}/api/channel/uk/vat/auth-url")
    r.raise_for_status()
    return r.json()["auth_url"]


def automate_oob_oauth():
    """
    尝试用 Playwright 自动化 urn:ietf:wg:oauth:2.0:oob
    一些 HMRC 沙盒工具会显示一个显示 code 的页面
    """
    print("=" * 70)
    print("HMRC Sandbox OAuth Automation (OOB mode)")
    print("=" * 70)

    # 尝试不同的 redirect_uri 看哪个能用
    redirect_candidates = [
        "urn:ietf:wg:oauth:2.0:oob",
        "urn:ietf:wg:oauth:2.0:oob:auto",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:9000",
    ]

    base = "https://test-api.service.hmrc.gov.uk/oauth/authorize"
    for uri in redirect_candidates:
        url = f"{base}?response_type=code&client_id={CLIENT_ID}&redirect_uri={uri}&scope=read:vat+write:vat"
        r = requests.get(url, allow_redirects=False, timeout=10)
        if r.status_code == 301:
            r2 = requests.get(r.headers["Location"], allow_redirects=True, timeout=10)
            if r2.status_code == 200:
                print(f"  Redirect URI '{uri}' accepted — final URL: {r2.url}")
                return uri
            elif r2.status_code == 400:
                err = r2.json().get("error_description", "")
                print(f"  '{uri}' rejected: {err[:80]}")
    return None


def automate_with_browser():
    """
    用浏览器自动化完成 OAuth 流程
    - 尝试 oob (会显示 code 页面)
    - 抓取页面中的 authorization code
    """
    print("\n" + "=" * 70)
    print("Attempting browser-based OAuth flow")
    print("=" * 70)

    base = "https://test-api.service.hmrc.gov.uk/oauth/authorize"
    url = f"{base}?response_type=code&client_id={CLIENT_ID}&redirect_uri=urn:ietf:wg:oauth:2.0:oob&scope=read:vat+write:vat"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            context = browser.new_context()
            page = context.new_page()

            # Capture the final URL or page text after redirects
            final_url = {"value": None}
            captured_text = {"value": None}

            def on_response(response):
                if "code=" in response.url:
                    final_url["value"] = response.url

            page.on("response", on_response)
            page.on("framenavigated", lambda f: final_url.update(value=f.url) if f == page.main_frame else None)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
            except Exception as e:
                print(f"  Navigation error: {e}")

            # Wait for the page to settle
            time.sleep(2)

            # Get the current state
            current_url = page.url
            current_text = page.inner_text("body") if page.locator("body").count() else ""
            print(f"  Current URL after navigation: {current_url[:150]}")
            print(f"  Page text (first 400): {current_text[:400]}")

            # Check if we got an error page
            if "invalid_request" in current_text or "redirect_uri" in current_text.lower():
                print("\n  ❌ redirect_uri 'oob' is rejected by HMRC sandbox")
                print("  The Application must have a registered redirect URI on Developer Hub")
                return None

            # Check if we got a sign-in form
            if "Government Gateway" in current_text or "User ID" in current_text or "userId" in page.content():
                print("\n  → On Government Gateway sign-in page")
                # Fill in credentials
                try:
                    page.fill('input[name="userId"], input[name="username"], #userId', TEST_USER_ID)
                    page.fill('input[name="password"], #password', TEST_PASSWORD)
                    time.sleep(0.5)
                    page.click('input[type="submit"], button[type="submit"], #signin, .button')
                    time.sleep(3)
                    new_url = page.url
                    new_text = page.inner_text("body") if page.locator("body").count() else ""
                    print(f"  After submit URL: {new_url[:150]}")
                    print(f"  After submit text (first 400): {new_text[:400]}")

                    if "code=" in new_url:
                        # Extract code from URL
                        from urllib.parse import parse_qs, urlparse
                        parsed = urlparse(new_url)
                        params = parse_qs(parsed.query)
                        code = params.get("code", [None])[0]
                        if code:
                            print(f"\n  ✅ Got authorization code: {code[:30]}...")
                            return code
                except Exception as e:
                    print(f"  Sign-in error: {e}")

            # Check for code in body (OOB display mode)
            if "code" in current_text.lower() and "your" in current_text.lower():
                import re
                m = re.search(r'(?:code|authorization)[^A-Za-z0-9]*([A-Za-z0-9_-]{16,})', current_text, re.IGNORECASE)
                if m:
                    print(f"\n  ✅ Code found in page text: {m.group(1)[:30]}...")
                    return m.group(1)

            # Check for oob code pattern
            import re
            m = re.search(r'\b([A-Za-z0-9_-]{32,})\b', current_text)
            if m and "code" in current_text.lower():
                print(f"\n  ✅ Possible code: {m.group(1)[:40]}...")

            return None
        finally:
            browser.close()


def exchange_code_via_backend(code: str):
    """用 authorization code 交换 token"""
    r = requests.post(
        f"{BACKEND_URL}/api/channel/uk/vat/callback",
        json={"code": code, "state": ""}
    )
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    # 1. Check which redirect URI is accepted
    print("Step 1: Check which redirect URI is accepted")
    print("-" * 70)
    accepted = automate_oob_oauth()
    if not accepted:
        print("\n⚠️  No redirect URI accepted. The Application must have a redirect URI registered.")
        print("   Please add one via HMRC Developer Hub UI, then re-run.")
        sys.exit(1)

    # 2. Automate browser flow
    print("\nStep 2: Automate browser flow")
    print("-" * 70)
    code = automate_with_browser()
    if not code:
        print("\n⚠️  Could not extract authorization code automatically.")
        sys.exit(1)

    # 3. Exchange code for token
    print("\nStep 3: Exchange code for token")
    print("-" * 70)
    result = exchange_code_via_backend(code)
    print(f"Result: {result}")
