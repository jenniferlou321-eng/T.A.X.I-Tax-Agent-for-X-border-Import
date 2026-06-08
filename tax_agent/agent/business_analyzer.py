"""Business Data Analyzer — 从原始企业发票数据计算 UK VAT Return

将 scripts/calculate_vat_return.py 的核心逻辑提取为可复用模块，
供 Agent MCP 工具调用。

输入: 原始企业 JSON 数据（含 sales_invoices, purchase_invoices, expense_claims 等）
输出: 结构化 VAT 分析报告 + HMRC 9-Box 值 + line_items（供后续工具链使用）
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from decimal import Decimal
from pathlib import Path
from typing import Any


# ── Types ──

@dataclass
class VATSummary:
    """VAT Return 汇总结果"""
    # HMRC 9-Box
    box1_vat_due_sales: Decimal = Decimal("0")
    box2_vat_due_acquisitions: Decimal = Decimal("0")
    box3_total_vat_due: Decimal = Decimal("0")
    box4_vat_reclaimed: Decimal = Decimal("0")
    box5_net_vat_due: Decimal = Decimal("0")
    box6_total_sales: int = 0
    box7_total_purchases: int = 0
    box8_goods_supplied_eu: int = 0
    box9_goods_acquired_eu: int = 0

    # 辅助明细
    domestic_sales_net: Decimal = Decimal("0")
    domestic_sales_vat: Decimal = Decimal("0")
    eu_sales_net: Decimal = Decimal("0")
    zero_rated_sales: Decimal = Decimal("0")
    export_sales: Decimal = Decimal("0")

    domestic_purchases_net: Decimal = Decimal("0")
    domestic_purchases_vat: Decimal = Decimal("0")
    import_vat: Decimal = Decimal("0")
    import_net: Decimal = Decimal("0")
    eu_acquisition_net: Decimal = Decimal("0")
    eu_acquisition_vat: Decimal = Decimal("0")

    expense_vat_recoverable: Decimal = Decimal("0")
    expense_net_recoverable: Decimal = Decimal("0")

    reverse_charge_vat: Decimal = Decimal("0")
    bad_debt_relief: Decimal = Decimal("0")
    pre_reg_vat: Decimal = Decimal("0")

    # 不可抵扣
    non_recoverable_vat: Decimal = Decimal("0")
    exempt_purchases: Decimal = Decimal("0")
    entertainment_expenses: Decimal = Decimal("0")

    period_key: str = ""
    vrn: str = ""
    company_name: str = ""
    period_label: str = ""
    period_start: str = ""
    period_end: str = ""
    period_due: str = ""

    @property
    def hmrc_payload(self) -> dict:
        """生成 HMRC API 提交格式"""
        return {
            "periodKey": self.period_key,
            "vatDueSales": round(float(self.box1_vat_due_sales), 2),
            "vatDueAcquisitions": round(float(self.box2_vat_due_acquisitions), 2),
            "totalVatDue": round(float(self.box3_total_vat_due), 2),
            "vatReclaimedCurrPeriod": round(float(self.box4_vat_reclaimed), 2),
            "netVatDue": round(float(self.box5_net_vat_due), 2),
            "totalValueSalesExVAT": self.box6_total_sales,
            "totalValuePurchasesExVAT": self.box7_total_purchases,
            "totalValueGoodsSuppliedExVAT": self.box8_goods_supplied_eu,
            "totalAcquisitionsExVAT": self.box9_goods_acquired_eu,
            "finalised": True,
        }

    def to_line_items(self) -> list[dict]:
        """转换为供 calculate_vat_return 工具使用的 line_items 格式"""
        return [
            {"category": "vat_due_sales", "amount": str(self.box1_vat_due_sales), "currency": "GBP"},
            {"category": "vat_due_acquisitions", "amount": str(self.box2_vat_due_acquisitions), "currency": "GBP"},
            {"category": "vat_reclaimed_purchases", "amount": str(self.box4_vat_reclaimed), "currency": "GBP"},
            {"category": "total_sales_ex_vat", "amount": str(self.box6_total_sales), "currency": "GBP"},
            {"category": "total_purchases_ex_vat", "amount": str(self.box7_total_purchases), "currency": "GBP"},
            {"category": "total_goods_supplied_eu", "amount": str(self.box8_goods_supplied_eu), "currency": "GBP"},
            {"category": "total_goods_acquired_eu", "amount": str(self.box9_goods_acquired_eu), "currency": "GBP"},
        ]

    def to_dict(self) -> dict:
        """序列化为 dict（Decimal 转 float）"""
        d = {}
        for k, v in asdict(self).items():
            if isinstance(v, Decimal):
                d[k] = float(v)
            else:
                d[k] = v
        return d


# ── Core Calculation ──

def calculate_vat_return_from_raw(data: dict) -> VATSummary:
    """从原始发票数据计算 VAT Return 9-Box

    Args:
        data: 原始企业数据，包含 company, sales_invoices, purchase_invoices,
              expense_claims, reverse_charge_transactions, vat_adjustments

    Returns:
        VATSummary 汇总结果
    """
    summary = VATSummary()
    company = data.get("company", {})
    period = company.get("period", {})

    summary.company_name = company.get("name", "")
    summary.vrn = company.get("vrn", "")
    summary.period_key = period.get("period_key", "")
    summary.period_label = period.get("label", "")
    summary.period_start = period.get("start", "")
    summary.period_end = period.get("end", "")
    summary.period_due = period.get("due", "")

    sales = data.get("sales_invoices", [])
    purchases = data.get("purchase_invoices", [])
    expenses = data.get("expense_claims", [])
    reverse_charges = data.get("reverse_charge_transactions", [])
    adjustments = data.get("vat_adjustments", [])

    # ── Sales Analysis ──
    for inv in sales:
        inv_type = inv.get("type", "")
        net = Decimal(str(inv.get("net", 0) or inv.get("net_gbp", 0)))
        vat = Decimal(str(inv.get("vat", 0)))

        if inv_type in ("domestic_b2b", "domestic_b2c"):
            summary.domestic_sales_net += net
            summary.domestic_sales_vat += vat
            summary.box1_vat_due_sales += vat
            summary.box6_total_sales += int(net)

        elif inv_type == "eu_b2b":
            summary.eu_sales_net += net
            summary.box8_goods_supplied_eu += int(net)
            # B2B EU 销售零税率，Box 1 不加

        elif inv_type == "zero_rated":
            summary.zero_rated_sales += net
            summary.box6_total_sales += int(net)
            # 零税率，Box 1 不加

        elif inv_type == "export":
            summary.export_sales += net
            summary.box6_total_sales += int(net)
            # 出口免税，Box 1 不加

    # ── Purchase Analysis ──
    for inv in purchases:
        inv_type = inv.get("type", "")
        net = Decimal(str(inv.get("net", 0) or inv.get("net_gbp", 0)))
        vat = Decimal(str(inv.get("vat", 0)))
        acq_vat = Decimal(str(inv.get("acquisition_vat", 0)))
        recoverable = inv.get("recoverable", True)

        if inv_type == "domestic":
            summary.domestic_purchases_net += net
            summary.domestic_purchases_vat += vat
            if recoverable:
                summary.box4_vat_reclaimed += vat
            else:
                summary.non_recoverable_vat += vat
            summary.box7_total_purchases += int(net)

        elif inv_type == "import":
            summary.import_net += net
            summary.import_vat += vat
            summary.box4_vat_reclaimed += vat
            summary.box7_total_purchases += int(net)

        elif inv_type == "eu_acquisition":
            summary.eu_acquisition_net += net
            summary.eu_acquisition_vat += acq_vat
            summary.box2_vat_due_acquisitions += acq_vat
            summary.box4_vat_reclaimed += acq_vat
            summary.box7_total_purchases += int(net)
            summary.box9_goods_acquired_eu += int(net)

        elif inv_type == "exempt":
            summary.exempt_purchases += net
            # 免税采购不计入 Box 7

    # ── Expense Claims ──
    for exp in expenses:
        net = Decimal(str(exp.get("net", 0)))
        vat = Decimal(str(exp.get("vat", 0)))
        recoverable = exp.get("recoverable", False)
        category = exp.get("category", "")

        if recoverable:
            summary.expense_vat_recoverable += vat
            summary.expense_net_recoverable += net
            summary.box4_vat_reclaimed += vat
            summary.box7_total_purchases += int(net)
        else:
            summary.non_recoverable_vat += vat
            if category in ("subsistence", "entertainment"):
                summary.entertainment_expenses += net

    # ── Reverse Charge (B2B Digital Services) ──
    for rc in reverse_charges:
        net = Decimal(str(rc.get("net", 0)))
        vat_due = Decimal(str(rc.get("vat_due", 0)))
        vat_reclaimable = Decimal(str(rc.get("vat_reclaimable", 0)))

        summary.reverse_charge_vat += vat_due
        summary.box1_vat_due_sales += vat_due
        summary.box4_vat_reclaimed += vat_reclaimable
        summary.box6_total_sales += int(net)

    # ── VAT Adjustments ──
    for adj in adjustments:
        amount = Decimal(str(adj.get("amount", 0)))
        adj_type = adj.get("type", "")

        if adj_type == "credit":
            summary.box4_vat_reclaimed += amount
            desc = adj.get("description", "").lower()
            if "bad debt" in desc:
                summary.bad_debt_relief += amount
            elif "pre-registration" in desc:
                summary.pre_reg_vat += amount

    # ── Box 3 and Box 5 (Auto-calculate) ──
    summary.box3_total_vat_due = (
        summary.box1_vat_due_sales + summary.box2_vat_due_acquisitions
    )
    summary.box5_net_vat_due = abs(
        summary.box3_total_vat_due - summary.box4_vat_reclaimed
    )

    return summary


# ── Detailed Report Generation ──

def generate_analysis_report(data: dict, summary: VATSummary) -> dict:
    """生成详细的 VAT 分析报告，包含法规依据和合规注释。

    Returns:
        dict 包含:
            - company_info: 企业基本信息
            - nine_box: HMRC 9-Box 值
            - sales_breakdown: 销售分类明细
            - purchase_breakdown: 采购分类明细
            - non_recoverable_items: 不可抵扣项目
            - compliance_notes: 合规性注释
            - hmrc_payload: HMRC API 提交格式
            - line_items: 供后续 calculate/validate 工具使用的 line items
    """
    company = data.get("company", {})
    period = company.get("period", {})
    sales = data.get("sales_invoices", [])
    purchases = data.get("purchase_invoices", [])
    expenses = data.get("expense_claims", [])

    # 销售分类统计
    sales_by_type: dict[str, list[dict]] = {}
    for inv in sales:
        t = inv.get("type", "unknown")
        sales_by_type.setdefault(t, []).append(inv)

    # 采购分类统计
    purchases_by_type: dict[str, list[dict]] = {}
    for inv in purchases:
        t = inv.get("type", "unknown")
        purchases_by_type.setdefault(t, []).append(inv)

    # 结果判断
    if summary.box3_total_vat_due > summary.box4_vat_reclaimed:
        result_type = "payment_due"
        result_text = f"Company OWES HMRC £{summary.box5_net_vat_due:,.2f}"
    elif summary.box3_total_vat_due < summary.box4_vat_reclaimed:
        result_type = "repayment"
        result_text = f"HMRC OWES company £{summary.box5_net_vat_due:,.2f} (repayment)"
    else:
        result_type = "nil"
        result_text = "Nil return - no VAT due"

    return {
        "company_info": {
            "name": summary.company_name,
            "vrn": summary.vrn,
            "industry": company.get("industry", ""),
            "vat_scheme": company.get("vat_scheme", ""),
            "period": {
                "label": summary.period_label,
                "start": summary.period_start,
                "end": summary.period_end,
                "due": summary.period_due,
                "period_key": summary.period_key,
            },
        },
        "nine_box": {
            "box1_vat_due_sales": float(summary.box1_vat_due_sales),
            "box2_vat_due_acquisitions": float(summary.box2_vat_due_acquisitions),
            "box3_total_vat_due": float(summary.box3_total_vat_due),
            "box4_vat_reclaimed": float(summary.box4_vat_reclaimed),
            "box5_net_vat_due": float(summary.box5_net_vat_due),
            "box6_total_sales": summary.box6_total_sales,
            "box7_total_purchases": summary.box7_total_purchases,
            "box8_goods_supplied_eu": summary.box8_goods_supplied_eu,
            "box9_goods_acquired_eu": summary.box9_goods_acquired_eu,
        },
        "sales_breakdown": {
            "domestic_standard_rate": {
                "count": len(sales_by_type.get("domestic_b2b", [])) + len(sales_by_type.get("domestic_b2c", [])),
                "net_total": float(summary.domestic_sales_net),
                "vat_total": float(summary.domestic_sales_vat),
                "notes": "Standard 20% VAT. Included in Box 1 (VAT) and Box 6 (net).",
            },
            "eu_b2b": {
                "count": len(sales_by_type.get("eu_b2b", [])),
                "net_total": float(summary.eu_sales_net),
                "vat_total": 0.0,
                "notes": "Zero-rated under EU B2B supply rules. Included in Box 8 only.",
            },
            "zero_rated": {
                "count": len(sales_by_type.get("zero_rated", [])),
                "net_total": float(summary.zero_rated_sales),
                "vat_total": 0.0,
                "notes": "Zero-rated goods (e.g. children's clothing, books). Included in Box 6.",
            },
            "export": {
                "count": len(sales_by_type.get("export", [])),
                "net_total": float(summary.export_sales),
                "vat_total": 0.0,
                "notes": "Export outside EU - VAT exempt. Included in Box 6.",
            },
        },
        "purchase_breakdown": {
            "domestic": {
                "count": len(purchases_by_type.get("domestic", [])),
                "net_total": float(summary.domestic_purchases_net),
                "vat_reclaimable": float(summary.domestic_purchases_vat),
                "notes": "Standard 20% VAT on domestic purchases. Included in Box 4 and Box 7.",
            },
            "import": {
                "count": len(purchases_by_type.get("import", [])),
                "net_total": float(summary.import_net),
                "vat_reclaimable": float(summary.import_vat),
                "notes": "Import VAT reclaimed via C79 certificate. Included in Box 4 and Box 7.",
            },
            "eu_acquisition": {
                "count": len(purchases_by_type.get("eu_acquisition", [])),
                "net_total": float(summary.eu_acquisition_net),
                "acquisition_vat": float(summary.eu_acquisition_vat),
                "notes": "EU acquisitions: Box 2 (VAT due) + Box 4 (reclaim) + Box 7 (net) + Box 9 (EU goods).",
            },
            "exempt": {
                "count": len(purchases_by_type.get("exempt", [])),
                "net_total": float(summary.exempt_purchases),
                "notes": "VAT exempt purchases (e.g. insurance). Not included in VAT Return.",
            },
            "recoverable_expenses": {
                "count": sum(1 for e in expenses if e.get("recoverable")),
                "net_total": float(summary.expense_net_recoverable),
                "vat_reclaimable": float(summary.expense_vat_recoverable),
                "notes": "Business expenses with recoverable VAT. Included in Box 4 and Box 7.",
            },
            "reverse_charge": {
                "count": len(data.get("reverse_charge_transactions", [])),
                "vat_due": float(summary.reverse_charge_vat),
                "notes": "Reverse charge on B2B digital services. Box 1 (VAT due) + Box 4 (reclaim). Net effect is zero.",
            },
            "vat_adjustments": {
                "count": len(data.get("vat_adjustments", [])),
                "bad_debt_relief": float(summary.bad_debt_relief),
                "pre_registration_vat": float(summary.pre_reg_vat),
                "notes": "Bad debt relief and pre-registration VAT. Added to Box 4.",
            },
        },
        "non_recoverable_items": {
            "non_recoverable_vat": float(summary.non_recoverable_vat),
            "exempt_purchases": float(summary.exempt_purchases),
            "entertainment_expenses": float(summary.entertainment_expenses),
            "notes": "These items are excluded from the VAT Return per HMRC rules.",
        },
        "compliance_notes": [
            {
                "rule": "Standard Rate",
                "description": "Domestic B2B and B2C sales charged at 20% standard rate.",
                "applies_to": "Box 1, Box 6",
            },
            {
                "rule": "EU B2B Zero Rating",
                "description": "Goods supplied to EU VAT-registered businesses are zero-rated under intra-EU supply rules.",
                "applies_to": "Box 8",
            },
            {
                "rule": "Zero-Rated Goods",
                "description": "Children's clothing and printed books are zero-rated under VAT Act 1994 Schedule 8.",
                "applies_to": "Box 6",
            },
            {
                "rule": "Export Outside EU",
                "description": "Goods exported outside the EU are VAT exempt (not zero-rated). Evidence of export required.",
                "applies_to": "Box 6",
            },
            {
                "rule": "Import VAT (C79)",
                "description": "Import VAT paid at customs is reclaimable with C79 certificate. Customs duty is not reclaimable.",
                "applies_to": "Box 4, Box 7",
            },
            {
                "rule": "EU Acquisition",
                "description": "Goods acquired from EU: Box 2 (VAT due) + Box 4 (reclaim) + Box 7 (net) + Box 9 (EU goods).",
                "applies_to": "Box 2, Box 4, Box 7, Box 9",
            },
            {
                "rule": "Reverse Charge (B2B Digital)",
                "description": "B2B digital services from outside UK: Box 1 (VAT due) + Box 4 (reclaim). Net effect zero but must be declared.",
                "applies_to": "Box 1, Box 4, Box 6",
            },
            {
                "rule": "Non-Recoverable VAT",
                "description": "Business entertainment, exempt purchases, and non-recoverable expenses excluded from VAT Return.",
                "applies_to": "Excluded",
            },
            {
                "rule": "Bad Debt Relief",
                "description": "VAT on debts > 6 months old where customer has gone into liquidation. Added to Box 4.",
                "applies_to": "Box 4",
            },
            {
                "rule": "Pre-Registration VAT",
                "description": "VAT on stock purchased within 4 years and services within 6 months before VAT registration.",
                "applies_to": "Box 4",
            },
        ],
        "result": {
            "type": result_type,
            "text": result_text,
        },
        "hmrc_payload": summary.hmrc_payload,
        "line_items": summary.to_line_items(),
    }


# ── Main Entry Point ──

def analyze_business_data(company_data_json: str) -> dict:
    """分析原始企业数据并生成 VAT 完整报告。

    Args:
        company_data_json: JSON 字符串，格式同 realCaseData.json

    Returns:
        dict 包含完整分析报告，或 error 字段
    """
    try:
        data = json.loads(company_data_json)
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON: {e}"}

    # 验证必要字段
    if "company" not in data:
        return {"success": False, "error": "Missing 'company' field in data"}

    summary = calculate_vat_return_from_raw(data)
    report = generate_analysis_report(data, summary)
    report["success"] = True

    return report


def load_sample_data() -> dict:
    """加载内置的 TechFlow Distribution Ltd 示例数据。

    Returns:
        示例企业数据 dict
    """
    # 尝试多个可能的路径
    paths = [
        Path(__file__).parent.parent / "data" / "realCaseData.json",
        Path(__file__).parent.parent.parent / "frontend" / "src" / "data" / "realCaseData.json",
        Path(__file__).parent.parent.parent.parent / "frontend" / "src" / "data" / "realCaseData.json",
    ]

    for p in paths:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)

    raise FileNotFoundError("realCaseData.json not found in expected locations")
