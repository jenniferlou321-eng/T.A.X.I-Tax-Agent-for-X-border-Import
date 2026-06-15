"""UK PAYE (RTI) Agent Tool Set"""

from __future__ import annotations

import json
from typing import Optional
from decimal import Decimal
from datetime import date

from backend.models.agent_tools import AgentToolSet
from backend.models.tax_data import (
    TaxData, TaxpayerInfo, FiscalPeriod, TaxType, LineItem, PeriodType,
)
from backend.channels.oauth import OAuth2Manager
from backend.channels.fraud_headers import FraudPreventionHeaders

from ..config import hmrc_config
from .._hmrc_base import hmrc_mode, tool_error, tool_ok
from .hmrc_service import HMRCPAYEService


# ── Helper: Build HMRC service ──

def _build_hmrc_service(empref: str) -> HMRCPAYEService:
    """Create an HMRC PAYE service instance for the given EMPREF."""
    oauth = OAuth2Manager(
        client_id=hmrc_config.paye_oauth.client_id,
        client_secret=hmrc_config.paye_oauth.client_secret,
        authorize_url=hmrc_config.paye_oauth.authorize_url,
        token_url=hmrc_config.paye_oauth.token_url,
        scope=hmrc_config.paye_oauth.scope,
        redirect_uri=hmrc_config.paye_oauth.redirect_uri,
        token_store_path=f"./.tokens/{empref}.json",
    )
    return HMRCPAYEService(
        base_url=hmrc_config.base_url,
        oauth=oauth,
        fraud_headers=FraudPreventionHeaders(),
    )


class UKPAYEAgentToolSet(AgentToolSet):
    """UK PAYE Agent 工具集 — HMRC RTI API"""

    country_code = "uk"
    tax_type = "paye"

    async def get_obligations(self, taxpayer_id: str, status_filter: str = "") -> dict:
        """查询 PAYE 提交历史"""
        empref = taxpayer_id
        if not empref:
            return tool_error("EMPREF (taxpayer_id) is required")

        if hmrc_mode() != "live":
            return tool_ok({
                "success": True,
                "mode": "mock",
                "obligations": [
                    {"period_key": "2024-04", "start": "2024-04-06", "end": "2024-05-05",
                     "due": "2024-05-19", "status": "F", "type": "FPS"},
                    {"period_key": "2024-03", "start": "2024-03-06", "end": "2024-04-05",
                     "due": "2024-04-19", "status": "F", "type": "FPS"},
                ],
            })

        try:
            service = _build_hmrc_service(empref)
            obligations = await service.get_obligations(
                empref=empref,
                status=status_filter or None,
            )
            result = [
                {
                    "period_key": ob.period_key,
                    "start": ob.start.isoformat(),
                    "end": ob.end.isoformat(),
                    "due": ob.due.isoformat(),
                    "status": ob.status,
                    "type": ob.submission_type,
                    "received": ob.received.isoformat() if ob.received else None,
                }
                for ob in obligations
            ]
            return tool_ok({"success": True, "obligations": result})
        except PermissionError as e:
            return tool_error("HMRC authentication required", str(e))
        except Exception as e:
            return tool_error(str(e))

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
            return tool_ok({
                "success": True,
                "total_payable": box_map.get("net_payable_to_hmrc", 0),
                "employment_allowance_applied": box_map.get("employment_allowance_applied", 0),
            })
        except Exception as e:
            return tool_error(str(e))

    async def validate_return(self, return_data: dict) -> dict:
        """校验 PAYE 数据"""
        errors = []
        if not return_data.get("empref"):
            errors.append({"field": "empref", "message": "Employer PAYE reference required"})
        if not return_data.get("payment_date"):
            errors.append({"field": "payment_date", "message": "Payment date required"})
        return tool_ok({
            "success": True,
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": [],
        })

    async def submit_return(self, taxpayer_id: str, period_key: str, return_data: dict) -> dict:
        """提交 FPS（默认）或 EPS"""
        empref = taxpayer_id
        if not empref or not period_key:
            return tool_error("EMPREF and period_key are required")

        submission_type = return_data.get("submission_type", "fps") if return_data else "fps"

        if hmrc_mode() != "live":
            return tool_ok({
                "success": True,
                "mode": "mock",
                "submission_id": f"{submission_type.upper()}-{empref}-{period_key}-001",
                "transaction_id": f"TX-{period_key}-{empref[:6]}",
                "message": f"{submission_type.upper()} submitted to HMRC (mock mode — not filed with HMRC). Set HMRC_MODE=live to file a real return.",
            })

        try:
            service = _build_hmrc_service(empref)
            if submission_type == "eps":
                receipt = await service.submit_eps(empref=empref, body=return_data)
            else:
                receipt = await service.submit_fps(empref=empref, body=return_data)
            return tool_ok({
                "success": True,
                "mode": "live",
                "submission_id": receipt.get("submissionId", ""),
                "transaction_id": receipt.get("transactionId", ""),
                "processing_date": receipt.get("processingDate", ""),
                "submission_type": submission_type.upper(),
            })
        except PermissionError as e:
            return tool_error("HMRC authentication required", str(e))
        except Exception as e:
            return tool_error(str(e))

    async def get_return(self, taxpayer_id: str, period_key: str) -> dict:
        """查询已提交的 FPS"""
        empref = taxpayer_id
        if not empref or not period_key:
            return tool_error("EMPREF and period_key are required")

        if hmrc_mode() != "live":
            return tool_ok({
                "success": True,
                "mode": "mock",
                "empref": empref,
                "period_key": period_key,
                "message": "FPS data (mock mode — no real return on file with HMRC).",
            })

        try:
            service = _build_hmrc_service(empref)
            ret = await service.get_fps(empref=empref, submission_id=period_key)
            return tool_ok({
                "success": True,
                "submission_id": ret.submission_id,
                "transaction_id": ret.transaction_id,
                "processing_date": ret.processing_date,
                "submission_type": ret.submission_type,
            })
        except PermissionError as e:
            return tool_error("HMRC authentication required", str(e))
        except Exception as e:
            return tool_error(str(e))

    async def analyze_business_data(self, company_data_json: str) -> dict:
        return tool_error("Use FPS to submit per-payroll; use CT or VAT for company-level analysis.")

    # ── Apprenticeship Levy ──

    async def calculate_apprenticeship_levy(self, args: dict) -> dict:
        """计算 UK Apprenticeship Levy：0.5% × 薪资总额 - £15,000 年免税额

        Args:
            total_pay_bill: 薪资总额（GBP），必须来自实际工资交易聚合
            paye_verified_payroll: 从 PAYE 工资交易行（payroll line items）独立聚合的年工资总额，
                用于交叉核验 total_pay_bill 的来源。必须与 total_pay_bill 的口径一致（均为年值）。
            levy_allowance_claimed: 免税额（默认 £15,000 年）
            is_annual: True = 输入是年总额；False = 月值（默认）
        """
        try:
            from .calculator import calculate_apprenticeship_levy as _calc_levy

            total_pay_bill = Decimal(str(args.get("total_pay_bill", 0)))
            result = _calc_levy(
                total_pay_bill=total_pay_bill,
                levy_allowance_claimed=Decimal(str(args.get("levy_allowance_claimed", 15000))),
                is_annual=bool(args.get("is_annual", False)),
            )

            warnings = list(result.warnings)

            # 交叉核验：要求 agent 同时提供从 PAYE 行聚合的年薪基数
            paye_verified = args.get("paye_verified_payroll")
            if paye_verified is None:
                warnings.append(
                    "paye_verified_payroll was not provided. Cannot verify that total_pay_bill "
                    "matches actual payroll transactions. Supply the sum of gross wages from "
                    "PAYE payroll line items to enable cross-check."
                )
            else:
                paye_dec = Decimal(str(paye_verified))
                annual_bill = total_pay_bill if bool(args.get("is_annual", False)) else total_pay_bill * 12
                if paye_dec > Decimal("0"):
                    ratio = annual_bill / paye_dec
                    if ratio > Decimal("1.1") or ratio < Decimal("0.9"):
                        warnings.append(
                            f"MISMATCH: total_pay_bill (annualised £{annual_bill:,.0f}) differs from "
                            f"paye_verified_payroll (£{paye_dec:,.0f}) by more than 10%. "
                            f"Ensure total_pay_bill is derived from payroll transactions, not from a "
                            f"narrative or scenario figure."
                        )

            box_map = {b.category: float(b.amount) for b in result.breakdown}
            return tool_ok({
                "success": True,
                "total_pay_bill": box_map.get("total_pay_bill", 0),
                "levy_rate": box_map.get("levy_rate", 0.005),
                "gross_levy": box_map.get("gross_levy", 0),
                "levy_allowance": box_map.get("levy_allowance", 0),
                "apprenticeship_levy_payable": box_map.get("apprenticeship_levy_payable", 0),
                "warnings": warnings,
            })
        except Exception as e:
            return tool_error(str(e))

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
            {
                "name": "calculate_apprenticeship_levy",
                "description": (
                    "Calculate UK Apprenticeship Levy (0.5% of total pay bill, minus £15,000 annual allowance). "
                    "Applies to employers with annual pay bill > £3 million. Reported via EPS. "
                    "IMPORTANT: total_pay_bill must be the actual payroll figure derived from payroll "
                    "transactions (e.g. sum of gross wages paid to employees), NOT a scenario narrative "
                    "figure or an estimate. If the annual pay bill is below £3,000,000 the levy is zero "
                    "and a warning is returned. "
                    "You MUST also supply paye_verified_payroll (the sum of gross wages from PAYE payroll "
                    "line items, as an annual figure) so the tool can cross-check that total_pay_bill is "
                    "consistent with actual payroll transactions."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "total_pay_bill": {
                            "type": "string",
                            "description": "Total pay bill in GBP used for Levy calculation. Must come from actual payroll transactions.",
                        },
                        "paye_verified_payroll": {
                            "type": "string",
                            "description": "Annual gross payroll total independently summed from PAYE payroll line items. Used to cross-verify total_pay_bill.",
                        },
                        "levy_allowance_claimed": {
                            "type": "string",
                            "description": "Annual allowance (default £15,000).",
                        },
                        "is_annual": {
                            "type": "boolean",
                            "description": "True if total_pay_bill is an annual figure; False for monthly (default).",
                        },
                    },
                    "required": ["total_pay_bill", "paye_verified_payroll"],
                },
            },
        ]
