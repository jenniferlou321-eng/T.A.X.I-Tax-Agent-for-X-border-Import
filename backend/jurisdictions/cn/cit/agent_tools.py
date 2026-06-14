"""CN CIT Agent Tool Set — 中国企业所得税 Agent 工具

复用 `calculate_cn_cit` 计算器。关键:计算结果**同时给三个口径数** —
  应纳所得税额(cit_tax) / 境外税收抵免(foreign_tax_credit) / 应补税额(tax_payable)
让 agent 能讲清「应纳 vs 应补」,呼应嘉汉「境外抵免」亮点。

已验证(嘉汉 FY2023):应纳 ¥2,032,500 / 抵免 ¥43,679 / 应补 ¥1,988,821。
提交走模拟模式,不连真实电子税务局。
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

from .calculator import calculate_cn_cit


class CNCITAgentToolSet(AgentToolSet):
    """中国企业所得税 Agent 工具集 — 本地计算 + 模拟提交。"""

    country_code = "cn"
    tax_type = "cn_cit"

    # ── 查询类 ──

    async def get_obligations(self, taxpayer_id: str, status_filter: str = "") -> dict:
        """查询企业所得税申报义务(季度预缴 + 年度汇算清缴)。"""
        return tool_ok({
            "success": True,
            "mode": "mock",
            "obligations": [
                {
                    "period_key": "FY2023",
                    "start": "2023-01-01",
                    "end": "2023-12-31",
                    "due": "2024-05-31",
                    "status": "O",
                    "note": "年度汇算清缴,次年 5 月 31 日前",
                },
            ],
        })

    # ── 计算类 ──

    async def calculate_return(self, line_items_json: str, period_info: Optional[dict] = None) -> dict:
        """计算中国企业所得税。

        line_items category:
          - accounting_profit(会计利润)、tax_adjustment_up(调增)、tax_adjustment_down(调减)
          - foreign_tax_credit(境外已缴)、overseas_income(境外所得,算抵免限额)
        metadata: tax_rate = standard(25%) / high_tech(15%) / small(5%)
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

            tax_rate = (period_info or {}).get("tax_rate", "standard")
            data = _agent_tax_data(line_items, period_info, tax_rate)
            calc = calculate_cn_cit(data)
            bd = {b.category: str(b.amount) for b in calc.breakdown}

            # 三个口径数:应纳 / 境外抵免 / 应补
            return tool_ok({
                "success": True,
                "taxable_income": bd.get("taxable_income", "0"),
                "cit_rate": bd.get("cit_rate", "0.25"),
                "income_tax_payable": bd.get("cit_tax", "0"),          # 应纳所得税额
                "foreign_tax_credit": bd.get("foreign_tax_credit", "0"),  # 境外抵免(实际可抵)
                "ftc_limit": bd.get("ftc_limit", "0"),
                "tax_payable": str(calc.total_tax_due),                # 应补税额(扣抵免/预缴后)
                "warnings": calc.warnings,
            })
        except Exception as e:
            return tool_error(str(e))

    async def validate_return(self, return_data: dict) -> dict:
        """校验企业所得税申报数据(金额非负;抵免超限给提示)。"""
        try:
            errors = []
            for key in ("income_tax_payable", "tax_payable"):
                if key in return_data and Decimal(str(return_data[key])) < 0:
                    errors.append({"field": key, "message": f"{key} 不能为负"})
            warnings = []
            ftc = Decimal(str(return_data.get("foreign_tax_credit", "0")))
            limit = Decimal(str(return_data.get("ftc_limit", "0")))
            if limit > 0 and ftc >= limit:
                warnings.append({"field": "foreign_tax_credit", "message": "境外抵免已达限额"})
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
        """模拟提交企业所得税年度汇算清缴。

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
                "income_tax_payable": str(return_data.get("income_tax_payable", "0")),
                "foreign_tax_credit": str(return_data.get("foreign_tax_credit", "0")),
                "tax_payable": str(return_data.get("tax_payable", "0")),
            },
            "warning": "模拟提交:未向电子税务局真正提交。",
        })

    async def get_return(self, taxpayer_id: str, period_key: str) -> dict:
        """查询已(模拟)提交的企业所得税申报。"""
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
                "name": "get_cn_cit_obligations",
                "description": "查询中国企业所得税申报义务(季度预缴 + 年度汇算清缴,次年 5 月 31 日前)。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "taxpayer_id": {"type": "string", "description": "USCC,18 位。别名 'uscc' 亦可。"},
                        "status_filter": {"type": "string", "enum": ["", "O", "F"]},
                    },
                    "required": ["taxpayer_id"],
                },
            },
            {
                "name": "calculate_cn_cit_return",
                "description": (
                    "计算中国企业所得税。应纳税所得额 = 会计利润 + 调增 − 调减,"
                    "应纳所得税额 = 应纳税所得额 × 税率,应补 = 应纳 − 境外抵免 − 已预缴。"
                    "返回同时给【应纳所得税额 income_tax_payable】【境外抵免 foreign_tax_credit】"
                    "【应补 tax_payable】三个数。"
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "line_items_json": {
                            "type": "string",
                            "description": (
                                "JSON 数组,如 "
                                "'[{\"category\":\"accounting_profit\",\"amount\":8000000},"
                                "{\"category\":\"tax_adjustment_up\",\"amount\":280000},"
                                "{\"category\":\"tax_adjustment_down\",\"amount\":150000},"
                                "{\"category\":\"foreign_tax_credit\",\"amount\":43679},"
                                "{\"category\":\"overseas_income\",\"amount\":1639750}]'。"
                            ),
                        },
                    },
                    "required": ["line_items_json"],
                },
            },
            {
                "name": "validate_cn_cit_return",
                "description": "校验中国企业所得税申报数据(金额非负,境外抵免超限给提示)。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "return_data": {
                            "type": "object",
                            "description": "企业所得税申报值",
                            "properties": {
                                "income_tax_payable": {"type": "string", "description": "应纳所得税额"},
                                "foreign_tax_credit": {"type": "string", "description": "境外税收抵免"},
                                "ftc_limit": {"type": "string", "description": "抵免限额"},
                                "tax_payable": {"type": "string", "description": "应补税额"},
                            },
                        },
                    },
                    "required": ["return_data"],
                },
            },
            {
                "name": "submit_cn_cit_return",
                "description": (
                    "模拟提交中国企业所得税年度汇算清缴。**不可逆操作** — "
                    "仅在用户明确确认后调用。注意:demo 环境为模拟提交,不会真正报送。"
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "taxpayer_id": {"type": "string", "description": "USCC,18 位。"},
                        "period_key": {"type": "string", "description": "纳税年度,如 'FY2023'。"},
                        "return_data": {
                            "type": "object",
                            "description": "企业所得税申报值。",
                            "properties": {
                                "income_tax_payable": {"type": "string"},
                                "foreign_tax_credit": {"type": "string"},
                                "tax_payable": {"type": "string"},
                            },
                        },
                    },
                    "required": ["taxpayer_id", "period_key", "return_data"],
                },
            },
            {
                "name": "get_cn_cit_return",
                "description": "查询已(模拟)提交的中国企业所得税申报。",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "taxpayer_id": {"type": "string", "description": "USCC。"},
                        "period_key": {"type": "string", "description": "纳税年度。"},
                    },
                    "required": ["taxpayer_id", "period_key"],
                },
            },
        ]


def _agent_tax_data(
    line_items: list[LineItem], period_info: Optional[dict], tax_rate: str,
) -> TaxData:
    """构造 agent 计算用的最小 TaxData(CIT 年度口径)。"""
    period_key = (period_info or {}).get("period_key", "FY2023")
    return TaxData(
        tax_type=TaxType.CN_CIT,
        period=FiscalPeriod(
            year=(period_info or {}).get("year", 2023),
            period_type=PeriodType.ANNUAL,
            period_key=period_key,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        ),
        taxpayer=TaxpayerInfo(name="AgentCalc", tax_id="", tax_id_type="uscc"),
        line_items=line_items,
        metadata={"tax_rate": tax_rate},
    )
