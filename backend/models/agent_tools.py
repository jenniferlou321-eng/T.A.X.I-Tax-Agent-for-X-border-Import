"""Agent Tool Set 抽象接口

定义每个管辖地/税种需要为 Agent 提供的工具能力。
Agent 工具层 (agent/tools.py) 通过 JurisdictionAdapter 获取对应实现，
实现解耦 —— 新增国家只需实现此接口即可。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional
from decimal import Decimal


class AgentToolSet(ABC):
    """Agent 工具集 —— 每个管辖地/税种实现一套

    这些工具被注册为 MCP 工具，供 Claude Agent 在对话中调用。
    所有方法都是异步的（async），返回 dict 格式 {"content": [{"type": "text", "text": ...}]}。
    """

    country_code: str = ""
    tax_type: str = ""

    # ── 查询类工具 ──

    @abstractmethod
    async def get_obligations(self, taxpayer_id: str, status_filter: str = "") -> dict:
        """查询待申报义务

        Args:
            taxpayer_id: 纳税人识别号（VRN, Steuernummer, USCC 等）
            status_filter: 状态过滤，如 "O"=Open, "F"=Fulfilled

        Returns:
            工具标准输出格式，包含 obligations 列表
        """
        ...

    # ── 计算类工具 ──

    @abstractmethod
    async def calculate_return(self, line_items_json: str, period_info: Optional[dict] = None) -> dict:
        """计算申报表

        Args:
            line_items_json: JSON array of line items
            period_info: 可选的期间信息

        Returns:
            计算结果，包含各 box/字段值
        """
        ...

    @abstractmethod
    async def validate_return(self, return_data: dict) -> dict:
        """校验申报数据合规性

        Args:
            return_data: 申报表数据（通常是各 box/字段值）

        Returns:
            校验报告，含 is_valid, errors, warnings
        """
        ...

    # ── 提交类工具 ──

    @abstractmethod
    async def submit_return(self, taxpayer_id: str, period_key: str, return_data: dict) -> dict:
        """提交申报表到税局

        WARNING: 不可逆操作

        Args:
            taxpayer_id: 纳税人识别号
            period_key: 期间标识
            return_data: 完整申报数据

        Returns:
            回执信息
        """
        ...

    @abstractmethod
    async def get_return(self, taxpayer_id: str, period_key: str) -> dict:
        """查询已提交的申报表

        Args:
            taxpayer_id: 纳税人识别号
            period_key: 期间标识

        Returns:
            已提交申报数据
        """
        ...

    # ── 数据分析工具（可选） ──

    async def analyze_business_data(self, company_data_json: str) -> dict:
        """分析原始企业数据（可选实现）

        默认返回未实现提示。管辖地如支持原始数据分析可覆盖此方法。

        Args:
            company_data_json: 原始企业 JSON 数据

        Returns:
            分析报告
        """
        return {
            "content": [{
                "type": "text",
                "text": '{"success": false, "error": "Raw business data analysis not supported for this jurisdiction yet"}'
            }],
            "is_error": True,
        }

    # ── 工具元数据 ──

    @abstractmethod
    def get_tool_metadata(self) -> list[dict]:
        """返回该工具集的所有工具元数据，用于 MCP Server 注册

        Returns:
            list of {
                "name": str,
                "description": str,
                "input_schema": dict,
            }
        """
        ...

    def get_allowlist(self) -> list[str]:
        """返回工具白名单（mcp__<server>__<tool> 格式）"""
        server_name = f"tax_agent_{self.country_code}_{self.tax_type}"
        return [f"mcp__{server_name}__{meta['name']}" for meta in self.get_tool_metadata()]
