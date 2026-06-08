"""Add redirect URI to HMRC Application via Developer Hub UI automation

Prerequisites:
  - Playwright installed:  pip install playwright && playwright install chromium
  - Your HMRC Developer Hub login credentials (email + password)

Usage:
  python scripts/add_redirect_uri.py
"""

import sys
from playwright.sync_api import sync_playwright

APP_ID = "c0526e36-0ce1-4d1c-8585-d15324ccba8b"
REDIRECT_URI = "http://localhost:8080"
DEV_HUB_LOGIN = "https://developer.service.hmrc.gov.uk/developer/login"
APP_EDIT_URL = f"https://developer.service.hmrc.gov.uk/developer/applications/{APP_ID}/details"


def main():
    print("=" * 70)
    print("HMRC Developer Hub — Add Redirect URI Automation")
    print("=" * 70)
    print()
    print("This script will:")
    print(f"  1. Log in to HMRC Developer Hub")
    print(f"  2. Open Application '{APP_ID}'")
    print(f"  3. Add redirect URI: {REDIRECT_URI}")
    print()

    # Ask for credentials
    email = input("Your HMRC Developer Hub email: ").strip()
    password = input("Your HMRC Developer Hub password: ").strip()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--no-sandbox"])
        page = browser.new_page()

        try:
            # 1. Login
            print("\n→ Logging in...")
            page.goto(DEV_HUB_LOGIN, wait_until="domcontentloaded")
            page.fill('input[name="emailaddress"]', email)
            page.fill('input[name="password"]', password)
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle")

            if "login" in page.url:
                print("❌ Login failed — please check credentials")
                browser.close()
                sys.exit(1)

            print("✅ Logged in")

            # 2. Navigate to application
            print(f"\n→ Opening application {APP_ID}...")
            page.goto(APP_EDIT_URL, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")

            # 3. Click "Change" next to Redirect URIs
            print("\n→ Finding Redirect URIs section...")
            # Look for the redirect URI edit link
            links = page.query_selector_all("a")
            edit_link = None
            for link in links:
                href = link.get_attribute("href") or ""
                text = link.inner_text().strip().lower()
                if "redirect" in text or "redirect" in href:
                    edit_link = href
                    print(f"   Found link: {href}")
                    break

            if not edit_link:
                print("⚠️  Could not find Redirect URIs edit link automatically.")
                print("   Please manually click 'Change' next to 'Redirect URIs' in the browser.")
                print("   Press Enter when ready...")
                input()
            else:
                page.goto(edit_link if edit_link.startswith("http") else f"https://developer.service.hmrc.gov.uk{edit_link}")
                page.wait_for_load_state("networkidle")

            # 4. Add the redirect URI
            print(f"\n→ Adding redirect URI: {REDIRECT_URI}")
            # Try to find the input field for redirect URI
            inputs = page.query_selector_all("input")
            for inp in inputs:
                name = inp.get_attribute("name") or ""
                placeholder = inp.get_attribute("placeholder") or ""
                if "redirect" in name.lower() or "uri" in name.lower() or "redirect" in placeholder.lower():
                    inp.fill(REDIRECT_URI)
                    print(f"   Filled input: {name}")
                    break
            else:
                print("⚠️  Could not find redirect URI input automatically.")
                print("   Please manually paste the URI and press Enter...")
                input()

            # 5. Submit
            submit_btn = page.query_selector('button[type="submit"], input[type="submit"]')
            if submit_btn:
                submit_btn.click()
                page.wait_for_load_state("networkidle")
                print("✅ Redirect URI added!")
            else:
                print("⚠️  Could not find submit button. Please click it manually.")
                input("Press Enter when done...")

            print("\n" + "=" * 70)
            print("Done! You can now close the browser.")
            print("=" * 70)
            input("Press Enter to close browser...")

        finally:
            browser.close()


if __name__ == "__main__":
    main()
