"""CN 不动产租赁 VAT 计算器 — 单元测试"""

from datetime import date
from decimal import Decimal

import pytest

from backend.models.tax_data import (
    LineItem, TaxData, TaxType, FiscalPeriod, TaxpayerInfo,
)
from backend.jurisdictions.cn.real_estate_rental_vat.calculator import (
    calculate_cn_real_estate_rental_vat,
    RATE_GENERAL,
    LEVY_RATE_SIMPLIFIED,
    CUTOFF_DATE,
)


# ── Fixtures ──


def make_data(line_items=None, metadata=None, taxpayer_id="CN-test-001") -> TaxData:
    return TaxData(
        tax_type=TaxType.CN_REAL_ESTATE_RENTAL_VAT,
        period=FiscalPeriod(
            year=2024,
            period_key="2024-Q1",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),
            period_type="quarterly",
        ),
        taxpayer=TaxpayerInfo(tax_id=taxpayer_id, name="Test Landlord", tax_id_type="uscc"),
        line_items=[LineItem(category=k, amount=v) for k, v in (line_items or {}).items()],
        metadata=metadata or {},
    )


# ── 一般纳税人,自动判定: 取得日期 ≤ 2016-04-30 → 5% 简易 ──


class TestGeneralTaxpayerPreCutoff:
    """一般纳税人 + 取得日期 ≤ 2016-04-30 → 5% 简易(按全额)"""

    def test_full_amount_no_differential(self):
        """年租金 ¥120,000(含税) → 120000 / 1.05 × 5% = ¥5,714.29"""
        data = make_data(
            line_items={"rental_income": Decimal("120000")},
            metadata={
                "taxpayer_type": "general",
                "acquisition_date": "2015-06-01",
                "use_differential": False,
            },
        )
        result = calculate_cn_real_estate_rental_vat(data)
        assert result.total_tax_due == Decimal("5714.29")

    def test_full_amount_with_warning(self):
        """5% 简易下提供进项税额,应警告忽略"""
        data = make_data(
            line_items={
                "rental_income": Decimal("120000"),
                "input_tax": Decimal("5000"),
            },
            metadata={
                "taxpayer_type": "general",
                "acquisition_date": "2010-01-01",
            },
        )
        result = calculate_cn_real_estate_rental_vat(data)
        # 5% 简易,不抵扣
        assert result.total_tax_due == Decimal("5714.29")
        assert any("进项税额" in w and "不允许抵扣" in w for w in result.warnings)

    def test_exact_cutoff_date_uses_simplified(self):
        """acquisition_date = 2016-04-30 (切割点) → 5% 简易"""
        data = make_data(
            line_items={"rental_income": Decimal("100000")},
            metadata={
                "taxpayer_type": "general",
                "acquisition_date": "2016-04-30",
            },
        )
        result = calculate_cn_real_estate_rental_vat(data)
        assert result.total_tax_due == Decimal("4761.90")  # 100000 / 1.05 × 5% = 4761.90

    def test_differential_method(self):
        """差额征税:(120000 - 80000) / 1.05 × 5% = ¥1,904.76"""
        data = make_data(
            line_items={
                "rental_income": Decimal("120000"),
                "original_purchase_price": Decimal("80000"),
            },
            metadata={
                "taxpayer_type": "general",
                "acquisition_date": "2014-01-01",
                "use_differential": True,
            },
        )
        result = calculate_cn_real_estate_rental_vat(data)
        assert result.total_tax_due == Decimal("1904.76")


# ── 一般纳税人,取得日期 > 2016-04-30 → 9% 一般计税 ──


class TestGeneralTaxpayerPostCutoff:
    """一般纳税人 + 取得日期 > 2016-04-30 → 9% 一般(销项 - 进项)"""

    def test_general_calculation_with_input_credit(self):
        """¥200,000 含税 → 销项 200000/1.09 × 9% = 16,513.76;扣进项 5,000 → ¥11,513.76"""
        data = make_data(
            line_items={
                "rental_income": Decimal("200000"),
                "input_tax": Decimal("5000"),
            },
            metadata={
                "taxpayer_type": "general",
                "acquisition_date": "2017-03-15",
            },
        )
        result = calculate_cn_real_estate_rental_vat(data)
        assert result.total_tax_due == Decimal("11513.76")
        # 应有 input_credit deduction
        assert any(d.category == "input_credit" for d in result.deductions)

    def test_general_calculation_no_input_credit(self):
        """无进项:全销项"""
        data = make_data(
            line_items={"rental_income": Decimal("109000")},  # 净 100k × 9% = 9k
            metadata={
                "taxpayer_type": "general",
                "acquisition_date": "2020-01-01",
            },
        )
        result = calculate_cn_real_estate_rental_vat(data)
        assert result.total_tax_due == Decimal("9000.00")

    def test_input_credit_exceeds_output_carry_zero(self):
        """进项 > 销项 → 应纳 = 0(留抵)"""
        data = make_data(
            line_items={
                "rental_income": Decimal("109000"),
                "input_tax": Decimal("20000"),
            },
            metadata={
                "taxpayer_type": "general",
                "acquisition_date": "2022-01-01",
            },
        )
        result = calculate_cn_real_estate_rental_vat(data)
        assert result.total_tax_due == Decimal("0.00")


# ── 小规模纳税人 ──


class TestSmallScaleTaxpayer:
    """小规模纳税人 → 5% 征收率(简易)"""

    def test_small_scale_basic(self):
        """¥60,000 含税 → 60000 / 1.05 × 5% = ¥2,857.14"""
        data = make_data(
            line_items={"rental_income": Decimal("60000")},
            metadata={"taxpayer_type": "small"},
        )
        result = calculate_cn_real_estate_rental_vat(data)
        assert result.total_tax_due == Decimal("2857.14")
        # 小规模 不应用差额征税
        assert "小规模纳税人" in result.warnings[0]

    def test_small_scale_ignores_acquisition_date(self):
        """小规模无视 acquisition_date,始终 5%"""
        data = make_data(
            line_items={"rental_income": Decimal("50000")},
            metadata={
                "taxpayer_type": "small",
                "acquisition_date": "2020-06-15",  # post-cutoff but doesn't matter
            },
        )
        result = calculate_cn_real_estate_rental_vat(data)
        assert result.total_tax_due == Decimal("2380.95")  # 50000/1.05 × 5%


# ── 边界条件 ──


class TestEdgeCases:

    def test_missing_acquisition_date_defaults_to_general(self):
        """未提供 acquisition_date,默认 9% 一般(更严)"""
        data = make_data(
            line_items={"rental_income": Decimal("109000")},
            metadata={"taxpayer_type": "general"},  # no acquisition_date
        )
        result = calculate_cn_real_estate_rental_vat(data)
        # 109000 / 1.09 × 9% = 9000
        assert result.total_tax_due == Decimal("9000.00")
        assert "默认一般计税" in result.warnings[0]

    def test_invalid_date_string_defaults_to_general(self):
        data = make_data(
            line_items={"rental_income": Decimal("109000")},
            metadata={"taxpayer_type": "general", "acquisition_date": "not-a-date"},
        )
        result = calculate_cn_real_estate_rental_vat(data)
        assert result.total_tax_due == Decimal("9000.00")
        assert "解析失败" in result.warnings[0]

    def test_explicit_method_simplified(self):
        data = make_data(
            line_items={"rental_income": Decimal("105000")},
            metadata={"taxpayer_type": "general", "method": "simplified"},
        )
        result = calculate_cn_real_estate_rental_vat(data)
        # 105000/1.05 × 5% = 5000
        assert result.total_tax_due == Decimal("5000.00")

    def test_explicit_method_general(self):
        data = make_data(
            line_items={"rental_income": Decimal("109000")},
            metadata={"taxpayer_type": "general", "method": "general"},
        )
        result = calculate_cn_real_estate_rental_vat(data)
        assert result.total_tax_due == Decimal("9000.00")

    def test_exclusive_tax_inclusive_false(self):
        """不含税口径:rental_income × rate"""
        data = make_data(
            line_items={"rental_income": Decimal("100000")},
            metadata={
                "taxpayer_type": "general",
                "acquisition_date": "2015-01-01",
                "tax_inclusive": False,
            },
        )
        result = calculate_cn_real_estate_rental_vat(data)
        assert result.total_tax_due == Decimal("5000.00")  # 100000 × 5%


# ── Constants ──


class TestConstants:
    def test_rate_general(self):
        assert RATE_GENERAL == Decimal("0.09")

    def test_rate_simplified(self):
        assert LEVY_RATE_SIMPLIFIED == Decimal("0.05")

    def test_cutoff_date(self):
        assert CUTOFF_DATE == date(2016, 4, 30)
