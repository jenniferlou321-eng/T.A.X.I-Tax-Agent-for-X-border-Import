"""UK PAYE (RTI) Agent Tool Set"""

from __future__ import annotations

import json
from typing import Optional
from decimal import Decimal
from datetime import date

from tax_agent.models.agent_tools import AgentToolSet
from tax_agent.models.tax_data import (
    TaxData, TaxpayerInfo, FiscalPeriod, TaxType, LineItem, PeriodType,
)


def _tool_error(msg: str) -> dict:
    return {"content": [{"type": "text", "text": json.dumps({"success": False, "error": msg})}], "is_error": True}


def _tool_ok(data: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(data, indent=2)}]}


class UKPAYEAgentToolSet(AgentToolSet):
    """UK PAYE Agent 工具集 — HMRC RTI API"""

    country_code = "uk"
    tax_type = "paye"

    async def get_obligations(self, taxpayer_id: str, status_filter: str = "") -> dict:
        """查询 PAYE 提交历史"""
        return _tool_ok({
            "success": True,
            "obligations": [
                {"period_key": "2024-04", "start": "2024-04-06", "end": "2024-05-05",
                 "due": "2024-05-19", "status": "F", "type": "FPS"},
                {"period_key": "2024-03", "start": "2024-03-06", "end": "2024-04-05",
                 "due": "2024-04-19", "status": "F", "type": "FPS"},
            ],
        })

    async def calculate_return(self, line_items_json: str, period_info: Optional[dict] = None) -> dict:
        """计算 PAYE"""
        try:
            from .calculator import calculate_paye
            raw_items = json.loads(line_items_json)
            line_items = [
                LineItem(category=li["category"], amount=Decimal(str(li["amount"])), currency="GBP")
                for li in raw_items
            ]
            data = TaxData(
                tax_type=TaxType.PAYE,
                period=FiscalPeriod(
                    year=2024, period_type=PeriodType.MONTHLY,
                    period_key="2024-04", start_date=date(2024, 4, 6), end_date=date(2024, 5, 5),
                ),
                taxpayer=TaxpayerInfo(name="Employer", tax_id=period_info.get("empref", "") if period_info else "", tax_id_type="empref"),
                line_items=line_items,
            )
            calc = calculate_paye(data)
            box_map = {b.category: float(b.amount) for b in calc.breakdown}
            return _tool_ok({
                "success": True,
                "total_payable": box_map.get("net_payable_to_hmrc", 0),
                "employment_allowance_applied": box_map.get("employment_allowance_applied", 0),
            })
        except Exception as e:
            return _tool_error(str(e))

    async def validate_return(self, return_data: dict) -> dict:
        """校验 PAYE 数据"""
        errors = []
        if not return_data.get("empref"):
            errors.append({"field": "empref", "message": "Employer PAYE reference required"})
        if not return_data.get("payment_date"):
            errors.append({"field": "payment_date", "message": "Payment date required"})
        return _tool_ok({
            "success": True,
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": [],
        })

    async def submit_return(self, taxpayer_id: str, period_key: str, return_data: dict) -> dict:
        """提交 FPS/EPS"""
        return _tool_ok({
            "success": True,
            "submission_id": f"FPS-{taxpayer_id}-{period_key}-001",
            "transaction_id": f"TX-{period_key}-{taxpayer_id[:6]}",
            "message": "FPS submitted to HMRC (simulated)",
        })

    async def get_return(self, taxpayer_id: str, period_key: str) -> dict:
        """查询已提交的 FPS"""
        return _tool_ok({
            "success": True,
            "empref": taxpayer_id,
            "period_key": period_key,
            "message": "FPS data (simulated)",
        })

    async def analyze_business_data(self, company_data_json: str) -> dict:
        return _tool_error("Use FPS to submit per-payroll; use CT or VAT for company-level analysis.")

    def get_tool_metadata(self) -> list[dict]:
        return [
            {
                "name": "get_paye_obligations",
                "description": "Query HMRC for PAYE filing history.",
                "input_schema": {"empref": str},
            },
            {
                "name": "calculate_paye",
                "description": "Calculate total PAYE/NIC payable to HMRC for a period.",
                "input_schema": {"line_items_json": str, "period_info": dict},
            },
            {
                "name": "validate_paye",
                "description": "Validate a PAYE FPS/EPS submission.",
                "input_schema": {"empref": str, "payment_date": str, "total_paye_income": str},
            },
            {
                "name": "submit_paye",
                "description": "Submit a PAYE FPS (Full Payment Submission) to HMRC.",
                "input_schema": {"empref": str, "period_key": str, "return_data_json": str},
            },
            {
                "name": "get_paye",
                "description": "Retrieve a previously submitted FPS/EPS.",
                "input_schema": {"empref": str, "period_key": str},
            },
        ]
