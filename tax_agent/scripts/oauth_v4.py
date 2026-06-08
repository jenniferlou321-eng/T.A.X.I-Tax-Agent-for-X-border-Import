"""Final OAuth automation"""
import time
import json
import requests
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright

BACKEND_URL = "http://localhost:8765"
TEST_USER_ID = "664155084356"
TEST_PASSWORD = "6ah0eYT1NlJ4"
TEST_VRN = "960606228"

auth_url = requests.get(f"{BACKEND_URL}/api/channel/uk/vat/auth-url").json()["auth_url"]
code = None

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--ignore-certificate-errors"])
    page = browser.new_page(ignore_https_errors=True)

    def on_nav(frame):
        global code
        if "localhost:8080" in frame.url and "code=" in frame.url:
            code = parse_qs(urlparse(frame.url).query).get("code", [None])[0]
            if code:
                print(f"Captured code: {code[:20]}...")

    page.on("framenavigated", on_nav)

    page.goto(auth_url, wait_until="domcontentloaded", timeout=30000)
    time.sleep(2)

    # Accept cookies
    try:
        page.click('button:has-text("Accept additional cookies")', timeout=2000)
    except:
        pass
    time.sleep(1)

    # Click signIn
    try:
        page.click('#signIn', timeout=5000)
    except:
        pass
    time.sleep(3)

    # Click Continue (grant authority)
    try:
        page.click('a:has-text("Continue"), button:has-text("Continue")', timeout=5000)
    except:
        pass
    time.sleep(3)

    # If on whatYouWillNeed, click signIn again
    if "whatYouWillNeed" in page.url:
        try:
            page.click('#signIn', timeout=5000)
        except:
            pass
        time.sleep(3)

    # On api-test-login - fill credentials
    if "api-test-login" in page.url or "test-login" in page.url:
        print(f"Test login URL: {page.url[:120]}")
        inputs = page.eval_on_selector_all("input", "els => els.map(e => ({name: e.name, id: e.id, type: e.type, visible: e.offsetParent !== null}))")
        for inp in inputs:
            if inp.get("visible"):
                print(f"  Input: {inp}")

        page.fill('input[name="userId"], input#userId, input#username', TEST_USER_ID, timeout=5000)
        page.fill('input[name="password"], input#password', TEST_PASSWORD, timeout=5000)
        time.sleep(0.5)
        page.click('button:has-text("Sign in"), input[type="submit"]', timeout=5000)
        time.sleep(5)

    # After login, may need to click Continue
    if "Continue" in page.inner_text("body"):
        try:
            page.click('a:has-text("Continue"), button:has-text("Continue")', timeout=5000)
        except:
            pass
        time.sleep(4)

    # Extract code
    if not code and "localhost:8080" in page.url and "code=" in page.url:
        code = parse_qs(urlparse(page.url).query).get("code", [None])[0]

    if not code:
        print(f"Final URL: {page.url}")
        text = page.inner_text("body") if page.locator("body").count() else ""
        print(f"Text: {text[:600]}")

    browser.close()

if code:
    print(f"\nCODE: {code}")
    r = requests.post(f"{BACKEND_URL}/api/channel/uk/vat/callback", json={"code": code, "state": ""})
    print(f"Token: {r.status_code} - {r.json()}")
    if r.json().get("success"):
        print("\n=== Testing Obligations ===")
        r2 = requests.get(f"{BACKEND_URL}/api/filings/obligations/uk/vat?vrn={TEST_VRN}", timeout=30)
        print(f"Status: {r2.status_code}")
        print(json.dumps(r2.json(), indent=2))
else:
    print("No code")
