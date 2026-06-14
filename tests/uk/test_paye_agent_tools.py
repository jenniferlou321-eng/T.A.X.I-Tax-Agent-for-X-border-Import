"""Tests for UKPAYEAgentToolSet — mock/live toggle behavior."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.jurisdictions.uk.paye.agent_tools import UKPAYEAgentToolSet


@pytest.fixture
def paye_tools():
    return UKPAYEAgentToolSet()


def _parse_content(result: dict) -> dict:
    """Extract JSON content from a tool result."""
    text = result["content"][0]["text"]
    return json.loads(text)


class TestGetObligationsMockMode:
    @pytest.mark.asyncio
    async def test_returns_mock_data_by_default(self, paye_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(await paye_tools.get_obligations("123/AB45678"))
        assert result["success"] is True
        assert result["mode"] == "mock"
        assert len(result["obligations"]) == 2
        assert result["obligations"][0]["type"] == "FPS"

    @pytest.mark.asyncio
    async def test_error_when_empref_missing(self, paye_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(await paye_tools.get_obligations(""))
        assert result["success"] is False
        assert "EMPREF" in result["error"]


class TestGetObligationsLiveMode:
    @pytest.mark.asyncio
    async def test_calls_service_when_live(self, paye_tools, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "live")

        mock_obligation = MagicMock()
        mock_obligation.period_key = "2024-04"
        mock_obligation.start.isoformat.return_value = "2024-04-06"
        mock_obligation.end.isoformat.return_value = "2024-05-05"
        mock_obligation.due.isoformat.return_value = "2024-05-19"
        mock_obligation.status = "F"
        mock_obligation.submission_type = "FPS"
        mock_obligation.received = None

        mock_service = MagicMock()
        mock_service.get_obligations = AsyncMock(return_value=[mock_obligation])

        with patch(
            "backend.jurisdictions.uk.paye.agent_tools._build_hmrc_service",
            return_value=mock_service,
        ):
            result = _parse_content(await paye_tools.get_obligations("123/AB45678"))

        assert result["success"] is True
        assert len(result["obligations"]) == 1
        assert result["obligations"][0]["period_key"] == "2024-04"
        assert result["obligations"][0]["type"] == "FPS"

    @pytest.mark.asyncio
    async def test_handles_permission_error(self, paye_tools, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "live")

        mock_service = MagicMock()
        mock_service.get_obligations = AsyncMock(
            side_effect=PermissionError("HMRC auth failed")
        )

        with patch(
            "backend.jurisdictions.uk.paye.agent_tools._build_hmrc_service",
            return_value=mock_service,
        ):
            result = _parse_content(await paye_tools.get_obligations("123/AB45678"))

        assert result["success"] is False
        assert "authentication" in result["error"].lower()


class TestSubmitReturnMockMode:
    @pytest.mark.asyncio
    async def test_returns_mock_fps_receipt(self, paye_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(
            await paye_tools.submit_return("123/AB45678", "2024-04", {"submission_type": "fps"})
        )
        assert result["success"] is True
        assert result["mode"] == "mock"
        assert "FPS-123/AB45678-2024-04" in result["submission_id"]

    @pytest.mark.asyncio
    async def test_returns_mock_eps_receipt(self, paye_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(
            await paye_tools.submit_return("123/AB45678", "2024-04", {"submission_type": "eps"})
        )
        assert result["success"] is True
        assert "EPS" in result["submission_id"]

    @pytest.mark.asyncio
    async def test_error_when_empref_missing(self, paye_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(await paye_tools.submit_return("", "2024-04", {}))
        assert result["success"] is False


class TestSubmitReturnLiveMode:
    @pytest.mark.asyncio
    async def test_submits_fps_when_live(self, paye_tools, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "live")

        mock_service = MagicMock()
        mock_service.submit_fps = AsyncMock(return_value={
            "submissionId": "FPS-001",
            "transactionId": "TX-001",
            "processingDate": "2024-05-10T10:00:00Z",
        })

        with patch(
            "backend.jurisdictions.uk.paye.agent_tools._build_hmrc_service",
            return_value=mock_service,
        ):
            result = _parse_content(
                await paye_tools.submit_return("123/AB45678", "2024-04", {"submission_type": "fps"})
            )

        assert result["success"] is True
        assert result["mode"] == "live"
        assert result["submission_id"] == "FPS-001"
        mock_service.submit_fps.assert_called_once()

    @pytest.mark.asyncio
    async def test_submits_eps_when_live(self, paye_tools, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "live")

        mock_service = MagicMock()
        mock_service.submit_eps = AsyncMock(return_value={
            "submissionId": "EPS-001",
            "transactionId": "TX-EPS-001",
            "processingDate": "2024-06-10T10:00:00Z",
        })

        with patch(
            "backend.jurisdictions.uk.paye.agent_tools._build_hmrc_service",
            return_value=mock_service,
        ):
            result = _parse_content(
                await paye_tools.submit_return("123/AB45678", "2024-04", {"submission_type": "eps"})
            )

        assert result["success"] is True
        assert result["submission_id"] == "EPS-001"
        mock_service.submit_eps.assert_called_once()


class TestGetReturnMockMode:
    @pytest.mark.asyncio
    async def test_returns_mock_data(self, paye_tools, monkeypatch):
        monkeypatch.delenv("HMRC_MODE", raising=False)
        result = _parse_content(await paye_tools.get_return("123/AB45678", "2024-04"))
        assert result["success"] is True
        assert result["mode"] == "mock"
        assert result["empref"] == "123/AB45678"


class TestGetReturnLiveMode:
    @pytest.mark.asyncio
    async def test_calls_service_when_live(self, paye_tools, monkeypatch):
        monkeypatch.setenv("HMRC_MODE", "live")

        mock_ret = MagicMock()
        mock_ret.submission_id = "FPS-001"
        mock_ret.transaction_id = "TX-001"
        mock_ret.processing_date = "2024-05-10T10:00:00Z"
        mock_ret.submission_type = "FPS"

        mock_service = MagicMock()
        mock_service.get_fps = AsyncMock(return_value=mock_ret)

        with patch(
            "backend.jurisdictions.uk.paye.agent_tools._build_hmrc_service",
            return_value=mock_service,
        ):
            result = _parse_content(await paye_tools.get_return("123/AB45678", "FPS-001"))

        assert result["success"] is True
        assert result["submission_id"] == "FPS-001"
        assert result["submission_type"] == "FPS"
