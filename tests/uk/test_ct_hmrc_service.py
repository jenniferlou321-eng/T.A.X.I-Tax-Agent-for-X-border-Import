"""Tests for HMRCCTService — Corporation Tax via GovTalk XML + REST obligations."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.jurisdictions.uk.corporation_tax.hmrc_service import (
    HMRCCTService,
    CTObligation,
    CTReturnView,
)
from backend.channels.govtalk import GovTalkClient


@pytest.fixture
def mock_oauth():
    oauth = MagicMock()
    oauth.authenticate_silent = AsyncMock()
    oauth.authenticate_silent.return_value = MagicMock(success=True, token="ct_test_token")
    return oauth


@pytest.fixture
def mock_govtalk():
    """Mock GovTalkClient that returns Accepted immediately."""
    govtalk = MagicMock(spec=GovTalkClient)
    govtalk.submit_and_poll = AsyncMock(return_value={
        "status": "Accepted",
        "receipt_id": "REC-CT-001",
        "poll_url": "https://test-transaction-engine.tax.service.gov.uk/poll",
        "correlation_id": "corr-ct-001",
        "form_bundle_number": "FB-CT-001",
        "processing_date": "2026-06-14T10:05:00Z",
        "message": "CT600 accepted",
    })
    govtalk.poll = AsyncMock(return_value={
        "status": "Accepted",
        "receipt_id": "REC-CT-001",
        "correlation_id": "corr-ct-001",
        "form_bundle_number": "FB-CT-001",
        "processing_date": "2026-06-14T10:05:00Z",
        "message": "",
    })
    return govtalk


@pytest.fixture
def ct_service(mock_oauth, mock_govtalk):
    return HMRCCTService(
        base_url="https://test-api.service.hmrc.gov.uk",
        oauth=mock_oauth,
        govtalk_client=mock_govtalk,
    )


class TestHMRCCTServiceInit:
    def test_accept_header_is_v2(self, ct_service):
        assert ct_service._accept_header == "application/vnd.hmrc.2.0+json"

    def test_govtalk_client_injected(self, ct_service, mock_govtalk):
        assert ct_service._govtalk is mock_govtalk


class TestGetObligations:
    @pytest.mark.asyncio
    async def test_returns_parsed_obligations(self, ct_service):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "obligations": [
                {
                    "start": "2024-04-01",
                    "end": "2025-03-31",
                    "due": "2026-01-01",
                    "status": "O",
                    "periodKey": "FY2024",
                },
                {
                    "start": "2023-04-01",
                    "end": "2024-03-31",
                    "due": "2025-01-01",
                    "status": "F",
                    "periodKey": "FY2023",
                    "received": "2025-02-15",
                },
            ]
        }

        with patch.object(ct_service, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = mock_client

            result = await ct_service.get_obligations(ctref="1234567890")

        assert len(result) == 2
        assert result[0].period_key == "FY2024"
        assert result[0].status == "O"
        assert result[0].start == date(2024, 4, 1)
        assert result[1].status == "F"
        assert result[1].received == date(2025, 2, 15)

    @pytest.mark.asyncio
    async def test_filters_by_status(self, ct_service):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {"obligations": []}

        with patch.object(ct_service, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = mock_client

            await ct_service.get_obligations(ctref="1234567890", status="O")

        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["status"] == "O"

    @pytest.mark.asyncio
    async def test_handles_hmrc_error(self, ct_service):
        import httpx
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"code": "INVALID_CTREF", "message": "Bad CT reference"}

        err = httpx.HTTPStatusError("bad", request=MagicMock(), response=mock_resp)
        mock_resp.raise_for_status.side_effect = err

        with patch.object(ct_service, '_get_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_get_client.return_value = mock_client

            with pytest.raises(ValueError, match="HMRC obligations error"):
                await ct_service.get_obligations(ctref="1234567890")


class TestSubmitReturn:
    @pytest.mark.asyncio
    async def test_uses_govtalk_client(self, ct_service, mock_govtalk):
        result = await ct_service.submit_return(
            ctref="1234567890",
            body={
                "turnover": 1000000,
                "taxable_total_profits": 250000,
                "company_name": "Acme Ltd",
                "period_start": "2024-04-01",
                "period_end": "2025-03-31",
            },
        )

        # GovTalkClient.submit_and_poll should have been called
        mock_govtalk.submit_and_poll.assert_called_once()
        call_args = mock_govtalk.submit_and_poll.call_args
        assert call_args[1]["class_name"] == GovTalkClient.CLASS_CT600
        # body_xml should contain the CTREF and company info
        assert "1234567890" in call_args[1]["body_xml"]
        assert "Acme Ltd" in call_args[1]["body_xml"]

        # Response mapped correctly
        assert result["formBundleNumber"] == "FB-CT-001"
        assert result["correlationId"] == "corr-ct-001"

    @pytest.mark.asyncio
    async def test_raises_permission_error_on_govtalk_auth(self, ct_service, mock_govtalk):
        from backend.channels.govtalk.exceptions import AuthError as GovTalkAuthError
        mock_govtalk.submit_and_poll.side_effect = GovTalkAuthError("bad creds")

        with pytest.raises(PermissionError, match="GovTalk authentication failed"):
            await ct_service.submit_return(ctref="1234567890", body={})

    @pytest.mark.asyncio
    async def test_raises_value_error_on_rejection(self, ct_service, mock_govtalk):
        from backend.channels.govtalk.exceptions import PermanentError
        mock_govtalk.submit_and_poll.side_effect = PermanentError("schema invalid")

        with pytest.raises(ValueError, match="CT600 submission rejected"):
            await ct_service.submit_return(ctref="1234567890", body={})

    @pytest.mark.asyncio
    async def test_handles_oauth_failure(self, ct_service, mock_govtalk):
        """submit_return no longer needs REST OAuth — it goes through GovTalk.
        OAuth failure is now a GovTalk auth error, tested above."""
        # Just verify the service still works when REST OAuth fails
        # (GovTalk uses Vendor ID, not REST OAuth tokens)
        ct_service.oauth.authenticate_silent.return_value = MagicMock(
            success=False, error="Token expired"
        )
        # submit_return should still work because it uses GovTalkClient
        result = await ct_service.submit_return(
            ctref="1234567890",
            body={"company_name": "Test", "period_start": "2024-04-01", "period_end": "2025-03-31"},
        )
        assert result["formBundleNumber"] == "FB-CT-001"


class TestGetReturn:
    @pytest.mark.asyncio
    async def test_returns_view_with_correlation_id(self, ct_service, mock_govtalk):
        result = await ct_service.get_return(
            ctref="1234567890",
            submission_id="REC-CT-001",
            correlation_id="corr-ct-001",
        )

        assert isinstance(result, CTReturnView)
        assert result.submission_id == "REC-CT-001"
        assert result.correlation_id == "corr-ct-001"
        # GovTalkClient.poll should have been called
        mock_govtalk.poll.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_basic_view_without_correlation_id(self, ct_service, mock_govtalk):
        result = await ct_service.get_return(
            ctref="1234567890",
            submission_id="SUB-001",
        )

        assert isinstance(result, CTReturnView)
        assert result.submission_id == "SUB-001"
        # No poll should be called without correlation_id
        mock_govtalk.poll.assert_not_called()
