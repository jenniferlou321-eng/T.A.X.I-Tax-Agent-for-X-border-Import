"""Tests for UKSAAgentToolSet — mock/live toggle behavior."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.jurisdictions.uk.self_assessment.agent_tools import UKSAAgentToolSet


@pytest.fixture
def sa_tools():
    return UKSAAgentToolSet()


def _parse_content(result: dict) -> dict:
    return json.loads(result["content"][0]["text"])


class TestGetObligationsMockMode:
    @pytest.mark.asyncio
    async def test_returns_mock_data_by_default(self, sa_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(await sa_tools.get_obligations("AB123456C"))
        assert result["success"] is True
        assert result["mode"] == "mock"
        assert len(result["obligations"]) == 2
        assert result["obligations"][0]["tax_year"] == "2023-24"

    @pytest.mark.asyncio
    async def test_error_when_nino_missing(self, sa_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(await sa_tools.get_obligations(""))
        assert result["success"] is False
        assert "NINO" in result["error"]


class TestGetObligationsLiveMode:
    @pytest.mark.asyncio
    async def test_calls_service_when_live(self, sa_tools, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "live")

        mock_ob = MagicMock()
        mock_ob.tax_year = "2023-24"
        mock_ob.start.isoformat.return_value = "2023-04-06"
        mock_ob.end.isoformat.return_value = "2024-04-05"
        mock_ob.due.isoformat.return_value = "2025-01-31"
        mock_ob.status = "O"

        mock_service = MagicMock()
        mock_service.get_obligations = AsyncMock(return_value=[mock_ob])

        with patch(
            "backend.jurisdictions.uk.self_assessment.agent_tools._build_hmrc_service",
            return_value=mock_service,
        ):
            result = _parse_content(await sa_tools.get_obligations("AB123456C"))

        assert result["success"] is True
        assert len(result["obligations"]) == 1
        assert result["obligations"][0]["tax_year"] == "2023-24"

    @pytest.mark.asyncio
    async def test_handles_permission_error(self, sa_tools, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "live")

        mock_service = MagicMock()
        mock_service.get_obligations = AsyncMock(
            side_effect=PermissionError("HMRC auth failed")
        )

        with patch(
            "backend.jurisdictions.uk.self_assessment.agent_tools._build_hmrc_service",
            return_value=mock_service,
        ):
            result = _parse_content(await sa_tools.get_obligations("AB123456C"))

        assert result["success"] is False
        assert "authentication" in result["error"].lower()


class TestSubmitReturnMockMode:
    @pytest.mark.asyncio
    async def test_returns_mock_receipt(self, sa_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(
            await sa_tools.submit_return("AB123456C", "2023-24", {"finalised": True})
        )
        assert result["success"] is True
        assert result["mode"] == "mock"
        assert "SA-AB123456C-2023-24" in result["submission_id"]

    @pytest.mark.asyncio
    async def test_error_when_nino_missing(self, sa_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(await sa_tools.submit_return("", "2023-24", {}))
        assert result["success"] is False


class TestSubmitReturnLiveMode:
    @pytest.mark.asyncio
    async def test_calls_service_when_live(self, sa_tools, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "live")

        mock_service = MagicMock()
        mock_service.submit_final_declaration = AsyncMock(return_value={
            "transactionReference": "TX-001",
            "processingDate": "2025-01-15",
        })

        with patch(
            "backend.jurisdictions.uk.self_assessment.agent_tools._build_hmrc_service",
            return_value=mock_service,
        ):
            result = _parse_content(
                await sa_tools.submit_return("AB123456C", "2023-24", {"finalised": True})
            )

        assert result["success"] is True
        assert result["mode"] == "live"
        assert result["submission_id"] == "TX-001"


class TestGetReturnMockMode:
    @pytest.mark.asyncio
    async def test_returns_mock_data(self, sa_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(await sa_tools.get_return("AB123456C", "2023-24"))
        assert result["success"] is True
        assert result["mode"] == "mock"
        assert result["nino"] == "AB123456C"


class TestGetReturnLiveMode:
    @pytest.mark.asyncio
    async def test_calls_service_when_live(self, sa_tools, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "live")

        mock_service = MagicMock()
        mock_service.get_final_declaration = AsyncMock(return_value={
            "nino": "AB123456C",
            "taxYear": "2023-24",
            "declaration": {"finalised": True},
        })

        with patch(
            "backend.jurisdictions.uk.self_assessment.agent_tools._build_hmrc_service",
            return_value=mock_service,
        ):
            result = _parse_content(await sa_tools.get_return("AB123456C", "2023-24"))

        assert result["success"] is True
        assert result["nino"] == "AB123456C"
        assert result["tax_year"] == "2023-24"
        # declaration contains the raw HMRC response
        assert "declaration" in result["declaration"]
