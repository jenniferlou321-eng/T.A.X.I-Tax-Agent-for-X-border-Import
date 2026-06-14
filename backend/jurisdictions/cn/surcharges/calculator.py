"""中国城建税/教育费附加计算器 — 基于 VAT 实缴

税率:
- 城市维护建设税: 7% (市区) / 5% (县城/镇) / 1% (其他)
- 教育费附加: 3%
- 地方教育附加: 2%
- 合计: 12% (市区标准)

计税依据: 实际缴纳的增值税 + 消费税

嘉汉案例: VAT ¥2,461,500 × 12% = ¥295,380
"""

from decimal import Decimal, ROUND_HALF_UP
from backend.models.tax_data import TaxData
from backend.models.results import CalculationResult, BreakdownItem


RATE_URBAN_MAINTENANCE = Decimal("0.07")
RATE_COUNTY_MAINTENANCE = Decimal("0.05")
RATE_RURAL_MAINTENANCE = Decimal("0.01")
RATE_EDUCATION = Decimal("0.03")
RATE_LOCAL_EDUCATION = Decimal("0.02")


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_cn_surcharges(data: TaxData) -> CalculationResult:
    """计算城建税/教育费附加/地方教育附加。

    line_items:
      - vat_paid: 实际缴纳增值税
      - consumption_tax_paid: 实际缴纳消费税 (可选)

    metadata:
      - location: "urban" (7%) / "county" (5%) / "rural" (1%)
    """
    line_map: dict[str, Decimal] = {li.category: li.amount for li in data.line_items}
    metadata = data.metadata

    vat_paid = _dec(line_map.get("vat_paid"))
    consumption_tax = _dec(line_map.get("consumption_tax_paid"))

    base = vat_paid + consumption_tax  # 计税依据

    location = metadata.get("location", "urban")
    if location == "county":
        maintenance_rate = RATE_COUNTY_MAINTENANCE
    elif location == "rural":
        maintenance_rate = RATE_RURAL_MAINTENANCE
    else:
        maintenance_rate = RATE_URBAN_MAINTENANCE

    urban_maintenance = _round_2(base * maintenance_rate)
    education = _round_2(base * RATE_EDUCATION)
    local_education = _round_2(base * RATE_LOCAL_EDUCATION)

    total = urban_maintenance + education + local_education

    total_rate = maintenance_rate + RATE_EDUCATION + RATE_LOCAL_EDUCATION

    breakdown = [
        BreakdownItem(category="vat_paid", amount=vat_paid),
        BreakdownItem(category="consumption_tax_paid", amount=consumption_tax),
        BreakdownItem(category="tax_base", amount=base),
        BreakdownItem(category="urban_maintenance_tax", amount=urban_maintenance),
        BreakdownItem(category="education_surcharge", amount=education),
        BreakdownItem(category="local_education_surcharge", amount=local_education),
        BreakdownItem(category="total_rate", amount=total_rate),
        BreakdownItem(category="total_surcharges", amount=total),
    ]

    return CalculationResult(
        total_tax_due=total,
        breakdown=breakdown,
        deductions=[],
        warnings=[],
    )
