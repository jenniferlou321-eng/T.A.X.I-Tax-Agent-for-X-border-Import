"""中国印花税计算器 — 应税凭证类型与税率映射

税率 (2024):
- 购销合同: 0.03%
- 加工承揽合同: 0.05%
- 建设工程勘察设计合同: 0.05%
- 建筑安装工程承包合同: 0.03%
- 财产租赁合同: 0.1%
- 货物运输合同: 0.05%
- 仓储保管合同: 0.1%
- 借款合同: 0.005%
- 财产保险合同: 0.1%
- 技术合同: 0.03%
- 产权转移书据: 0.05%
- 营业账簿 (实收资本+资本公积): 0.025%
- 权利许可证照: 5元/件
"""

from decimal import Decimal, ROUND_HALF_UP
from backend.models.tax_data import TaxData
from backend.models.results import CalculationResult, BreakdownItem


# 合同类型 → 税率
CONTRACT_RATES = {
    "purchase_sale": Decimal("0.0003"),       # 购销合同 0.03%
    "processing": Decimal("0.0005"),          # 加工承揽 0.05%
    "survey_design": Decimal("0.0005"),       # 勘察设计 0.05%
    "construction": Decimal("0.0003"),        # 建筑安装 0.03%
    "property_lease": Decimal("0.001"),       # 财产租赁 0.1%
    "freight_transport": Decimal("0.0005"),   # 货物运输 0.05%
    "warehousing": Decimal("0.001"),          # 仓储保管 0.1%
    "loan": Decimal("0.00005"),               # 借款合同 0.005%
    "property_insurance": Decimal("0.001"),   # 财产保险 0.1%
    "technology": Decimal("0.0003"),           # 技术合同 0.03%
    "property_transfer": Decimal("0.0005"),   # 产权转移 0.05%
    "capital_record": Decimal("0.00025"),     # 营业账簿 0.025%
}


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_cn_stamp_duty(data: TaxData) -> CalculationResult:
    """计算中国印花税。

    line_items:
      - 每个 category 对应一种合同类型 (见 CONTRACT_RATES key)
      - amount = 合同金额

    metadata:
      - license_count: 权利许可证照件数 (5元/件)
    """
    line_map: dict[str, Decimal] = {li.category: li.amount for li in data.line_items}
    metadata = data.metadata

    total_tax = Decimal("0")
    breakdown = []

    for contract_type, rate in CONTRACT_RATES.items():
        amount = _dec(line_map.get(contract_type))
        if amount > 0:
            tax = _round_2(amount * rate)
            total_tax += tax
            breakdown.append(BreakdownItem(
                category=f"stamp_duty_{contract_type}",
                amount=tax,
            ))

    # 权利许可证照 (固定税额)
    license_count = int(metadata.get("license_count", 0))
    if license_count > 0:
        license_tax = Decimal("5") * license_count
        total_tax += license_tax
        breakdown.append(BreakdownItem(
            category="stamp_duty_license",
            amount=license_tax,
        ))

    breakdown.append(BreakdownItem(category="total_stamp_duty", amount=total_tax))

    return CalculationResult(
        total_tax_due=total_tax,
        breakdown=breakdown,
        deductions=[],
        warnings=[],
    )
