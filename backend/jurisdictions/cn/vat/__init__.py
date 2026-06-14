"""CN VAT Adapter — 中国增值税子 adapter

照 UK SDLT / Testland 子 adapter 形态:计算复用现成 `calculate_cn_vat`,
提交走 MockChannel(模拟回执),不连真实电子税务局。
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

from .template import CN_VAT_TEMPLATE
from .calculator import calculate_cn_vat
from .agent_tools import CNVATAgentToolSet


def validate_cn_vat(data: TaxData) -> ValidationReport:
    """最小校验:所有金额非负。"""
    errors = []
    for li in data.line_items:
        if li.amount < 0:
            errors.append(ValidationError(
                field=li.category, message=f"金额不能为负: {li.amount}",
            ))
    return ValidationReport(is_valid=len(errors) == 0, errors=errors, warnings=[])


class CNVATAdapter:
    """中国增值税 — 本地计算 + 模拟提交。"""

    tax_type = TaxType.CN_VAT

    def __init__(self):
        self._channel = MockChannel(receipt_prefix="CN-MOCK")
        self._tools = CNVATAgentToolSet()

    def get_template(self, tax_type: TaxType) -> DataTemplate:
        return CN_VAT_TEMPLATE

    def calculate(self, tax_type: TaxType, data: TaxData) -> CalculationResult:
        return calculate_cn_vat(data)

    def validate(self, tax_type: TaxType, data: TaxData) -> ValidationReport:
        return validate_cn_vat(data)

    def get_channel(self, tax_type: TaxType) -> FilingChannel:
        return self._channel

    def get_agent_tools(self, tax_type: TaxType):
        return self._tools

    def to_filing_format(self, tax_type: TaxType, data: TaxData) -> FilingPayload:
        calc = calculate_cn_vat(data)
        bd = {b.category: b.amount for b in calc.breakdown}
        return FilingPayload(
            tax_type=TaxType.CN_VAT,
            period=data.period,
            taxpayer=data.taxpayer,
            body={
                "output_tax": float(bd.get("output_tax", Decimal("0"))),
                "input_tax": float(bd.get("input_tax", Decimal("0"))),
                "vat_payable": float(calc.total_tax_due),
            },
        )
