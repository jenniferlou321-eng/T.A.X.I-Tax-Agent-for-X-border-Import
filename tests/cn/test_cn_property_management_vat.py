"""CN 物业管理服务 VAT 计算器 — 单元测试"""

from datetime import date
from decimal import Decimal

import pytest

from backend.models.tax_data import (
    LineItem, TaxData, TaxType, FiscalPeriod, TaxpayerInfo,
)
from backend.jurisdictions.cn.property_management_vat.calculator import (
    calculate_cn_property_management_vat,
    RATE_GENERAL,
    LEVY_RATE_SMALL,
    LEVY_RATE_SMALL_REDUCED,
)


def make_data(line_items=None, metadata=None, taxpayer_id="CN-pm-001") -> TaxData:
    return TaxData(
        tax_type=TaxType.CN_PROPERTY_MGMT_VAT,
        period=FiscalPeriod(
            year=2024,
            period_key="2024-Q1",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            period_type="quarterly",
        ),
        taxpayer=TaxpayerInfo(tax_id=taxpayer_id, name="Test PMC", tax_id_type="uscc"),
        line_items=[LineItem(category=k, amount=v) for k, v in (line_items or {}).items()],
        metadata=metadata or {},
    )


# ── 一般纳税人(6% 现代服务业) ──


class TestGeneralTaxpayer:

    def test_basic_6_percent(self):
        """年物业费 ¥120,000(含税) → 120000 / 1.06 × 6% = ¥6,792.45"""
        data = make_data(
            line_items={"service_income": Decimal("120000")},
            metadata={"taxpayer_type": "general"},
        )
        result = calculate_cn_property_management_vat(data)
        assert result.total_tax_due == Decimal("6792.45")
        assert result.warnings[0] == "一般纳税人 → 6% 现代服务业(物业管理)"

    def test_with_input_credit(self):
        """¥200,000 + 进项 ¥3,000 → 销项 11,320.75;应纳 8,320.75"""
        data = make_data(
            line_items={
                "service_income": Decimal("200000"),
                "input_tax": Decimal("3000"),
            },
            metadata={"taxpayer_type": "general"},
        )
        result = calculate_cn_property_management_vat(data)
        assert result.total_tax_due == Decimal("8320.75")
        assert any(d.category == "input_credit" for d in result.deductions)

    def test_with_ancillary_income(self):
        """物业费 ¥100,000 + 广告/停车等辅助收入 ¥20,000 = ¥120,000 → 6,792.45"""
        data = make_data(
            line_items={
                "service_income": Decimal("100000"),
                "ancillary_income": Decimal("20000"),
            },
            metadata={"taxpayer_type": "general"},
        )
        result = calculate_cn_property_management_vat(data)
        assert result.total_tax_due == Decimal("6792.45")

    def test_input_credit_exceeds_output_zero(self):
        data = make_data(
            line_items={
                "service_income": Decimal("106000"),
                "input_tax": Decimal("50000"),
            },
            metadata={"taxpayer_type": "general"},
        )
        result = calculate_cn_property_management_vat(data)
        # 销项 6000 - 进项 50000 → 留抵 → 0
        assert result.total_tax_due == Decimal("0.00")

    def test_exclusive_tax_inclusive_false(self):
        data = make_data(
            line_items={"service_income": Decimal("100000")},
            metadata={"taxpayer_type": "general", "tax_inclusive": False},
        )
        result = calculate_cn_property_management_vat(data)
        assert result.total_tax_due == Decimal("6000.00")


# ── 小规模纳税人(3% 征收率) ──


class TestSmallScaleTaxpayer:

    def test_basic_3_percent(self):
        """¥60,000 → 60000 / 1.03 × 3% = ¥1,747.57"""
        data = make_data(
            line_items={"service_income": Decimal("60000")},
            metadata={"taxpayer_type": "small"},
        )
        result = calculate_cn_property_management_vat(data)
        assert result.total_tax_due == Decimal("1747.57")
        assert "3% 征收率" in result.warnings[0]

    def test_reduced_1_percent_2023_2027(self):
        """小规模 + 阶段性减按 1% → 60000 / 1.01 × 1% = ¥594.06"""
        data = make_data(
            line_items={"service_income": Decimal("60000")},
            metadata={"taxpayer_type": "small", "reduced_rate": True},
        )
        result = calculate_cn_property_management_vat(data)
        assert result.total_tax_due == Decimal("594.06")
        assert "阶段性减按 1%" in result.warnings[0]

    def test_small_ignores_input_credit(self):
        data = make_data(
            line_items={
                "service_income": Decimal("60000"),
                "input_tax": Decimal("1000"),
            },
            metadata={"taxpayer_type": "small"},
        )
        result = calculate_cn_property_management_vat(data)
        # 简易计税,进项忽略
        assert result.total_tax_due == Decimal("1747.57")
        assert any("不允许抵扣" in w for w in result.warnings)


# ── 服务分项 ──


class TestServiceBreakdown:

    def test_breakdown_categories_present(self):
        data = make_data(
            line_items={"service_income": Decimal("120000")},
            metadata={
                "taxpayer_type": "general",
                "service_breakdown": {
                    "保安服务": Decimal("60000"),
                    "保洁服务": Decimal("40000"),
                    "绿化": Decimal("20000"),
                },
            },
        )
        result = calculate_cn_property_management_vat(data)
        categories = [b.category for b in result.breakdown]
        assert "breakdown_保安服务" in categories
        assert "breakdown_保洁服务" in categories
        assert "breakdown_绿化" in categories


# ── Constants ──


class TestConstants:

    def test_rate_general(self):
        assert RATE_GENERAL == Decimal("0.06")

    def test_rate_small(self):
        assert LEVY_RATE_SMALL == Decimal("0.03")

    def test_rate_small_reduced(self):
        assert LEVY_RATE_SMALL_REDUCED == Decimal("0.01")
