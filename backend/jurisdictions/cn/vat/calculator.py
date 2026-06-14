"""中国增值税计算器 — 多档税率、销项/进项抵扣

税率 (2024):
- 13%: 货物销售、加工修理修配、租赁有形动产
- 9%: 交通运输、建筑、房地产租赁、基础电信
- 6%: 现代服务业、金融服务、生活服务、增值电信
- 5%: 不动产租赁 (简易计税,2016-04-30 前取得)
- 3%: 小规模纳税人/简易征收

计算逻辑:
  应纳增值税 = 销项税额 - 进项税额
  销项 = Σ(各税率销售额 × 税率)
  进项 = Σ(各税率进项 × 税率)
"""

from decimal import Decimal, ROUND_HALF_UP
from backend.models.tax_data import TaxData
from backend.models.results import CalculationResult, BreakdownItem, DeductionItem


# ── 税率常量 ──

RATE_13 = Decimal("0.13")
RATE_9 = Decimal("0.09")
RATE_6 = Decimal("0.06")
RATE_5 = Decimal("0.05")
RATE_3 = Decimal("0.03")


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_cn_vat(data: TaxData) -> CalculationResult:
    """计算中国增值税。

    line_items 中 category 约定:
      - output_13, output_9, output_6, output_5, output_3: 各税率含税或不含税销售额
      - input_13, input_9, input_6: 各税率进项税额
      - 或直接: output_tax (销项税额合计), input_tax (进项税额合计)

    metadata:
      - tax_inclusive: bool (默认 True, 销售额是否含税)
      - taxpayer_type: "general" | "small" (默认 "general")
    """
    line_map: dict[str, Decimal] = {li.category: li.amount for li in data.line_items}
    metadata = data.metadata
    tax_inclusive = bool(metadata.get("tax_inclusive", True))

    # ── 销项 ──
    output_items = {
        "output_13": (RATE_13, "销项 13%"),
        "output_9": (RATE_9, "销项 9%"),
        "output_6": (RATE_6, "销项 6%"),
        "output_5": (RATE_5, "销项 5%"),
        "output_3": (RATE_3, "销项 3%"),
    }

    total_output_tax = Decimal("0")
    total_output_amount = Decimal("0")
    breakdown = []

    for key, (rate, label) in output_items.items():
        amount = _dec(line_map.get(key))
        if amount > 0:
            if tax_inclusive:
                tax = _round_2(amount * rate / (1 + rate))
                net = amount - tax
            else:
                tax = _round_2(amount * rate)
                net = amount
            total_output_tax += tax
            total_output_amount += amount
            breakdown.append(BreakdownItem(category=f"output_tax_{key}", amount=tax))
            breakdown.append(BreakdownItem(category=f"output_net_{key}", amount=net))

    # 直接传入销项税额
    direct_output = _dec(line_map.get("output_tax"))
    if direct_output > 0 and total_output_tax == 0:
        total_output_tax = direct_output
        breakdown.append(BreakdownItem(category="output_tax_total", amount=direct_output))

    total_sales = _dec(line_map.get("total_sales"))
    if total_sales > 0:
        breakdown.append(BreakdownItem(category="total_sales", amount=total_sales))
    elif total_output_amount > 0:
        breakdown.append(BreakdownItem(category="total_sales", amount=total_output_amount))

    # ── 进项 ──
    input_items = {
        "input_13": RATE_13,
        "input_9": RATE_9,
        "input_6": RATE_6,
    }

    total_input_tax = Decimal("0")
    total_input_amount = Decimal("0")

    for key, rate in input_items.items():
        amount = _dec(line_map.get(key))
        if amount > 0:
            if tax_inclusive:
                tax = _round_2(amount * rate / (1 + rate))
                net = amount - tax
            else:
                tax = _round_2(amount * rate)
                net = amount
            total_input_tax += tax
            total_input_amount += amount

    # 直接传入进项税额
    direct_input = _dec(line_map.get("input_tax"))
    if direct_input > 0 and total_input_tax == 0:
        total_input_tax = direct_input

    total_input = _dec(line_map.get("total_input"))
    if total_input > 0:
        breakdown.append(BreakdownItem(category="total_input", amount=total_input))
    elif total_input_amount > 0:
        breakdown.append(BreakdownItem(category="total_input", amount=total_input_amount))

    # ── 应纳税额 ──
    vat_payable = max(Decimal("0"), total_output_tax - total_input_tax)

    breakdown.extend([
        BreakdownItem(category="output_tax", amount=total_output_tax),
        BreakdownItem(category="input_tax", amount=total_input_tax),
        BreakdownItem(category="vat_payable", amount=vat_payable),
    ])

    warnings = []
    if vat_payable == 0 and total_output_tax > 0:
        warnings.append("留抵: 进项 > 销项,差额可结转下期")

    return CalculationResult(
        total_tax_due=vat_payable,
        breakdown=breakdown,
        deductions=[DeductionItem(category="input_credit", amount=total_input_tax, rule_ref="进项税额抵扣")],
        warnings=warnings,
    )
