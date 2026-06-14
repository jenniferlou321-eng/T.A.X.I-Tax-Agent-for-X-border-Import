"""Tests for UKSDLTAgentToolSet — mock/live toggle behavior."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.jurisdictions.uk.stamp_duty.agent_tools import UKSDLTAgentToolSet


@pytest.fixture
def sdlt_tools():
    return UKSDLTAgentToolSet()


def _parse_content(result: dict) -> dict:
    return json.loads(result["content"][0]["text"])


class TestGetObligations:
    @pytest.mark.asyncio
    async def test_returns_empty_obligations(self, sdlt_tools):
        result = _parse_content(await sdlt_tools.get_obligations("1234567890123"))
        assert result["success"] is True
        assert result["obligations"] == []
        assert "transaction-based" in result["note"].lower()


class TestSubmitReturnMockMode:
    @pytest.mark.asyncio
    async def test_returns_mock_receipt(self, sdlt_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(
            await sdlt_tools.submit_return("1234567890123", "SDLT-2024", {"property_value": 500000})
        )
        assert result["success"] is True
        assert result["mode"] == "mock"
        assert "SDLT-1234567890123" in result["submission_id"]

    @pytest.mark.asyncio
    async def test_error_when_utr_missing(self, sdlt_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(await sdlt_tools.submit_return("", "SDLT-2024", {}))
        assert result["success"] is False
        assert "UTR" in result["error"]


class TestSubmitReturnLiveMode:
    @pytest.mark.asyncio
    async def test_calls_service_when_live(self, sdlt_tools, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "live")

        mock_service = MagicMock()
        mock_service.submit_return = AsyncMock(return_value={
            "submissionId": "REC-SDLT-LIVE-001",
            "processingDate": "2026-06-14T10:05:00Z",
            "formBundleNumber": "FB-SDLT-001",
            "correlationId": "corr-001",
        })

        with patch(
            "backend.jurisdictions.uk.stamp_duty.agent_tools.HMRCSDLTService",
            return_value=mock_service,
        ):
            result = _parse_content(
                await sdlt_tools.submit_return("1234567890123", "SDLT-2024", {"property_value": 500000})
            )

        assert result["success"] is True
        assert result["mode"] == "live"
        assert result["submission_id"] == "REC-SDLT-LIVE-001"


class TestGetReturnMockMode:
    @pytest.mark.asyncio
    async def test_returns_mock_data(self, sdlt_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(await sdlt_tools.get_return("1234567890123", "SDLT-2024"))
        assert result["success"] is True
        assert result["mode"] == "mock"


class TestGetReturnLiveMode:
    @pytest.mark.asyncio
    async def test_calls_service_when_live(self, sdlt_tools, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "live")

        from backend.jurisdictions.uk.stamp_duty.hmrc_service import SDLTReturnView
        mock_service = MagicMock()
        mock_service.get_return = AsyncMock(return_value=SDLTReturnView(
            submission_id="REC-SDLT-001",
            processing_date="2026-06-14",
            form_bundle_number="FB-001",
            correlation_id="corr-001",
        ))

        with patch(
            "backend.jurisdictions.uk.stamp_duty.agent_tools.HMRCSDLTService",
            return_value=mock_service,
        ):
            result = _parse_content(await sdlt_tools.get_return("1234567890123", "REC-SDLT-001"))

        assert result["success"] is True
        assert result["submission_id"] == "REC-SDLT-001"


class TestCalculateReturn:
    @pytest.mark.asyncio
    async def test_calculates_sdlt(self, sdlt_tools):
        result = _parse_content(
            await sdlt_tools.calculate_return(
                json.dumps([{"category": "property_value", "amount": 500000}]),
                {"property_type": "residential", "buyer_type": "individual"},
            )
        )
        assert result["success"] is True
        assert result["property_value"] == 500000
        assert result["sdlt_payable"] > 0


class TestValidateReturn:
    @pytest.mark.asyncio
    async def test_validates_missing_property_value(self, sdlt_tools):
        result = _parse_content(await sdlt_tools.validate_return({}))
        assert result["is_valid"] is False
        assert any(e["field"] == "property_value" for e in result["errors"])

    @pytest.mark.asyncio
    async def test_validates_with_property_value(self, sdlt_tools):
        result = _parse_content(await sdlt_tools.validate_return({"property_value": 500000}))
        assert result["is_valid"] is True
