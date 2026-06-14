"""中国企业所得税计算器 — 季度预缴 + 年度汇算清缴 + DTA/DTL + 境外抵免

税率:
- 一般企业: 25%
- 小型微利企业: 有效税率 5% (年应纳税所得额 ≤ 300万,2024-2027)
- 高新技术企业: 15%

计算逻辑:
  应纳税所得额 = 会计利润 + 纳税调增 - 纳税调减
  应纳所得税 = 应纳税所得额 × 税率
  所得税费用 = 应纳所得税 - DTA确认 + DTL确认 - 境外税收抵免
"""

from decimal import Decimal, ROUND_HALF_UP
from backend.models.tax_data import TaxData
from backend.models.results import CalculationResult, BreakdownItem, DeductionItem


# ── 税率 ──

RATE_STANDARD = Decimal("0.25")
RATE_HIGH_TECH = Decimal("0.15")
RATE_SMALL_EFF = Decimal("0.05")  # 小微实际有效税率


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_cn_cit(data: TaxData) -> CalculationResult:
    """计算中国企业所得税。

    line_items category 约定:
      - accounting_profit: 会计利润
      - tax_adjustment_up: 纳税调增
      - tax_adjustment_down: 纳税调减
      - dta_recognized: 当期确认递延所得税资产
      - dtl_recognized: 当期确认递延所得税负债
      - foreign_tax_credit: 境外税收抵免

    metadata:
      - tax_rate: "standard"(25%) / "high_tech"(15%) / "small"(5%有效)
      - quarterly_prepaid: 已预缴税额
    """
    line_map: dict[str, Decimal] = {li.category: li.amount for li in data.line_items}
    metadata = data.metadata

    # ── 应纳税所得额 ──
    accounting_profit = _dec(line_map.get("accounting_profit"))
    tax_adj_up = _dec(line_map.get("tax_adjustment_up"))
    tax_adj_down = _dec(line_map.get("tax_adjustment_down"))

    taxable_income = accounting_profit + tax_adj_up - tax_adj_down

    # ── 税率 ──
    rate_key = metadata.get("tax_rate", "standard")
    if rate_key == "high_tech":
        rate = RATE_HIGH_TECH
    elif rate_key == "small":
        rate = RATE_SMALL_EFF
    else:
        rate = RATE_STANDARD

    # ── 应纳所得税 ──
    cit_tax = _round_2(taxable_income * rate)

    # ── 境外税收抵免 ──
    ftc = _dec(line_map.get("foreign_tax_credit"))
    # 抵免限额 = 境外所得 × 中国税率
    overseas_income = _dec(line_map.get("overseas_income"))
    ftc_limit = _round_2(overseas_income * rate) if overseas_income > 0 else Decimal("0")
    actual_ftc = min(ftc, ftc_limit)  # 不能超过限额

    # ── DTA/DTL ──
    dta = _dec(line_map.get("dta_recognized"))
    dtl = _dec(line_map.get("dtl_recognized"))

    # ── 已预缴 ──
    quarterly_prepaid = _dec(metadata.get("quarterly_prepaid", 0))

    # ── 所得税费用 ──
    # 会计口径: tax expense = current tax + DTL - DTA
    income_tax_expense = cit_tax - actual_ftc + dtl - dta

    # ── 应补/应退 ──
    tax_payable = max(Decimal("0"), cit_tax - actual_ftc - quarterly_prepaid)

    breakdown = [
        BreakdownItem(category="accounting_profit", amount=accounting_profit),
        BreakdownItem(category="tax_adjustment_up", amount=tax_adj_up),
        BreakdownItem(category="tax_adjustment_down", amount=tax_adj_down),
        BreakdownItem(category="taxable_income", amount=taxable_income),
        BreakdownItem(category="cit_rate", amount=rate),
        BreakdownItem(category="cit_tax", amount=cit_tax),
        BreakdownItem(category="foreign_tax_credit", amount=actual_ftc),
        BreakdownItem(category="ftc_limit", amount=ftc_limit),
        BreakdownItem(category="dta_recognized", amount=dta),
        BreakdownItem(category="dtl_recognized", amount=dtl),
        BreakdownItem(category="income_tax_expense", amount=income_tax_expense),
        BreakdownItem(category="quarterly_prepaid", amount=quarterly_prepaid),
        BreakdownItem(category="tax_payable", amount=tax_payable),
    ]

    warnings = []
    if ftc > ftc_limit and ftc_limit > 0:
        warnings.append(f"境外税收抵免超限额: 已缴 ¥{ftc} > 限额 ¥{ftc_limit},超出的 ¥{ftc - ftc_limit} 不可抵免")

    return CalculationResult(
        total_tax_due=tax_payable,
        breakdown=breakdown,
        deductions=[
            DeductionItem(category="foreign_tax_credit", amount=actual_ftc, rule_ref="境外税收抵免"),
            DeductionItem(category="quarterly_prepaid", amount=quarterly_prepaid, rule_ref="季度已预缴"),
        ],
        warnings=warnings,
    )
