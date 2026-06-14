"""Tests for UKCTAgentToolSet — mock/live toggle behavior."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.jurisdictions.uk.corporation_tax.agent_tools import UKCTAgentToolSet


@pytest.fixture
def ct_tools():
    return UKCTAgentToolSet()


def _parse_content(result: dict) -> dict:
    """Extract JSON content from a tool result."""
    text = result["content"][0]["text"]
    return json.loads(text)


class TestGetObligationsMockMode:
    @pytest.mark.asyncio
    async def test_returns_mock_data_by_default(self, ct_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(await ct_tools.get_obligations("1234567890"))
        assert result["success"] is True
        assert result["mode"] == "mock"
        assert len(result["obligations"]) == 2
        assert result["obligations"][0]["status"] == "O"

    @pytest.mark.asyncio
    async def test_error_when_ctref_missing(self, ct_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(await ct_tools.get_obligations(""))
        assert result["success"] is False
        assert "CTREF" in result["error"]


class TestGetObligationsLiveMode:
    @pytest.mark.asyncio
    async def test_calls_service_when_live(self, ct_tools, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "live")

        mock_obligation = MagicMock()
        mock_obligation.period_key = "FY2024"
        mock_obligation.start.isoformat.return_value = "2024-04-01"
        mock_obligation.end.isoformat.return_value = "2025-03-31"
        mock_obligation.due.isoformat.return_value = "2026-01-01"
        mock_obligation.status = "O"
        mock_obligation.received = None

        mock_service = MagicMock()
        mock_service.get_obligations = AsyncMock(return_value=[mock_obligation])

        with patch(
            "backend.jurisdictions.uk.corporation_tax.agent_tools._build_hmrc_service",
            return_value=mock_service,
        ):
            result = _parse_content(await ct_tools.get_obligations("1234567890"))

        assert result["success"] is True
        assert len(result["obligations"]) == 1
        assert result["obligations"][0]["period_key"] == "FY2024"

    @pytest.mark.asyncio
    async def test_handles_permission_error(self, ct_tools, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "live")

        mock_service = MagicMock()
        mock_service.get_obligations = AsyncMock(
            side_effect=PermissionError("HMRC auth failed")
        )

        with patch(
            "backend.jurisdictions.uk.corporation_tax.agent_tools._build_hmrc_service",
            return_value=mock_service,
        ):
            result = _parse_content(await ct_tools.get_obligations("1234567890"))

        assert result["success"] is False
        assert "authentication" in result["error"].lower()


class TestSubmitReturnMockMode:
    @pytest.mark.asyncio
    async def test_returns_mock_receipt(self, ct_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(
            await ct_tools.submit_return("1234567890", "FY2024", {"test": "data"})
        )
        assert result["success"] is True
        assert result["mode"] == "mock"
        assert "submission_id" in result
        assert "CT-1234567890-FY2024" in result["submission_id"]

    @pytest.mark.asyncio
    async def test_error_when_ctref_missing(self, ct_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(await ct_tools.submit_return("", "FY2024", {}))
        assert result["success"] is False


class TestSubmitReturnLiveMode:
    @pytest.mark.asyncio
    async def test_calls_service_when_live(self, ct_tools, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "live")

        mock_service = MagicMock()
        mock_service.submit_return = AsyncMock(return_value={
            "submissionId": "SUB-001",
            "processingDate": "2025-12-15",
            "formBundleNumber": "FB-001",
            "chargeRefNumber": "CR-001",
        })

        with patch(
            "backend.jurisdictions.uk.corporation_tax.agent_tools._build_hmrc_service",
            return_value=mock_service,
        ):
            result = _parse_content(
                await ct_tools.submit_return("1234567890", "FY2024", {"test": "data"})
            )

        assert result["success"] is True
        assert result["mode"] == "live"
        assert result["submission_id"] == "SUB-001"


class TestGetReturnMockMode:
    @pytest.mark.asyncio
    async def test_returns_mock_data(self, ct_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(await ct_tools.get_return("1234567890", "FY2024"))
        assert result["success"] is True
        assert result["mode"] == "mock"
        assert result["ctref"] == "1234567890"


class TestGetReturnLiveMode:
    @pytest.mark.asyncio
    async def test_calls_service_when_live(self, ct_tools, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "live")

        mock_ret = MagicMock()
        mock_ret.submission_id = "SUB-001"
        mock_ret.processing_date = "2025-12-15"
        mock_ret.form_bundle_number = "FB-001"
        mock_ret.charge_ref_number = "CR-001"
        mock_ret.period_start = "2024-04-01"
        mock_ret.period_end = "2025-03-31"

        mock_service = MagicMock()
        mock_service.get_return = AsyncMock(return_value=mock_ret)

        with patch(
            "backend.jurisdictions.uk.corporation_tax.agent_tools._build_hmrc_service",
            return_value=mock_service,
        ):
            result = _parse_content(await ct_tools.get_return("1234567890", "SUB-001"))

        assert result["success"] is True
        assert result["submission_id"] == "SUB-001"
