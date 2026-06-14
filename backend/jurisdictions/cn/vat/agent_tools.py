"""CN VAT Agent Tool Set — 中国增值税 Agent 工具

复用 `calculate_cn_vat` 计算器(已验证:销 ¥2,732,000 − 进 ¥270,500 = ¥2,461,500)。
提交走模拟模式(MockChannel 同款语义),不连真实电子税务局。

工具名用 `cn_vat_` 前缀,经 agent/tools.py 的前缀剥离映射到 AgentToolSet 抽象方法。
"""

from __future__ import annotations

import json
from decimal import Decimal
from datetime import date
from typing import Optional

from backend.models.agent_tools import AgentToolSet
from backend.models.tax_data import (
    TaxData, TaxpayerInfo, FiscalPeriod, TaxType, LineItem, PeriodType,
)
from backend.jurisdictions.uk._hmrc_base import tool_ok, tool_error

from .calculator import calculate_cn_vat


class CNVATAgentToolSet(AgentToolSet):
    """中国增值税 Agent 工具集 — 本地计算 + 模拟提交。"""

    country_code = "cn"
    tax_type = "cn_vat"

    # ── 查询类 ──

    async def get_obligations(self, taxpayer_id: str, status_filter: str = "") -> dict:
        """查询增值税申报义务(中国按月申报,次月 15 日前)。"""
        return tool_ok({
            "success": True,
            "mode": "mock",
            "obligations": [
                {
                    "period_key": "2023-12",
                    "start": "2023-12-01",
                    "end": "2023-12-31",
                    "due": "2024-01-15",
                    "status": "O",
                },
                {
                    "period_key": "FY2023",
                    "start": "2023-01-01",
                    "end": "2023-12-31",
                    "due": "2024-01-15",
                    "status": "O",
                    "note": "全年汇总(12 个月度申报)",
                },
            ],
        })

    # ── 计算类 ──

    async def calculate_return(self, line_items_json: str, period_info: Optional[dict] = None) -> dict:
        """计算中国增值税应纳税额。

        line_items category 支持:
          - output_tax / input_tax(税额合计,推荐)
          - output_13/9/6/5/3、input_13/9/6(按档销售额,calculator 自动算税)
        """
        try:
            raw_items = json.loads(line_items_json)
            if not isinstance(raw_items, list):
                return tool_error("line_items_json must be a JSON array")

            line_items = [
                LineItem(
                    category=li["category"],
                    amount=Decimal(str(li["amount"])),
                    currency=li.get("currency", "CNY"),
                    sub_category=li.get("sub_category", ""),
                )
                for li in raw_items
            ]

            data = _agent_tax_data(TaxType.CN_VAT, line_items, period_info)
            calc = calculate_cn_vat(data)
            bd = {b.category: str(b.amount) for b in calc.breakdown}

            return tool_ok({
                "success": True,
                "output_tax": bd.get("output_tax", "0"),
                "input_tax": bd.get("input_tax", "0"),
                "vat_payable": str(calc.total_tax_due),
                "warnings": calc.warnings,
            })
        except Exception as e:
            return tool_error(str(e))

    async def validate_return(self, return_data: dict) -> dict:
        """校验增值税申报数据(金额非负;留抵给提示)。"""
        try:
            errors = []
            for key in ("output_tax", "input_tax", "vat_payable"):
                if key in return_data and Decimal(str(return_data[key])) < 0:
                    errors.append({"field": key, "message": f"{key} 不能为负"})
            warnings = []
            out = Decimal(str(return_data.get("output_tax", "0")))
            inp = Decimal(str(return_data.get("input_tax", "0")))
            if inp > out:
                warnings.append({"field": "input_tax", "message": "进项 > 销项,差额可结转下期留抵"})
            return tool_ok({
                "success": True,
                "is_valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
            })
        except Exception as e:
            return tool_error(str(e))

    # ── 提交类 ──

    async def submit_return(self, taxpayer_id: str, period_key: str, return_data: dict) -> dict:
        """模拟提交增值税申报到电子税务局。

        WARNING: 模拟提交 — 不会真正提交到任何税局。
        """
        if not taxpayer_id or not period_key:
            return tool_error("taxpayer_id (USCC) 和 period_key 必填")
        return tool_ok({
            "success": True,
            "mode": "mock",
            "receipt_id": f"CN-MOCK-{period_key}-{taxpayer_id[-6:]}",
            "accepted": True,
            "submitted_body": {
                "period": period_key,
                "output_tax": str(return_data.get("output_tax", "0")),
                "input_tax": str(return_data.get("input_tax", "0")),
                "vat_payable": str(return_data.get("vat_payable", "0")),
            },
            "warning": "模拟提交:未向电子税务局真正提交。",
        })

    async def get_return(self, taxpayer_id: str, period_key: str) -> dict:
        """查询已(模拟)提交的增值税申报。"""
        return tool_ok({
            "success": True,
            "mode": "mock",
            "period_key": period_key,
            "taxpayer_id": taxpayer_id,
            "message": "模拟数据:电子税务局无真实底档。",
        })

    # ── 元数据 ──

    def get_tool_metadata(self) -> list[dict]:
        return [
            {
                "name": "get_cn_vat_obligations",
                "description": "查询中国增值税申报义务(按月申报,次月 15 日前)。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "taxpayer_id": {
                            "type": "string",
                            "description": "统一社会信用代码(USCC),18 位。别名 'uscc' 亦可。",
                        },
                        "status_filter": {
                            "type": "string",
                            "enum": ["", "O", "F"],
                            "description": "'' = 全部,'O' = 待申报,'F' = 已申报。",
                        },
                    },
                    "required": ["taxpayer_id"],
                },
            },
            {
                "name": "calculate_cn_vat_return",
                "description": (
                    "计算中国增值税应纳税额 = 销项税额 − 进项税额。"
                    "line_items 可直接给税额合计(output_tax / input_tax),"
                    "或按各档税率销售额(output_13/9/6/5/3、input_13/9/6)由计算器算税。"
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "line_items_json": {
                            "type": "string",
                            "description": (
                                "JSON 数组,如 "
                                "'[{\"category\":\"output_tax\",\"amount\":2732000},"
                                "{\"category\":\"input_tax\",\"amount\":270500}]'。"
                            ),
                        },
                    },
                    "required": ["line_items_json"],
                },
            },
            {
                "name": "validate_cn_vat_return",
                "description": "校验中国增值税申报数据(金额非负,进项>销项给留抵提示)。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "return_data": {
                            "type": "object",
                            "description": "增值税申报值",
                            "properties": {
                                "output_tax": {"type": "string", "description": "销项税额合计"},
                                "input_tax": {"type": "string", "description": "进项税额合计"},
                                "vat_payable": {"type": "string", "description": "应纳增值税"},
                            },
                        },
                    },
                    "required": ["return_data"],
                },
            },
            {
                "name": "submit_cn_vat_return",
                "description": (
                    "模拟提交中国增值税申报到电子税务局。**不可逆操作** — "
                    "仅在用户明确确认后调用。注意:demo 环境为模拟提交,不会真正报送。"
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "taxpayer_id": {"type": "string", "description": "USCC,18 位。"},
                        "period_key": {"type": "string", "description": "申报所属期,如 '2023-12' 或 'FY2023'。"},
                        "return_data": {
                            "type": "object",
                            "description": "增值税申报值(output_tax / input_tax / vat_payable)。",
                            "properties": {
                                "output_tax": {"type": "string"},
                                "input_tax": {"type": "string"},
                                "vat_payable": {"type": "string"},
                            },
                        },
                    },
                    "required": ["taxpayer_id", "period_key", "return_data"],
                },
            },
            {
                "name": "get_cn_vat_return",
                "description": "查询已(模拟)提交的中国增值税申报。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "taxpayer_id": {"type": "string", "description": "USCC。"},
                        "period_key": {"type": "string", "description": "申报所属期。"},
                    },
                    "required": ["taxpayer_id", "period_key"],
                },
            },
        ]


def _agent_tax_data(
    tax_type: TaxType, line_items: list[LineItem], period_info: Optional[dict],
) -> TaxData:
    """构造 agent 计算用的最小 TaxData。"""
    period_key = (period_info or {}).get("period_key", "FY2023")
    return TaxData(
        tax_type=tax_type,
        period=FiscalPeriod(
            year=(period_info or {}).get("year", 2023),
            period_type=PeriodType.ANNUAL,
            period_key=period_key,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        ),
        taxpayer=TaxpayerInfo(name="AgentCalc", tax_id="", tax_id_type="uscc"),
        line_items=line_items,
    )
