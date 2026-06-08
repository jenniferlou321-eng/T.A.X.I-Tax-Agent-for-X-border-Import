"""UK VAT Calculator — 9-box VAT 计算逻辑

HMRC MTD for VAT API 规范:
- Box 3 = Box 1 + Box 2
- Box 5 = |Box 3 − Box 4| (必须为非负值)
- Box 6-9 为整磅数（无小数位）
"""

from decimal import Decimal
from tax_agent.models.tax_data import TaxType, TaxData
from tax_agent.models.results import CalculationResult, BreakdownItem


def calculate_uk_vat(data: TaxData) -> CalculationResult:
    """计算 UK VAT Return 9-box 值

    Box 3 = Box 1 + Box 2
    Box 5 = |Box 3 − Box 4|  (HMRC 要求 netVatDue 必须 ≥ 0)
    """
    line_map = {li.category: li.amount for li in data.line_items}

    box1 = line_map.get("vat_due_sales", Decimal("0"))
    box2 = line_map.get("vat_due_acquisitions", Decimal("0"))
    box3 = box1 + box2
    box4 = line_map.get("vat_reclaimed_purchases", Decimal("0"))
    box5 = abs(box3 - box4)  # HMRC: netVatDue must be positive

    return CalculationResult(
        total_tax_due=box5,
        breakdown=[
            BreakdownItem(category="vat_due_sales", amount=box1),
            BreakdownItem(category="vat_due_acquisitions", amount=box2),
            BreakdownItem(category="total_vat_due", amount=box3),
            BreakdownItem(category="vat_reclaimed_purchases", amount=box4),
            BreakdownItem(category="net_vat_due", amount=box5),
        ],
        warnings=(
            ["Net VAT due is negative (repayment due from HMRC) — Box 5 shown as positive per HMRC requirements"]
            if (box3 - box4) < 0
            else []
        ),
    )
