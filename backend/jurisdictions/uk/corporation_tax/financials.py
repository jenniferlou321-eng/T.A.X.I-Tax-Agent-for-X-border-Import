"""UK CT 财务数据导入器

从企业财务报表 (P&L, BS) 自动生成 CT 申报数据。

支持的输入格式：
- P&L dict: {"revenue": ..., "cost_of_sales": ..., "operating_expenses": ..., "finance_costs": ...}
- Balance Sheet dict: {"fixed_assets_additions": ..., "disposals": ...}
- Trial Balance dict: {"account_code": amount, ...}
- XBRL iXBRL（简化版）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional


@dataclass
class FinancialSummary:
    """从财务报表提取的关键数字"""
    trading_income: Decimal = Decimal("0")
    cost_of_sales: Decimal = Decimal("0")
    operating_expenses: Decimal = Decimal("0")
    depreciation: Decimal = Decimal("0")
    finance_costs: Decimal = Decimal("0")
    net_trading_profit: Decimal = Decimal("0")
    investment_income: Decimal = Decimal("0")
    property_income: Decimal = Decimal("0")
    chargeable_gains: Decimal = Decimal("0")
    fixed_asset_additions: Decimal = Decimal("0")
    fixed_asset_disposals: Decimal = Decimal("0")
    main_pool_opening_balance: Decimal = Decimal("0")
    rd_qualifying_expenditure: Decimal = Decimal("0")
    notes: list[str] = field(default_factory=list)


@dataclass
class CT600Mapping:
    """P&L/BS → CT600 的映射结果"""
    line_items: dict[str, Decimal] = field(default_factory=dict)
    capital_allowances_inputs: dict[str, Decimal] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_line_items(self) -> list[dict]:
        """转换为 LineItem 列表"""
        return [
            {"category": k, "amount": str(v), "currency": "GBP"}
            for k, v in self.line_items.items()
        ]


def _dec(v) -> Decimal:
    return Decimal(str(v)) if v is not None else Decimal("0")


def _round_2(d: Decimal) -> Decimal:
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ── P&L 导入器 ──

def import_profit_and_loss(pl_data: dict) -> FinancialSummary:
    """从 P&L 报表提取 CT 申报数据

    期望字段（灵活匹配）：
        revenue / turnover / sales
        cost_of_sales / cogs
        operating_expenses / opex
        depreciation
        finance_costs
        investment_income
        property_income
        chargeable_gains

    Returns:
        FinancialSummary with extracted values
    """
    summary = FinancialSummary()

    # 灵活匹配字段名
    revenue_fields = ["revenue", "turnover", "sales", "total_revenue", "gross_income"]
    cos_fields = ["cost_of_sales", "cogs", "cost_of_goods_sold", "direct_costs"]
    opex_fields = ["operating_expenses", "opex", "general_admin", "sga", "overheads"]
    dep_fields = ["depreciation", "amortisation", "amortization"]
    fin_fields = ["finance_costs", "interest_payable", "interest_expense"]

    for field_list, target in [
        (revenue_fields, "trading_income"),
        (cos_fields, "cost_of_sales"),
        (opex_fields, "operating_expenses"),
        (dep_fields, "depreciation"),
        (fin_fields, "finance_costs"),
    ]:
        for f in field_list:
            if f in pl_data and pl_data[f] is not None:
                setattr(summary, target, _dec(pl_data[f]))
                break

    # 投资收入
    for f in ("investment_income", "interest_receivable", "dividend_income"):
        if f in pl_data and pl_data[f] is not None:
            summary.investment_income += _dec(pl_data[f])

    # 财产收入
    for f in ("property_income", "rental_income", "letting_income"):
        if f in pl_data and pl_data[f] is not None:
            summary.property_income += _dec(pl_data[f])

    # 应税收益
    for f in ("chargeable_gains", "capital_gains"):
        if f in pl_data and pl_data[f] is not None:
            summary.chargeable_gains += _dec(pl_data[f])

    # 计算净交易利润
    summary.net_trading_profit = (
        summary.trading_income
        - summary.cost_of_sales
        - summary.operating_expenses
        - summary.depreciation
        - summary.finance_costs
    )

    # 验证
    if summary.net_trading_profit < 0:
        summary.notes.append("Net trading profit is negative - consider loss relief")

    return summary


# ── 资产负债表导入器 ──

def import_balance_sheet(bs_data: dict, opening_main_pool: Decimal = Decimal("0")) -> dict:
    """从资产负债表提取资本减免数据

    期望字段：
        fixed_asset_additions / capex / capital_expenditure
        fixed_asset_disposals / disposals
        main_pool_opening_balance（可选）

    Returns:
        dict of capital_allowances inputs (Decimal values)
    """
    additions = Decimal("0")
    disposals = Decimal("0")

    for f in ("fixed_asset_additions", "capex", "capital_expenditure", "additions"):
        if f in bs_data and bs_data[f] is not None:
            additions += _dec(bs_data[f])

    for f in ("fixed_asset_disposals", "disposals", "asset_disposals"):
        if f in bs_data and bs_data[f] is not None:
            disposals += _dec(bs_data[f])

    return {
        "main_pool_expenditure": additions,
        "main_pool_opening_balance": opening_main_pool,
        "disposals_proceeds": disposals,
        "disposals_pool": "main",
    }


# ── 总转换器 ──

def convert_financials_to_ct600(
    profit_and_loss: dict,
    balance_sheet: Optional[dict] = None,
    opening_main_pool: Decimal = Decimal("0"),
    rd_qualifying_expenditure: Decimal = Decimal("0"),
    num_associated_companies: int = 1,
) -> CT600Mapping:
    """从 P&L + BS 自动生成 CT600 申报数据

    Args:
        profit_and_loss: P&L 报表 dict
        balance_sheet: 资产负债表 dict (可选)
        opening_main_pool: Main Pool 期初余额
        rd_qualifying_expenditure: R&D 支出
        num_associated_companies: 关联企业数

    Returns:
        CT600Mapping with all line items, capital allowances inputs, and metadata
    """
    # 提取 P&L
    pl_summary = import_profit_and_loss(profit_and_loss)

    # 提取 BS
    bs_inputs = {}
    if balance_sheet:
        bs_inputs = import_balance_sheet(balance_sheet, opening_main_pool)

    # 构造 line_items
    line_items = {
        "trading_income": pl_summary.trading_income,
        "trading_expenses": (
            pl_summary.cost_of_sales
            + pl_summary.operating_expenses
            + pl_summary.finance_costs
        ),
        "investment_income": pl_summary.investment_income,
        "property_income": pl_summary.property_income,
        "chargeable_gains": pl_summary.chargeable_gains,
    }

    # 折旧加回（资本减免独立计算）
    # 不在 trading_expenses 中减
    line_items["trading_expenses"] -= pl_summary.depreciation
    # 实际折旧将通过资本减免体现

    # 合并 BS
    capital_allowances_inputs = {
        **bs_inputs,
        "main_pool_opening_balance": opening_main_pool,
        "rd_qualifying_expenditure": rd_qualifying_expenditure,
    }

    return CT600Mapping(
        line_items={k: _round_2(v) for k, v in line_items.items() if v != 0},
        capital_allowances_inputs={
            k: _round_2(v) for k, v in capital_allowances_inputs.items()
            if isinstance(v, Decimal) and v != 0
        },
        metadata={
            "company_name": profit_and_loss.get("company_name", ""),
            "ctref": profit_and_loss.get("ctref", ""),
            "period_start": profit_and_loss.get("period_start", ""),
            "period_end": profit_and_loss.get("period_end", ""),
            "num_associated_companies": num_associated_companies,
            "depreciation_addback": pl_summary.depreciation,
        },
        warnings=[
            *pl_summary.notes,
            f"Added back depreciation: £{pl_summary.depreciation:,.2f} (to be claimed as capital allowances separately)",
        ] if pl_summary.depreciation else pl_summary.notes,
    )


# ── Trial Balance 简单转换器 ──

def import_trial_balance(tb_data: dict) -> FinancialSummary:
    """从试算表 (Trial Balance) 提取数据

    期望格式：
        {
            "1000": 1000000,  # 销售额
            "2000": -600000,  # 销售成本
            ...
        }

    通用账户代码范围（按 UK GAAP）：
        1000-1999: 收入
        2000-2999: 销售成本
        3000-3999: 行政费用
        4000-4999: 财务成本
        5000-5999: 投资收入
        6000-6999: 财产收入
        7000-7999: 资产处置
    """
    summary = FinancialSummary()

    for code, amount in tb_data.items():
        if not isinstance(code, str) or not code[0].isdigit():
            continue
        first_digit = code[0]
        value = _dec(amount)

        if first_digit == "1":
            summary.trading_income += abs(value)
        elif first_digit == "2":
            summary.cost_of_sales += abs(value)
        elif first_digit == "3":
            summary.operating_expenses += abs(value)
        elif first_digit == "4":
            summary.finance_costs += abs(value)
        elif first_digit == "5":
            summary.investment_income += abs(value)
        elif first_digit == "6":
            summary.property_income += abs(value)
        elif first_digit == "7":
            if value < 0:
                summary.chargeable_gains += abs(value)
            else:
                summary.chargeable_gains -= value

    summary.net_trading_profit = (
        summary.trading_income
        - summary.cost_of_sales
        - summary.operating_expenses
        - summary.finance_costs
    )

    return summary
