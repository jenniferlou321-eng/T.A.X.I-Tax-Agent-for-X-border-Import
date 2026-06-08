"""Jurisdiction Adapter 抽象基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from ..models.tax_data import TaxType, ChannelType, TaxData
from ..models.template import DataTemplate
from ..models.results import CalculationResult, ValidationReport, FilingPayload
from ..models.agent_tools import AgentToolSet
from ..channels import FilingChannel


class JurisdictionAdapter(ABC):
    """管辖地适配器基类 — 每个国家实现一个"""

    country_code: str                   # "uk", "de", "cn"
    country_name: str                   # "United Kingdom"
    tax_types: list[TaxType]            # [TaxType.VAT, TaxType.SELF_ASSESSMENT]
    supported_channels: list[ChannelType]

    @abstractmethod
    def get_template(self, tax_type: TaxType) -> DataTemplate:
        """返回该税种的数据录入模板"""
        ...

    @abstractmethod
    def calculate(self, tax_type: TaxType, data: TaxData) -> CalculationResult:
        """计算应纳税额"""
        ...

    @abstractmethod
    def validate(self, tax_type: TaxType, data: TaxData) -> ValidationReport:
        """校验数据合规性"""
        ...

    @abstractmethod
    def get_channel(self, tax_type: TaxType) -> FilingChannel:
        """返回该税种的提交渠道"""
        ...

    @abstractmethod
    def to_filing_format(self, tax_type: TaxType, data: TaxData) -> FilingPayload:
        """将内部数据转换为管辖地要求的提交格式"""
        ...

    def get_agent_tools(self, tax_type: TaxType) -> AgentToolSet | None:
        """返回该税种的 Agent 工具集实现（可选）

        如果管辖地支持 Agent 智能对话报税，则返回对应的 AgentToolSet。
        默认返回 None，表示该管辖地/税种暂不支持 Agent 工具。
        """
        return None

    async def get_obligations(self, tax_type: TaxType, taxpayer_id: str, status_filter: str = "") -> list[dict]:
        """查询待申报义务（可选，但强烈推荐实现）

        Args:
            tax_type: 税种
            taxpayer_id: 纳税人识别号
            status_filter: 状态过滤

        Returns:
            义务列表，每项包含 period_key, start, end, due, status 等

        Raises:
            NotImplementedError: 如果该管辖地未实现此方法
        """
        raise NotImplementedError(f"get_obligations not implemented for {self.country_code}/{tax_type.value}")