"""Tests for UK Apprenticeship Levy — calculator, template, adapter, agent tool."""

import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from backend.jurisdictions.uk.paye.calculator import (
    calculate_apprenticeship_levy,
    APPRENTICESHIP_LEVY_RATE,
    APPRENTICESHIP_LEVY_ANNUAL_ALLOWANCE,
)
from backend.jurisdictions.uk.paye.template import PAYE_TEMPLATE
from backend.jurisdictions.uk.paye import UKPAYEAdapter
from backend.jurisdictions.uk.paye.agent_tools import UKPAYEAgentToolSet
from backend.models.tax_data import (
    TaxData, TaxpayerInfo, FiscalPeriod, TaxType, LineItem, PeriodType,
)


def _parse_content(result: dict) -> dict:
    return json.loads(result["content"][0]["text"])


# ── Calculator ──

class TestCalculateApprenticeshipLevy:
    def test_constants(self):
        assert APPRENTICESHIP_LEVY_RATE == Decimal("0.005")
        assert APPRENTICESHIP_LEVY_ANNUAL_ALLOWANCE == Decimal("15000")

    def test_monthly_above_threshold(self):
        """£500k monthly pay bill → £2,500 gross - £1,250 allowance = £1,250 payable."""
        result = calculate_apprenticeship_levy(
            total_pay_bill=Decimal("500000"),
            levy_allowance_claimed=Decimal("15000"),
            is_annual=False,
        )
        assert result.total_tax_due == Decimal("1250.00")
        box_map = {b.category: b.amount for b in result.breakdown}
        assert box_map["total_pay_bill"] == Decimal("500000")
        assert box_map["gross_levy"] == Decimal("2500.00")
        assert box_map["levy_allowance"] == Decimal("1250.00")
        assert box_map["apprenticeship_levy_payable"] == Decimal("1250.00")

    def test_monthly_small_pay_bill_levy_zero(self):
        """£100k monthly → £500 gross - £1,250 allowance → max(0, ...) = 0."""
        result = calculate_apprenticeship_levy(
            total_pay_bill=Decimal("100000"),
            is_annual=False,
        )
        assert result.total_tax_due == Decimal("0.00")
        assert result.breakdown[4].amount == Decimal("0.00")  # apprenticeship_levy_payable

    def test_annual_pay_bill_large_employer(self):
        """Annual £3.6M → 0.5% = £18,000 - £15,000 = £3,000."""
        result = calculate_apprenticeship_levy(
            total_pay_bill=Decimal("3600000"),
            levy_allowance_claimed=Decimal("15000"),
            is_annual=True,
        )
        assert result.total_tax_due == Decimal("3000.00")
        assert result.breakdown[3].amount == Decimal("15000.00")  # allowance

    def test_annual_just_below_threshold(self):
        """Annual £2.9M → 0.5% = £14,500 - £15,000 = 0."""
        result = calculate_apprenticeship_levy(
            total_pay_bill=Decimal("2900000"),
            is_annual=True,
        )
        assert result.total_tax_due == Decimal("0.00")

    def test_warning_for_sub_threshold_employer(self):
        """Annual pay bill below £3M should trigger a warning (when given monthly)."""
        result = calculate_apprenticeship_levy(
            total_pay_bill=Decimal("100000"),  # annual £1.2M
            is_annual=False,
        )
        assert len(result.warnings) == 1
        assert "£3,000,000 threshold" in result.warnings[0]

    def test_no_warning_when_above_threshold(self):
        """Annual pay bill above £3M should NOT trigger a warning."""
        result = calculate_apprenticeship_levy(
            total_pay_bill=Decimal("500000"),  # annual £6M
            is_annual=False,
        )
        assert result.warnings == []

    def test_default_allowance_is_15000(self):
        result = calculate_apprenticeship_levy(
            total_pay_bill=Decimal("1000000"),
            is_annual=True,
        )
        # £1M × 0.5% = £5,000 - £15,000 → 0
        assert result.total_tax_due == Decimal("0.00")

    def test_rounding(self):
        """Check 2-decimal rounding."""
        result = calculate_apprenticeship_levy(
            total_pay_bill=Decimal("1234567"),
            is_annual=False,
        )
        # gross = 1234567 × 0.005 = 6172.835
        # allowance (monthly) = 1250
        # payable = max(0, 6172.835 - 1250) = 4922.835 → 4922.84
        assert result.total_tax_due == Decimal("4922.84")

    def test_zero_pay_bill(self):
        result = calculate_apprenticeship_levy(
            total_pay_bill=Decimal("0"),
            is_annual=False,
        )
        assert result.total_tax_due == Decimal("0.00")


# ── Template ──

class TestApprenticeshipLevyTemplate:
    def test_template_has_levy_fields(self):
        # Find the EPS section
        eps_section = next(s for s in PAYE_TEMPLATE.sections if "EPS" in s.title)
        field_keys = {f.key for f in eps_section.fields}
        assert "apprenticeship_levy_payable" in field_keys
        assert "total_pay_bill" in field_keys

    def test_eps_section_is_optional(self):
        eps_section = next(s for s in PAYE_TEMPLATE.sections if "EPS" in s.title)
        assert eps_section.is_optional is True


# ── Adapter to_filing_format ──

class TestAdapterEPSBody:
    def _build_data(self, submission_type: str, line_items=None, metadata=None):
        return TaxData(
            tax_type=TaxType.PAYE,
            period=FiscalPeriod(
                year=2024, period_type=PeriodType.MONTHLY,
                period_key="2024-04", start_date=date(2024, 4, 6), end_date=date(2024, 5, 5),
            ),
            taxpayer=TaxpayerInfo(name="Acme Ltd", tax_id="123/AB45678", tax_id_type="empref"),
            line_items=line_items or [],
            metadata=metadata or {"submission_type": submission_type},
        )

    def test_eps_body_includes_apprenticeship_levy(self):
        adapter = UKPAYEAdapter()
        data = self._build_data(
            "eps",
            line_items=[
                LineItem(category="total_pay_bill", amount=Decimal("500000"), currency="GBP"),
                LineItem(category="apprenticeship_levy_payable", amount=Decimal("1250"), currency="GBP"),
                LineItem(category="employment_allowance_claimed", amount=Decimal("5000"), currency="GBP"),
            ],
        )
        payload = adapter.to_filing_format(TaxType.PAYE, data)
        body = payload.body
        assert "apprenticeshipLevy" in body
        assert body["apprenticeshipLevy"]["totalPayBill"] == 500000.0
        assert body["apprenticeshipLevy"]["levyDueYTD"] == 1250.0
        assert body["apprenticeshipLevy"]["levyAllowance"] == 1250.0  # default monthly
        assert "employmentAllowance" in body
        assert body["employmentAllowance"]["amountClaimed"] == 5000.0

    def test_fps_body_unchanged(self):
        adapter = UKPAYEAdapter()
        data = self._build_data(
            "fps",
            line_items=[
                LineItem(category="total_paye_income", amount=Decimal("100000"), currency="GBP"),
                LineItem(category="total_tax_deducted", amount=Decimal("20000"), currency="GBP"),
            ],
        )
        payload = adapter.to_filing_format(TaxType.PAYE, data)
        body = payload.body
        assert "totals" in body
        assert body["totals"]["grossPay"] == 100000.0
        assert body["totals"]["taxDeducted"] == 20000.0
        assert "apprenticeshipLevy" not in body

    def test_default_submission_type_is_fps(self):
        adapter = UKPAYEAdapter()
        data = TaxData(
            tax_type=TaxType.PAYE,
            period=FiscalPeriod(
                year=2024, period_type=PeriodType.MONTHLY,
                period_key="2024-04", start_date=date(2024, 4, 6), end_date=date(2024, 5, 5),
            ),
            taxpayer=TaxpayerInfo(name="Acme", tax_id="123/AB", tax_id_type="empref"),
            line_items=[],
            metadata={},  # no submission_type
        )
        payload = adapter.to_filing_format(TaxType.PAYE, data)
        # Defaults to FPS
        assert "totals" in payload.body
        assert "apprenticeshipLevy" not in payload.body


# ── Agent Tool ──

class TestApprenticeshipLevyAgentTool:
    @pytest.fixture
    def tools(self):
        return UKPAYEAgentToolSet()

    @pytest.mark.asyncio
    async def test_monthly_pay_bill(self, tools):
        result = _parse_content(await tools.calculate_apprenticeship_levy({
            "total_pay_bill": "500000",
            "levy_allowance_claimed": "15000",
        }))
        assert result["success"] is True
        assert result["apprenticeship_levy_payable"] == 1250.0
        assert result["gross_levy"] == 2500.0
        assert result["levy_allowance"] == 1250.0
        assert result["levy_rate"] == 0.005

    @pytest.mark.asyncio
    async def test_annual_pay_bill(self, tools):
        result = _parse_content(await tools.calculate_apprenticeship_levy({
            "total_pay_bill": "3600000",
            "is_annual": True,
        }))
        assert result["success"] is True
        assert result["apprenticeship_levy_payable"] == 3000.0
        assert result["levy_allowance"] == 15000.0  # full annual

    @pytest.mark.asyncio
    async def test_zero_pay_bill(self, tools):
        result = _parse_content(await tools.calculate_apprenticeship_levy({
            "total_pay_bill": "0",
        }))
        assert result["success"] is True
        assert result["apprenticeship_levy_payable"] == 0.0

    @pytest.mark.asyncio
    async def test_warning_for_small_employer(self, tools):
        result = _parse_content(await tools.calculate_apprenticeship_levy({
            "total_pay_bill": "50000",  # annual £600k, well below £3M
        }))
        assert result["success"] is True
        assert len(result["warnings"]) == 1
        assert "threshold" in result["warnings"][0].lower()

    @pytest.mark.asyncio
    async def test_handles_error(self, tools):
        # Pass invalid string that can't convert to Decimal
        result = _parse_content(await tools.calculate_apprenticeship_levy({
            "total_pay_bill": "not_a_number",
        }))
        assert result["success"] is False

    def test_metadata_includes_levy_tool(self, tools):
        meta = tools.get_tool_metadata()
        names = {m["name"] for m in meta}
        assert "calculate_apprenticeship_levy" in names

        # Verify the metadata has a proper JSON schema
        levy_meta = next(m for m in meta if m["name"] == "calculate_apprenticeship_levy")
        assert "input_schema" in levy_meta
        schema = levy_meta["input_schema"]
        assert "total_pay_bill" in schema.get("properties", {})
        assert "is_annual" in schema.get("properties", {})
