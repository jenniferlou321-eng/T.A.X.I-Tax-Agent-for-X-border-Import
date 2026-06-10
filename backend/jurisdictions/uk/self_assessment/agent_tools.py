"""UK Self Assessment Agent Tool Set — HMRC MTD for ITSA 实现"""

from __future__ import annotations

import json
from typing import Optional

from backend.models.agent_tools import AgentToolSet
from backend.models.tax_data import (
    TaxData, TaxpayerInfo, FiscalPeriod, TaxType, LineItem, PeriodType,
)
from backend.channels.oauth import OAuth2Manager
from backend.agent.business_analyzer import analyze_business_data as _analyze_business_data


def _tool_error(msg: str, detail: str = "") -> dict:
    payload = {"success": False, "error": msg}
    if detail:
        payload["detail"] = detail
    return {"content": [{"type": "text", "text": json.dumps(payload)}], "is_error": True}


def _tool_ok(data: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(data, indent=2)}]}


class UKSAAgentToolSet(AgentToolSet):
    """UK Self Assessment Agent 工具集 — HMRC MTD for ITSA"""

    country_code = "uk"
    tax_type = "self_assessment"

    async def get_obligations(self, taxpayer_id: str, status_filter: str = "") -> dict:
        """查询 HMRC ITSA 申报义务"""
        from backend.jurisdictions.uk.config import hmrc_config
        nino = taxpayer_id
        if not nino:
            return _tool_error("NINO is required")
        # 模拟返回（生产环境调用真实 API）
        return _tool_ok({
            "success": True,
            "obligations": [
                {
                    "tax_year": "2023-24",
                    "start": "2023-04-06",
                    "end": "2024-04-05",
                    "due": "2025-01-31",
                    "status": "O",
                },
                {
                    "tax_year": "2022-23",
                    "start": "2022-04-06",
                    "end": "2023-04-05",
                    "due": "2024-01-31",
                    "status": "F",
                },
            ],
        })

    async def calculate_return(self, line_items_json: str, period_info: Optional[dict] = None) -> dict:
        """计算 Self Assessment 应纳税额"""
        try:
            raw_items = json.loads(line_items_json)
            line_items = [
                LineItem(
                    category=li["category"],
                    amount=__import__("decimal").Decimal(str(li["amount"])),
                    currency=li.get("currency", "GBP"),
                )
                for li in raw_items
            ]
            data = TaxData(
                tax_type=TaxType.SELF_ASSESSMENT,
                period=FiscalPeriod(
                    year=2024,
                    period_type=PeriodType.ANNUAL,
                    period_key=period_info.get("period_key", "2023-24") if period_info else "2023-24",
                    start_date=__import__("datetime").date(2023, 4, 6),
                    end_date=__import__("datetime").date(2024, 4, 5),
                ),
                taxpayer=TaxpayerInfo(
                    name="AgentCalc",
                    tax_id=period_info.get("nino", "AB123456C") if period_info else "AB123456C",
                    tax_id_type="nino",
                ),
                line_items=line_items,
            )
            from .calculator import calculate_self_assessment
            calc = calculate_self_assessment(data)
            box_map = {b.category: float(b.amount) for b in calc.breakdown}

            return _tool_ok({
                "success": True,
                "total_income": box_map.get("total_income", 0),
                "personal_allowance": box_map.get("personal_allowance", 0),
                "taxable_income": box_map.get("taxable_income", 0),
                "income_tax_due": box_map.get("income_tax_due", 0),
                "capital_gains_tax_due": box_map.get("capital_gains_tax_due", 0),
                "total_tax_due": box_map.get("total_tax_due", 0),
                "tax_already_paid": box_map.get("tax_already_paid", 0),
                "balancing_payment": box_map.get("balancing_payment", 0),
            })
        except Exception as e:
            return _tool_error(str(e))

    async def validate_return(self, return_data: dict) -> dict:
        """校验 Self Assessment 数据"""
        try:
            from .validator import validate_self_assessment
            line_items = []
            for key, val in return_data.items():
                if key in (
                    "employment_income", "self_employment_net_profit",
                    "property_net_income", "foreign_income", "savings_income",
                    "dividend_income", "other_income", "pension_contributions",
                    "gift_aid", "tax_withheld", "total_gains", "total_losses",
                ):
                    line_items.append(LineItem(
                        category=key,
                        amount=__import__("decimal").Decimal(str(val)) if val is not None else 0,
                        currency="GBP",
                    ))
            data = TaxData(
                tax_type=TaxType.SELF_ASSESSMENT,
                period=FiscalPeriod(
                    year=2024,
                    period_type=PeriodType.ANNUAL,
                    period_key=return_data.get("tax_year", "2023-24"),
                    start_date=__import__("datetime").date(2023, 4, 6),
                    end_date=__import__("datetime").date(2024, 4, 5),
                ),
                taxpayer=TaxpayerInfo(
                    name="AgentVal",
                    tax_id=return_data.get("nino", ""),
                    tax_id_type="nino",
                ),
                line_items=line_items,
            )
            report = validate_self_assessment(data)
            return _tool_ok({
                "success": True,
                "is_valid": report.is_valid,
                "errors": [{"field": e.field, "message": e.message} for e in report.errors],
                "warnings": [{"field": w.field, "message": w.message} for w in report.warnings],
            })
        except Exception as e:
            return _tool_error(str(e))

    async def submit_return(self, taxpayer_id: str, period_key: str, return_data: dict) -> dict:
        """提交 Self Assessment 至 HMRC"""
        nino = taxpayer_id
        if not nino or not period_key:
            return _tool_error("NINO and tax_year (period_key) are required")
        # 模拟提交
        return _tool_ok({
            "success": True,
            "submission_id": f"SA-{nino}-{period_key}-001",
            "processing_date": "2025-01-15T10:00:00Z",
            "tax_year": period_key,
            "message": "Self Assessment submitted to HMRC (simulated)",
        })

    async def get_return(self, taxpayer_id: str, period_key: str) -> dict:
        """查询已提交的 Self Assessment"""
        nino = taxpayer_id
        if not nino or not period_key:
            return _tool_error("NINO and tax_year are required")
        return _tool_ok({
            "success": True,
            "nino": nino,
            "tax_year": period_key,
            "message": "Submitted SA return data (simulated)",
        })

    async def analyze_business_data(self, company_data_json: str) -> dict:
        """SA 不直接分析原始业务数据，但可复用通用分析器"""
        # 复用 UK VAT 的业务分析器
        result = _analyze_business_data(company_data_json)
        if result.get("success"):
            return _tool_ok(result)
        return _tool_error(result.get("error", "Analysis failed"))

    def get_tool_metadata(self) -> list[dict]:
        return [
            {
                "name": "get_self_assessment_obligations",
                "description": "Query HMRC for Self Assessment filing obligations for a given NINO.",
                "input_schema": {"nino": str},
            },
            {
                "name": "calculate_self_assessment",
                "description": "Calculate UK Self Assessment tax liability from line items (employment, self-employment, property, capital gains, etc.).",
                "input_schema": {"line_items_json": str, "period_info": dict},
            },
            {
                "name": "validate_self_assessment",
                "description": "Validate a Self Assessment submission for HMRC compliance.",
                "input_schema": {
                    "nino": str,
                    "tax_year": str,
                    "employment_income": str,
                    "self_employment_net_profit": str,
                    "property_net_income": str,
                    "pension_contributions": str,
                    "total_gains": str,
                },
            },
            {
                "name": "submit_self_assessment",
                "description": "Submit a Self Assessment to HMRC MTD for ITSA. WARNING: irreversible action.",
                "input_schema": {
                    "nino": str,
                    "tax_year": str,
                    "return_data_json": str,
                },
            },
            {
                "name": "get_self_assessment",
                "description": "Retrieve a previously submitted Self Assessment from HMRC.",
                "input_schema": {"nino": str, "tax_year": str},
            },
        ]
