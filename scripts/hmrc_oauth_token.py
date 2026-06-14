#!/usr/bin/env python3
"""HMRC Sandbox OAuth — Get access token without Playwright

Works on any machine with a browser (manually visit one URL once).
Saves the access_token to .tokens/{vrn}.json for use by the agent.

Usage:
    python scripts/hmrc_oauth_token.py                    # Use VRN from .env
    python scripts/hmrc_oauth_token.py --vrn 960606228    # Specific VRN
    python scripts/hmrc_oauth_token.py --scope "read:vat write:vat read:self-assessment write:self-assessment"

This is the ONLY step that requires a browser. After this script saves the token,
all subsequent VAT/SA operations work headlessly.
"""

import argparse
import json
import re
import sys
import time
import webbrowser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

# ── 凭据 — 从 .env 读取,默认值与你已有的 sandbox app 一致 ──

def load_env() -> dict:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    env = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = load_env()
CLIENT_ID = ENV.get("HMRC_CLIENT_ID", "2U9ktG6rDRDpxUG1kNJ4Mld8y6Fl")
CLIENT_SECRET = ENV.get("HMRC_CLIENT_SECRET", "ef505ced-ee2c-4797-85b6-c673de1e9121")
REDIRECT_URI = ENV.get("HMRC_REDIRECT_URI", "http://localhost:8080")
TEST_VRN = ENV.get("HMRC_TEST_VRN", "960606228")
DEFAULT_SCOPE = "read:vat write:vat read:self-assessment write:self-assessment"


def build_auth_url(scope: str, state: str = "") -> str:
    return (
        f"https://test-api.service.hmrc.gov.uk/oauth/authorize"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={'+'.join(scope.split())}"
    )


def extract_code_from_url(url: str) -> str | None:
    """从浏览器重定向后的 URL 中提取 code 参数。

    URL 形如: http://localhost:8080/?code=abc123&state=...
    """
    parsed = urlparse(url)
    code = parse_qs(parsed.query).get("code", [None])[0]
    if code:
        return code
    # 也可能 code 嵌在 path 中
    match = re.search(r'code=([A-Za-z0-9_-]+)', url)
    return match.group(1) if match else None


def exchange_code(code: str, scope: str) -> dict:
    """用 authorization code 换 access_token。"""
    resp = httpx.post(
        "https://test-api.service.hmrc.gov.uk/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "scope": scope,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"Token exchange failed: {resp.status_code} {resp.text}")
    return resp.json()


def save_token(token_data: dict, vrn: str):
    """保存到 .tokens/{vrn}.json"""
    token_path = Path(f".tokens/{vrn}.json")
    token_path.parent.mkdir(exist_ok=True)
    payload = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
        "expires_at": time.time() + token_data.get("expires_in", 14400),
        "token_type": token_data.get("token_type", "bearer"),
        "scope": token_data.get("scope", ""),
    }
    token_path.write_text(json.dumps(payload, indent=2))
    print(f"✅ Token saved to {token_path}")
    print(f"   Access token: {payload['access_token'][:30]}...")
    print(f"   Expires in: {token_data.get('expires_in', '?')}s")
    print(f"   Scope: {payload['scope']}")


def test_token(token: str, vrn: str) -> bool:
    """用 token 调一次真实 API,确认可用。"""
    headers = {
        "Accept": "application/vnd.hmrc.1.0+json",
        "Authorization": f"Bearer {token}",
        "Gov-Client-Connection-Method": "OTHER",
        "Gov-Client-Device-ID": "taxi-cli",
        "Gov-Client-User-IDs": f"vrn={vrn}",
        "Gov-Client-Time": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        "Gov-Vendor-Version": "taxi=0.1.0",
        "Gov-Vendor-Product-Name": "taxi",
        "Gov-Vendor-License-Identifier": "dev",
    }
    resp = httpx.get(
        f"https://test-api.service.hmrc.gov.uk/organisations/vat/{vrn}/obligations",
        params={"from": "2023-01-01", "to": "2024-12-31"},
        headers=headers,
        timeout=15,
    )
    if resp.status_code == 200:
        obs = resp.json().get("obligations", [])
        print(f"✅ VAT API live: {len(obs)} obligations fetched")
        for ob in obs[:3]:
            print(f"   - {ob.get('periodKey')}: {ob.get('status')} due {ob.get('due')}")
        return True
    else:
        print(f"❌ VAT API call failed: {resp.status_code}")
        print(resp.text[:200])
        return False


def main():
    parser = argparse.ArgumentParser(description="Get HMRC sandbox OAuth access token")
    parser.add_argument("--vrn", default=TEST_VRN, help=f"VRN (default: {TEST_VRN})")
    parser.add_argument("--scope", default=DEFAULT_SCOPE, help="OAuth scopes")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open browser")
    args = parser.parse_args()

    print("=" * 70)
    print("HMRC Sandbox OAuth Token Generator")
    print("=" * 70)
    print(f"Client ID:    {CLIENT_ID[:20]}...")
    print(f"Redirect URI: {REDIRECT_URI}")
    print(f"VRN:          {args.vrn}")
    print(f"Scopes:       {args.scope}")
    print()

    auth_url = build_auth_url(args.scope)

    print("Step 1: Open this URL in a browser (sign in with HMRC test user):")
    print()
    print(f"  {auth_url}")
    print()
    print("  HMRC sandbox test user:")
    print("    User ID:  664155084356")
    print("    Password: 6ah0eYT1NlJ4")
    print()

    if not args.no_browser:
        try:
            webbrowser.open(auth_url)
            print("(Browser opened automatically.)")
        except Exception:
            pass

    print("Step 2: After signing in and granting authority, your browser will redirect to:")
    print(f"  {REDIRECT_URI}?code=XXXXX")
    print()
    print("Copy the ENTIRE redirected URL (or just the `code=...` value) and paste below.")
    print()

    redirect_url = input("Paste the full redirect URL (or just the code): ").strip()

    code = extract_code_from_url(redirect_url) if redirect_url.startswith("http") else redirect_url
    if not code:
        print("❌ Could not extract code from input")
        sys.exit(1)

    print(f"\nGot code: {code[:20]}...")
    print("Step 3: Exchanging code for access token...")

    token_data = exchange_code(code, args.scope)
    save_token(token_data, args.vrn)

    print()
    print("Step 4: Testing token against real HMRC sandbox...")
    test_token(token_data["access_token"], args.vrn)
    print()
    print("✅ DONE. Set HMRC_MODE=live in .env to use the real API.")


if __name__ == "__main__":
    main()
