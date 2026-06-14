"""中国个人所得税代扣代缴计算器 — 工资薪金累计预扣法

税率 (月度累计, 2024):
- ≤ 36,000:     3%
- 36,001-144,000: 10%
- 144,001-300,000: 20%
- 300,001-420,000: 25%
- 420,001-660,000: 30%
- 660,001-960,000: 35%
- > 960,000:     45%

专项附加扣除: 子女教育、继续教育、大病医疗、住房贷款利息、住房租金、赡养老人
年终奖: 可选单独计税 (2027年底前)
"""

from decimal import Decimal, ROUND_HALF_UP
from backend.models.tax_data import TaxData
from backend.models.results import CalculationResult, BreakdownItem, DeductionItem


# 累计预扣税率表
BRACKETS = [
    (Decimal("36000"), Decimal("0.03"), Decimal("0")),
    (Decimal("144000"), Decimal("0.10"), Decimal("2520")),
    (Decimal("300000"), Decimal("0.20"), Decimal("16920")),
    (Decimal("420000"), Decimal("0.25"), Decimal("31920")),
    (Decimal("660000"), Decimal("0.30"), Decimal("52920")),
    (Decimal("960000"), Decimal("0.35"), Decimal("85920")),
    (None, Decimal("0.45"), Decimal("181920")),
]


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _calc_bracket(taxable: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """计算累进税额。返回 (税额, 适用税率, 速算扣除数)"""
    Decimal("0")
    for threshold, rate, deduction in BRACKETS:
        if threshold is None or taxable <= threshold:
            return (_round_2(taxable * rate - deduction), rate, deduction)
    return (Decimal("0"), Decimal("0"), Decimal("0"))


def calculate_cn_iit(data: TaxData) -> CalculationResult:
    """计算中国个人所得税（工资薪金累计预扣法）。

    line_items:
      - monthly_salary: 月工资
      - monthly_bonus: 月奖金
      - special_deduction: 专项扣除 (五险一金)
      - special_additional_deduction: 专项附加扣除
      - other_deduction: 其他扣除
      - tax_exempt: 免税收入

    metadata:
      - months_accumulated: 累计月数 (1-12)
      - tax_already_paid: 已预扣税额
    """
    line_map: dict[str, Decimal] = {li.category: li.amount for li in data.line_items}
    metadata = data.metadata

    monthly_salary = _dec(line_map.get("monthly_salary"))
    monthly_bonus = _dec(line_map.get("monthly_bonus"))
    special_deduction = _dec(line_map.get("special_deduction"))
    special_additional = _dec(line_map.get("special_additional_deduction"))
    other_deduction = _dec(line_map.get("other_deduction"))
    tax_exempt = _dec(line_map.get("tax_exempt"))

    months = int(metadata.get("months_accumulated", 1))
    tax_already_paid = _dec(metadata.get("tax_already_paid", 0))

    # ── 累计收入 ──
    cumulative_income = (monthly_salary + monthly_bonus - tax_exempt) * months

    # ── 累计扣除 ──
    basic_deduction = Decimal("5000") * months  # 基本减除 5000/月
    cumulative_deductions = basic_deduction + (special_deduction + special_additional + other_deduction) * months

    # ── 累计应纳税所得额 ──
    cumulative_taxable = max(Decimal("0"), cumulative_income - cumulative_deductions)

    # ── 累计应纳税额 ──
    cumulative_tax, rate, deduction = _calc_bracket(cumulative_taxable)

    # ── 本期应扣税额 ──
    current_tax = max(Decimal("0"), cumulative_tax - tax_already_paid)

    breakdown = [
        BreakdownItem(category="cumulative_income", amount=cumulative_income),
        BreakdownItem(category="basic_deduction", amount=basic_deduction),
        BreakdownItem(category="special_deduction", amount=special_deduction * months),
        BreakdownItem(category="special_additional_deduction", amount=special_additional * months),
        BreakdownItem(category="cumulative_taxable", amount=cumulative_taxable),
        BreakdownItem(category="applicable_rate", amount=rate),
        BreakdownItem(category="cumulative_tax", amount=cumulative_tax),
        BreakdownItem(category="tax_already_paid", amount=tax_already_paid),
        BreakdownItem(category="current_tax", amount=current_tax),
    ]

    return CalculationResult(
        total_tax_due=current_tax,
        breakdown=breakdown,
        deductions=[
            DeductionItem(category="basic_deduction", amount=basic_deduction, rule_ref="基本减除费用"),
            DeductionItem(category="special_deduction", amount=special_deduction * months, rule_ref="专项扣除(五险一金)"),
        ],
        warnings=[],
    )


def calculate_annual_bonus_separate(bonus: Decimal) -> Decimal:
    """年终奖单独计税 (2027年底前有效)。

    将年终奖除以12,按月度税率表找税率,再乘以年终奖总额。
    """
    monthly_equiv = bonus / 12
    _, rate, deduction = _calc_bracket(monthly_equiv)
    return _round_2(bonus * rate - deduction)
