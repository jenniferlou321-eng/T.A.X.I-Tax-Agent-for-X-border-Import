"""UK SDLT 计算器 — 分级税率

2024/25 住宅用 SDLT 税率（rUK）：
- £0 - £250,000: 0%
- £250,001 - £925,000: 5%
- £925,001 - £1,500,000: 10%
- £1,500,001+: 12%

首次购房者减免：
- £0 - £425,000: 0%
- £425,001 - £625,000: 5%

非住宅 SDLT 税率：
- £0 - £150,000: 0%
- £150,001 - £250,000: 2%
- £250,000+: 5%

附加住宅 5%（buying additional dwellings）
"""

from decimal import Decimal, ROUND_HALF_UP
from backend.models.tax_data import TaxData
from backend.models.results import CalculationResult, BreakdownItem, DeductionItem


# Residential bands (rUK, 2024/25)
RES_BANDS = [
    (Decimal("250000"), Decimal("0.00")),
    (Decimal("925000"), Decimal("0.05")),
    (Decimal("1500000"), Decimal("0.10")),
    (None, Decimal("0.12")),  # 12% over £1.5m
]

# First-time buyer relief
FTB_BANDS = [
    (Decimal("425000"), Decimal("0.00")),
    (Decimal("625000"), Decimal("0.05")),
]

# Non-residential bands
NR_BANDS = [
    (Decimal("150000"), Decimal("0.00")),
    (Decimal("250000"), Decimal("0.02")),
    (None, Decimal("0.05")),
]

# Additional dwellings surcharge
ADDITIONAL_SURCHARGE = Decimal("0.05")


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_sdlt(data: TaxData) -> CalculationResult:
    """计算 SDLT 应纳税额"""
    line_map: dict[str, Decimal] = {li.category: li.amount for li in data.line_items}
    metadata = data.metadata

    property_value = _dec(line_map.get("property_value"))
    if property_value == 0:
        property_value = _dec(metadata.get("property_value"))

    property_type = metadata.get("property_type", "residential")
    buyer_type = metadata.get("buyer_type", "individual")
    is_additional = bool(metadata.get("is_additional_dwelling", False))

    if property_type == "residential":
        if buyer_type == "first_time_buyer":
            tax, bands_used = _tiered_calc(property_value, FTB_BANDS)
        else:
            tax, bands_used = _tiered_calc(property_value, RES_BANDS)
    else:
        tax, bands_used = _tiered_calc(property_value, NR_BANDS)

    # Additional dwellings surcharge (residential only)
    if is_additional and property_type == "residential":
        surcharge = _round_2(property_value * ADDITIONAL_SURCHARGE)
        tax += surcharge

    effective_rate = (tax / property_value).quantize(Decimal("0.0001")) if property_value > 0 else Decimal("0")

    breakdown = [
        BreakdownItem(category="property_value", amount=property_value),
        BreakdownItem(category="sdlt_payable", amount=tax),
        BreakdownItem(category="effective_rate", amount=effective_rate),
    ]

    return CalculationResult(
        total_tax_due=tax,
        breakdown=breakdown,
        deductions=[],
        warnings=[],
    )


def _tiered_calc(value: Decimal, bands: list[tuple[Decimal, Decimal]]) -> tuple[Decimal, str]:
    """分级计算税

    Args:
        value: 应税金额
        bands: [(threshold, rate), ...] threshold 之上按此 rate 计

    Returns:
        (税额, 使用的规则说明)
    """
    tax = Decimal("0")
    prev_threshold = Decimal("0")
    rule_desc = []

    for threshold, rate in bands:
        if threshold is None or value <= threshold:
            # 剩余部分按此 rate
            taxable = value - prev_threshold
            if taxable > 0:
                t = _round_2(taxable * rate)
                tax += t
                rule_desc.append(f"£{prev_threshold:,.0f}-£{value:,.0f} @ {rate*100:.0f}% = £{t:,.2f}")
            break
        else:
            # 全部此区间按此 rate
            taxable = threshold - prev_threshold
            if taxable > 0:
                t = _round_2(taxable * rate)
                tax += t
                rule_desc.append(f"£{prev_threshold:,.0f}-£{threshold:,.0f} @ {rate*100:.0f}% = £{t:,.2f}")
            prev_threshold = threshold

    return tax, "; ".join(rule_desc)
