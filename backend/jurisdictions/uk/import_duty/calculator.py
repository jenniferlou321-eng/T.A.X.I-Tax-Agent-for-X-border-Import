"""UK Import Duty Calculator — CIF → Duty + Import VAT

进口关税计算:
1. CIF = FOB + Freight + Insurance
2. Duty = CIF × HS Code duty rate
3. Import VAT = (CIF + Duty) × 20% (标准) 或 5% (减让)
4. PVA (Postponed VAT Accounting): Import VAT 可延迟申报

嘉汉案例: C1-103 CIF £157,500 × 5% = £7,875
"""

from decimal import Decimal, ROUND_HALF_UP
from backend.models.tax_data import TaxData
from backend.models.results import CalculationResult, BreakdownItem, DeductionItem


VAT_STANDARD = Decimal("0.20")
VAT_REDUCED = Decimal("0.05")


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# 简化 HS Code → duty rate 映射 (常见品类)
HS_DUTY_RATES = {
    "electronics": Decimal("0.00"),    # 多数电子零关税
    "clothing": Decimal("0.12"),       # 服装
    "machinery": Decimal("0.00"),      # 大多数机械零关税
    "chemicals": Decimal("0.05"),      # 化工品
    "food_processed": Decimal("0.05"), # 加工食品
    "food_fresh": Decimal("0.00"),     # 鲜活零关税
    "vehicles": Decimal("0.10"),       # 车辆
    "steel": Decimal("0.00"),          # 钢铁
    "textiles": Decimal("0.08"),       # 纺织品
    "default": Decimal("0.05"),        # 默认
}


def calculate_import_duty(data: TaxData) -> CalculationResult:
    """计算 UK 进口关税。

    line_items:
      - fob_value: FOB 价值
      - freight: 运费
      - insurance: 保险费
      - 或: cif_value (直接提供 CIF)

    metadata:
      - hs_category: HS 品类 (见 HS_DUTY_RATES) 或直接 duty_rate
      - duty_rate: 直接指定税率 (覆盖 hs_category)
      - pva: 是否使用 Postponed VAT Accounting (默认 False)
      - import_vat_rate: 进口增值税率 (默认 20%)
    """
    line_map: dict[str, Decimal] = {li.category: li.amount for li in data.line_items}
    metadata = data.metadata

    # ── CIF 计算 ──
    cif = _dec(line_map.get("cif_value"))
    if cif == 0:
        fob = _dec(line_map.get("fob_value"))
        freight = _dec(line_map.get("freight"))
        insurance = _dec(line_map.get("insurance"))
        cif = fob + freight + insurance

    # ── 关税税率 ──
    if "duty_rate" in metadata:
        duty_rate = _dec(metadata["duty_rate"])
    else:
        hs_cat = metadata.get("hs_category", "default")
        duty_rate = HS_DUTY_RATES.get(hs_cat, HS_DUTY_RATES["default"])

    # ── 关税 ──
    duty = _round_2(cif * duty_rate)

    # ── 进口增值税 ──
    vat_rate = _dec(metadata.get("import_vat_rate", VAT_STANDARD))
    import_vat = _round_2((cif + duty) * vat_rate)

    # ── PVA ──
    pva = bool(metadata.get("pva", False))

    # ── 合计 ──
    total_at_border = duty + import_vat

    breakdown = [
        BreakdownItem(category="cif_value", amount=cif),
        BreakdownItem(category="duty_rate", amount=duty_rate),
        BreakdownItem(category="import_duty", amount=duty),
        BreakdownItem(category="import_vat_rate", amount=vat_rate),
        BreakdownItem(category="import_vat", amount=import_vat),
        BreakdownItem(category="total_at_border", amount=total_at_border),
        BreakdownItem(category="pva_enabled", amount=Decimal("1") if pva else Decimal("0")),
    ]

    warnings = []
    if pva:
        warnings.append("PVA 启用: Import VAT 不在进口时缴纳,而是在 VAT Return 中申报 (Box 1 + Box 4)")

    deductions = []
    if pva:
        deductions.append(DeductionItem(
            category="pva_deferred",
            amount=import_vat,
            description="PVA: Import VAT 延迟到 VAT Return 申报",
        ))

    return CalculationResult(
        total_tax_due=total_at_border,
        breakdown=breakdown,
        deductions=deductions,
        warnings=warnings,
    )
