"""Testland VAT Agent Tool Set — 示例实现

演示新增国家时 AgentToolSet 的最小实现。
"""

from __future__ import annotations

import json

from tax_agent.models.agent_tools import AgentToolSet


def _tool_error(msg: str) -> dict:
    return {"content": [{"type": "text", "text": json.dumps({"success": False, "error": msg})}], "is_error": True}


def _tool_ok(data: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(data, indent=2)}]}


class TestlandVATAgentToolSet(AgentToolSet):
    """Testland VAT Agent 工具集 — 示例实现"""

    country_code = "testland"
    tax_type = "vat"

    async def get_obligations(self, taxpayer_id: str, status_filter: str = "") -> dict:
        return _tool_ok({
            "success": True,
            "obligations": [
                {
                    "period_key": "2026-Q1",
                    "start": "2026-01-01",
                    "end": "2026-03-31",
                    "due": "2026-04-30",
                    "status": "O",
                },
            ],
        })

    async def calculate_return(self, line_items_json: str, period_info=None) -> dict:
        try:
            items = json.loads(line_items_json)
            total_sales = sum(float(i.get("amount", 0)) for i in items if i.get("category") == "total_sales")
            total_purchases = sum(float(i.get("amount", 0)) for i in items if i.get("category") == "total_purchases")
            vat_rate = 0.15
            vat_due = round(total_sales * vat_rate, 2)
            vat_reclaimed = round(total_purchases * vat_rate, 2)
            net_vat = round(abs(vat_due - vat_reclaimed), 2)
            return _tool_ok({
                "success": True,
                "vat_due": vat_due,
                "vat_reclaimed": vat_reclaimed,
                "net_vat": net_vat,
                "vat_rate": f"{vat_rate * 100:.0f}%",
                "note": "Testland uses a flat 15% VAT rate",
            })
        except Exception as e:
            return _tool_error(str(e))

    async def validate_return(self, return_data: dict) -> dict:
        errors = []
        for key in ["vat_due", "vat_reclaimed", "net_vat"]:
            val = return_data.get(key)
            if val is None:
                errors.append({"field": key, "message": f"{key} is required"})
            elif float(val) < 0:
                errors.append({"field": key, "message": f"{key} must be non-negative"})
        return _tool_ok({
            "success": True,
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": [],
        })

    async def submit_return(self, taxpayer_id: str, period_key: str, return_data: dict) -> dict:
        return _tool_ok({
            "success": True,
            "receipt_id": f"TESTLAND-{period_key}-{taxpayer_id}",
            "message": "This is a simulated submission for Testland (demo only)",
        })

    async def get_return(self, taxpayer_id: str, period_key: str) -> dict:
        return _tool_ok({
            "success": True,
            "period_key": period_key,
            "taxpayer_id": taxpayer_id,
            "message": "Simulated return data for Testland",
        })

    async def analyze_business_data(self, company_data_json: str) -> dict:
        return _tool_error("Raw business data analysis not yet implemented for Testland")

    def get_tool_metadata(self) -> list[dict]:
        return [
            {
                "name": "get_vat_obligations",
                "description": "Query Testland for VAT filing obligations.",
                "input_schema": {"taxpayer_id": str, "status_filter": str},
            },
            {
                "name": "calculate_vat_return",
                "description": "Calculate Testland VAT Return (flat 15% rate).",
                "input_schema": {"line_items_json": str},
            },
            {
                "name": "validate_vat_return",
                "description": "Validate a VAT Return calculation.",
                "input_schema": {
                    "vat_due": str,
                    "vat_reclaimed": str,
                    "net_vat": str,
                },
            },
            {
                "name": "submit_vat_return",
                "description": "Submit a VAT Return to Testland Tax Authority. WARNING: irreversible action.",
                "input_schema": {
                    "taxpayer_id": str,
                    "period_key": str,
                    "vat_due": str,
                    "vat_reclaimed": str,
                    "net_vat": str,
                },
            },
            {
                "name": "get_vat_return",
                "description": "Retrieve a previously submitted VAT Return from Testland.",
                "input_schema": {"taxpayer_id": str, "period_key": str},
            },
        ]
