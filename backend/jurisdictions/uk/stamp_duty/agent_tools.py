"""UK SDLT Agent Tool Set"""

from __future__ import annotations

import json
from typing import Optional
from decimal import Decimal
from datetime import date

from backend.models.agent_tools import AgentToolSet
from backend.models.tax_data import (
    TaxData, TaxpayerInfo, FiscalPeriod, TaxType, LineItem, PeriodType,
)


def _tool_error(msg: str) -> dict:
    return {"content": [{"type": "text", "text": json.dumps({"success": False, "error": msg})}], "is_error": True}


def _tool_ok(data: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(data, indent=2)}]}


class UKSDLTAgentToolSet(AgentToolSet):
    """UK SDLT Agent 工具集"""

    country_code = "uk"
    tax_type = "stamp_duty"

    async def get_obligations(self, taxpayer_id: str, status_filter: str = "") -> dict:
        return _tool_ok({
            "success": True,
            "obligations": [],
            "note": "SDLT is transaction-based; no periodic obligations",
        })

    async def calculate_return(self, line_items_json: str, period_info: Optional[dict] = None) -> dict:
        """计算 SDLT"""
        try:
            from .calculator import calculate_sdlt
            raw_items = json.loads(line_items_json)
            line_items = [
                LineItem(category=li["category"], amount=Decimal(str(li["amount"])), currency="GBP")
                for li in raw_items
            ]
            data = TaxData(
                tax_type=TaxType.STAMP_DUTY,
                period=FiscalPeriod(
                    year=2024, period_type=PeriodType.ANNUAL,
                    period_key="SDLT-2024",
                    start_date=date(2024, 1, 1), end_date=date(2024, 12, 31),
                ),
                taxpayer=TaxpayerInfo(name="Buyer", tax_id="", tax_id_type="utr"),
                line_items=line_items,
                metadata=period_info or {},
            )
            calc = calculate_sdlt(data)
            box_map = {b.category: float(b.amount) for b in calc.breakdown}
            return _tool_ok({
                "success": True,
                "property_value": box_map.get("property_value", 0),
                "sdlt_payable": box_map.get("sdlt_payable", 0),
                "effective_rate": box_map.get("effective_rate", 0),
            })
        except Exception as e:
            return _tool_error(str(e))

    async def validate_return(self, return_data: dict) -> dict:
        errors = []
        if not return_data.get("property_value"):
            errors.append({"field": "property_value", "message": "Property value required"})
        return _tool_ok({"success": True, "is_valid": len(errors) == 0, "errors": errors, "warnings": []})

    async def submit_return(self, taxpayer_id: str, period_key: str, return_data: dict) -> dict:
        return _tool_ok({
            "success": True,
            "submission_id": f"SDLT-{period_key}",
            "message": "SDLT return submitted (simulated)",
        })

    async def get_return(self, taxpayer_id: str, period_key: str) -> dict:
        return _tool_ok({"success": True, "transaction_id": period_key, "message": "SDLT data (simulated)"})

    async def analyze_business_data(self, company_data_json: str) -> dict:
        return _tool_error("SDLT is transaction-based; not applicable to bulk business data analysis.")

    def get_tool_metadata(self) -> list[dict]:
        return [
            {
                "name": "calculate_sdlt",
                "description": "Calculate UK Stamp Duty Land Tax (SDLT) for a property transaction with tiered rates (0%/5%/10%/12% residential, with first-time buyer relief and additional dwellings surcharge).",
                "input_schema": {"line_items_json": str, "period_info": dict},
            },
            {
                "name": "validate_sdlt",
                "description": "Validate an SDLT submission.",
                "input_schema": {"property_value": str, "property_type": str, "buyer_type": str},
            },
            {
                "name": "submit_sdlt",
                "description": "Submit an SDLT return to HMRC.",
                "input_schema": {"transaction_id": str, "period_key": str, "return_data_json": str},
            },
            {
                "name": "get_sdlt",
                "description": "Retrieve a previously submitted SDLT return.",
                "input_schema": {"transaction_id": str, "period_key": str},
            },
        ]
