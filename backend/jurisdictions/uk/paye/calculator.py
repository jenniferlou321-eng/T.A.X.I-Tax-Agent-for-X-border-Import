"""UK PAYE 计算器

主要计算：
- 雇主应支付的 PAYE/NIC 总和
- Employment Allowance 减免
- 净应支付金额
- Apprenticeship Levy（学徒税）：0.5% × 薪资总额 - £15,000 年免税额
"""

from decimal import Decimal, ROUND_HALF_UP
from backend.models.tax_data import TaxData
from backend.models.results import CalculationResult, BreakdownItem, DeductionItem


# 2024/25 NIC 阈值
EMPLOYMENT_ALLOWANCE = Decimal("5000")

# Apprenticeship Levy 2024/25
APPRENTICESHIP_LEVY_RATE = Decimal("0.005")  # 0.5%
APPRENTICESHIP_LEVY_ANNUAL_ALLOWANCE = Decimal("15000")  # £15,000 per year


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_paye(data: TaxData) -> CalculationResult:
    """计算 PAYE 雇主应支付金额"""
    line_map: dict[str, Decimal] = {li.category: li.amount for li in data.line_items}

    tax_deducted = _dec(line_map.get("total_tax_deducted"))
    employee_nics = _dec(line_map.get("total_employees_nics"))
    employer_nics = _dec(line_map.get("total_employer_nics"))

    # 总应付
    total_payable_before_allowance = tax_deducted + employee_nics + employer_nics

    # Employment Allowance
    employment_allowance = _dec(line_map.get("employment_allowance_claimed"))
    if employment_allowance == 0:
        employment_allowance = EMPLOYMENT_ALLOWANCE
    employment_allowance_applied = min(employment_allowance, employer_nics)

    net_payable = total_payable_before_allowance - employment_allowance_applied

    breakdown = [
        BreakdownItem(category="total_tax_deducted", amount=tax_deducted),
        BreakdownItem(category="total_employee_nics", amount=employee_nics),
        BreakdownItem(category="total_employer_nics", amount=employer_nics),
        BreakdownItem(category="total_payable_before_allowance", amount=total_payable_before_allowance),
        BreakdownItem(category="employment_allowance_applied", amount=employment_allowance_applied),
        BreakdownItem(category="net_payable_to_hmrc", amount=net_payable),
    ]

    return CalculationResult(
        total_tax_due=net_payable,
        breakdown=breakdown,
        deductions=[
            DeductionItem(category="employment_allowance", amount=employment_allowance_applied, rule_ref="NIC Regs 2015"),
        ],
        warnings=[],
    )


def calculate_apprenticeship_levy(
    total_pay_bill: Decimal,
    levy_allowance_claimed: Decimal = APPRENTICESHIP_LEVY_ANNUAL_ALLOWANCE,
    is_annual: bool = False,
) -> CalculationResult:
    """计算 UK Apprenticeship Levy（学徒税）

    规则（2024/25）：
    - 税率：薪资总额的 0.5%
    - 年免税额：£15,000
    - 仅当年薪资总额 > £300 万时产生税费
    - 通过 EPS 申报

    Args:
        total_pay_bill: 薪资总额（Decimal）
        levy_allowance_claimed: 免税额，默认 £15,000（年）
        is_annual: True = 输入是年总额；False = 月值（默认）

    Returns:
        CalculationResult 包含:
        - total_tax_due: 本期应缴学徒税
        - breakdown: total_pay_bill, levy_rate, gross_levy, levy_allowance, apprenticeship_levy_payable
        - warnings: 提醒（如未达阈值）
    """
    pay_bill = _dec(total_pay_bill)
    allowance = _dec(levy_allowance_claimed)

    # 如果是月值，将年免税额除以 12
    if not is_annual:
        period_allowance = allowance / Decimal("12")
    else:
        period_allowance = allowance

    # 0.5% 税率
    gross_levy = _round_2(pay_bill * APPRENTICESHIP_LEVY_RATE)

    # 实际应缴 = max(0, 总税额 - 免税额)
    levy_payable = _round_2(max(Decimal("0"), gross_levy - period_allowance))

    breakdown = [
        BreakdownItem(category="total_pay_bill", amount=pay_bill),
        BreakdownItem(category="levy_rate", amount=APPRENTICESHIP_LEVY_RATE),
        BreakdownItem(category="gross_levy", amount=gross_levy),
        BreakdownItem(category="levy_allowance", amount=_round_2(period_allowance)),
        BreakdownItem(category="apprenticeship_levy_payable", amount=levy_payable),
    ]

    warnings: list[str] = []
    if not is_annual and pay_bill * Decimal("12") < Decimal("3000000"):
        warnings.append(
            f"Annual pay bill £{pay_bill * 12:,.0f} is below the £3,000,000 threshold — "
            f"Apprenticeship Levy not strictly required, but reported via EPS for transparency."
        )

    return CalculationResult(
        total_tax_due=levy_payable,
        breakdown=breakdown,
        deductions=[
            DeductionItem(
                category="apprenticeship_levy_allowance",
                amount=_round_2(period_allowance),
                rule_ref="Finance Act 2017, Part 4",
            ),
        ],
        warnings=warnings,
    )
