#!/usr/bin/env python3
"""
VAT Return 9-Box Calculator — 从发票明细自动计算 HMRC VAT Return

用法:
    python calculate_vat_return.py ../frontend/src/data/realCaseData.json

输出:
    - 9-Box 汇总值
    - HMRC JSON payload
    - 审计追踪
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, asdict
from decimal import Decimal
from pathlib import Path
from typing import Optional


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

    period_key: str = ""


# ── Calculation ──

def calculate_vat_return(data: dict) -> VATSummary:
    """从发票数据计算 VAT Return 9-Box"""

    summary = VATSummary()
    summary.period_key = data["company"]["period"]["period_key"]

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

        if inv_type == "domestic_b2b":
            summary.domestic_sales_net += net
            summary.domestic_sales_vat += vat
            summary.box1_vat_due_sales += vat
            summary.box6_total_sales += int(net)

        elif inv_type == "domestic_b2c":
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
            # 注意：进口商品 Box 7 包含进口净值

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
        # 注意：reverse charge 的服务销售计入 Box 6

    # ── VAT Adjustments ──
    for adj in adjustments:
        amount = Decimal(str(adj.get("amount", 0)))
        adj_type = adj.get("type", "")

        if adj_type == "credit":
            # 坏账减免和注册前 VAT 增加 Box 4 抵扣
            summary.box4_vat_reclaimed += amount
            if "bad debt" in adj.get("description", "").lower():
                summary.bad_debt_relief += amount
            elif "pre-registration" in adj.get("description", "").lower():
                summary.pre_reg_vat += amount

    # ── Box 3 and Box 5 (Auto-calculate) ──
    summary.box3_total_vat_due = (
        summary.box1_vat_due_sales + summary.box2_vat_due_acquisitions
    )
    summary.box5_net_vat_due = abs(summary.box3_total_vat_due - summary.box4_vat_reclaimed)

    return summary


# ── Reporting ──

def print_report(data: dict, summary: VATSummary) -> None:
    """打印详细报告"""
    company = data["company"]
    period = company["period"]

    print("=" * 70)
    print(f"  VAT RETURN CALCULATION REPORT")
    print("=" * 70)
    print(f"  Company:     {company['name']}")
    print(f"  VRN:         {company['vrn']}")
    print(f"  Period:      {period['label']} ({period['start']} to {period['end']})")
    print(f"  Due Date:    {period['due']}")
    print("=" * 70)

    print("\n📊 SALES BREAKDOWN")
    print("-" * 50)
    print(f"  Domestic B2B + B2C (Standard 20%):")
    print(f"    Net value:       £{summary.domestic_sales_net:,.2f}  → Box 6")
    print(f"    VAT charged:     £{summary.domestic_sales_vat:,.2f}  → Box 1")
    print(f"  EU B2B Sales (Zero-rated):")
    print(f"    Net value:       £{summary.eu_sales_net:,.2f}  → Box 8")
    print(f"    VAT:             £0.00 (reverse charge)")
    print(f"  Zero-rated Sales:")
    print(f"    Net value:       £{summary.zero_rated_sales:,.2f}  → Box 6")
    print(f"  Export Sales (Outside EU):")
    print(f"    Net value:       £{summary.export_sales:,.2f}  → Box 6")
    print(f"  ─────────────────────────────────────────")
    print(f"  TOTAL Sales Box 6: £{summary.box6_total_sales:,}")
    print(f"  TOTAL VAT Box 1:   £{summary.box1_vat_due_sales:,.2f}")

    print("\n📦 PURCHASES BREAKDOWN")
    print("-" * 50)
    print(f"  Domestic Purchases:")
    print(f"    Net value:       £{summary.domestic_purchases_net:,.2f}  → Box 7")
    print(f"    VAT reclaimable: £{summary.domestic_purchases_vat:,.2f}  → Box 4")
    print(f"  Import Purchases (from China):")
    print(f"    Net value:       £{summary.import_net:,.2f}  → Box 7")
    print(f"    Import VAT:      £{summary.import_vat:,.2f}  → Box 4 (C79)")
    print(f"  EU Acquisitions:")
    print(f"    Net value:       £{summary.eu_acquisition_net:,.2f}  → Box 7 + Box 9")
    print(f"    Acquisition VAT: £{summary.eu_acquisition_vat:,.2f}  → Box 2 + Box 4")
    print(f"  Recoverable Expenses:")
    print(f"    Net value:       £{summary.expense_net_recoverable:,.2f}  → Box 7")
    print(f"    VAT reclaimable: £{summary.expense_vat_recoverable:,.2f}  → Box 4")
    print(f"  Reverse Charge (Digital Services):")
    print(f"    VAT:             £{summary.reverse_charge_vat:,.2f}  → Box 1 + Box 4")
    print(f"  VAT Adjustments:")
    print(f"    Bad debt relief: £{summary.bad_debt_relief:,.2f}  → Box 4")
    print(f"    Pre-reg VAT:     £{summary.pre_reg_vat:,.2f}  → Box 4")
    print(f"  ─────────────────────────────────────────")
    print(f"  TOTAL Purchases Box 7: £{summary.box7_total_purchases:,}")
    print(f"  TOTAL VAT Box 4:       £{summary.box4_vat_reclaimed:,.2f}")

    print("\n🚫 NON-RECOVERABLE ITEMS (Not in VAT Return)")
    print("-" * 50)
    print(f"  Non-recoverable VAT:     £{summary.non_recoverable_vat:,.2f}")
    print(f"  Exempt purchases:        £{summary.exempt_purchases:,.2f}")
    print(f"  Entertainment expenses:  £{summary.entertainment_expenses:,.2f}")

    print("\n📋 HMRC 9-BOX VAT RETURN")
    print("=" * 50)
    print(f"  ┌─────────────────────────────────────────┐")
    print(f"  │ Box 1  VAT due on sales:      £{summary.box1_vat_due_sales:>10,.2f} │")
    print(f"  │ Box 2  VAT due on acquisitions:£{summary.box2_vat_due_acquisitions:>10,.2f} │")
    print(f"  │ Box 3  Total VAT due:          £{summary.box3_total_vat_due:>10,.2f} │")
    print(f"  │ Box 4  VAT reclaimed:          £{summary.box4_vat_reclaimed:>10,.2f} │")
    print(f"  │ Box 5  Net VAT due:            £{summary.box5_net_vat_due:>10,.2f} │")
    print(f"  ├─────────────────────────────────────────┤")
    print(f"  │ Box 6  Total sales ex VAT:     £{summary.box6_total_sales:>10,} │")
    print(f"  │ Box 7  Total purchases ex VAT: £{summary.box7_total_purchases:>10,} │")
    print(f"  │ Box 8  Goods supplied to EU:   £{summary.box8_goods_supplied_eu:>10,} │")
    print(f"  │ Box 9  Goods acquired from EU: £{summary.box9_goods_acquired_eu:>10,} │")
    print(f"  └─────────────────────────────────────────┘")

    if summary.box3_total_vat_due > summary.box4_vat_reclaimed:
        print(f"\n💰 RESULT: Company OWES HMRC £{summary.box5_net_vat_due:,.2f}")
    elif summary.box3_total_vat_due < summary.box4_vat_reclaimed:
        print(f"\n💰 RESULT: HMRC OWES company £{summary.box5_net_vat_due:,.2f} (repayment)")
    else:
        print(f"\n💰 RESULT: Nil return - no VAT due")

    print("\n📤 HMRC API PAYLOAD")
    print("-" * 50)
    payload = summary.hmrc_payload
    print(json.dumps(payload, indent=2))

    # Save payload to file
    output_path = Path("vat_return_payload.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\n💾 Payload saved to: {output_path.absolute()}")


# ── Main ──

def main() -> int:
    if len(sys.argv) < 2:
        data_path = Path(__file__).parent.parent / "frontend" / "src" / "data" / "realCaseData.json"
    else:
        data_path = Path(sys.argv[1])

    if not data_path.exists():
        print(f"❌ File not found: {data_path}")
        return 1

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    summary = calculate_vat_return(data)
    print_report(data, summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())
