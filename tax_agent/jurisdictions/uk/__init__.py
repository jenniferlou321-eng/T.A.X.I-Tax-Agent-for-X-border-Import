"""UK Jurisdiction Adapter — 支持 6 个税种

支持的税种：
- VAT (Value Added Tax) — MTD for VAT
- SELF_ASSESSMENT — MTD for ITSA
- CORPORATION_TAX — MTD for CT
- PAYE — RTI
- STAMP_DUTY — SDLT
- NATIONAL_INSURANCE — NICs
"""

from __future__ import annotations

import json
from typing import Optional

from tax_agent.models.tax_data import TaxType, ChannelType, TaxData
from tax_agent.models.template import DataTemplate
from tax_agent.models.results import CalculationResult, ValidationReport, FilingPayload
from tax_agent.jurisdictions import JurisdictionAdapter
from tax_agent.channels import FilingChannel
from tax_agent.models.agent_tools import AgentToolSet

from .vat import UKVATAdapter
from .vat.template import UK_VAT_TEMPLATE
from .vat.calculator import calculate_uk_vat
from .vat.validator import validate_uk_vat
from .vat.agent_tools import UKVATAgentToolSet

from .self_assessment import UKSAAdapter
from .self_assessment.template import SA_TEMPLATE
from .self_assessment.calculator import calculate_self_assessment
from .self_assessment.validator import validate_self_assessment
from .self_assessment.agent_tools import UKSAAgentToolSet

from .corporation_tax import UKCTAdapter
from .corporation_tax.template import CT600_FULL_TEMPLATE
from .corporation_tax.calculator import calculate_corporation_tax
from .corporation_tax.validator import validate_corporation_tax
from .corporation_tax.agent_tools import UKCTAgentToolSet

from .paye import UKPAYEAdapter
from .paye.template import PAYE_TEMPLATE
from .paye.calculator import calculate_paye
from .paye.agent_tools import UKPAYEAgentToolSet

from .stamp_duty import UKSDLTAdapter
from .stamp_duty.template import SDLT_TEMPLATE
from .stamp_duty.calculator import calculate_sdlt
from .stamp_duty.agent_tools import UKSDLTAgentToolSet


class UKJurisdictionAdapter(JurisdictionAdapter):
    """United Kingdom — 支持 6 个税种"""

    country_code = "uk"
    country_name = "United Kingdom"
    tax_types = [
        TaxType.VAT,
        TaxType.SELF_ASSESSMENT,
        TaxType.CORPORATION_TAX,
        TaxType.PAYE,
        TaxType.STAMP_DUTY,
    ]
    supported_channels = [ChannelType.API]

    def __init__(self):
        self._adapters = {
            TaxType.VAT: UKVATAdapter(),
            TaxType.SELF_ASSESSMENT: UKSAAdapter(),
            TaxType.CORPORATION_TAX: UKCTAdapter(),
            TaxType.PAYE: UKPAYEAdapter(),
            TaxType.STAMP_DUTY: UKSDLTAdapter(),
        }
        self._tool_sets = {
            TaxType.VAT: UKVATAgentToolSet(),
            TaxType.SELF_ASSESSMENT: UKSAAgentToolSet(),
            TaxType.CORPORATION_TAX: UKCTAgentToolSet(),
            TaxType.PAYE: UKPAYEAgentToolSet(),
            TaxType.STAMP_DUTY: UKSDLTAgentToolSet(),
        }

    def _get_adapter(self, tax_type: TaxType):
        adapter = self._adapters.get(tax_type)
        if adapter is None:
            raise ValueError(f"Tax type {tax_type.value} not yet supported for UK")
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
        """返回对应税种的 Agent 工具集"""
        return self._tool_sets.get(tax_type)

    async def get_obligations(self, tax_type: TaxType, taxpayer_id: str, status_filter: str = "") -> list[dict]:
        """查询申报义务 — 路由到对应工具集"""
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
