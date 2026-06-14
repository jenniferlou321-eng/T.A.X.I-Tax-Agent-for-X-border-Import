"""中国境外税收抵免计算器 — 分国不分项限额法

计算逻辑:
1. 境外所得 × 中国税率 = 抵免限额
2. 境外已缴税款 ≤ 抵免限额 → 全额抵免
3. 境外已缴税款 > 抵免限额 → 只能抵免限额,超出部分可结转 5 年

嘉汉案例:
- 境外所得 ¥1,561,373
- 境外已缴 ¥43,679
- 抵免限额 = ¥1,561,373 × 25% = ¥390,343
- 实际抵免 = ¥43,679 (已缴 < 限额,全额抵免)
"""

from decimal import Decimal, ROUND_HALF_UP
from backend.models.tax_data import TaxData
from backend.models.results import CalculationResult, BreakdownItem, DeductionItem


CN_CIT_RATE = Decimal("0.25")


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_cn_ftc(data: TaxData) -> CalculationResult:
    """计算中国境外税收抵免 (分国不分项)。

    line_items:
      - overseas_income_{country}: 各国境外所得 (如 overseas_income_UK)
      - overseas_tax_paid_{country}: 各国已缴税款 (如 overseas_tax_paid_UK)
      - 或: overseas_income (总额), overseas_tax_paid (总额)

    metadata:
      - cn_tax_rate: 中国税率 (默认 25%)
      - carry_forward_years: 超出限额可结转年数 (默认 5)
    """
    line_map: dict[str, Decimal] = {li.category: li.amount for li in data.line_items}
    metadata = data.metadata

    cn_rate = _dec(metadata.get("cn_tax_rate", CN_CIT_RATE))

    # ── 逐国计算 ──
    countries = set()
    for key in line_map:
        if key.startswith("overseas_income_"):
            countries.add(key.replace("overseas_income_", ""))

    total_overseas_income = Decimal("0")
    total_overseas_tax = Decimal("0")
    total_ftc = Decimal("0")
    total_excess = Decimal("0")
    breakdown = []
    country_details = []

    if countries:
        for country in sorted(countries):
            income = _dec(line_map.get(f"overseas_income_{country}"))
            tax_paid = _dec(line_map.get(f"overseas_tax_paid_{country}"))
            limit = _round_2(income * cn_rate)
            actual_ftc = min(tax_paid, limit)
            excess = max(Decimal("0"), tax_paid - limit)

            total_overseas_income += income
            total_overseas_tax += tax_paid
            total_ftc += actual_ftc
            total_excess += excess

            country_details.append({
                "country": country,
                "income": float(income),
                "tax_paid": float(tax_paid),
                "limit": float(limit),
                "ftc": float(actual_ftc),
                "excess": float(excess),
            })
            breakdown.append(BreakdownItem(
                category=f"ftc_{country}",
                amount=actual_ftc,
            ))
    else:
        # 单一总额模式
        income = _dec(line_map.get("overseas_income"))
        tax_paid = _dec(line_map.get("overseas_tax_paid"))
        limit = _round_2(income * cn_rate)
        actual_ftc = min(tax_paid, limit)
        excess = max(Decimal("0"), tax_paid - limit)

        total_overseas_income = income
        total_overseas_tax = tax_paid
        total_ftc = actual_ftc
        total_excess = excess

    breakdown.extend([
        BreakdownItem(category="total_overseas_income", amount=total_overseas_income),
        BreakdownItem(category="total_overseas_tax_paid", amount=total_overseas_tax),
        BreakdownItem(category="total_ftc_limit", amount=_round_2(total_overseas_income * cn_rate)),
        BreakdownItem(category="total_ftc", amount=total_ftc),
        BreakdownItem(category="total_excess", amount=total_excess),
    ])

    warnings = []
    if total_excess > 0:
        warnings.append(f"抵免超限额 ¥{total_excess},可结转未来 5 年抵免")

    return CalculationResult(
        total_tax_due=total_ftc,
        breakdown=breakdown,
        deductions=[
            DeductionItem(category="foreign_tax_credit", amount=total_ftc, rule_ref="境外税收抵免"),
        ],
        warnings=warnings,
    )
