"""中国物业管理服务增值税计算器 — 6% 现代服务业 vs 3% 征收率

政策依据:
- 财税〔2016〕36 号 附件 1: 物业管理服务属于"现代服务业 — 商务辅助服务 —
  物业管理服务",一般纳税人适用 6% 税率。
- 国家税务总局公告: 房地产开发企业的一般纳税人出租其 2016-04-30
  前自行开发的房地产项目,可以选择 5% 简易计税(已在不动产租赁 VAT
  calculator 中处理);本计算器只覆盖"物业管理服务"(非租赁)收入。
- 小规模纳税人提供物业管理服务,适用 3% 征收率;2023-2027 阶段性减按 1%
  政策可叠加使用(本计算器默认 3%,如需 1% 可在 metadata 指定)。

决策树:
  ┌─ 小规模纳税人 ────────→ 3% 征收率(简易)
  └─ 一般纳税人 ───────────→ 6% 现代服务业(销项 - 进项)

区分要点(与不动产租赁 VAT 的边界):
- 物业管理服务 = 受托管理房屋、设备、场地、安保、保洁等,
  收入性质是"服务费",不是"租金"。
- 不动产租赁 = 让渡不动产使用权,按"租金"申报(见 real_estate_rental_vat)。
- 实务中物业 + 租赁可同时存在(如物业公司既收物业费也代收房租),应分别入账。
"""

from decimal import Decimal, ROUND_HALF_UP
from backend.models.tax_data import TaxData
from backend.models.results import CalculationResult, BreakdownItem, DeductionItem


# ── 税率/征收率常量 ──

RATE_GENERAL = Decimal("0.06")        # 现代服务业 6%
LEVY_RATE_SMALL = Decimal("0.03")     # 小规模 3%
LEVY_RATE_SMALL_REDUCED = Decimal("0.01")  # 阶段性减按 1%(2023-2027)


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_cn_property_management_vat(data: TaxData) -> CalculationResult:
    """计算中国物业管理服务增值税。

    line_items 约定:
      - service_income: 物业服务费含税收入
      - input_tax: 进项税额(仅一般计税下使用)
      - ancillary_income: 增值辅助收入(如广告费、停车费,默认并入 service_income)

    metadata 约定:
      - taxpayer_type: "general" (一般纳税人,默认) | "small" (小规模纳税人)
      - tax_inclusive: bool (默认 True;含税/不含税)
      - reduced_rate: bool (默认 False;小规模阶段性减按 1%,仅 2023-2027 有效)
      - service_breakdown: dict (可选,用于展示各类服务分项,如
        {"保安服务": 60000, "保洁服务": 40000, "绿化": 20000})
    """
    line_map: dict[str, Decimal] = {li.category: li.amount for li in data.line_items}
    metadata = data.metadata

    taxpayer_type = metadata.get("taxpayer_type", "general")
    tax_inclusive = bool(metadata.get("tax_inclusive", True))
    reduced_rate = bool(metadata.get("reduced_rate", False))

    if taxpayer_type == "small":
        rate = LEVY_RATE_SMALL_REDUCED if reduced_rate else LEVY_RATE_SMALL
        method = "simplified"
        reason = (
            "小规模纳税人 + 阶段性减按 1% (2023-2027)"
            if reduced_rate
            else "小规模纳税人 → 3% 征收率"
        )
    else:
        rate = RATE_GENERAL
        method = "general"
        reason = "一般纳税人 → 6% 现代服务业(物业管理)"

    # ── 服务费收入(可加增值辅助收入) ──
    service_income = _dec(line_map.get("service_income"))
    ancillary = _dec(line_map.get("ancillary_income"))
    input_tax = _dec(line_map.get("input_tax"))
    gross_income = service_income + ancillary

    breakdown: list[BreakdownItem] = []
    warnings: list[str] = [reason]
    vat_payable = Decimal("0")

    if method == "simplified":
        # ── 3% 简易(无进项抵扣) ──
        if tax_inclusive:
            vat_payable = _round_2(gross_income * rate / (1 + rate))
            net = gross_income - vat_payable
        else:
            vat_payable = _round_2(gross_income * rate)
            net = gross_income
        breakdown.extend([
            BreakdownItem(category="service_income_gross", amount=gross_income),
            BreakdownItem(category="service_income_net", amount=net),
            BreakdownItem(category="rate", amount=rate),
            BreakdownItem(category="vat_payable", amount=vat_payable),
        ])
        if input_tax > 0:
            warnings.append(
                f"简易计税方法下进项税额 ¥{input_tax} 不允许抵扣,已忽略"
            )
    else:
        # ── 6% 一般(销项 - 进项) ──
        if tax_inclusive:
            output_tax = _round_2(gross_income * rate / (1 + rate))
            net_sales = gross_income - output_tax
        else:
            output_tax = _round_2(gross_income * rate)
            net_sales = gross_income
        vat_payable = max(Decimal("0"), output_tax - input_tax)
        breakdown.extend([
            BreakdownItem(category="service_income_gross", amount=gross_income),
            BreakdownItem(category="service_income_net", amount=net_sales),
            BreakdownItem(category="rate", amount=rate),
            BreakdownItem(category="output_tax", amount=output_tax),
            BreakdownItem(category="input_tax", amount=input_tax),
            BreakdownItem(category="vat_payable", amount=vat_payable),
        ])

    # ── 服务分项明细(展示用) ──
    service_breakdown = metadata.get("service_breakdown") or {}
    for svc, amount in service_breakdown.items():
        breakdown.append(BreakdownItem(
            category=f"breakdown_{svc}",
            amount=Decimal(str(amount)),
        ))

    return CalculationResult(
        total_tax_due=vat_payable,
        breakdown=breakdown,
        deductions=(
            [DeductionItem(category="input_credit", amount=input_tax, rule_ref="进项抵扣(仅一般计税)")]
            if method == "general" and input_tax > 0
            else []
        ),
        warnings=warnings,
    )
