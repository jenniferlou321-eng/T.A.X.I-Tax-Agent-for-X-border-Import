"""Tests for backend/jurisdictions/uk/_hmrc_base.py — shared HMRC utilities."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.jurisdictions.uk._hmrc_base import (
    hmrc_mode,
    tool_error,
    tool_ok,
    HMRCError,
    HMRCService,
)


# ── hmrc_mode ──

class TestHMRCMode:
    def test_defaults_to_mock(self, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        assert hmrc_mode() == "mock"

    def test_returns_live_when_set(self, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "live")
        assert hmrc_mode() == "live"

    def test_is_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "LIVE")
        assert hmrc_mode() == "live"

    def test_unknown_value_passed_through(self, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "staging")
        assert hmrc_mode() == "staging"


# ── tool_error ──

class TestToolError:
    def test_basic_error(self):
        result = tool_error("Something went wrong")
        assert result["is_error"] is True
        content = json.loads(result["content"][0]["text"])
        assert content["success"] is False
        assert content["error"] == "Something went wrong"
        assert "detail" not in content

    def test_error_with_detail(self):
        result = tool_error("Not found", "case_id 'xyz' unknown")
        content = json.loads(result["content"][0]["text"])
        assert content["detail"] == "case_id 'xyz' unknown"


# ── tool_ok ──

class TestToolOk:
    def test_basic_success(self):
        result = tool_ok({"foo": "bar"})
        assert "is_error" not in result
        content = json.loads(result["content"][0]["text"])
        assert content["foo"] == "bar"


# ── HMRCError ──

class TestHMRCError:
    def test_creation(self):
        err = HMRCError(code="BUSINESS_ERROR", message="Invalid period", path="/periodKey")
        assert err.code == "BUSINESS_ERROR"
        assert err.message == "Invalid period"
        assert err.path == "/periodKey"


# ── HMRCService base class ──

class ConcreteService(HMRCService):
    """Concrete subclass for testing the base class."""
    pass


class TestHMRCService:
    def test_init_sets_attributes(self):
        oauth_mock = MagicMock()
        fraud_mock = MagicMock()
        svc = ConcreteService(
            base_url="https://test.example.com",
            oauth=oauth_mock,
            fraud_headers=fraud_mock,
            accept_header="application/vnd.hmrc.2.0+json",
        )
        assert svc.base_url == "https://test.example.com"
        assert svc.oauth is oauth_mock
        assert svc._fraud is fraud_mock
        assert svc._accept_header == "application/vnd.hmrc.2.0+json"

    def test_init_strips_trailing_slash(self):
        svc = ConcreteService(
            base_url="https://test.example.com/",
            oauth=MagicMock(),
        )
        assert svc.base_url == "https://test.example.com"

    @pytest.mark.asyncio
    async def test_get_client_creates_async_client(self):
        svc = ConcreteService(base_url="https://test.example.com", oauth=MagicMock())
        client = await svc._get_client()
        assert client is not None
        # Second call returns same client
        client2 = await svc._get_client()
        assert client is client2

    def test_build_headers_without_fraud(self):
        svc = ConcreteService(base_url="https://test.example.com", oauth=MagicMock())
        headers = svc._build_headers(user_id="test123")
        assert headers["Accept"] == "application/vnd.hmrc.1.0+json"
        assert headers["Content-Type"] == "application/json"

    def test_build_headers_with_fraud(self):
        fraud_mock = MagicMock()
        fraud_mock.build_headers.return_value = {"Gov-Client-Device-ID": "abc"}
        svc = ConcreteService(
            base_url="https://test.example.com",
            oauth=MagicMock(),
            fraud_headers=fraud_mock,
        )
        headers = svc._build_headers(user_id="test123")
        assert headers["Gov-Client-Device-ID"] == "abc"
        fraud_mock.build_headers.assert_called_once_with(user_id="test123")

    @pytest.mark.asyncio
    async def test_authenticate_success(self):
        oauth_mock = MagicMock()
        oauth_mock.authenticate_silent = AsyncMock()
        oauth_mock.authenticate_silent.return_value = MagicMock(success=True, token="tok_123")
        svc = ConcreteService(base_url="https://test.example.com", oauth=oauth_mock)
        token = await svc._authenticate()
        assert token == "tok_123"

    @pytest.mark.asyncio
    async def test_authenticate_failure(self):
        oauth_mock = MagicMock()
        oauth_mock.authenticate_silent = AsyncMock()
        oauth_mock.authenticate_silent.return_value = MagicMock(success=False, error="No token")
        svc = ConcreteService(base_url="https://test.example.com", oauth=oauth_mock)
        with pytest.raises(PermissionError, match="HMRC auth failed"):
            await svc._authenticate()

    def test_parse_hmrc_errors_single(self):
        svc = ConcreteService(base_url="https://test.example.com", oauth=MagicMock())
        errors = svc._parse_hmrc_errors({
            "code": "INVALID_REQUEST",
            "message": "Bad request",
        })
        assert len(errors) == 1
        assert errors[0].code == "INVALID_REQUEST"

    def test_parse_hmrc_errors_with_field_errors(self):
        svc = ConcreteService(base_url="https://test.example.com", oauth=MagicMock())
        errors = svc._parse_hmrc_errors({
            "code": "INVALID_PAYLOAD",
            "message": "Validation failed",
            "errors": [
                {"code": "INVALID_FIELD", "message": "Bad periodKey", "path": "/periodKey"},
                {"code": "MISSING_FIELD", "message": "Missing vrn", "path": "/vrn"},
            ],
        })
        assert len(errors) == 3  # 1 top-level + 2 field-level
        assert errors[1].path == "/periodKey"

    def test_parse_hmrc_errors_missing_fields(self):
        svc = ConcreteService(base_url="https://test.example.com", oauth=MagicMock())
        errors = svc._parse_hmrc_errors({})
        assert len(errors) == 1
        assert errors[0].code == "UNKNOWN"

    def test_raise_for_hmrc_error(self):
        svc = ConcreteService(base_url="https://test.example.com", oauth=MagicMock())
        resp_mock = MagicMock()
        resp_mock.status_code = 400
        resp_mock.json.return_value = {"code": "BAD", "message": "nope"}
        with pytest.raises(ValueError, match="HMRC testop error"):
            svc._raise_for_hmrc_error(resp_mock, "testop")
