"""UK Withholding Tax Calculator — 利息 / 特许权使用费

UK 不征股息预提税 (Dividend WHT = 0%)。
利息和特许权使用费的 WHT 通过 DTA 确定税率,并在 CT600 supplementary 页申报。

常见 UK→CN DTA 税率:
- 利息: Art.11 → 10%
- 特许权使用费: Art.12 → 10%
- 股息: Art.10 → 0% (≥25%控股)

WHT 由付款方代扣,不单独提交,而是:
1. 在 CT600 中申报已扣 WHT 作为费用
2. 收款方在居住国申请 FTC
"""

from decimal import Decimal, ROUND_HALF_UP
from backend.models.tax_data import TaxData
from backend.models.results import CalculationResult, BreakdownItem


# DTA 税率数据库 (UK 作为付款方)
# 格式: {country_code: {income_type: rate}}
TREATY_RATES = {
    "CN": {
        "interest": Decimal("0.10"),       # Art.11
        "royalty": Decimal("0.10"),        # Art.12
        "dividend_25pct": Decimal("0.00"), # Art.10(a) ≥25%
        "dividend_10pct": Decimal("0.05"), # Art.10(b) ≥10%
        "dividend_other": Decimal("0.10"), # Art.10(c)
    },
    "HK": {
        "interest": Decimal("0.00"),
        "royalty": Decimal("0.03"),
        "dividend_25pct": Decimal("0.00"),
        "dividend_10pct": Decimal("0.00"),
        "dividend_other": Decimal("0.00"),
    },
    "US": {
        "interest": Decimal("0.00"),
        "royalty": Decimal("0.00"),
        "dividend_25pct": Decimal("0.00"),
        "dividend_10pct": Decimal("0.05"),
        "dividend_other": Decimal("0.15"),
    },
    "DE": {
        "interest": Decimal("0.00"),
        "royalty": Decimal("0.00"),
        "dividend_25pct": Decimal("0.05"),
        "dividend_10pct": Decimal("0.10"),
        "dividend_other": Decimal("0.15"),
    },
    "FR": {
        "interest": Decimal("0.00"),
        "royalty": Decimal("0.00"),
        "dividend_25pct": Decimal("0.00"),
        "dividend_10pct": Decimal("0.10"),
        "dividend_other": Decimal("0.15"),
    },
}


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_treaty_rate(country_code: str, income_type: str, ownership_pct: Decimal = Decimal("100")) -> Decimal:
    """获取 DTA 税率。

    Args:
        country_code: 收款方居住国 (如 "CN")
        income_type: "interest" / "royalty" / "dividend"
        ownership_pct: 持股比例 (仅股息需要)

    Returns:
        协定税率 (如 0.10 = 10%)
    """
    country_rates = TREATY_RATES.get(country_code.upper(), {})

    if income_type in ("interest", "royalty"):
        return country_rates.get(income_type, Decimal("0.20"))  # 默认 20% UK 标准率

    if income_type == "dividend":
        if ownership_pct >= 25:
            return country_rates.get("dividend_25pct", Decimal("0.00"))
        elif ownership_pct >= 10:
            return country_rates.get("dividend_10pct", Decimal("0.05"))
        else:
            return country_rates.get("dividend_other", Decimal("0.15"))

    return Decimal("0.20")


def calculate_wht(data: TaxData) -> CalculationResult:
    """计算 UK WHT。

    line_items:
      - interest_amount: 利息支付总额
      - royalty_amount: 特许权使用费支付总额
      - dividend_amount: 股息支付总额

    metadata:
      - recipient_country: 收款方国家代码 (如 "CN")
      - ownership_pct: 持股比例 (股息用,默认 100)
    """
    line_map: dict[str, Decimal] = {li.category: li.amount for li in data.line_items}
    metadata = data.metadata

    country = metadata.get("recipient_country", "CN")
    ownership = _dec(metadata.get("ownership_pct", 100))

    total_wht = Decimal("0")
    breakdown = []

    # 利息
    interest = _dec(line_map.get("interest_amount"))
    if interest > 0:
        rate = get_treaty_rate(country, "interest")
        tax = _round_2(interest * rate)
        total_wht += tax
        breakdown.extend([
            BreakdownItem(category="interest_amount", amount=interest),
            BreakdownItem(category="interest_wht_rate", amount=rate),
            BreakdownItem(category="interest_wht", amount=tax),
        ])

    # 特许权使用费
    royalty = _dec(line_map.get("royalty_amount"))
    if royalty > 0:
        rate = get_treaty_rate(country, "royalty")
        tax = _round_2(royalty * rate)
        total_wht += tax
        breakdown.extend([
            BreakdownItem(category="royalty_amount", amount=royalty),
            BreakdownItem(category="royalty_wht_rate", amount=rate),
            BreakdownItem(category="royalty_wht", amount=tax),
        ])

    # 股息
    dividend = _dec(line_map.get("dividend_amount"))
    if dividend > 0:
        rate = get_treaty_rate(country, "dividend", ownership)
        tax = _round_2(dividend * rate)
        total_wht += tax
        breakdown.extend([
            BreakdownItem(category="dividend_amount", amount=dividend),
            BreakdownItem(category="dividend_wht_rate", amount=rate),
            BreakdownItem(category="dividend_wht", amount=tax),
        ])

    breakdown.append(BreakdownItem(category="total_wht", amount=total_wht))

    return CalculationResult(
        total_tax_due=total_wht,
        breakdown=breakdown,
        deductions=[],
        warnings=[],
    )
