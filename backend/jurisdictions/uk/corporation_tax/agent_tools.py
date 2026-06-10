"""UK Corporation Tax Agent Tool Set — 增强版

包含的工具：
1. get_corporation_tax_obligations
2. calculate_corporation_tax (含边际减免、关联企业规则)
3. calculate_marginal_relief (单独)
4. calculate_capital_allowances (详细)
5. calculate_group_relief (集团减免)
6. calculate_loss_relief (损失减免)
7. calculate_rd_relief (R&D 减免)
8. validate_corporation_tax
9. submit_corporation_tax
10. get_corporation_tax
11. suggest_optimization (税务优化建议)
"""

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


class UKCTAgentToolSet(AgentToolSet):
    """UK Corporation Tax Agent 工具集（增强版）"""

    country_code = "uk"
    tax_type = "corporation_tax"

    # ── 查询 ──

    async def get_obligations(self, taxpayer_id: str, status_filter: str = "") -> dict:
        ctref = taxpayer_id
        if not ctref:
            return _tool_error("CTREF is required")
        return _tool_ok({
            "success": True,
            "obligations": [
                {
                    "period_key": "FY2024",
                    "start": "2024-04-01",
                    "end": "2025-03-31",
                    "due": "2026-01-01",
                    "status": "O",
                },
                {
                    "period_key": "FY2023",
                    "start": "2023-04-01",
                    "end": "2024-03-31",
                    "due": "2025-01-01",
                    "status": "F",
                },
            ],
        })

    # ── 计算 ──

    async def calculate_return(self, line_items_json: str, period_info: Optional[dict] = None) -> dict:
        """计算 Corporation Tax（含关联企业、损失、group relief、capital allowances）"""
        try:
            from .calculator import calculate_corporation_tax
            from .associated import compute_marginal_relief
            from .allowances import (
                calculate_capital_allowances, apply_loss_relief, calculate_rd_relief,
                calculate_group_relief_claim,
            )

            raw_items = json.loads(line_items_json)
            line_items = [
                LineItem(category=li["category"], amount=Decimal(str(li["amount"])), currency=li.get("currency", "GBP"))
                for li in raw_items
            ]
            data = TaxData(
                tax_type=TaxType.CORPORATION_TAX,
                period=FiscalPeriod(
                    year=2024, period_type=PeriodType.ANNUAL,
                    period_key="FY2024", start_date=date(2024, 4, 1), end_date=date(2025, 3, 31),
                ),
                taxpayer=TaxpayerInfo(
                    name=period_info.get("company_name", "Company") if period_info else "Company",
                    tax_id=period_info.get("ctref", "") if period_info else "",
                    tax_id_type="ctref",
                ),
                line_items=line_items,
                metadata=period_info or {},
            )
            calc = calculate_corporation_tax(data)
            box_map = {b.category: float(b.amount) for b in calc.breakdown}

            # 应用损失减免
            trading_loss = Decimal(str(box_map.get("current_year_loss", 0)))
            profits_chargeable = Decimal(str(box_map.get("taxable_total_profits", 0)))
            if trading_loss > 0:
                loss_result = apply_loss_relief(trading_loss, profits_chargeable)
                loss_relief_used = float(loss_result.loss_relief_used + loss_result.carry_back_loss)
            else:
                loss_relief_used = 0

            # 应用关联企业
            num_assoc = int((period_info or {}).get("num_associated_companies", 1))
            if num_assoc > 1:
                # 重新计算含关联企业的 CT
                profits = Decimal(str(box_map.get("taxable_total_profits", 0)))
                ct_chargeable, eff_lower, eff_upper = compute_marginal_relief(profits, num_assoc)
                effective_lower_upper = {
                    "effective_lower": float(eff_lower),
                    "effective_upper": float(eff_upper),
                    "num_associated": num_assoc,
                }
            else:
                ct_chargeable = box_map.get("corporation_tax_chargeable", 0)
                effective_lower_upper = {}

            return _tool_ok({
                "success": True,
                "taxable_total_profits": box_map.get("taxable_total_profits", 0),
                "ct_rate_applied": box_map.get("ct_rate_applied", 0),
                "corporation_tax_chargeable": float(ct_chargeable),
                "tax_already_paid": box_map.get("tax_already_paid", 0),
                "amount_payable": float(ct_chargeable) - box_map.get("tax_already_paid", 0),
                "loss_relief_used": loss_relief_used,
                "associated_companies": effective_lower_upper,
                "warnings": calc.warnings,
            })
        except Exception as e:
            return _tool_error(str(e))

    # ── 资本减免详细计算 ──

    async def calculate_capital_allowances(self, args: dict) -> dict:
        """详细计算资本减免

        Args:
            aia_expenditure: AIA 合格支出
            fya_expenditure: FYA 合格支出
            main_pool_expenditure: Main pool 当年新增
            main_pool_opening_balance: Main pool 期初余额
            special_rate_pool_expenditure: Special rate pool 当年新增
            special_rate_pool_opening_balance: Special rate pool 期初余额
            sba_expenditure: SBA 当年新增
            sba_opening_balance: SBA 期初余额
            disposals_proceeds: 处置收入
            disposals_pool: 处置收入计入的 pool
        """
        try:
            from .allowances import calculate_capital_allowances
            result = calculate_capital_allowances(
                aia_expenditure=Decimal(str(args.get("aia_expenditure", 0))),
                fya_expenditure=Decimal(str(args.get("fya_expenditure", 0))),
                main_pool_expenditure=Decimal(str(args.get("main_pool_expenditure", 0))),
                main_pool_opening_balance=Decimal(str(args.get("main_pool_opening_balance", 0))),
                special_rate_pool_expenditure=Decimal(str(args.get("special_rate_pool_expenditure", 0))),
                special_rate_pool_opening_balance=Decimal(str(args.get("special_rate_pool_opening_balance", 0))),
                sba_expenditure=Decimal(str(args.get("sba_expenditure", 0))),
                sba_opening_balance=Decimal(str(args.get("sba_opening_balance", 0))),
                disposals_proceeds=Decimal(str(args.get("disposals_proceeds", 0))),
                disposals_pool=args.get("disposals_pool", "main"),
            )
            return _tool_ok({"success": True, **{
                k: float(v) for k, v in [
                    ("aia_allowance", result.aia_allowance),
                    ("fya_allowance", result.fya_allowance),
                    ("main_pool_wda", result.main_pool_wda),
                    ("special_rate_pool_wda", result.special_rate_pool_wda),
                    ("structures_buildings_allowance", result.structures_buildings_allowance),
                    ("balancing_charges", result.balancing_charges),
                    ("total_allowance", result.total_allowance),
                ]
            }})
        except Exception as e:
            return _tool_error(str(e))

    # ── 关联企业边际减免 ──

    async def calculate_marginal_relief(self, args: dict) -> dict:
        """根据关联企业数量计算 marginal relief"""
        try:
            from .associated import compute_marginal_relief
            profits = Decimal(str(args.get("profits_chargeable", 0)))
            num_assoc = int(args.get("num_associated_companies", 1))

            ct_tax, eff_lower, eff_upper = compute_marginal_relief(profits, num_assoc)

            effective_rate = (ct_tax / profits).quantize(Decimal("0.0001")) if profits > 0 else Decimal("0")

            return _tool_ok({
                "success": True,
                "profits_chargeable": float(profits),
                "num_associated_companies": num_assoc,
                "effective_lower_limit": float(eff_lower),
                "effective_upper_limit": float(eff_upper),
                "ct_chargeable": float(ct_tax),
                "effective_rate": float(effective_rate),
            })
        except Exception as e:
            return _tool_error(str(e))

    # ── Group Relief ──

    async def calculate_group_relief(self, args: dict) -> dict:
        """计算 Group Relief 转移"""
        try:
            from .associated import calculate_group_relief_transfer
            result = calculate_group_relief_transfer(
                claimant_company=args.get("claimant_company", ""),
                claimant_profits_chargeable=Decimal(str(args.get("claimant_profits", 0))),
                surrendering_company=args.get("surrendering_company", ""),
                surrendering_relief=Decimal(str(args.get("surrendering_relief", 0))),
                already_claimed_by_claimant=Decimal(str(args.get("already_claimed", 0))),
            )
            return _tool_ok({
                "success": True,
                **{
                    k: float(v) for k, v in [
                        ("surrendering_company_relief", result.available_relief),
                        ("max_claimable", result.max_relief_claimable),
                        ("relief_claimed", result.relief_to_claim),
                        ("relief_not_used", result.relief_not_used),
                    ]
                }
            })
        except Exception as e:
            return _tool_error(str(e))

    # ── Loss Relief ──

    async def calculate_loss_relief(self, args: dict) -> dict:
        """应用损失减免"""
        try:
            from .allowances import apply_loss_relief
            result = apply_loss_relief(
                trading_loss=Decimal(str(args.get("trading_loss", 0))),
                other_income_chargeable_to_ct=Decimal(str(args.get("other_income", 0))),
                losses_brought_forward=Decimal(str(args.get("losses_brought_forward", 0))),
                carry_back=bool(args.get("carry_back", True)),
            )
            return _tool_ok({
                "success": True,
                **{
                    k: float(v) for k, v in [
                        ("current_year_loss", result.current_year_loss),
                        ("loss_relief_used", result.loss_relief_used),
                        ("carry_back_loss", result.carry_back_loss),
                        ("carry_forward_loss", result.carry_forward_loss),
                        ("remaining_loss_to_carry_forward", result.remaining_loss_to_carry_forward),
                    ]
                }
            })
        except Exception as e:
            return _tool_error(str(e))

    # ── R&D ──

    async def calculate_rd_relief(self, args: dict) -> dict:
        """R&D 税收减免"""
        try:
            from .allowances import calculate_rd_relief
            result = calculate_rd_relief(
                qualifying_expenditure=Decimal(str(args.get("qualifying_expenditure", 0))),
                is_sme=bool(args.get("is_sme", True)),
            )
            return _tool_ok({
                "success": True,
                "is_sme": result.is_sme,
                "qualifying_expenditure": float(result.qualifying_expenditure),
                "rd_relief": float(result.rd_relief),
                "enhanced_deduction_rate": float(result.rd_enhanced_deduction_rate),
            })
        except Exception as e:
            return _tool_error(str(e))

    # ── 税务优化建议 ──

    async def suggest_optimization(self, args: dict) -> dict:
        """基于当前 CT 数据给出优化建议"""
        try:
            suggestions = []
            num_assoc = int(args.get("num_associated_companies", 1))
            profits = float(args.get("profits_chargeable", 0))
            aia = float(args.get("aia_expenditure", 0))
            rd_exp = float(args.get("rd_qualifying_expenditure", 0))
            has_ip = bool(args.get("has_patents", False))

            # 1. AIA 检查
            if aia > 0 and aia < 1000000:
                suggestions.append({
                    "category": "capital_allowances",
                    "title": "充分利用 Annual Investment Allowance (AIA)",
                    "description": f"AIA 限额为 £1m。当前使用了 £{aia:,.0f}，剩余 £{1_000_000 - aia:,.0f} 可加速投资以获得 100% 减免。",
                    "potential_saving": float(min(aia, 1_000_000 - aia) * 0.19),
                })

            # 2. R&D 提示
            if rd_exp == 0:
                suggestions.append({
                    "category": "rd_relief",
                    "title": "考虑 R&D 税收减免",
                    "description": "如果企业在科技创新方面有投入，可申请 R&D Relief。SME 可获得 86% 增强扣除。",
                    "potential_saving": "Varies based on qualifying expenditure",
                })

            # 3. Patent Box
            if has_ip:
                suggestions.append({
                    "category": "patent_box",
                    "title": "申请 Patent Box 优惠",
                    "description": "专利相关利润可按 10% 的优惠税率计算。",
                    "potential_saving": "10% vs 25% on relevant IP profits",
                })

            # 4. 关联企业
            if num_assoc > 1:
                suggestions.append({
                    "category": "associated_companies",
                    "title": "注意关联企业阈值分摊",
                    "description": f"有 {num_assoc} 家关联企业，lower/upper limits 需要除以 {num_assoc}。考虑在关联企业间合理分配利润。",
                    "potential_saving": "Optimize profit allocation across group",
                })

            # 5. Loss Relief
            if profits <= 0:
                suggestions.append({
                    "category": "loss_relief",
                    "title": "利用损失 carry back",
                    "description": "亏损可向上年 carry back 1 年立即获得退税，或无限期 carry forward。",
                    "potential_saving": "Up to 25% of loss × 1 year",
                })

            # 6. Marginal Relief
            elif 50000 < profits < 250000:
                suggestions.append({
                    "category": "marginal_relief",
                    "title": "考虑 timing of income/expenses",
                    "description": f"利润在边际区间内。可考虑将收入延后到下个会计期间，或加速扣除（如奖金）。",
                    "potential_saving": "Up to 6% of profits",
                })

            return _tool_ok({
                "success": True,
                "suggestions": suggestions,
                "num_suggestions": len(suggestions),
            })
        except Exception as e:
            return _tool_error(str(e))

    # ── 校验 ──

    async def validate_return(self, return_data: dict) -> dict:
        try:
            from .validator import validate_corporation_tax
            line_items = []
            for key in (
                "trading_income", "trading_expenses", "investment_income",
                "property_income", "chargeable_gains", "capital_allowances_claimed",
                "trading_losses_brought_forward", "group_relief_claimed",
                "rd_qualifying_expenditure", "tax_already_paid",
                "aia_expenditure", "fya_expenditure", "main_pool_expenditure",
                "special_rate_pool_expenditure", "sba_expenditure",
                "main_pool_opening_balance", "special_rate_pool_opening_balance",
                "sba_opening_balance", "disposals_proceeds",
            ):
                if key in return_data and return_data[key] is not None:
                    line_items.append(LineItem(
                        category=key,
                        amount=Decimal(str(return_data[key])),
                        currency="GBP",
                    ))
            data = TaxData(
                tax_type=TaxType.CORPORATION_TAX,
                period=FiscalPeriod(
                    year=2024, period_type=PeriodType.ANNUAL,
                    period_key=return_data.get("period_key", "FY2024"),
                    start_date=date(2024, 4, 1), end_date=date(2025, 3, 31),
                ),
                taxpayer=TaxpayerInfo(
                    name=return_data.get("company_name", "Unknown"),
                    tax_id=return_data.get("ctref", ""),
                    tax_id_type="ctref",
                ),
                line_items=line_items,
                metadata={"num_associated_companies": return_data.get("num_associated_companies", 1)},
            )
            report = validate_corporation_tax(data)
            return _tool_ok({
                "success": True,
                "is_valid": report.is_valid,
                "errors": [{"field": e.field, "message": e.message} for e in report.errors],
                "warnings": [{"field": w.field, "message": w.message} for w in report.warnings],
            })
        except Exception as e:
            return _tool_error(str(e))

    # ── 提交 ──

    async def submit_return(self, taxpayer_id: str, period_key: str, return_data: dict) -> dict:
        ctref = taxpayer_id
        if not ctref or not period_key:
            return _tool_error("CTREF and accounting period are required")
        return _tool_ok({
            "success": True,
            "submission_id": f"CT-{ctref}-{period_key}-001",
            "processing_date": "2025-12-15T10:00:00Z",
            "message": "Corporation Tax return submitted (simulated)",
        })

    # ── 查询 ──

    async def get_return(self, taxpayer_id: str, period_key: str) -> dict:
        ctref = taxpayer_id
        if not ctref or not period_key:
            return _tool_error("CTREF and period_key are required")
        return _tool_ok({
            "success": True,
            "ctref": ctref,
            "period_key": period_key,
            "message": "Submitted CT return data (simulated)",
        })

    # ── 元数据 ──

    async def analyze_business_data(self, company_data_json: str) -> dict:
        return _tool_error("For CT, use the financial statements to fill CT600 fields. The data analyzer is for VAT.")

    def get_tool_metadata(self) -> list[dict]:
        return [
            {
                "name": "get_corporation_tax_obligations",
                "description": "Query HMRC for Corporation Tax filing obligations for a given CTREF.",
                "input_schema": {"ctref": str},
            },
            {
                "name": "calculate_corporation_tax",
                "description": "Calculate UK Corporation Tax with marginal rate (19%-25%), associated companies, loss relief, group relief, R&D relief.",
                "input_schema": {"line_items_json": str, "period_info": dict},
            },
            {
                "name": "calculate_capital_allowances",
                "description": "Detailed Capital Allowances calculation: AIA (£1m), FYA, Main Pool (18%), Special Rate Pool (6%), SBA (3%), with disposal handling.",
                "input_schema": {
                    "aia_expenditure": str,
                    "fya_expenditure": str,
                    "main_pool_expenditure": str,
                    "main_pool_opening_balance": str,
                    "special_rate_pool_expenditure": str,
                    "special_rate_pool_opening_balance": str,
                    "sba_expenditure": str,
                    "sba_opening_balance": str,
                    "disposals_proceeds": str,
                    "disposals_pool": str,
                },
            },
            {
                "name": "calculate_marginal_relief",
                "description": "Calculate CT with associated companies' lower/upper limits adjustment.",
                "input_schema": {"profits_chargeable": str, "num_associated_companies": str},
            },
            {
                "name": "calculate_group_relief",
                "description": "Calculate Group Relief transfer between associated companies.",
                "input_schema": {
                    "claimant_company": str,
                    "claimant_profits": str,
                    "surrendering_company": str,
                    "surrendering_relief": str,
                    "already_claimed": str,
                },
            },
            {
                "name": "calculate_loss_relief",
                "description": "Apply trading loss relief: offset against current year, carry back 1 year, or carry forward indefinitely.",
                "input_schema": {
                    "trading_loss": str,
                    "other_income": str,
                    "losses_brought_forward": str,
                    "carry_back": str,
                },
            },
            {
                "name": "calculate_rd_relief",
                "description": "Calculate R&D tax relief (SME 86% enhanced deduction, or large company RDEC 20%).",
                "input_schema": {"qualifying_expenditure": str, "is_sme": str},
            },
            {
                "name": "suggest_ct_optimization",
                "description": "Get AI-driven tax optimization suggestions for CT (AIA, R&D, Patent Box, group relief, timing).",
                "input_schema": {
                    "profits_chargeable": str,
                    "aia_expenditure": str,
                    "rd_qualifying_expenditure": str,
                    "has_patents": str,
                    "num_associated_companies": str,
                },
            },
            {
                "name": "validate_corporation_tax",
                "description": "Validate a CT600 return for HMRC compliance.",
                "input_schema": {
                    "ctref": str,
                    "company_name": str,
                    "trading_income": str,
                    "trading_expenses": str,
                    "investment_income": str,
                    "capital_allowances_claimed": str,
                },
            },
            {
                "name": "submit_corporation_tax",
                "description": "Submit a Corporation Tax return to HMRC. WARNING: irreversible action.",
                "input_schema": {"ctref": str, "period_key": str, "return_data_json": str},
            },
            {
                "name": "get_corporation_tax",
                "description": "Retrieve a previously submitted Corporation Tax return.",
                "input_schema": {"ctref": str, "period_key": str},
            },
        ]
