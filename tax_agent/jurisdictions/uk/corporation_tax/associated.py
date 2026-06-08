"""UK Corporation Tax 关联企业 (Associated Companies) 规则

关联企业的定义 (CTA 2010 s.1262)：
- 两家公司其中一方控制另一方
- 双方均被同一第三方控制
- 同一企业或个人控制两家公司

影响：
- Lower/Upper limits 需按关联企业数量平分
- 关联企业数量 = n 时：
  - Effective Lower Limit = £50,000 / n
  - Effective Upper Limit = £250,000 / n
- 适用于 1 个会计期间（apportionment）

集团减免 (Group Relief)：
- 集团成员间可互相转移利润/亏损
- 集团定义：75% 子公司关系（一般 group）
- Capital gains group: 75% 直接持有
- 上限：接受方的应付税款
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


# ── 关联企业限制参数 ──

BASE_LOWER_LIMIT = Decimal("50000")
BASE_UPPER_LIMIT = Decimal("250000")
BASE_LOWER_RATE = Decimal("0.19")
BASE_MAIN_RATE = Decimal("0.25")


@dataclass
class AssociatedCompaniesResult:
    """关联企业计算结果"""
    num_associated_companies: int = 1  # 包含本企业
    effective_lower_limit: Decimal = BASE_LOWER_LIMIT
    effective_upper_limit: Decimal = BASE_UPPER_LIMIT
    lower_rate_applies_to: Decimal = BASE_LOWER_LIMIT
    main_rate_applies_to: Decimal = BASE_UPPER_LIMIT
    marginal_band_width: Decimal = BASE_UPPER_LIMIT - BASE_LOWER_LIMIT

    def to_breakdown(self) -> list[dict]:
        return [
            {"category": "num_associated_companies", "amount": str(self.num_associated_companies)},
            {"category": "effective_lower_limit", "amount": str(self.effective_lower_limit)},
            {"category": "effective_upper_limit", "amount": str(self.effective_upper_limit)},
        ]


def compute_associated_companies_limits(
    num_associated_companies: int,
) -> AssociatedCompaniesResult:
    """根据关联企业数量计算 effective lower/upper limits

    Args:
        num_associated_companies: 关联企业总数量（包括本公司）
            例如：本公司 + 1 关联 = 2
            例如：本公司 + 3 关联 = 4

    Returns:
        AssociatedCompaniesResult

    Note:
        If num_associated_companies < 1, treated as 1.
    """
    n = max(1, num_associated_companies)

    effective_lower = (BASE_LOWER_LIMIT / Decimal(n)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    effective_upper = (BASE_UPPER_LIMIT / Decimal(n)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    return AssociatedCompaniesResult(
        num_associated_companies=n,
        effective_lower_limit=effective_lower,
        effective_upper_limit=effective_upper,
        lower_rate_applies_to=effective_lower,
        main_rate_applies_to=effective_upper,
        marginal_band_width=effective_upper - effective_lower,
    )


def compute_marginal_relief(
    profits_chargeable: Decimal,
    num_associated_companies: int = 1,
) -> tuple[Decimal, Decimal, Decimal]:
    """计算关联企业下的 CT（含边际减免）

    Args:
        profits_chargeable: 应税利润
        num_associated_companies: 关联企业数量

    Returns:
        (tax_amount, effective_lower_limit, effective_upper_limit)

    公式:
    - 若 profits ≤ effective_lower: tax = profits × 19%
    - 若 profits ≥ effective_upper: tax = profits × 25%
    - 边际:
        lower_band_tax = effective_lower × 19%
        main_band_tax = (profits - effective_lower) × 25%
        tax = lower_band_tax + main_band_tax
    """
    limits = compute_associated_companies_limits(num_associated_companies)
    lower = limits.effective_lower_limit
    upper = limits.effective_upper_limit

    if profits_chargeable <= 0:
        return Decimal("0"), lower, upper

    if profits_chargeable <= lower:
        tax = (profits_chargeable * BASE_LOWER_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return tax, lower, upper

    if profits_chargeable >= upper:
        tax = (profits_chargeable * BASE_MAIN_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return tax, lower, upper

    # 边际: 低于 lower 部分按 19%，超出部分按 25%
    lower_band_tax = (lower * BASE_LOWER_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    main_band_tax = ((profits_chargeable - lower) * BASE_MAIN_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total = lower_band_tax + main_band_tax

    return total, lower, upper


def is_associated_company_relationship(
    company_a_controls_company_b: bool,
    third_party_controls_both: bool,
    same_person_controls_both: bool,
) -> bool:
    """判断两家公司是否关联

    关联的任一条件：
    - A 控制 B
    - 同第三方控制 A 和 B
    - 同一自然人/企业控制 A 和 B
    """
    return company_a_controls_company_b or third_party_controls_both or same_person_controls_both


# ── Group Relief 详细计算 ──

@dataclass
class GroupReliefResult:
    """Group Relief 申请结果"""
    surrendering_company: str
    available_relief: Decimal
    claimant_profits: Decimal
    claimant_company: str
    max_relief_claimable: Decimal
    relief_to_claim: Decimal
    relief_not_used: Decimal  # 可能因为是 capital loss 不能 claim 在 trading profit

    def to_breakdown(self) -> list[dict]:
        return [
            {"category": "surrender", "amount": str(self.available_relief)},
            {"category": "claimant_profits", "amount": str(self.claimant_profits)},
            {"category": "relief_claimed", "amount": str(self.relief_to_claim)},
            {"category": "relief_not_used", "amount": str(self.relief_not_used)},
        ]


def calculate_group_relief_transfer(
    claimant_company: str,
    claimant_profits_chargeable: Decimal,
    surrendering_company: str,
    surrendering_relief: Decimal,
    already_claimed_by_claimant: Decimal = Decimal("0"),
) -> GroupReliefResult:
    """计算 Group Relief 转移

    Args:
        claimant_company: 申请方公司名
        claimant_profits_chargeable: 申请方应税利润
        surrendering_company: 让渡方公司名
        surrendering_relief: 让渡方提供的 relief（损失）
        already_claimed_by_claimant: 申请方已使用的其他 group relief

    Returns:
        GroupReliefResult

    限制：
    - 申请方最大申请 = 申请方的应税利润 - 已使用的 group relief
    - 让渡方提供的 group relief 不能超过让渡方的当期损失
    """
    max_claimable = max(
        Decimal("0"),
        claimant_profits_chargeable - already_claimed_by_claimant,
    )
    relief_to_claim = min(surrendering_relief, max_claimable)
    relief_not_used = surrendering_relief - relief_to_claim

    return GroupReliefResult(
        surrendering_company=surrendering_company,
        available_relief=surrendering_relief,
        claimant_profits=claimant_profits_chargeable,
        claimant_company=claimant_company,
        max_relief_claimable=max_claimable,
        relief_to_claim=relief_to_claim,
        relief_not_used=relief_not_used,
    )
