"""CN CIT Adapter — 中国企业所得税子 adapter

照 UK SDLT / Testland 子 adapter 形态:计算复用现成 `calculate_cn_cit`,
提交走 MockChannel(模拟回执)。
"""

from __future__ import annotations

from decimal import Decimal

from backend.models.tax_data import TaxType, TaxData
from backend.models.template import DataTemplate
from backend.models.results import (
    CalculationResult, ValidationReport, ValidationError, FilingPayload,
)
from backend.channels import FilingChannel
from backend.channels.mock_channel import MockChannel

from .template import CN_CIT_TEMPLATE
from .calculator import calculate_cn_cit
from .agent_tools import CNCITAgentToolSet


def validate_cn_cit(data: TaxData) -> ValidationReport:
    """最小校验:所有金额非负。"""
    errors = []
    for li in data.line_items:
        if li.amount < 0:
            errors.append(ValidationError(
                field=li.category, message=f"金额不能为负: {li.amount}",
            ))
    return ValidationReport(is_valid=len(errors) == 0, errors=errors, warnings=[])


class CNCITAdapter:
    """中国企业所得税 — 本地计算 + 模拟提交。"""

    tax_type = TaxType.CN_CIT

    def __init__(self):
        self._channel = MockChannel(receipt_prefix="CN-MOCK")
        self._tools = CNCITAgentToolSet()

    def get_template(self, tax_type: TaxType) -> DataTemplate:
        return CN_CIT_TEMPLATE

    def calculate(self, tax_type: TaxType, data: TaxData) -> CalculationResult:
        return calculate_cn_cit(data)

    def validate(self, tax_type: TaxType, data: TaxData) -> ValidationReport:
        return validate_cn_cit(data)

    def get_channel(self, tax_type: TaxType) -> FilingChannel:
        return self._channel

    def get_agent_tools(self, tax_type: TaxType):
        return self._tools

    def to_filing_format(self, tax_type: TaxType, data: TaxData) -> FilingPayload:
        calc = calculate_cn_cit(data)
        bd = {b.category: b.amount for b in calc.breakdown}
        return FilingPayload(
            tax_type=TaxType.CN_CIT,
            period=data.period,
            taxpayer=data.taxpayer,
            body={
                "income_tax_payable": float(bd.get("cit_tax", Decimal("0"))),
                "foreign_tax_credit": float(bd.get("foreign_tax_credit", Decimal("0"))),
                "tax_payable": float(calc.total_tax_due),
            },
        )
