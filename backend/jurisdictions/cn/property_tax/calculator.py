"""中国房产税计算器 — 从价计征 / 从租计征

税率:
- 从价计征: 房产原值 × (1 - 扣除比例) × 1.2%/年
  - 扣除比例: 10%-30% (各省自定,默认 30%)
- 从租计征: 年租金收入 × 12%

嘉汉案例: 房产原值 ¥50,000,000 × 70% × 1.2% = ¥420,000/年
"""

from decimal import Decimal, ROUND_HALF_UP
from backend.models.tax_data import TaxData
from backend.models.results import CalculationResult, BreakdownItem


RATE_FROM_VALUE = Decimal("0.012")  # 从价 1.2%
RATE_FROM_RENT = Decimal("0.12")    # 从租 12%
DEFAULT_DEDUCTION_RATIO = Decimal("0.30")  # 默认扣除比例 30%


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_cn_property_tax(data: TaxData) -> CalculationResult:
    """计算中国房产税。

    line_items:
      - property_original_value: 房产原值 (从价计征用)
      - annual_rent: 年租金收入 (从租计征用)

    metadata:
      - method: "from_value" (从价,默认) / "from_rent" (从租)
      - deduction_ratio: 扣除比例 (默认 0.30)
    """
    line_map: dict[str, Decimal] = {li.category: li.amount for li in data.line_items}
    metadata = data.metadata

    method = metadata.get("method", "from_value")
    deduction_ratio = _dec(metadata.get("deduction_ratio", DEFAULT_DEDUCTION_RATIO))

    breakdown = []

    if method == "from_rent":
        # ── 从租计征 ──
        annual_rent = _dec(line_map.get("annual_rent"))
        tax = _round_2(annual_rent * RATE_FROM_RENT)
        breakdown.extend([
            BreakdownItem(category="annual_rent", amount=annual_rent),
            BreakdownItem(category="rate", amount=RATE_FROM_RENT),
            BreakdownItem(category="property_tax", amount=tax),
        ])
    else:
        # ── 从价计征 ──
        original_value = _dec(line_map.get("property_original_value"))
        taxable_value = original_value * (1 - deduction_ratio)
        tax = _round_2(taxable_value * RATE_FROM_VALUE)
        breakdown.extend([
            BreakdownItem(category="property_original_value", amount=original_value),
            BreakdownItem(category="deduction_ratio", amount=deduction_ratio),
            BreakdownItem(category="taxable_value", amount=taxable_value),
            BreakdownItem(category="rate", amount=RATE_FROM_VALUE),
            BreakdownItem(category="property_tax_annual", amount=tax),
            BreakdownItem(category="property_tax_quarterly", amount=_round_2(tax / 4)),
        ])

    return CalculationResult(
        total_tax_due=tax,
        breakdown=breakdown,
        deductions=[],
        warnings=[],
    )
