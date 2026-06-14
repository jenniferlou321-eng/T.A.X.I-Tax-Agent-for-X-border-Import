"""中国不动产租赁增值税计算器 — 5% 简易计税 vs 9% 一般计税

政策依据:
- 财税〔2016〕47 号: 一般纳税人出租 2016-04-30 前取得的不动产,
  可选择适用简易计税方法,按 5% 征收率计算应纳税额(2024 起恢复 5%)。
- 营改增试点实施办法: 一般纳税人出租 2016-05-01 后取得的不动产,
  适用一般计税方法,税率为 9%。
- 国家税务总局公告: 小规模纳税人出租不动产,适用 5% 征收率。

决策树:
  ┌─ 小规模纳税人 ───────────→ 5% 征收率(简易)
  └─ 一般纳税人
       ├─ 取得日期 ≤ 2016-04-30 → 5% 简易(可选;按售价全额,或差额征税)
       └─ 取得日期 > 2016-04-30 → 9% 一般(销项 - 进项)

差额征税(简易计税、一般纳税人):
  应纳税额 = (含税销售额 - 购置原价或法定的其他扣除项) / (1 + 5%) × 5%
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from backend.models.tax_data import TaxData
from backend.models.results import CalculationResult, BreakdownItem, DeductionItem


# ── 税率/征收率常量 ──

RATE_GENERAL = Decimal("0.09")      # 一般计税 9%
LEVY_RATE_SIMPLIFIED = Decimal("0.05")  # 简易/征收率 5%
CUTOFF_DATE = date(2016, 4, 30)     # 营改增全面推开节点


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_cn_real_estate_rental_vat(data: TaxData) -> CalculationResult:
    """计算中国不动产租赁增值税。

    line_items 约定:
      - rental_income: 租金含税销售额
      - input_tax: 进项税额(仅一般计税下使用)
      - original_purchase_price: 不动产购置原价(差额征税时使用)

    metadata 约定:
      - taxpayer_type: "general" (一般纳税人,默认) | "small" (小规模纳税人)
      - acquisition_date: ISO 日期 (YYYY-MM-DD);一般纳税人下区分 5%/9%
      - method: "simplified" | "general" | "auto"
        "auto" = 按 acquisition_date 自动判定(默认)
      - tax_inclusive: bool (默认 True;含税/不含税)
      - use_differential: bool (默认 True;一般纳税人简易计税下是否差额征税)
    """
    line_map: dict[str, Decimal] = {li.category: li.amount for li in data.line_items}
    metadata = data.metadata

    taxpayer_type = metadata.get("taxpayer_type", "general")
    tax_inclusive = bool(metadata.get("tax_inclusive", True))
    method = metadata.get("method", "auto")

    # ── 决定计税方法 ──
    if taxpayer_type == "small":
        effective_method = "simplified"
        rate = LEVY_RATE_SIMPLIFIED
        reason = "小规模纳税人 → 5% 征收率"
    elif method == "simplified":
        effective_method = "simplified"
        rate = LEVY_RATE_SIMPLIFIED
        reason = "一般纳税人选择 5% 简易计税(取得日期 ≤ 2016-04-30)"
    elif method == "general":
        effective_method = "general"
        rate = RATE_GENERAL
        reason = "一般计税 9%(取得日期 > 2016-04-30)"
    else:  # auto
        acq_str = metadata.get("acquisition_date")
        if not acq_str:
            # 缺数据时默认走一般计税 9%(更严,鼓励补数据)
            effective_method = "general"
            rate = RATE_GENERAL
            reason = "未提供 acquisition_date,默认一般计税 9%"
        else:
            try:
                acq = date.fromisoformat(acq_str)
            except ValueError:
                effective_method = "general"
                rate = RATE_GENERAL
                reason = f"acquisition_date 解析失败({acq_str}),默认一般计税 9%"
            else:
                if acq <= CUTOFF_DATE:
                    effective_method = "simplified"
                    rate = LEVY_RATE_SIMPLIFIED
                    reason = f"取得日期 {acq.isoformat()} ≤ 2016-04-30,允许 5% 简易"
                else:
                    effective_method = "general"
                    rate = RATE_GENERAL
                    reason = f"取得日期 {acq.isoformat()} > 2016-04-30,适用一般计税 9%"

    # ── 销项 / 应税销售额 ──
    rental_income = _dec(line_map.get("rental_income"))
    input_tax = _dec(line_map.get("input_tax"))
    original_price = _dec(line_map.get("original_purchase_price"))
    use_differential = bool(metadata.get("use_differential", True))

    breakdown: list[BreakdownItem] = []
    warnings: list[str] = [reason]
    vat_payable = Decimal("0")

    if effective_method == "simplified":
        # ── 5% 简易: 销项 = 含税/(1+5%)×5%,或差额(售价-购置原价) ──
        if use_differential and original_price > 0 and taxpayer_type == "general":
            # 差额征税(仅一般纳税人简易可选)
            sales_base = max(Decimal("0"), rental_income - original_price)
            vat_payable = _round_2(sales_base / (1 + rate) * rate)
            breakdown.extend([
                BreakdownItem(category="rental_income_gross", amount=rental_income),
                BreakdownItem(category="original_purchase_price", amount=original_price),
                BreakdownItem(category="differential_sales_base", amount=sales_base),
                BreakdownItem(category="rate", amount=rate),
                BreakdownItem(category="vat_payable", amount=vat_payable),
            ])
        else:
            if tax_inclusive:
                vat_payable = _round_2(rental_income * rate / (1 + rate))
                net = rental_income - vat_payable
            else:
                vat_payable = _round_2(rental_income * rate)
                net = rental_income
            breakdown.extend([
                BreakdownItem(category="rental_income_gross", amount=rental_income),
                BreakdownItem(category="rental_income_net", amount=net),
                BreakdownItem(category="rate", amount=rate),
                BreakdownItem(category="vat_payable", amount=vat_payable),
            ])
        # 简易计税下进项不允许抵扣
        if input_tax > 0:
            warnings.append(
                f"简易计税方法下进项税额 ¥{input_tax} 不允许抵扣,已忽略"
            )
    else:
        # ── 9% 一般: 销项 - 进项 ──
        if tax_inclusive:
            output_tax = _round_2(rental_income * rate / (1 + rate))
            net_sales = rental_income - output_tax
        else:
            output_tax = _round_2(rental_income * rate)
            net_sales = rental_income
        vat_payable = max(Decimal("0"), output_tax - input_tax)
        breakdown.extend([
            BreakdownItem(category="rental_income_gross", amount=rental_income),
            BreakdownItem(category="rental_income_net", amount=net_sales),
            BreakdownItem(category="rate", amount=rate),
            BreakdownItem(category="output_tax", amount=output_tax),
            BreakdownItem(category="input_tax", amount=input_tax),
            BreakdownItem(category="vat_payable", amount=vat_payable),
        ])

    return CalculationResult(
        total_tax_due=vat_payable,
        breakdown=breakdown,
        deductions=(
            [DeductionItem(category="input_credit", amount=input_tax, rule_ref="进项抵扣(仅一般计税)")]
            if effective_method == "general" and input_tax > 0
            else []
        ),
        warnings=warnings,
    )
