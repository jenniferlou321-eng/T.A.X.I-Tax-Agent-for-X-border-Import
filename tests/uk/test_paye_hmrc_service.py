"""Tests for HMRCPAYEService — PAYE RTI via GovTalk XML + REST obligations."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.jurisdictions.uk.paye.hmrc_service import (
    HMRCPAYEService,
    PAYEObligation,
    PAYEReturnView,
)
from backend.channels.govtalk import GovTalkClient


@pytest.fixture
def mock_oauth():
    oauth = MagicMock()
    oauth.authenticate_silent = AsyncMock()
    oauth.authenticate_silent.return_value = MagicMock(success=True, token="paye_test_token")
    return oauth


@pytest.fixture
def mock_govtalk():
    """Mock GovTalkClient that returns Accepted immediately."""
    govtalk = MagicMock(spec=GovTalkClient)
    govtalk.submit_and_poll = AsyncMock(return_value={
        "status": "Accepted",
        "receipt_id": "REC-FPS-001",
        "poll_url": "https://test-transaction-engine.tax.service.gov.uk/poll",
        "correlation_id": "corr-fps-001",
        "form_bundle_number": "FB-FPS-001",
        "processing_date": "2026-06-14T10:05:00Z",
        "message": "FPS accepted",
    })
    govtalk.poll = AsyncMock(return_value={
        "status": "Accepted",
        "receipt_id": "REC-FPS-001",
        "correlation_id": "corr-fps-001",
        "form_bundle_number": "FB-FPS-001",
        "processing_date": "2026-06-14T10:05:00Z",
        "message": "",
    })
    return govtalk


@pytest.fixture
def paye_service(mock_oauth, mock_govtalk):
    return HMRCPAYEService(
        base_url="https://test-api.service.hmrc.gov.uk",
        oauth=mock_oauth,
        govtalk_client=mock_govtalk,
    )


class TestHMRCPAYEServiceInit:
    def test_accept_header_is_v2(self, paye_service):
        assert paye_service._accept_header == "application/vnd.hmrc.2.0+json"

    def test_govtalk_client_injected(self, paye_service, mock_govtalk):
        assert paye_service._govtalk is mock_govtalk


class TestGetObligations:
    @pytest.mark.asyncio
    async def test_returns_parsed_obligations(self, paye_service):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "obligations": [
                {
                    "start": "2024-04-06",
                    "end": "2024-05-05",
                    "due": "2024-05-19",
                    "status": "F",
                    "periodKey": "2024-04",
                    "type": "FPS",
                    "received": "2024-05-10",
                },
                {
                    "start": "2024-05-06",
                    "end": "2024-06-05",
                    "due": "2024-06-19",
                    "status": "O",
                    "periodKey": "2024-05",
                    "type": "FPS",
                },
            ]
        }

        with patch.object(paye_service, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = mock_client

            result = await paye_service.get_obligations(empref="123/AB45678")

        assert len(result) == 2
        assert result[0].period_key == "2024-04"
        assert result[0].submission_type == "FPS"
        assert result[0].status == "F"
        assert result[1].status == "O"

    @pytest.mark.asyncio
    async def test_uses_empref_in_url(self, paye_service):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"obligations": []}

        with patch.object(paye_service, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = mock_client

            await paye_service.get_obligations(empref="456/CD78901")

        call_args = mock_client.get.call_args
        assert "456/CD78901" in str(call_args)


class TestSubmitFPS:
    @pytest.mark.asyncio
    async def test_uses_govtalk_client(self, paye_service, mock_govtalk):
        result = await paye_service.submit_fps(
            empref="123/AB45678",
            body={
                "total_paye_income": 50000,
                "total_tax_deducted": 8000,
                "tax_year": "2024-25",
                "period_start": "2024-04-06",
                "period_end": "2024-05-05",
            },
        )

        mock_govtalk.submit_and_poll.assert_called_once()
        call_args = mock_govtalk.submit_and_poll.call_args
        assert call_args[1]["class_name"] == GovTalkClient.CLASS_FPS
        assert "123/AB45678" in call_args[1]["body_xml"]

        assert result["submissionId"] == "REC-FPS-001"
        assert result["correlationId"] == "corr-fps-001"

    @pytest.mark.asyncio
    async def test_raises_permission_error_on_auth(self, paye_service, mock_govtalk):
        from backend.channels.govtalk.exceptions import AuthError as GovTalkAuthError
        mock_govtalk.submit_and_poll.side_effect = GovTalkAuthError("bad creds")

        with pytest.raises(PermissionError, match="GovTalk authentication failed"):
            await paye_service.submit_fps(empref="123/AB45678", body={})

    @pytest.mark.asyncio
    async def test_raises_value_error_on_rejection(self, paye_service, mock_govtalk):
        from backend.channels.govtalk.exceptions import PermanentError
        mock_govtalk.submit_and_poll.side_effect = PermanentError("invalid FPS")

        with pytest.raises(ValueError, match="FPS submission rejected"):
            await paye_service.submit_fps(empref="123/AB45678", body={})


class TestSubmitEPS:
    @pytest.mark.asyncio
    async def test_uses_govtalk_client_eps_class(self, paye_service, mock_govtalk):
        result = await paye_service.submit_eps(
            empref="123/AB45678",
            body={
                "total_pay_bill": 500000,
                "apprenticeship_levy_payable": 1250,
                "tax_year": "2024-25",
            },
        )

        mock_govtalk.submit_and_poll.assert_called_once()
        call_args = mock_govtalk.submit_and_poll.call_args
        assert call_args[1]["class_name"] == GovTalkClient.CLASS_EPS
        assert "123/AB45678" in call_args[1]["body_xml"]

    @pytest.mark.asyncio
    async def test_includes_levy_in_body(self, paye_service, mock_govtalk):
        await paye_service.submit_eps(
            empref="123/AB45678",
            body={
                "total_pay_bill": 1000000,
                "apprenticeship_levy_payable": 3750,
                "tax_year": "2024-25",
            },
        )

        call_args = mock_govtalk.submit_and_poll.call_args
        body_xml = call_args[1]["body_xml"]
        assert "ApprenticeshipLevy" in body_xml


class TestSubmitEYU:
    @pytest.mark.asyncio
    async def test_uses_govtalk_client_eyu_class(self, paye_service, mock_govtalk):
        result = await paye_service.submit_eyu(
            empref="123/AB45678",
            body={
                "total_paye_income": 45000,
                "tax_year": "2023-24",
            },
        )

        mock_govtalk.submit_and_poll.assert_called_once()
        call_args = mock_govtalk.submit_and_poll.call_args
        assert call_args[1]["class_name"] == GovTalkClient.CLASS_EYU


class TestGetFPS:
    @pytest.mark.asyncio
    async def test_returns_view_with_correlation_id(self, paye_service, mock_govtalk):
        result = await paye_service.get_fps(
            empref="123/AB45678",
            submission_id="REC-FPS-001",
            correlation_id="corr-fps-001",
        )

        assert isinstance(result, PAYEReturnView)
        assert result.submission_id == "REC-FPS-001"
        assert result.correlation_id == "corr-fps-001"
        mock_govtalk.poll.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_basic_view_without_correlation_id(self, paye_service, mock_govtalk):
        result = await paye_service.get_fps(
            empref="123/AB45678",
            submission_id="FPS-001",
        )

        assert isinstance(result, PAYEReturnView)
        assert result.submission_id == "FPS-001"
        mock_govtalk.poll.assert_not_called()
