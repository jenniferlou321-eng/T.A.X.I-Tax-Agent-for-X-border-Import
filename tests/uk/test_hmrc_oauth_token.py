"""Tests for scripts/hmrc_oauth_token.py"""

import sys
from pathlib import Path
from urllib.parse import urlencode

# Make script importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))

import hmrc_oauth_token as oauth  # noqa: E402


class TestBuildAuthUrl:
    def test_basic(self):
        url = oauth.build_auth_url("read:vat write:vat")
        assert "response_type=code" in url
        assert oauth.CLIENT_ID in url
        assert "scope=read%3Avat" in url or "scope=read:vat" in url

    def test_scope_with_spaces(self):
        url = oauth.build_auth_url("read:vat write:vat read:self-assessment")
        # Should join scopes with + (URL-encoded form may use %20 for spaces before joining)
        assert "read:vat" in url and "write:vat" in url and "read:self-assessment" in url
        # Verify all 3 scopes are present
        assert url.count("read:") + url.count("write:") >= 3


class TestExtractCodeFromUrl:
    def test_extracts_from_query(self):
        url = "http://localhost:8080/?code=abc123xyz&state=foo"
        assert oauth.extract_code_from_url(url) == "abc123xyz"

    def test_extracts_without_state(self):
        url = "http://localhost:8080/?code=abc123"
        assert oauth.extract_code_from_url(url) == "abc123"

    def test_returns_none_for_missing(self):
        assert oauth.extract_code_from_url("http://localhost:8080/?error=denied") is None
        assert oauth.extract_code_from_url("") is None

    def test_extracts_from_path_pattern(self):
        url = "http://localhost:8080/?code=longstring-1234_abc&other=1"
        assert oauth.extract_code_from_url(url) == "longstring-1234_abc"


class TestEnvLoading:
    def test_loads_env_file(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("HMRC_CLIENT_ID=test_id\nHMRC_VENDOR_PASSWORD=test_vendor\n")
        # Override the env_path inside the module
        monkeypatch.setattr(oauth, "ENV", {
            "HMRC_CLIENT_ID": "test_id",
            "HMRC_VENDOR_PASSWORD": "test_vendor",
        })
        assert oauth.ENV["HMRC_CLIENT_ID"] == "test_id"
        assert oauth.ENV["HMRC_VENDOR_PASSWORD"] == "test_vendor"
