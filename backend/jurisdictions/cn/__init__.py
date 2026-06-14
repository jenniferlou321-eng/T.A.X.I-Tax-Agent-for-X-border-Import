"""CN Jurisdiction Adapter — 中国,支持 CN_VAT + CN_CIT 两个 P0 税种

照 UKJurisdictionAdapter 形态:_adapters / _tool_sets dict 路由到税种子 adapter。
计算复用 `backend/jurisdictions/cn/{vat,cit}/calculator.py` 现成函数,
提交走 MockChannel(模拟回执,不连真实电子税务局)。

其余 7 个 CN 税种(IIT / 附加税 / 印花税 / 房产税 / FTC / 不动产租赁VAT /
物业管理VAT)的 calculator 已存在但暂未接入,前端继续用 jiahangCnFiling.json 展示。
"""

from __future__ import annotations

import json

from backend.models.tax_data import TaxType, ChannelType, TaxData
from backend.models.template import DataTemplate
from backend.models.results import CalculationResult, ValidationReport, FilingPayload
from backend.jurisdictions import JurisdictionAdapter
from backend.channels import FilingChannel
from backend.models.agent_tools import AgentToolSet

from .vat import CNVATAdapter
from .cit import CNCITAdapter


class CNJurisdictionAdapter(JurisdictionAdapter):
    """China — 支持 CN_VAT + CN_CIT"""

    country_code = "cn"
    country_name = "China"
    tax_types = [TaxType.CN_VAT, TaxType.CN_CIT]
    supported_channels = [ChannelType.API]

    def __init__(self):
        self._adapters = {
            TaxType.CN_VAT: CNVATAdapter(),
            TaxType.CN_CIT: CNCITAdapter(),
        }
        self._tool_sets = {
            TaxType.CN_VAT: self._adapters[TaxType.CN_VAT].get_agent_tools(TaxType.CN_VAT),
            TaxType.CN_CIT: self._adapters[TaxType.CN_CIT].get_agent_tools(TaxType.CN_CIT),
        }

    def _get_adapter(self, tax_type: TaxType):
        adapter = self._adapters.get(tax_type)
        if adapter is None:
            raise ValueError(f"Tax type {tax_type.value} not yet supported for CN")
        return adapter

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

    def get_agent_tools(self, tax_type: TaxType) -> AgentToolSet | None:
        return self._tool_sets.get(tax_type)

    async def get_obligations(self, tax_type: TaxType, taxpayer_id: str, status_filter: str = "") -> list[dict]:
        """查询申报义务 — 路由到对应工具集。"""
        tool_set = self._tool_sets.get(tax_type)
        if tool_set is None:
            raise NotImplementedError(f"get_obligations not supported for {self.country_code}/{tax_type.value}")
        result = await tool_set.get_obligations(taxpayer_id, status_filter)
        content = result.get("content", [{}])
        if content and isinstance(content[0], dict):
            text = content[0].get("text", "{}")
            data = json.loads(text)
            return data.get("obligations", [])
        return []
