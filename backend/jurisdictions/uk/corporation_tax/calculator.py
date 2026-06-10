"""UK Corporation Tax 计算器

参考 2024/25 税率：
- 利润 ≤ £50,000: 19%
- 利润 ≥ £250,000: 25%
- 边际: £50,000 - £250,000 之间，使用边际税率（避免跳跃）
"""

from decimal import Decimal, ROUND_HALF_UP
from backend.models.tax_data import TaxData
from backend.models.results import CalculationResult, BreakdownItem, DeductionItem


# ── 2024/25 CT 税率参数 ──

LOWER_LIMIT = Decimal("50000")
UPPER_LIMIT = Decimal("250000")
LOWER_RATE = Decimal("0.19")
UPPER_RATE = Decimal("0.25")
MAIN_RATE = Decimal("0.25")  # 2024/25 main rate (for >= £250k)

# 边际税率计算常数
# 公式: standard fraction = (UPPER_LIMIT × MAIN_RATE - LOWER_LIMIT × LOWER_RATE) / (UPPER_LIMIT - LOWER_LIMIT)
STANDARD_FRACTION = (
    (UPPER_LIMIT * MAIN_RATE - LOWER_LIMIT * LOWER_RATE)
    / (UPPER_LIMIT - LOWER_LIMIT)
).quantize(Decimal("0.000001"))


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_corporation_tax(data: TaxData) -> CalculationResult:
    """计算 CT 应纳税额

    Args:
        data: TaxData with line_items containing:
            - trading_income, trading_expenses
            - investment_income, property_income, chargeable_gains
            - capital_allowances_claimed, balancing_charges
            - trading_losses_brought_forward, group_relief_claimed
            - tax_already_paid

    Returns:
        CalculationResult with breakdown
    """
    line_map: dict[str, Decimal] = {li.category: li.amount for li in data.line_items}

    # ── 1. 交易利润 ──
    trading_income = _dec(line_map.get("trading_income"))
    trading_expenses = _dec(line_map.get("trading_expenses"))
    trading_profit = trading_income - trading_expenses

    # ── 2. 其他收入 ──
    investment_income = _dec(line_map.get("investment_income"))
    property_income = _dec(line_map.get("property_income"))
    chargeable_gains = _dec(line_map.get("chargeable_gains"))
    balancing_charges = _dec(line_map.get("balancing_charges"))

    # ── 3. 总利润 ──
    total_profits_before_allowances = (
        trading_profit + investment_income + property_income
        + chargeable_gains + balancing_charges
    )

    # ── 4. 资本减免 ──
    capital_allowances = _dec(line_map.get("capital_allowances_claimed"))
    total_profits_after_allowances = total_profits_before_allowances - capital_allowances

    # ── 5. 损失与减免 ──
    losses_bf = _dec(line_map.get("trading_losses_brought_forward"))
    group_relief = _dec(line_map.get("group_relief_claimed"))
    profits_chargeable = max(
        Decimal("0"),
        total_profits_after_allowances - losses_bf - group_relief,
    )

    # ── 6. 计算税额（应用边际税率） ──
    ct_chargeable, effective_rate = _compute_ct(profits_chargeable)

    # ── 7. 已缴税款 ──
    tax_paid = _dec(line_map.get("tax_already_paid"))
    amount_payable = ct_chargeable - tax_paid

    breakdown = [
        BreakdownItem(category="trading_profit", amount=trading_profit),
        BreakdownItem(category="investment_income", amount=investment_income),
        BreakdownItem(category="property_income", amount=property_income),
        BreakdownItem(category="chargeable_gains", amount=chargeable_gains),
        BreakdownItem(category="capital_allowances_claimed", amount=capital_allowances),
        BreakdownItem(category="losses_brought_forward", amount=losses_bf),
        BreakdownItem(category="group_relief", amount=group_relief),
        BreakdownItem(category="taxable_total_profits", amount=profits_chargeable),
        BreakdownItem(category="ct_rate_applied", amount=effective_rate),
        BreakdownItem(category="corporation_tax_chargeable", amount=ct_chargeable),
        BreakdownItem(category="tax_already_paid", amount=tax_paid),
        BreakdownItem(category="amount_payable", amount=amount_payable),
    ]

    deductions = [
        DeductionItem(category="trading_expenses", amount=trading_expenses, rule_ref="CTA 2009"),
        DeductionItem(category="capital_allowances", amount=capital_allowances, rule_ref="CAA 2001"),
        DeductionItem(category="loss_relief", amount=losses_bf, rule_ref="CTA 2010 s.45"),
        DeductionItem(category="group_relief", amount=group_relief, rule_ref="CTA 2010 Pt 5"),
    ]

    warnings = []
    if profits_chargeable > Decimal("0") and tax_paid == 0:
        warnings.append("CT liability calculated but no tax already paid - check payments on account")

    return CalculationResult(
        total_tax_due=ct_chargeable,
        breakdown=breakdown,
        deductions=deductions,
        warnings=warnings,
    )


def _compute_ct(profits: Decimal) -> tuple[Decimal, Decimal]:
    """计算 CT，考虑边际税率

    HM Treasury 边际税率公式 (FY2024):
    整个边际区间内的利润按"分层"计算:
    - £0 - £50,000 部分按 19% (lower rate)
    - £50,000 - Profits 部分按 25% (main rate)

    Returns:
        (tax_amount, effective_rate)
    """
    if profits <= 0:
        return Decimal("0"), Decimal("0")

    if profits <= LOWER_LIMIT:
        # 全部按 19% 计税
        tax = _round_2(profits * LOWER_RATE)
        return tax, LOWER_RATE

    if profits >= UPPER_LIMIT:
        # 全部按 25% 计税
        tax = _round_2(profits * MAIN_RATE)
        return tax, MAIN_RATE

    # 边际区间：£50k - £250k
    # 分层计算：前 £50k @ 19% + 超过 £50k 部分 @ 25%
    lower_band_tax = LOWER_LIMIT * LOWER_RATE
    main_band_tax = (profits - LOWER_LIMIT) * MAIN_RATE
    tax = _round_2(lower_band_tax + main_band_tax)
    effective_rate = (tax / profits).quantize(Decimal("0.0001"))
    return tax, effective_rate
