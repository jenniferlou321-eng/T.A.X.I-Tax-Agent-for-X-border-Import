"""Tests for GovTalkClient — envelope building, IRmark, submit, poll."""

import uuid
import zlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.channels.govtalk.client import GovTalkClient, NS_GOV, _xml_escape
from backend.channels.govtalk.exceptions import (
    GovTalkError,
    TransientError,
    PermanentError,
    AuthError,
)


# ── Fixtures ──

@pytest.fixture
def client():
    return GovTalkClient(
        vendor_id="TEST_VENDOR",
        vendor_password="test_pass",
        base_url="https://test-transaction-engine.tax.service.gov.uk",
        gateway_test=True,
    )


# ── compute_irmark ──

class TestComputeIRmark:
    def test_crc32_uppercase_hex(self):
        body = "<IRenvelope><CT600 /></IRenvelope>"
        irmark = GovTalkClient.compute_irmark(body)
        expected = format(zlib.crc32(body.encode("utf-8")) & 0xFFFFFFFF, "08X")
        assert irmark == expected
        assert len(irmark) == 8
        assert irmark.isupper()

    def test_empty_body_gives_crc32_of_empty(self):
        irmark = GovTalkClient.compute_irmark("")
        expected = format(zlib.crc32(b"") & 0xFFFFFFFF, "08X")
        assert irmark == expected

    def test_deterministic(self):
        body = "<Test>content</Test>"
        assert GovTalkClient.compute_irmark(body) == GovTalkClient.compute_irmark(body)


# ── build_envelope ──

class TestBuildEnvelope:
    def test_contains_required_elements(self, client):
        xml = client.build_envelope(
            class_name="HMRC-CT-CT600",
            body_xml="<IRenvelope />",
        )
        assert "HMRC-CT-CT600" in xml
        assert "<Qualifier>request</Qualifier>" in xml
        assert "<EnvelopeVersion>1.0</EnvelopeVersion>" in xml
        assert "<SenderID>TEST_VENDOR</SenderID>" in xml
        assert "<Method>clear</Method>" in xml
        assert "<Value>test_pass</Value>" in xml
        assert "<GatewayTest>1</GatewayTest>" in xml
        assert "<Body>" in xml
        assert "<IRenvelope />" in xml
        assert "<IRmark>" in xml

    def test_irmark_in_envelope_matches_body(self, client):
        body_xml = "<IRenvelope><Data>123</Data></IRenvelope>"
        xml = client.build_envelope(class_name="HMRC-CT-CT600", body_xml=body_xml)
        expected_irmark = GovTalkClient.compute_irmark(body_xml)
        assert f"<IRmark>{expected_irmark}</IRmark>" in xml

    def test_custom_correlation_id(self, client):
        cid = "my-custom-id-123"
        xml = client.build_envelope(
            class_name="HMRC-CT-CT600",
            body_xml="<Data />",
            correlation_id=cid,
        )
        assert f"<CorrelationID>{cid}</CorrelationID>" in xml

    def test_auto_correlation_id_is_uuid(self, client):
        xml = client.build_envelope(
            class_name="HMRC-CT-CT600",
            body_xml="<Data />",
        )
        # Extract correlation ID
        import re
        match = re.search(r"<CorrelationID>([^<]+)</CorrelationID>", xml)
        assert match is not None
        cid = match.group(1)
        # Should be a valid UUID
        uuid.UUID(cid)

    def test_qualifier_poll(self, client):
        xml = client.build_envelope(
            class_name="HMRC-CT-CT600",
            body_xml="",
            qualifier="poll",
        )
        assert "<Qualifier>poll</Qualifier>" in xml

    def test_gateway_test_false(self):
        client_prod = GovTalkClient(
            vendor_id="V", vendor_password="P",
            gateway_test=False,
        )
        xml = client_prod.build_envelope("HMRC-CT-CT600", "<X />")
        assert "<GatewayTest>0</GatewayTest>" in xml

    def test_xml_escapes_special_chars(self, client):
        xml = client.build_envelope(
            class_name="HMRC-<CT>",  # should be escaped
            body_xml="<Data />",
        )
        assert "HMRC-&lt;CT&gt;" in xml
        assert "HMRC-<CT>" not in xml

    def test_empty_body_no_irmark(self, client):
        xml = client.build_envelope(
            class_name="HMRC-CT-CT600",
            body_xml="",
            qualifier="poll",
        )
        assert "<IRmark>" not in xml
        assert "<Body />" in xml


# ── _xml_escape ──

class TestXmlEscape:
    def test_ampersand(self):
        assert _xml_escape("a&b") == "a&amp;b"

    def test_angle_brackets(self):
        assert _xml_escape("<x>") == "&lt;x&gt;"

    def test_quotes(self):
        assert _xml_escape('"hi"') == "&quot;hi&quot;"
        assert _xml_escape("'hi'") == "&apos;hi&apos;"


# ── submit ──

class TestSubmit:
    @pytest.mark.asyncio
    async def test_returns_receipt_and_poll_url(self, client):
        correlation_id = str(uuid.uuid4())
        mock_response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="{NS_GOV}">
  <Header>
    <MessageDetails>
      <Class>HMRC-CT-CT600</Class>
      <Qualifier>response</Qualifier>
      <CorrelationID>{correlation_id}</CorrelationID>
    </MessageDetails>
  </Header>
  <Body>
    <SubmitResponse>
      <ReceiptID>REC-12345</ReceiptID>
      <PollURL>https://test-transaction-engine.tax.service.gov.uk/poll</PollURL>
      <Message>Received</Message>
    </SubmitResponse>
  </Body>
</GovTalkMessage>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = mock_response_xml

        with patch.object(client, '_get_client') as mock_get:
            mock_http = MagicMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            result = await client.submit("HMRC-CT-CT600", "<IRenvelope />")

        assert result["receipt_id"] == "REC-12345"
        assert "poll" in result["poll_url"]
        assert result["correlation_id"] == correlation_id

    @pytest.mark.asyncio
    async def test_raises_auth_error_on_401(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = ""

        with patch.object(client, '_get_client') as mock_get:
            mock_http = MagicMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            with pytest.raises(AuthError, match="authentication failed"):
                await client.submit("HMRC-CT-CT600", "<X />")

    @pytest.mark.asyncio
    async def test_raises_transient_on_500(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = ""

        with patch.object(client, '_get_client') as mock_get:
            mock_http = MagicMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            with pytest.raises(TransientError, match="server error"):
                await client.submit("HMRC-CT-CT600", "<X />")

    @pytest.mark.asyncio
    async def test_raises_permanent_on_error_response(self, client):
        mock_response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="{NS_GOV}">
  <Body>
    <ErrorResponse>
      <Error>Invalid XML schema</Error>
    </ErrorResponse>
  </Body>
</GovTalkMessage>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = mock_response_xml

        with patch.object(client, '_get_client') as mock_get:
            mock_http = MagicMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            with pytest.raises(PermanentError, match="Invalid XML schema"):
                await client.submit("HMRC-CT-CT600", "<X />")

    @pytest.mark.asyncio
    async def test_raises_transient_on_network_error(self, client):
        import httpx
        with patch.object(client, '_get_client') as mock_get:
            mock_http = MagicMock()
            mock_http.post = AsyncMock(side_effect=httpx.RequestError("timeout"))
            mock_get.return_value = mock_http

            with pytest.raises(TransientError, match="Network error"):
                await client.submit("HMRC-CT-CT600", "<X />")


# ── poll ──

class TestPoll:
    @pytest.mark.asyncio
    async def test_returns_accepted(self, client):
        mock_response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="{NS_GOV}">
  <Body>
    <PollResponse>
      <Result>Accepted</Result>
      <Message>Your CT600 has been successfully submitted</Message>
      <Receipt>
        <ReceiptID>REC-12345</ReceiptID>
        <ServiceSpecificMessage>
          <FormBundleNumber>FB-987654</FormBundleNumber>
          <ProcessingDate>2026-06-14T10:05:00Z</ProcessingDate>
        </ServiceSpecificMessage>
      </Receipt>
    </PollResponse>
  </Body>
</GovTalkMessage>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = mock_response_xml

        with patch.object(client, '_get_client') as mock_get:
            mock_http = MagicMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            result = await client.poll("HMRC-CT-CT600", "corr-id-123")

        assert result["status"] == "Accepted"
        assert result["receipt_id"] == "REC-12345"
        assert result["form_bundle_number"] == "FB-987654"
        assert result["correlation_id"] == "corr-id-123"

    @pytest.mark.asyncio
    async def test_returns_pending(self, client):
        mock_response_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="{NS_GOV}">
  <Body>
    <PollResponse>
      <Result>Pending</Result>
    </PollResponse>
  </Body>
</GovTalkMessage>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = mock_response_xml

        with patch.object(client, '_get_client') as mock_get:
            mock_http = MagicMock()
            mock_http.post = AsyncMock(return_value=mock_resp)
            mock_get.return_value = mock_http

            result = await client.poll("HMRC-CT-CT600", "corr-id-123")

        assert result["status"] == "Pending"


# ── submit_and_poll ──

class TestSubmitAndPoll:
    @pytest.mark.asyncio
    async def test_accepts_after_pending(self, client):
        # Mock submit to return poll URL
        submit_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="{NS_GOV}">
  <Header><MessageDetails><CorrelationID>corr-1</CorrelationID></MessageDetails></Header>
  <Body>
    <SubmitResponse>
      <ReceiptID>REC-1</ReceiptID>
      <PollURL>https://test-transaction-engine.tax.service.gov.uk/poll</PollURL>
    </SubmitResponse>
  </Body>
</GovTalkMessage>"""

        pending_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="{NS_GOV}">
  <Body><PollResponse><Result>Pending</Result></PollResponse></Body>
</GovTalkMessage>"""

        accepted_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="{NS_GOV}">
  <Body>
    <PollResponse>
      <Result>Accepted</Result>
      <Message>Done</Message>
      <Receipt><ReceiptID>REC-1</ReceiptID>
        <ServiceSpecificMessage><FormBundleNumber>FB-1</FormBundleNumber></ServiceSpecificMessage>
      </Receipt>
    </PollResponse>
  </Body>
</GovTalkMessage>"""

        submit_resp = MagicMock(status_code=200, text=submit_xml)
        pending_resp = MagicMock(status_code=200, text=pending_xml)
        accepted_resp = MagicMock(status_code=200, text=accepted_xml)

        call_count = 0
        async def mock_post(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return submit_resp
            elif call_count == 2:
                return pending_resp
            else:
                return accepted_resp

        with patch.object(client, '_get_client') as mock_get:
            mock_http = MagicMock()
            mock_http.post = mock_post
            mock_get.return_value = mock_http

            # Speed up polling for test
            client.poll_interval_base = 0.01
            client.poll_interval_max = 0.01

            result = await client.submit_and_poll("HMRC-CT-CT600", "<X />")

        assert result["status"] == "Accepted"
        assert result["form_bundle_number"] == "FB-1"


# ── Class constants ──

class TestClassConstants:
    def test_ct600(self, client):
        assert client.CLASS_CT600 == "HMRC-CT-CT600"

    def test_fps(self, client):
        assert client.CLASS_FPS == "HMRC-PAYE-RTI-FPS"

    def test_eps(self, client):
        assert client.CLASS_EPS == "HMRC-PAYE-RTI-EPS"

    def test_eyu(self, client):
        assert client.CLASS_EYU == "HMRC-PAYE-RTI-EYU"

    def test_sdlt(self, client):
        assert client.CLASS_SDLT == "HMRC-SDLT-RETURN"
