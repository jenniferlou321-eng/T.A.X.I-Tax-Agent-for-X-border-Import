"""Tests for BrowserChannel abstract base + CN concrete channels."""

import pytest

from backend.channels.browser_channel import (
    BrowserChannel,
    BrowserChannelError,
    LoginRequired,
)
from backend.models.results import FilingPayload, FilingStatus
from backend.models.tax_data import TaxType, FiscalPeriod, TaxpayerInfo, PeriodType
from datetime import date


def make_payload(body: dict) -> FilingPayload:
    return FilingPayload(
        tax_type=TaxType.CORPORATION_TAX,
        period=FiscalPeriod(
            year=2023,
            period_type=PeriodType.QUARTERLY,
            period_key="2023-Q1",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 3, 31),
        ),
        taxpayer=TaxpayerInfo(name="Test Co", tax_id="91110000000000000X", tax_id_type="uscc"),
        body=body,
    )


class TestBrowserChannel:
    def test_abstract_methods_required(self):
        """Cannot instantiate BrowserChannel directly."""
        with pytest.raises(TypeError):
            BrowserChannel(jurisdiction="xx", tax_type="yy")

    def test_concrete_subclass_can_instantiate(self):
        from backend.jurisdictions.cn.channels.cn_vat_channel import CNVATBrowserChannel
        ch = CNVATBrowserChannel(province="beijing", headless=True)
        assert ch.jurisdiction == "cn"
        assert ch.tax_type == "cn_vat"
        assert ch.headless is True

    def test_login_url_cn_vat(self):
        from backend.jurisdictions.cn.channels.cn_vat_channel import CNVATBrowserChannel
        ch = CNVATBrowserChannel(province="shanghai")
        assert "etax.shanghai.chinatax.gov.cn" in ch.login_url()
        assert "login" in ch.login_url()

    def test_form_url_cn_vat(self):
        from backend.jurisdictions.cn.channels.cn_vat_channel import CNVATBrowserChannel
        ch = CNVATBrowserChannel(province="beijing")
        url = ch.form_url()
        assert "etax.beijing.chinatax.gov.cn" in url
        assert "zzs" in url  # 增值税

    def test_form_url_cn_cit_quarterly(self):
        from backend.jurisdictions.cn.channels.cn_cit_channel import CNCITBrowserChannel
        ch = CNCITBrowserChannel(declaration_type="quarterly")
        assert "jdys" in ch.form_url() or "qydsds" in ch.form_url()

    def test_form_url_cn_cit_annual(self):
        from backend.jurisdictions.cn.channels.cn_cit_channel import CNCITBrowserChannel
        ch = CNCITBrowserChannel(declaration_type="annual")
        assert "hscz" in ch.form_url()

    def test_screenshot_dir_created(self, tmp_path):
        from backend.jurisdictions.cn.channels.cn_vat_channel import CNVATBrowserChannel
        ch = CNVATBrowserChannel(headless=True)
        ch.screenshot_dir = tmp_path / "shots"
        ch.screenshot_dir.mkdir(parents=True, exist_ok=True)
        assert ch.screenshot_dir.exists()

    def test_login_required_can_be_raised(self):
        with pytest.raises(LoginRequired) as exc_info:
            raise LoginRequired("Need 2FA", session_id="abc-123")
        assert "Need 2FA" in str(exc_info.value)
        assert exc_info.value.session_id == "abc-123"

    def test_channel_type_is_browser(self):
        from backend.models.tax_data import ChannelType
        from backend.jurisdictions.cn.channels.cn_cit_channel import CNCITBrowserChannel
        ch = CNCITBrowserChannel()
        assert ch.channel_type == ChannelType.BROWSER


class TestCreateBrowserChannel:
    def test_factory_creates_cn_vat(self):
        from backend.channels.browser_channel import create_browser_channel
        ch = create_browser_channel("cn", "cn_vat", headless=True)
        assert ch.tax_type == "cn_vat"

    def test_factory_creates_cn_cit(self):
        from backend.channels.browser_channel import create_browser_channel
        ch = create_browser_channel("cn", "cn_cit", headless=True)
        assert ch.tax_type == "cn_cit"

    def test_factory_unknown_raises(self):
        from backend.channels.browser_channel import create_browser_channel
        with pytest.raises(NotImplementedError):
            create_browser_channel("xx", "yy")
