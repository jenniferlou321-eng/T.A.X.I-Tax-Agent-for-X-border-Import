"""UK Self Assessment (ITSA) 计算器

参考 2024/25 税率：
- Personal Allowance: £12,570 (收入 > £100,000 时每 £2 减少 £1)
- Basic Rate: 20% (£0 - £37,700)
- Higher Rate: 40% (£37,700 - £125,140)
- Additional Rate: 45% (> £125,140)
- Scotland 税率不同（本计算器使用 rUK 税率）

资本利得税率（2024/25）：
- 免税额: £3,000
- Basic rate taxpayers: 18%
- Higher/Additional rate taxpayers: 24%
"""

from decimal import Decimal, ROUND_HALF_UP

from backend.models.tax_data import TaxData
from backend.models.results import CalculationResult, BreakdownItem, DeductionItem


# ── 2024/25 税率参数 ──

PERSONAL_ALLOWANCE = Decimal("12570")
PA_TAPER_THRESHOLD = Decimal("100000")  # > 此值每 £2 减 £1 personal allowance
BASIC_RATE_BAND = Decimal("37700")
BASIC_RATE = Decimal("0.20")
HIGHER_RATE_BAND_END = Decimal("125140")
HIGHER_RATE = Decimal("0.40")
ADDITIONAL_RATE = Decimal("0.45")

CGT_ANNUAL_EXEMPT = Decimal("3000")
CGT_BASIC_RATE = Decimal("0.18")
CGT_HIGHER_RATE = Decimal("0.24")


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_self_assessment(data: TaxData) -> CalculationResult:
    """计算 Self Assessment 应纳税额

    Args:
        data: TaxData with line_items containing all income/deduction fields
            Each LineItem.category must match a field in SA template
            E.g., 'employment_income', 'self_employment_net_profit', 'pension_contributions'

    Returns:
        CalculationResult with breakdown of tax components
    """
    line_map: dict[str, Decimal] = {li.category: li.amount for li in data.line_items}

    # ── 1. 收集收入 ──
    employment_income = _dec(line_map.get("employment_income"))
    self_employment_profit = _dec(line_map.get("self_employment_net_profit"))
    property_income = _dec(line_map.get("property_net_income"))
    foreign_income = _dec(line_map.get("foreign_income"))
    savings_income = _dec(line_map.get("savings_income"))
    dividend_income = _dec(line_map.get("dividend_income"))
    other_income = _dec(line_map.get("other_income"))

    # 资本利得
    total_gains = _dec(line_map.get("total_gains"))
    total_losses = _dec(line_map.get("total_losses"))
    net_cg = total_gains - total_losses

    # ── 2. 总收入 ──
    total_income = (
        employment_income
        + self_employment_profit
        + property_income
        + foreign_income
        + savings_income
        + dividend_income
        + other_income
    )

    # ── 3. 个人免税额（收入 > £100k 时递减） ──
    personal_allowance = _dec(line_map.get("personal_allowance"))
    if personal_allowance == 0:
        personal_allowance = PERSONAL_ALLOWANCE

    if total_income > PA_TAPER_THRESHOLD:
        excess = total_income - PA_TAPER_THRESHOLD
        reduction = (excess / Decimal("2")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        personal_allowance = max(Decimal("0"), personal_allowance - reduction)

    # ── 4. 资本利得免税额 ──
    cgt_exempt = min(CGT_ANNUAL_EXEMPT, net_cg) if net_cg > 0 else Decimal("0")
    chargeable_gain = max(Decimal("0"), net_cg - cgt_exempt)

    # ── 5. 应税收入 ──
    taxable_income = max(Decimal("0"), total_income - personal_allowance)
    # 注意：资本利得单独计税，不从 taxable_income 中扣除

    # ── 6. 扣除项 ──
    pension = _dec(line_map.get("pension_contributions"))
    gift_aid = _dec(line_map.get("gift_aid"))
    _dec(line_map.get("other_reliefs"))

    taxable_income_after_reliefs = max(
        Decimal("0"),
        taxable_income - pension - (gift_aid * Decimal("0.20") if gift_aid > 0 else Decimal("0"))
    )

    # ── 7. 累进所得税计算 ──
    income_tax = _calculate_progressive_tax(taxable_income_after_reliefs)

    # ── 8. 资本利得税 ──
    # CGT 税率取决于总收入（是否高于 basic rate 阈值）
    if (total_income - personal_allowance) > BASIC_RATE_BAND:
        cgt_rate = CGT_HIGHER_RATE
    else:
        cgt_rate = CGT_BASIC_RATE
    cgt = _round_2(chargeable_gain * cgt_rate) if chargeable_gain > 0 else Decimal("0")

    # ── 9. 汇总 ──
    total_tax = income_tax + cgt

    # ── 10. 已缴税款 ──
    tax_withheld = _dec(line_map.get("tax_withheld"))
    foreign_tax = _dec(line_map.get("foreign_tax_paid"))
    payments_on_account = _dec(line_map.get("payments_on_account"))
    total_paid = tax_withheld + foreign_tax + payments_on_account

    balancing = total_tax - total_paid  # 正=应补缴，负=应退税

    # ── 11. 输出 BreakdownItem ──
    breakdown = [
        BreakdownItem(category="employment_income", amount=employment_income),
        BreakdownItem(category="self_employment_income", amount=self_employment_profit),
        BreakdownItem(category="property_income", amount=property_income),
        BreakdownItem(category="foreign_income", amount=foreign_income),
        BreakdownItem(category="total_income", amount=total_income),
        BreakdownItem(category="personal_allowance", amount=personal_allowance),
        BreakdownItem(category="taxable_income", amount=taxable_income_after_reliefs),
        BreakdownItem(category="income_tax_due", amount=income_tax),
        BreakdownItem(category="capital_gains_tax_due", amount=cgt),
        BreakdownItem(category="total_tax_due", amount=total_tax),
        BreakdownItem(category="tax_already_paid", amount=total_paid),
        BreakdownItem(category="balancing_payment", amount=balancing),
    ]

    deductions = [
        DeductionItem(category="pension_contributions", amount=pension, rule_ref="ITEPA 2003 s.188"),
        DeductionItem(category="gift_aid", amount=gift_aid, rule_ref="ITTOIA 2005 s.108"),
    ]

    return CalculationResult(
        total_tax_due=total_tax,
        breakdown=breakdown,
        deductions=deductions,
        warnings=[],
    )


def _calculate_progressive_tax(taxable_income: Decimal) -> Decimal:
    """累进税率计算（rUK 2024/25）

    | 区间              | 税率   |
    |-------------------|--------|
    | £0 - £37,700      | 20%    |
    | £37,700 - £125,140| 40%    |
    | > £125,140        | 45%    |
    """
    if taxable_income <= 0:
        return Decimal("0")

    # Basic rate
    basic_band = min(taxable_income, BASIC_RATE_BAND)
    basic_tax = basic_band * BASIC_RATE

    # Higher rate
    if taxable_income > BASIC_RATE_BAND:
        higher_band = min(taxable_income, HIGHER_RATE_BAND_END) - BASIC_RATE_BAND
        higher_tax = higher_band * HIGHER_RATE
    else:
        higher_tax = Decimal("0")

    # Additional rate
    if taxable_income > HIGHER_RATE_BAND_END:
        additional_band = taxable_income - HIGHER_RATE_BAND_END
        additional_tax = additional_band * ADDITIONAL_RATE
    else:
        additional_tax = Decimal("0")

    return _round_2(basic_tax + higher_tax + additional_tax)
