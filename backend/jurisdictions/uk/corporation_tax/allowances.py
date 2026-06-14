"""UK Corporation Tax 资本减免与损失处理

包含：
- Capital Allowances (Main Pool, Special Rate Pool, FYA, AIA)
- Loss Relief (trading losses, capital losses)
- Group Relief
- R&D Tax Relief
- Patents and Know-how Relief
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


# ── 资本减免参数 (FY2024/25) ──

# Annual Investment Allowance
AIA_LIMIT = Decimal("1000000")  # 100% 减免，上限 £1m
AIA_RATE = Decimal("1.00")

# Main Rate Pool
MAIN_POOL_WRITING_DOWN_RATE = Decimal("0.18")  # 18% per year (reducing balance)
MAIN_POOL_FIRST_YEAR_RATE = Decimal("0.06")   # 6% first year

# Special Rate Pool (integral features, long-life assets)
SPECIAL_RATE_POOL_WDA_RATE = Decimal("0.06")  # 6% per year

# First Year Allowances (FYA)
FYA_RATES = {
    "electric_charge_point": Decimal("1.00"),
    "zero_emission_cars": Decimal("1.00"),
    "main_rate_assets_2y": Decimal("1.00"),  # 2024-25 temporary FYA
}

# Structures and Buildings
SBA_RATE = Decimal("0.03")  # 3% per year


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ── Capital Allowances 计算 ──

@dataclass
class CapitalAllowancesResult:
    """资本减免计算结果"""
    aia_allowance: Decimal = Decimal("0")
    fya_allowance: Decimal = Decimal("0")
    main_pool_wda: Decimal = Decimal("0")
    special_rate_pool_wda: Decimal = Decimal("0")
    structures_buildings_allowance: Decimal = Decimal("0")
    balancing_charges: Decimal = Decimal("0")
    total_allowance: Decimal = Decimal("0")

    def to_breakdown(self) -> list[dict]:
        return [
            {"category": "aia_allowance", "amount": str(self.aia_allowance)},
            {"category": "fya_allowance", "amount": str(self.fya_allowance)},
            {"category": "main_pool_wda", "amount": str(self.main_pool_wda)},
            {"category": "special_rate_pool_wda", "amount": str(self.special_rate_pool_wda)},
            {"category": "structures_buildings_allowance", "amount": str(self.structures_buildings_allowance)},
            {"category": "balancing_charges", "amount": str(self.balancing_charges)},
            {"category": "total_allowance", "amount": str(self.total_allowance)},
        ]


def calculate_capital_allowances(
    aia_expenditure: Decimal,
    fya_expenditure: Decimal,
    main_pool_expenditure: Decimal,
    main_pool_opening_balance: Decimal,
    special_rate_pool_expenditure: Decimal,
    special_rate_pool_opening_balance: Decimal,
    sba_expenditure: Decimal,
    sba_opening_balance: Decimal,
    disposals_proceeds: Decimal = Decimal("0"),
    disposals_pool: str = "main",
) -> CapitalAllowancesResult:
    """计算资本减免总额

    Args:
        aia_expenditure: 当年 AIA 合格支出（plant & machinery）
        fya_expenditure: FYA 合格支出（如电动车、充电桩）
        main_pool_expenditure: 投入 main pool 的资产
        main_pool_opening_balance: main pool 期初余额（含往年未减完部分）
        special_rate_pool_expenditure: 投入 special rate pool 的资产
        special_rate_pool_opening_balance: special rate pool 期初余额
        sba_expenditure: 当年 new structures and buildings 支出
        sba_opening_balance: SBA 期初余额
        disposals_proceeds: 资产处置收入
        disposals_pool: 处置收入计入的 pool ("main" / "special")
    """
    result = CapitalAllowancesResult()

    # ── 1. AIA (Annual Investment Allowance) ──
    aia_qualifying = aia_expenditure
    result.aia_allowance = min(aia_qualifying, AIA_LIMIT)

    # 超出 AIA 的部分转入 main pool
    aia_excess_to_main = aia_qualifying - result.aia_allowance
    main_pool_total_expenditure = main_pool_expenditure + aia_excess_to_main

    # ── 2. FYA ──
    result.fya_allowance = fya_expenditure * Decimal("1.00")  # 100% in year

    # ── 3. Main Pool WDA (Writing Down Allowance) ──
    # 处置收入从对应 pool 中扣除
    if disposals_pool == "main":
        # 处置先冲销 main pool
        net_main_balance = (
            main_pool_opening_balance
            + main_pool_total_expenditure
            - disposals_proceeds
        )
    else:
        net_main_balance = main_pool_opening_balance + main_pool_total_expenditure

    if net_main_balance > 0:
        result.main_pool_wda = _round_2(net_main_balance * MAIN_POOL_WRITING_DOWN_RATE)
    else:
        # 可能产生 balancing charge
        result.balancing_charges += abs(net_main_balance)
        result.main_pool_wda = Decimal("0")

    # ── 4. Special Rate Pool WDA ──
    if disposals_pool == "special":
        net_special_balance = (
            special_rate_pool_opening_balance
            + special_rate_pool_expenditure
            - disposals_proceeds
        )
    else:
        net_special_balance = special_rate_pool_opening_balance + special_rate_pool_expenditure

    if net_special_balance > 0:
        result.special_rate_pool_wda = _round_2(net_special_balance * SPECIAL_RATE_POOL_WDA_RATE)
    elif net_special_balance < 0:
        result.balancing_charges += abs(net_special_balance)
        result.special_rate_pool_wda = Decimal("0")

    # ── 5. Structures and Buildings Allowance (SBA) ──
    sba_total_balance = sba_opening_balance + sba_expenditure
    if sba_total_balance > 0:
        result.structures_buildings_allowance = _round_2(sba_total_balance * SBA_RATE)

    # ── 6. 总减免 ──
    result.total_allowance = (
        result.aia_allowance
        + result.fya_allowance
        + result.main_pool_wda
        + result.special_rate_pool_wda
        + result.structures_buildings_allowance
        - result.balancing_charges
    )

    return result


# ── 损失减免 ──

@dataclass
class LossReliefResult:
    """损失减免结果"""
    current_year_loss: Decimal = Decimal("0")
    carry_back_loss: Decimal = Decimal("0")
    carry_forward_loss: Decimal = Decimal("0")
    loss_relief_used: Decimal = Decimal("0")
    remaining_loss_to_carry_forward: Decimal = Decimal("0")
    carry_back_years: int = 1  # FY2024: 可以 carry back 1 year

    def to_breakdown(self) -> list[dict]:
        return [
            {"category": "current_year_loss", "amount": str(self.current_year_loss)},
            {"category": "loss_relief_used", "amount": str(self.loss_relief_used)},
            {"category": "remaining_loss_to_carry_forward", "amount": str(self.remaining_loss_to_carry_forward)},
        ]


def apply_loss_relief(
    trading_loss: Decimal,
    other_income_chargeable_to_ct: Decimal,
    losses_brought_forward: Decimal = Decimal("0"),
    carry_back: bool = True,
) -> LossReliefResult:
    """应用损失减免

    规则 (FY2024):
    - 当年交易亏损可向上年 carry back 1 年
    - 剩余可无限期 carry forward
    - 允许用亏损冲抵当年其他应税收入
    """
    result = LossReliefResult()
    # 接受正数或负数（trading_loss 是亏损，正数表示绝对值）
    abs_loss = abs(trading_loss)
    if abs_loss == 0:
        return result

    result.current_year_loss = abs_loss

    # 1. 先冲抵当年其他收入
    offset_against_current_year = min(abs_loss, other_income_chargeable_to_ct)
    result.loss_relief_used = offset_against_current_year
    remaining = abs_loss - offset_against_current_year

    # 2. 向上年 carry back（如果启用）
    if carry_back and remaining > 0:
        result.carry_back_loss = remaining
        # 假设 carry back 全部被前一年吸收
        remaining = Decimal("0")
    elif remaining > 0:
        # 不 carry back，剩余 forward
        result.carry_forward_loss = remaining

    # 加上前期 carry forward
    result.remaining_loss_to_carry_forward = losses_brought_forward + result.carry_forward_loss

    return result


# ── R&D Tax Relief ──

@dataclass
class RnDResult:
    """R&D 税收减免结果"""
    qualifying_expenditure: Decimal = Decimal("0")
    rd_relief: Decimal = Decimal("0")
    rd_enhanced_deduction_rate: Decimal = Decimal("0.86")  # 默认 86% enhanced deduction
    is_sme: bool = True

    def to_breakdown(self) -> list[dict]:
        return [
            {"category": "rd_qualifying_expenditure", "amount": str(self.qualifying_expenditure)},
            {"category": "rd_relief", "amount": str(self.rd_relief)},
        ]


def calculate_rd_relief(
    qualifying_expenditure: Decimal,
    is_sme: bool = True,
) -> RnDResult:
    """计算 R&D 税收减免

    规则 (FY2024):
    - SME scheme: 86% enhanced deduction (for accounting periods from 1 April 2023)
    - Large company RDEC: 20% credit
    """
    result = RnDResult(qualifying_expenditure=qualifying_expenditure, is_sme=is_sme)

    if is_sme:
        # 86% enhanced deduction
        result.rd_enhanced_deduction_rate = Decimal("0.86")
        result.rd_relief = _round_2(qualifying_expenditure * Decimal("0.86"))
    else:
        # RDEC scheme: 20% taxable credit
        result.rd_enhanced_deduction_rate = Decimal("0.20")
        result.rd_relief = _round_2(qualifying_expenditure * Decimal("0.20"))

    return result


# ── Group Relief ──

def calculate_group_relief_claim(
    group_relief_available: Decimal,
    profits_chargeable: Decimal,
    already_used: Decimal = Decimal("0"),
) -> tuple[Decimal, Decimal]:
    """计算 Group Relief 申请

    Args:
        group_relief_available: 同集团其他公司可提供的 group relief
        profits_chargeable: 当前公司应税利润
        already_used: 已使用的 group relief

    Returns:
        (允许使用的 group relief, 剩余)
    """
    remaining_capacity = max(Decimal("0"), profits_chargeable - already_used)
    can_claim = min(group_relief_available, remaining_capacity)
    return _round_2(can_claim), group_relief_available - can_claim
