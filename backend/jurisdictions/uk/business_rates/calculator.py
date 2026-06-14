"""UK Business Rates Calculator — Rateable Value × UBR multiplier

计算:
  Business Rates = Rateable Value × UBR multiplier × (1 - reliefs)

UBR multipliers (2024/25):
- 标准: 54.6p (0.546)
- 小企业: 49.9p (0.499) — RV < £15,000

常见减免:
- Small Business Rate Relief: RV < £12,000 → 100% 免除; £12,000-£15,000 递减
- Retail Discount: 50% (部分零售/餐饮)
- Empty Property Relief: 空置 3-6 月免

嘉汉案例: 年额 £102,400, 季度 £25,600
"""

from decimal import Decimal, ROUND_HALF_UP
from backend.models.tax_data import TaxData
from backend.models.results import CalculationResult, BreakdownItem, DeductionItem


UBR_STANDARD = Decimal("0.546")  # 54.6p
UBR_SMALL = Decimal("0.499")     # 49.9p

SMALL_BUSINESS_FULL_EXEMPTION = Decimal("12000")    # £12,000 RV → 100% 免除
SMALL_BUSINESS_TAPER_START = Decimal("12000")
SMALL_BUSINESS_TAPER_END = Decimal("15000")


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_business_rates(data: TaxData) -> CalculationResult:
    """计算 UK Business Rates。

    line_items:
      - rateable_value: 评估价值 (RV)

    metadata:
      - small_business: bool (是否适用小企业税率)
      - retail_discount_pct: 零售减免百分比 (如 50)
      - empty_property_months: 空置月数 (3个月免)
    """
    line_map: dict[str, Decimal] = {li.category: li.amount for li in data.line_items}
    metadata = data.metadata

    rv = _dec(line_map.get("rateable_value"))

    # ── UBR multiplier ──
    small_business = bool(metadata.get("small_business", False))
    if small_business and rv < SMALL_BUSINESS_TAPER_END:
        ubr = UBR_SMALL
    else:
        ubr = UBR_STANDARD

    # ── 基本税额 ──
    gross_rates = _round_2(rv * ubr)

    # ── Small Business Rate Relief ──
    sbr_relief = Decimal("0")
    if rv <= SMALL_BUSINESS_FULL_EXEMPTION:
        sbr_relief = gross_rates  # 100% 免除
    elif rv < SMALL_BUSINESS_TAPER_END:
        # 递减: 从 £12,000 到 £15,000,减免从 100% 递减到 0%
        taper_pct = (SMALL_BUSINESS_TAPER_END - rv) / (SMALL_BUSINESS_TAPER_END - SMALL_BUSINESS_TAPER_START)
        sbr_relief = _round_2(gross_rates * taper_pct)

    # ── Retail Discount ──
    retail_discount_pct = _dec(metadata.get("retail_discount_pct", 0)) / 100
    retail_discount = _round_2(gross_rates * retail_discount_pct)

    # ── Empty Property Relief ──
    empty_months = int(metadata.get("empty_property_months", 0))
    empty_relief = Decimal("0")
    if empty_months > 0 and empty_months <= 3:
        empty_relief = gross_rates  # 前 3 月全免
    elif empty_months > 3:
        empty_relief = _round_2(gross_rates * 3 / 12)  # 只免前 3 月

    # ── 净税额 ──
    total_relief = min(gross_rates, sbr_relief + retail_discount + empty_relief)
    net_rates = gross_rates - total_relief
    quarterly = _round_2(net_rates / 4)

    breakdown = [
        BreakdownItem(category="rateable_value", amount=rv),
        BreakdownItem(category="ubr_multiplier", amount=ubr),
        BreakdownItem(category="gross_rates", amount=gross_rates),
        BreakdownItem(category="sbr_relief", amount=sbr_relief),
        BreakdownItem(category="retail_discount", amount=retail_discount),
        BreakdownItem(category="empty_property_relief", amount=empty_relief),
        BreakdownItem(category="total_relief", amount=total_relief),
        BreakdownItem(category="net_rates_annual", amount=net_rates),
        BreakdownItem(category="net_rates_quarterly", amount=quarterly),
    ]

    return CalculationResult(
        total_tax_due=net_rates,
        breakdown=breakdown,
        deductions=[
            DeductionItem(category="sbr_relief", amount=sbr_relief, rule_ref="Small Business Rate Relief"),
            DeductionItem(category="retail_discount", amount=retail_discount, rule_ref="Retail Discount"),
        ],
        warnings=[],
    )
