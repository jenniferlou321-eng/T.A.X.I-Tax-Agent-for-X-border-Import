"""Tests for HMRCSDLTService — SDLT via GovTalk XML."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.jurisdictions.uk.stamp_duty.hmrc_service import (
    HMRCSDLTService,
    SDLTReturnView,
)
from backend.channels.govtalk import GovTalkClient


@pytest.fixture
def mock_govtalk():
    govtalk = MagicMock(spec=GovTalkClient)
    govtalk.submit_and_poll = AsyncMock(return_value={
        "status": "Accepted",
        "receipt_id": "REC-SDLT-001",
        "poll_url": "https://test-transaction-engine.tax.service.gov.uk/poll",
        "correlation_id": "corr-sdlt-001",
        "form_bundle_number": "FB-SDLT-001",
        "processing_date": "2026-06-14T10:05:00Z",
        "message": "SDLT return accepted",
    })
    govtalk.poll = AsyncMock(return_value={
        "status": "Accepted",
        "receipt_id": "REC-SDLT-001",
        "correlation_id": "corr-sdlt-001",
        "form_bundle_number": "FB-SDLT-001",
        "processing_date": "2026-06-14T10:05:00Z",
        "message": "",
    })
    return govtalk


@pytest.fixture
def sdlt_service(mock_govtalk):
    return HMRCSDLTService(govtalk_client=mock_govtalk)


class TestSubmitReturn:
    @pytest.mark.asyncio
    async def test_uses_govtalk_client(self, sdlt_service, mock_govtalk):
        result = await sdlt_service.submit_return(
            utr="1234567890123",
            body={
                "property_value": 500000,
                "property_type": "residential",
                "sdlt_payable": 12500,
                "effective_date": "2024-06-15",
            },
        )

        mock_govtalk.submit_and_poll.assert_called_once()
        call_args = mock_govtalk.submit_and_poll.call_args
        assert call_args[1]["class_name"] == GovTalkClient.CLASS_SDLT
        assert "1234567890123" in call_args[1]["body_xml"]

        assert result["formBundleNumber"] == "FB-SDLT-001"
        assert result["correlationId"] == "corr-sdlt-001"

    @pytest.mark.asyncio
    async def test_raises_permission_error_on_auth(self, sdlt_service, mock_govtalk):
        from backend.channels.govtalk.exceptions import AuthError as GovTalkAuthError
        mock_govtalk.submit_and_poll.side_effect = GovTalkAuthError("bad creds")

        with pytest.raises(PermissionError, match="GovTalk authentication failed"):
            await sdlt_service.submit_return(utr="1234567890123", body={})

    @pytest.mark.asyncio
    async def test_raises_value_error_on_rejection(self, sdlt_service, mock_govtalk):
        from backend.channels.govtalk.exceptions import PermanentError
        mock_govtalk.submit_and_poll.side_effect = PermanentError("invalid XML")

        with pytest.raises(ValueError, match="SDLT submission rejected"):
            await sdlt_service.submit_return(utr="1234567890123", body={})


class TestGetReturn:
    @pytest.mark.asyncio
    async def test_returns_view_with_correlation_id(self, sdlt_service, mock_govtalk):
        result = await sdlt_service.get_return(
            utr="1234567890123",
            submission_id="REC-SDLT-001",
            correlation_id="corr-sdlt-001",
        )

        assert isinstance(result, SDLTReturnView)
        assert result.submission_id == "REC-SDLT-001"
        assert result.correlation_id == "corr-sdlt-001"
        mock_govtalk.poll.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_basic_view_without_correlation_id(self, sdlt_service, mock_govtalk):
        result = await sdlt_service.get_return(
            utr="1234567890123",
            submission_id="SDLT-001",
        )

        assert isinstance(result, SDLTReturnView)
        assert result.submission_id == "SDLT-001"
        mock_govtalk.poll.assert_not_called()
