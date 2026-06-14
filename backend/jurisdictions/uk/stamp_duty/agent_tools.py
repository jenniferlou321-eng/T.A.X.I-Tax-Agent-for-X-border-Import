"""UK SDLT Agent Tool Set — HMRC GovTalk XML 实现"""

from __future__ import annotations

import json
from typing import Optional
from decimal import Decimal
from datetime import date

from backend.models.agent_tools import AgentToolSet
from backend.models.tax_data import (
    TaxData, TaxpayerInfo, FiscalPeriod, TaxType, LineItem, PeriodType,
)

from .._hmrc_base import hmrc_mode, tool_error, tool_ok
from .hmrc_service import HMRCSDLTService


class UKSDLTAgentToolSet(AgentToolSet):
    """UK SDLT Agent 工具集 — GovTalk XML 提交"""

    country_code = "uk"
    tax_type = "stamp_duty"

    async def get_obligations(self, taxpayer_id: str, status_filter: str = "") -> dict:
        """SDLT 是基于交易的税种,没有周期性申报义务。"""
        return tool_ok({
            "success": True,
            "obligations": [],
            "note": "SDLT is transaction-based; no periodic obligations. Each property transaction requires a separate SDLT return.",
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
            return tool_ok({
                "success": True,
                "property_value": box_map.get("property_value", 0),
                "sdlt_payable": box_map.get("sdlt_payable", 0),
                "effective_rate": box_map.get("effective_rate", 0),
            })
        except Exception as e:
            return tool_error(str(e))

    async def validate_return(self, return_data: dict) -> dict:
        """校验 SDLT 数据"""
        errors = []
        if not return_data.get("property_value"):
            errors.append({"field": "property_value", "message": "Property value required"})
        return tool_ok({"success": True, "is_valid": len(errors) == 0, "errors": errors, "warnings": []})

    async def submit_return(self, taxpayer_id: str, period_key: str, return_data: dict) -> dict:
        """提交 SDLT Return 至 HMRC via GovTalk XML"""
        utr = taxpayer_id
        if not utr:
            return tool_error("UTR (SDLT Unique Transaction Reference) is required")

        if hmrc_mode() != "live":
            return tool_ok({
                "success": True,
                "mode": "mock",
                "submission_id": f"SDLT-{utr}-{period_key}-001",
                "processing_date": "2026-06-14T10:00:00Z",
                "form_bundle_number": f"MOCK-SDLT-{period_key}",
                "message": "SDLT return submitted (mock mode — not filed with HMRC). Set HMRC_MODE=live to file a real return.",
            })

        try:
            service = HMRCSDLTService()
            receipt = await service.submit_return(
                utr=utr,
                body=return_data,
                effective_date=return_data.get("effective_date", ""),
            )
            return tool_ok({
                "success": True,
                "mode": "live",
                "submission_id": receipt.get("submissionId", ""),
                "processing_date": receipt.get("processingDate", ""),
                "form_bundle_number": receipt.get("formBundleNumber", ""),
                "correlation_id": receipt.get("correlationId", ""),
            })
        except PermissionError as e:
            return tool_error("HMRC authentication required", str(e))
        except Exception as e:
            return tool_error(str(e))

    async def get_return(self, taxpayer_id: str, period_key: str) -> dict:
        """查询已提交的 SDLT Return"""
        utr = taxpayer_id
        if not utr:
            return tool_error("UTR is required")

        if hmrc_mode() != "live":
            return tool_ok({
                "success": True,
                "mode": "mock",
                "utr": utr,
                "submission_id": period_key,
                "message": "SDLT return data (mock mode — no real return on file with HMRC).",
            })

        try:
            service = HMRCSDLTService()
            ret = await service.get_return(utr=utr, submission_id=period_key)
            return tool_ok({
                "success": True,
                "submission_id": ret.submission_id,
                "processing_date": ret.processing_date,
                "form_bundle_number": ret.form_bundle_number,
                "correlation_id": ret.correlation_id,
            })
        except PermissionError as e:
            return tool_error("HMRC authentication required", str(e))
        except Exception as e:
            return tool_error(str(e))

    async def analyze_business_data(self, company_data_json: str) -> dict:
        return tool_error("SDLT is transaction-based; not applicable to bulk business data analysis.")

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
                "description": "Submit an SDLT return to HMRC via GovTalk XML. WARNING: irreversible action.",
                "input_schema": {"utr": str, "period_key": str, "return_data_json": str},
            },
            {
                "name": "get_sdlt",
                "description": "Retrieve a previously submitted SDLT return from HMRC.",
                "input_schema": {"utr": str, "period_key": str},
            },
        ]
