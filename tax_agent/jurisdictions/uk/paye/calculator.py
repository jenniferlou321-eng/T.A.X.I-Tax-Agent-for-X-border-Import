"""UK PAYE 计算器

主要计算：
- 雇主应支付的 PAYE/NIC 总和
- Employment Allowance 减免
- 净应支付金额
"""

from decimal import Decimal, ROUND_HALF_UP
from tax_agent.models.tax_data import TaxData
from tax_agent.models.results import CalculationResult, BreakdownItem, DeductionItem


# 2024/25 NIC 阈值
EMPLOYMENT_ALLOWANCE = Decimal("5000")


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
