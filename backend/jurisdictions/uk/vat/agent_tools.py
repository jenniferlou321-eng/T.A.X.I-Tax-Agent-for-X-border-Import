"""UK VAT Agent Tool Set — 实现 AgentToolSet 接口的 HMRC MTD for VAT 工具

所有工具逻辑从 agent/tools.py 迁移至此，实现与 Agent 层的解耦。
新增国家只需实现对应的 AgentToolSet 子类。
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Optional

from backend.models.agent_tools import AgentToolSet
from backend.models.tax_data import TaxData, TaxpayerInfo, FiscalPeriod, TaxType, LineItem, PeriodType
from backend.channels.oauth import OAuth2Manager
from backend.channels.fraud_headers import FraudPreventionHeaders
from backend.agent.business_analyzer import analyze_business_data as _analyze_business_data

from .hmrc_service import HMRCVATService
from .calculator import calculate_uk_vat
from .validator import validate_uk_vat
from ..config import hmrc_config


# ── Helper: Build HMRC service ──

def _build_hmrc_service(vrn: str) -> HMRCVATService:
    """Create an HMRC VAT service instance for the given VRN."""
    oauth = OAuth2Manager(
        client_id=hmrc_config.vat_oauth.client_id,
        client_secret=hmrc_config.vat_oauth.client_secret,
        authorize_url=hmrc_config.vat_oauth.authorize_url,
        token_url=hmrc_config.vat_oauth.token_url,
        scope=hmrc_config.vat_oauth.scope,
        redirect_uri=hmrc_config.vat_oauth.redirect_uri,
        token_store_path=f"./.tokens/{vrn}.json",
    )
    return HMRCVATService(
        base_url=hmrc_config.base_url,
        oauth=oauth,
        fraud_headers=FraudPreventionHeaders(),
    )


def _tool_error(msg: str, detail: str = "") -> dict:
    payload = {"success": False, "error": msg}
    if detail:
        payload["detail"] = detail
    return {"content": [{"type": "text", "text": json.dumps(payload)}], "is_error": True}


def _tool_ok(data: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(data, indent=2)}]}


# ── UK VAT Agent Tool Set ──

class UKVATAgentToolSet(AgentToolSet):
    """UK VAT Agent 工具集 — 对接 HMRC MTD for VAT API"""

    country_code = "uk"
    tax_type = "vat"

    # ── 查询类工具 ──

    async def get_obligations(self, taxpayer_id: str, status_filter: str = "") -> dict:
        """Query HMRC for VAT filing obligations."""
        vrn = taxpayer_id
        if not vrn:
            return _tool_error("VRN (taxpayer_id) is required")

        # 默认使用模拟模式（除非显式启用 HMRC_MODE=live）
        # 这样 Kimi/ANTHROPIC 凭证不会被误用为 HMRC 凭证
        import os
        hmrc_mode = os.environ.get("HMRC_MODE", "mock").lower()
        if hmrc_mode != "live":
            return _tool_ok({
                "success": True,
                "mode": "mock",
                "obligations": [
                    {
                        "period_key": "26A1",
                        "start": "2026-01-01",
                        "end": "2026-03-31",
                        "due": "2026-05-07",
                        "status": "O",
                    },
                    {
                        "period_key": "25A4",
                        "start": "2025-10-01",
                        "end": "2025-12-31",
                        "due": "2026-02-07",
                        "status": "F",
                        "received": "2026-01-25T10:00:00Z",
                    },
                ],
            })

        try:
            service = _build_hmrc_service(vrn)
            obligations = await service.get_obligations(
                vrn=vrn,
                status=status_filter or None,
            )
            result = [
                {
                    "period_key": ob.period_key,
                    "start": ob.start.isoformat(),
                    "end": ob.end.isoformat(),
                    "due": ob.due.isoformat(),
                    "status": ob.status,
                    "received": ob.received.isoformat() if ob.received else None,
                }
                for ob in obligations
            ]
            return _tool_ok({"success": True, "obligations": result})
        except PermissionError as e:
            return _tool_error("HMRC authentication required", str(e))
        except Exception as e:
            return _tool_error(str(e))

    # ── 计算类工具 ──

    async def calculate_return(self, line_items_json: str, period_info: Optional[dict] = None) -> dict:
        """Calculate UK VAT Return 9-box values from line items."""
        try:
            raw_items = json.loads(line_items_json)
            if not isinstance(raw_items, list):
                return _tool_error("line_items_json must be a JSON array")

            line_items = [
                LineItem(
                    category=li["category"],
                    amount=Decimal(str(li["amount"])),
                    currency=li.get("currency", "GBP"),
                    sub_category=li.get("sub_category", ""),
                )
                for li in raw_items
            ]

            from datetime import date
            data = TaxData(
                tax_type=TaxType.VAT,
                period=FiscalPeriod(
                    year=date.today().year,
                    period_type=PeriodType.QUARTERLY,
                    period_key="AGENT_CALC",
                    start_date=date.today(),
                    end_date=date.today(),
                ),
                taxpayer=TaxpayerInfo(name="AgentCalc", tax_id="", tax_id_type="vrn"),
                line_items=line_items,
            )

            calc = calculate_uk_vat(data)
            box_map = {b.category: str(b.amount) for b in calc.breakdown}

            result = {
                "success": True,
                "box1_vat_due_sales": box_map.get("vat_due_sales", "0"),
                "box2_vat_due_acquisitions": box_map.get("vat_due_acquisitions", "0"),
                "box3_total_vat_due": box_map.get("total_vat_due", "0"),
                "box4_vat_reclaimed": box_map.get("vat_reclaimed_purchases", "0"),
                "box5_net_vat_due": box_map.get("net_vat_due", "0"),
                "warnings": calc.warnings,
            }
            return _tool_ok(result)
        except Exception as e:
            return _tool_error(str(e))

    async def validate_return(self, return_data: dict) -> dict:
        """Validate UK VAT Return 9-box values."""
        try:
            line_items = [
                LineItem(category="vat_due_sales", amount=Decimal(str(return_data.get("vat_due_sales", "0"))), currency="GBP"),
                LineItem(category="vat_due_acquisitions", amount=Decimal(str(return_data.get("vat_due_acquisitions", "0"))), currency="GBP"),
                LineItem(category="vat_reclaimed_purchases", amount=Decimal(str(return_data.get("vat_reclaimed_purchases", "0"))), currency="GBP"),
                LineItem(category="total_sales_ex_vat", amount=Decimal(str(return_data.get("total_sales_ex_vat", "0"))), currency="GBP"),
                LineItem(category="total_purchases_ex_vat", amount=Decimal(str(return_data.get("total_purchases_ex_vat", "0"))), currency="GBP"),
                LineItem(category="total_goods_supplied_eu", amount=Decimal(str(return_data.get("total_goods_supplied_eu", "0"))), currency="GBP"),
                LineItem(category="total_goods_acquired_eu", amount=Decimal(str(return_data.get("total_goods_acquired_eu", "0"))), currency="GBP"),
            ]
            from datetime import date
            data = TaxData(
                tax_type=TaxType.VAT,
                period=FiscalPeriod(
                    year=date.today().year,
                    period_type=PeriodType.QUARTERLY,
                    period_key="AGENT_VAL",
                    start_date=date.today(),
                    end_date=date.today(),
                ),
                taxpayer=TaxpayerInfo(name="AgentVal", tax_id="", tax_id_type="vrn"),
                line_items=line_items,
            )
            report = validate_uk_vat(data)
            result = {
                "success": True,
                "is_valid": report.is_valid,
                "errors": [{"field": e.field, "message": e.message} for e in report.errors],
                "warnings": [{"field": w.field, "message": w.message} for w in report.warnings],
            }
            return _tool_ok(result)
        except Exception as e:
            return _tool_error(str(e))

    # ── ERP 集成 MCP tools (v0 新加) ──

    async def ingest_erp_data(
        self,
        source: str,
        case_id: Optional[str] = None,
        csv_base64: Optional[str] = None,
        profile: Optional[str] = None,
    ) -> dict:
        """MCP tool: 加载 demo case 或解析 CSV base64。

        Returns: ImportResult (Pydantic dict) + 推荐 case 列表（如 case_id 不存在）。
        """
        from backend.erp.erp_samples_loader import (
            list_demo_cases,
            load_demo_case,
            DemoCaseNotFoundError,
        )
        from backend.erp.csv_parser import parse_csv, CsvParseError
        import base64

        try:
            if source == "demo":
                if not case_id:
                    return _tool_error(
                        "case_id is required for source='demo'",
                        detail={"available_cases": list_demo_cases()},
                    )
                try:
                    ir = load_demo_case(case_id)
                except DemoCaseNotFoundError as e:
                    return _tool_error(
                        str(e),
                        detail={"available_cases": list_demo_cases()},
                    )
            elif source == "csv":
                if not csv_base64:
                    return _tool_error("csv_base64 is required for source='csv'")
                csv_bytes = base64.b64decode(csv_base64)
                if len(csv_bytes) > 10 * 1024 * 1024:
                    return _tool_error("file exceeds 10MB limit")
                try:
                    ir = parse_csv(csv_bytes, profile=profile)
                except CsvParseError as e:
                    return _tool_error(f"CSV parse error: {e}")
            elif source == "erpnext":
                from backend.services.erpnext_buffer import get_import_result
                ir = get_import_result()
                if ir is None:
                    return _tool_error(
                        "no ERPNext data received yet",
                        detail={
                            "hint": "submit a Sales/Purchase Invoice in ERPNext "
                                    "to push data here",
                        },
                    )
            else:
                return _tool_error(f"unknown source: {source!r}")
        except Exception as e:
            return _tool_error(f"unexpected error: {e}")

        ir_dict = ir.model_dump(mode="json")

        # 工具链互操作: ImportResult Pydantic 模型没有 `company` / `metadata`
        # 字段（erp_models.py:55），但业务分析器
        # (business_analyzer.analyze_business_data) 期望 top-level `company`。
        # 把 metadata 子树平铺到顶层，避免 agent 端"再调一次 analyze 时手动塞
        # company"的脆弱模式。
        metadata = ir_dict.pop("metadata", None) or {}
        for k, v in metadata.items():
            # 不覆盖已有字段（防御性）
            ir_dict.setdefault(k, v)

        return _tool_ok({
            "success": True,
            "import_result": ir_dict,
            "summary": {
                "source_profile": ir.source_profile,
                "source_hash": ir.source_hash,
                "sales_count": len(ir.sales),
                "purchases_count": len(ir.purchases),
                "warnings_count": len(ir.warnings),
                "rejected_count": len(ir.rejected_rows),
            },
        })

    async def filter_invoices(
        self,
        txn_type: Optional[str] = None,  # "sale" | "purchase" | None
        flagged_only: bool = False,  # 只返有差异的发票（v0 暂未实现，用 reserved）
        invoice_ids: Optional[list[str]] = None,  # 限制到这些 ID
    ) -> dict:
        """MCP tool: 列出当前 session 里的发票（用 session.uploaded_data 缓存）。

        v0 简化：从 import_result 缓存读，不查 DB。
        """
        # v0 暂不接入 session 缓存 → 返空 + 提示
        return _tool_ok({
            "success": True,
            "invoices": [],
            "note": "v0: InvoiceMultiSelectPanel loads from /api/erp/cases/{case_id} directly, not via this tool",
        })

    # ── 提交类工具 ──

    async def submit_return(self, taxpayer_id: str, period_key: str, return_data: dict) -> dict:
        """Submit a UK VAT Return to HMRC."""
        vrn = taxpayer_id
        if not vrn or not period_key:
            return _tool_error("VRN and period_key are required")

        # 默认使用模拟模式 (与 get_obligations 对齐)。这样 Kimi/ANTHROPIC
        # 凭证不会被误用为 HMRC 凭证, 演示时也不需要真 OAuth token。
        import os
        hmrc_mode = os.environ.get("HMRC_MODE", "mock").lower()
        if hmrc_mode != "live":
            # mock 模式: 不调真 HMRC, 返回一个伪 receipt
            return _tool_ok({
                "success": True,
                "mode": "mock",
                "processing_date": "2026-04-07",
                "form_bundle_number": f"MOCK-{period_key}-{vrn[:4]}",
                "payment_indicator": "BANK",
                "charge_ref_number": f"CHG-MOCK-{period_key}",
                "submitted_body": {
                    "periodKey": period_key,
                    "vatDueSales": round(float(return_data.get("vat_due_sales", 0)), 2),
                    "totalVatDue": round(float(return_data.get("total_vat_due", 0)), 2),
                    "netVatDue": round(float(return_data.get("net_vat_due", 0)), 2),
                },
                "warning": "Mock mode: this was NOT actually submitted to HMRC. Set HMRC_MODE=live to file a real return.",
            })

        try:
            body = {
                "periodKey": period_key,
                "vatDueSales": round(float(return_data.get("vat_due_sales", 0)), 2),
                "vatDueAcquisitions": round(float(return_data.get("vat_due_acquisitions", 0)), 2),
                "totalVatDue": round(float(return_data.get("total_vat_due", 0)), 2),
                "vatReclaimedCurrPeriod": round(float(return_data.get("vat_reclaimed_purchases", 0)), 2),
                "netVatDue": round(float(return_data.get("net_vat_due", 0)), 2),
                "totalValueSalesExVAT": int(float(return_data.get("total_sales_ex_vat", 0))),
                "totalValuePurchasesExVAT": int(float(return_data.get("total_purchases_ex_vat", 0))),
                "totalValueGoodsSuppliedExVAT": int(float(return_data.get("total_goods_supplied_eu", 0))),
                "totalAcquisitionsExVAT": int(float(return_data.get("total_goods_acquired_eu", 0))),
                "finalised": True,
            }

            service = _build_hmrc_service(vrn)
            receipt = await service.submit_return(vrn=vrn, body=body)
            result = {
                "success": True,
                "mode": "live",
                "processing_date": receipt.get("processingDate"),
                "form_bundle_number": receipt.get("formBundleNumber"),
                "payment_indicator": receipt.get("paymentIndicator"),
                "charge_ref_number": receipt.get("chargeRefNumber"),
            }
            return _tool_ok(result)
        except PermissionError as e:
            return _tool_error("HMRC authentication required", str(e))
        except Exception as e:
            return _tool_error(str(e))

    async def get_return(self, taxpayer_id: str, period_key: str) -> dict:
        """Retrieve a previously submitted UK VAT Return."""
        vrn = taxpayer_id
        if not vrn or not period_key:
            return _tool_error("VRN and period_key are required")

        # mock 短路 (与 submit_return / get_obligations 对齐)
        import os
        hmrc_mode = os.environ.get("HMRC_MODE", "mock").lower()
        if hmrc_mode != "live":
            return _tool_ok({
                "success": True,
                "mode": "mock",
                "period_key": period_key,
                "vat_due_sales": "0.00",
                "vat_due_acquisitions": "0.00",
                "total_vat_due": "0.00",
                "vat_reclaimed": "0.00",
                "net_vat_due": "0.00",
                "total_sales_ex_vat": 0,
                "total_purchases_ex_vat": 0,
                "received": None,
                "warning": "Mock mode: no real return on file with HMRC.",
            })

        try:
            service = _build_hmrc_service(vrn)
            ret = await service.get_return(vrn=vrn, period_key=period_key)
            result = {
                "success": True,
                "period_key": ret.period_key,
                "vat_due_sales": str(ret.vat_due_sales),
                "vat_due_acquisitions": str(ret.vat_due_acquisitions),
                "total_vat_due": str(ret.total_vat_due),
                "vat_reclaimed": str(ret.vat_reclaimed_curr_period),
                "net_vat_due": str(ret.net_vat_due),
                "total_sales_ex_vat": ret.total_value_sales_ex_vat,
                "total_purchases_ex_vat": ret.total_value_purchases_ex_vat,
                "received": ret.received,
            }
            return _tool_ok(result)
        except PermissionError as e:
            return _tool_error("HMRC authentication required", str(e))
        except Exception as e:
            return _tool_error(str(e))

    # ── 数据分析工具 ──

    async def analyze_business_data(self, company_data_json: str) -> dict:
        """Analyze raw business data and calculate UK VAT Return."""
        if not company_data_json:
            return _tool_error("company_data_json is required")

        try:
            result = _analyze_business_data(company_data_json)
            if not result.get("success"):
                return _tool_error(result.get("error", "Analysis failed"))
            return _tool_ok(result)
        except Exception as e:
            return _tool_error(f"Analysis error: {str(e)}")

    # ── 工具元数据 ──

    def get_tool_metadata(self) -> list[dict]:
        """返回 8 个 UK VAT 工具的元数据 (JSON Schema 完整版)。

        input_schema 全部是 JSON Schema dict (不是 Python type), 让 LLM 看到
        字段 description + 嵌套对象结构。

        关键设计 (2026-06 修复):
        - validate_vat_return / submit_vat_return 的 9-Box 字段包成
          return_data 子对象 (而不是平面展开), 跟 _make_tool_wrapper 的
          takes_dict 检测对齐, 避免 **mapped 展开时 TypeError。
        - 输入顶层只放"非 9-Box 字段" (taxpayer_id, period_key 等) + return_data 子对象。
        """
        return [
            {
                "name": "get_vat_obligations",
                "description": (
                    "Query HMRC for VAT filing obligations for a given VRN. "
                    "Returns open (status='O') and fulfilled (status='F') periods."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "taxpayer_id": {
                            "type": "string",
                            "description": (
                                "VRN (VAT Registration Number), 9 digits, e.g. '123456789'. "
                                "Alternative name 'vrn' is also accepted and mapped to taxpayer_id."
                            ),
                        },
                        "status_filter": {
                            "type": "string",
                            "enum": ["", "O", "F"],
                            "description": (
                                "Filter by status: '' = all, 'O' = Open, 'F' = Fulfilled. "
                                "Default '' returns both."
                            ),
                        },
                    },
                    "required": ["taxpayer_id"],
                },
            },
            {
                "name": "calculate_vat_return",
                "description": (
                    "Calculate UK VAT Return 9-box values from pre-aggregated line items. "
                    "Use this when you already have category-level totals. For raw invoice data, "
                    "use `analyze_business_data` first."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "line_items_json": {
                            "type": "string",
                            "description": (
                                "JSON array of line items, e.g. "
                                "'[{\"category\":\"vat_due_sales\",\"amount\":2500.00,\"currency\":\"GBP\"}]'. "
                                "Each item: category (one of vat_due_sales, vat_due_acquisitions, "
                                "vat_reclaimed_purchases, total_sales_ex_vat, total_purchases_ex_vat, "
                                "total_goods_supplied_eu, total_goods_acquired_eu), "
                                "amount (number, GBP), currency (default 'GBP')."
                            ),
                        },
                    },
                    "required": ["line_items_json"],
                },
            },
            {
                "name": "validate_vat_return",
                "description": (
                    "Validate a UK VAT Return 9-Box calculation for HMRC compliance. "
                    "Checks Box 5 >= 0, Box 1 <= 9.99M (annual scheme cap), period_key format, "
                    "and other HMRC rules. Pass the 9-Box values as a `return_data` sub-object."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "return_data": {
                            "type": "object",
                            "description": "9-Box VAT return values in HMRC field-name format",
                            "properties": {
                                "vat_due_sales": {"type": "string", "description": "Box 1: VAT due on sales, e.g. '2500.00'"},
                                "vat_due_acquisitions": {"type": "string", "description": "Box 2: VAT due on EU acquisitions, e.g. '0.00'"},
                                "vat_reclaimed_purchases": {"type": "string", "description": "Box 4: VAT reclaimed on purchases, e.g. '1200.00'"},
                                "total_sales_ex_vat": {"type": "string", "description": "Box 6: Total sales ex VAT (integer pounds), e.g. '12500'"},
                                "total_purchases_ex_vat": {"type": "string", "description": "Box 7: Total purchases ex VAT (integer pounds), e.g. '6000'"},
                                "total_goods_supplied_eu": {"type": "string", "description": "Box 8: Goods supplied to EU (integer pounds), e.g. '0'"},
                                "total_goods_acquired_eu": {"type": "string", "description": "Box 9: Goods acquired from EU (integer pounds), e.g. '0'"},
                            },
                            "required": [
                                "vat_due_sales", "vat_due_acquisitions",
                                "vat_reclaimed_purchases", "total_sales_ex_vat",
                                "total_purchases_ex_vat", "total_goods_supplied_eu",
                                "total_goods_acquired_eu",
                            ],
                        },
                    },
                    "required": ["return_data"],
                },
            },
            {
                "name": "submit_vat_return",
                "description": (
                    "Submit a UK VAT Return to HMRC. **IRREVERSIBLE ACTION** - "
                    "only call after explicit user confirmation. The 9-Box values go in "
                    "the `return_data` sub-object; `taxpayer_id` and `period_key` are top-level."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "taxpayer_id": {
                            "type": "string",
                            "description": "VRN, 9 digits, e.g. '123456789'. ('vrn' also accepted.)",
                        },
                        "period_key": {
                            "type": "string",
                            "description": (
                                "HMRC period identifier, e.g. '26A1' = 2026 Q1 (Jan-Mar). "
                                "Format: <2-digit-year><A-M> where A=Jan/Feb Q1, B=May/Jun Q2, etc."
                            ),
                        },
                        "return_data": {
                            "type": "object",
                            "description": "9-Box values in HMRC field-name format (same shape as validate_vat_return).",
                            "properties": {
                                "vat_due_sales": {"type": "string", "description": "Box 1"},
                                "vat_due_acquisitions": {"type": "string", "description": "Box 2"},
                                "total_vat_due": {"type": "string", "description": "Box 3 (= Box 1 + Box 2)"},
                                "vat_reclaimed_purchases": {"type": "string", "description": "Box 4"},
                                "net_vat_due": {"type": "string", "description": "Box 5 (= |Box 3 - Box 4|)"},
                                "total_sales_ex_vat": {"type": "string", "description": "Box 6 (integer pounds)"},
                                "total_purchases_ex_vat": {"type": "string", "description": "Box 7 (integer pounds)"},
                                "total_goods_supplied_eu": {"type": "string", "description": "Box 8 (integer pounds)"},
                                "total_goods_acquired_eu": {"type": "string", "description": "Box 9 (integer pounds)"},
                            },
                            "required": [
                                "vat_due_sales", "vat_due_acquisitions", "total_vat_due",
                                "vat_reclaimed_purchases", "net_vat_due",
                                "total_sales_ex_vat", "total_purchases_ex_vat",
                                "total_goods_supplied_eu", "total_goods_acquired_eu",
                            ],
                        },
                    },
                    "required": ["taxpayer_id", "period_key", "return_data"],
                },
            },
            {
                "name": "get_vat_return",
                "description": "Retrieve a previously submitted UK VAT Return from HMRC.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "taxpayer_id": {
                            "type": "string",
                            "description": "VRN, 9 digits, e.g. '123456789'.",
                        },
                        "period_key": {
                            "type": "string",
                            "description": "HMRC period identifier, e.g. '26A1'.",
                        },
                    },
                    "required": ["taxpayer_id", "period_key"],
                },
            },
            {
                "name": "analyze_business_data",
                "description": (
                    "Analyze raw business invoice data and calculate UK VAT Return 9-Box "
                    "values with regulatory compliance notes. Returns `nine_box` in HMRC "
                    "field-name format (vat_due_sales, total_sales_ex_vat, etc.) - pass "
                    "this directly to `validate_vat_return` / `submit_vat_return` as the "
                    "`return_data` argument. Also returns `nine_box_legacy` (box1_xxx style) "
                    "for one release as backwards compatibility."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "company_data_json": {
                            "type": "string",
                            "description": (
                                "JSON string of company data. Accepts both styles:\n"
                                "- raw style: { company, sales_invoices, purchase_invoices, ... }\n"
                                "- ImportResult style: output of `ingest_erp_data` "
                                "(with sales, purchases, erp_provided_boxes, optional metadata.company)\n"
                                "The `analyze_business_data` tool handles field-name translation internally."
                            ),
                        },
                    },
                    "required": ["company_data_json"],
                },
            },
            {
                "name": "ingest_erp_data",
                "description": (
                    "Load raw ERP data: either a built-in demo case (source='demo', case_id='...') "
                    "or a user-supplied CSV (source='csv', csv_base64='...'). Returns an "
                    "ImportResult (sales, purchases, erp_provided_boxes, metadata) that you can "
                    "serialize and pass to `analyze_business_data` as `company_data_json`. "
                    "If case_id is unknown, call with case_id omitted to get the available_cases list."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "enum": ["demo", "csv"],
                            "description": "'demo' = built-in case; 'csv' = user-supplied CSV (base64).",
                        },
                        "case_id": {
                            "type": "string",
                            "description": "demo case ID, e.g. 'case-a-uk-subsidiary', 'case-x-uk-standard', 'case-b-cn-parent'. Omit to list available cases.",
                        },
                        "csv_base64": {
                            "type": "string",
                            "description": "base64-encoded CSV bytes (max 10MB). Required when source='csv'.",
                        },
                        "profile": {
                            "type": "string",
                            "description": "Force CSV profile, e.g. 'generic'. Auto-detected by default.",
                        },
                    },
                    "required": ["source"],
                },
            },
            {
                "name": "filter_invoices",
                "description": (
                    "Filter / list invoices from the current session's ImportResult. "
                    "**v0 STUB**: returns an empty list and a note pointing to "
                    "POST /api/erp/cases/{case_id} for direct inspection. Do not rely on this tool."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "txn_type": {
                            "type": "string",
                            "enum": ["sale", "purchase"],
                            "description": "Filter by transaction type.",
                        },
                        "flagged_only": {
                            "type": "boolean",
                            "description": "Only return invoices flagged for review (v0: not implemented).",
                        },
                        "invoice_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Limit to specific invoice IDs (v0: not implemented).",
                        },
                    },
                },
            },
        ]
