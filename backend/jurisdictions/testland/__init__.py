"""Testland Jurisdiction Adapter — 用于验证多国扩展架构的示例实现

新增国家时的最小实现模板。Testland 是一个虚拟国家，
演示了实现 JurisdictionAdapter + AgentToolSet 所需的最少代码。

实际新增国家时，复制此目录结构并替换为真实税务逻辑即可。
"""

from __future__ import annotations

from backend.models.tax_data import TaxType, ChannelType, TaxData
from backend.models.template import DataTemplate, TemplateSection, TemplateField, FieldType, FieldValidation
from backend.models.results import CalculationResult, ValidationReport, FilingPayload, BreakdownItem
from backend.models.agent_tools import AgentToolSet
from backend.jurisdictions import JurisdictionAdapter
from backend.channels import FilingChannel
from backend.channels.api_channel import APIChannel

from .vat.agent_tools import TestlandVATAgentToolSet


# ── Testland VAT Template ──

from datetime import date

TESTLAND_VAT_TEMPLATE = DataTemplate(
    tax_type=TaxType.VAT,
    jurisdiction="testland",
    version="1.0.0",
    valid_from=date(2026, 1, 1),
    sections=[
        TemplateSection(
            title="Sales",
            description="Sales transactions",
            fields=[
                TemplateField(
                    key="total_sales",
                    label="Total Sales",
                    field_type=FieldType.NUMBER,
                    required=True,
                    hint="Total sales amount",
                ),
            ],
        ),
        TemplateSection(
            title="Purchases",
            description="Purchase transactions",
            fields=[
                TemplateField(
                    key="total_purchases",
                    label="Total Purchases",
                    field_type=FieldType.NUMBER,
                    required=True,
                    hint="Total purchase amount",
                ),
            ],
        ),
    ],
)


# ── Testland VAT Adapter ──

class TestlandVATAdapter:
    """Testland VAT — 简化实现"""

    tax_type = TaxType.VAT

    def __init__(self):
        # 模拟 API 通道（无真实后端）
        self._channel = APIChannel(
            base_url="https://api.testland.tax",
            oauth_config=None,  # type: ignore
            submit_endpoint="/v1/vat-returns",
            status_endpoint="/v1/vat-returns/{receipt_id}/status",
            accept_header="application/json",
        )

    def get_template(self, tax_type: TaxType) -> DataTemplate:
        return TESTLAND_VAT_TEMPLATE

    def calculate(self, tax_type: TaxType, data: TaxData) -> CalculationResult:
        """简化计算: 销售 VAT 15% - 采购 VAT 15%"""
        from decimal import Decimal
        line_map = {li.category: li.amount for li in data.line_items}
        sales = line_map.get("total_sales", Decimal("0"))
        purchases = line_map.get("total_purchases", Decimal("0"))
        vat_due = sales * Decimal("0.15")
        vat_reclaimed = purchases * Decimal("0.15")
        net_vat = abs(vat_due - vat_reclaimed)
        return CalculationResult(
            total_tax_due=net_vat,
            breakdown=[
                BreakdownItem(category="vat_due_sales", amount=vat_due, rate=Decimal("0.15")),
                BreakdownItem(category="vat_reclaimed_purchases", amount=vat_reclaimed, rate=Decimal("0.15")),
                BreakdownItem(category="net_vat_due", amount=net_vat),
            ],
        )

    def validate(self, tax_type: TaxType, data: TaxData) -> ValidationReport:
        """简化校验: 所有金额必须非负"""
        from backend.models.results import ValidationError
        errors = []
        for li in data.line_items:
            if li.amount < 0:
                errors.append(ValidationError(
                    field=li.category,
                    message=f"Amount must be non-negative: {li.amount}",
                ))
        return ValidationReport(
            is_valid=len(errors) == 0,
            errors=errors,
        )

    def get_channel(self, tax_type: TaxType) -> FilingChannel:
        return self._channel

    def to_filing_format(self, tax_type: TaxType, data: TaxData) -> FilingPayload:
        calc = self.calculate(tax_type, data)
        line_map = {li.category: li.amount for li in data.line_items}
        return FilingPayload(
            tax_type=TaxType.VAT,
            period=data.period,
            taxpayer=data.taxpayer,
            body={
                "sales": float(line_map.get("total_sales", 0)),
                "purchases": float(line_map.get("total_purchases", 0)),
                "vat_due": float(calc.breakdown[0].amount),
                "vat_reclaimed": float(calc.breakdown[1].amount),
                "net_vat": float(calc.total_tax_due),
            },
        )


# ── Testland Jurisdiction Adapter ──

class TestlandJurisdictionAdapter(JurisdictionAdapter):
    """Testland — Example multi-country extension

    Demonstrates the minimum implementation needed to add a new country.
    """

    country_code = "testland"
    country_name = "Testland"
    tax_types = [TaxType.VAT]
    supported_channels = [ChannelType.API]

    def __init__(self):
        self._vat = TestlandVATAdapter()
        self._vat_tools = TestlandVATAgentToolSet()

    def _get_adapter(self, tax_type: TaxType):
        if tax_type == TaxType.VAT:
            return self._vat
        raise ValueError(f"Tax type {tax_type.value} not supported for Testland")

    def get_template(self, tax_type: TaxType) -> DataTemplate:
        return self._get_adapter(tax_type).get_template(tax_type)

    def calculate(self, tax_type: TaxType, data: TaxData) -> CalculationResult:
        return self._get_adapter(tax_type).calculate(tax_type, data)

    def validate(self, tax_type: TaxType, data: TaxData) -> ValidationReport:
        return self._get_adapter(tax_type).validate(tax_type, data)

    def get_channel(self, tax_type: TaxType) -> FilingChannel:
        return self._get_adapter(tax_type).get_channel(tax_type)

    def to_filing_format(self, tax_type: TaxType, data: TaxData) -> FilingPayload:
        return self._get_adapter(tax_type).to_filing_format(tax_type, data)

    def get_agent_tools(self, tax_type: TaxType):
        """返回 Testland VAT 的 Agent 工具集"""
        if tax_type == TaxType.VAT:
            return self._vat_tools
        return None

    async def get_obligations(self, tax_type: TaxType, taxpayer_id: str, status_filter: str = "") -> list[dict]:
        """模拟查询申报义务"""
        return [
            {
                "period_key": "2026-Q1",
                "start": "2026-01-01",
                "end": "2026-03-31",
                "due": "2026-04-30",
                "status": "O",
                "received": None,
            },
            {
                "period_key": "2026-Q2",
                "start": "2026-04-01",
                "end": "2026-06-30",
                "due": "2026-07-31",
                "status": "O",
                "received": None,
            },
        ]
