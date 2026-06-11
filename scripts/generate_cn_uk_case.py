"""中资跨境案例生成器 — 母公司（深圳中科智造）→ UK 子公司（TechFlow UK Ltd）Q1 2026

业务范围：UK 子公司 Q1 2026 的所有 VAT 相关业务事件，覆盖 9-Box 全部字段。
从原始凭证（采购订单、销售订单、海关 C79、银行回单、集团内部发票、费用报销）出发，
按 UK VAT MTD 规则推导出：
  1. transactions.json      - 原始业务事件（smart-analyzer 输入格式）
  2. ledger.csv             - 标准化后的 CSV（CSV parser 输入）
  3. erp_import.json        - 模拟 ERP 系统的 9-Box 自报值（带故意小差异）
  4. expected_nine_box.json - T.A.X.I. 算法的预期 9-Box
  5. source_docs/*.json     - 每张发票对应的"原始凭证"占位

VAT 处理规则（UK 9-Box 简表）：
  T1 (domestic standard 20%)   → Box1 (+vat), Box4 (-vat if recoverable), Box6 (sales) / Box7 (purchases)
  T0 (zero-rated / exempt)     → Box6 (sales) / Box7 (purchases, 不影响 Box4)
  T9 (EU B2B reverse charge)   → Box8 (sales net) - 不进 Box1
  T2 (EU acquisition RC)       → Box2 (+acq_vat), Box4 (-acq_vat), Box7 (net), Box9 (EU goods)
  T8 (import from third country) → Box4 (-import_vat from C79), Box7 (net)
  bad debt relief / credit note → 反向影响 Box1/Box4

Usage:
  python scripts/generate_cn_uk_case.py
"""
import json
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "erp_samples" / "cn_parent_uk_sub_q1_2026"
SOURCE_DOCS_DIR = OUT_DIR / "source_docs"

D = Decimal
TWO = D("0.20")
ZERO = D("0.00")

# ════════════════════════════════════════════════════════════
# 1. 公司元数据
# ════════════════════════════════════════════════════════════

COMPANY = {
    "name": "TechFlow UK Ltd",
    "registered_name": "TechFlow UK Limited",
    "vrn": "GB123456789",
    "company_number": "12345678",
    "address": "88 City Road, London EC1Y 2AA, United Kingdom",
    "vat_scheme": "standard",
    "industry": "import_trade",
    "period": {
        "label": "Q1 2026",
        "period_key": "26A1",
        "start": "2026-01-01",
        "end": "2026-03-31",
        "due": "2026-05-07",
    },
    "parent_company": {
        "name": "Shenzhen ZK Smart Manufacturing Co., Ltd",
        "name_cn": "深圳中科智造科技有限公司",
        "address": "Block C, Bao'an Industrial Park, Shenzhen, China",
        "unified_social_credit_code": "91440300MA5GXXXXX",
        "relationship": "100% parent / sole shareholder",
    },
}

# ════════════════════════════════════════════════════════════
# 2. 销售发票（25 笔，覆盖 T1/T0/T9 三类）
# ════════════════════════════════════════════════════════════

# 每笔：(id, date, counterparty, net, vat_rate, tax_code, type, is_eu, is_rc, scenario_note)
# 净金额用 round 的整数英镑，方便 Box6/Box8/Box9 的 int() 转换
def gbp(amount):
    """把字符串/数字转成 Decimal，保留 2 位"""
    return D(str(amount)).quantize(D("0.01"), rounding=ROUND_HALF_UP)


SALES_INVOICES = [
    # ── 国内标准 20% (T1) ── 10 笔
    ("SI-2026-001", "2026-01-08", "Currys PC World",         12500, TWO, "T1", "domestic_b2b",  False, False, "high-street retailer, B2B"),
    ("SI-2026-002", "2026-01-12", "Amazon UK Marketplace",   8750,  TWO, "T1", "domestic_b2b",  False, False, "online marketplace B2B"),
    ("SI-2026-003", "2026-01-15", "John Lewis Partnership",  18750, TWO, "T1", "domestic_b2c",  False, False, "department store B2C"),
    ("SI-2026-004", "2026-01-18", "Argos Ltd",               15200, TWO, "T1", "domestic_b2b",  False, False, "high-street B2B"),
    ("SI-2026-005", "2026-01-22", "eBay UK Seller Hub",      6300,  TWO, "T1", "domestic_b2c",  False, False, "online B2C"),
    ("SI-2026-006", "2026-01-25", "Tesco Direct",            22000, TWO, "T1", "domestic_b2b",  False, False, "supermarket B2B"),
    ("SI-2026-008", "2026-02-03", "B&Q (Kingfisher)",        9500,  TWO, "T1", "domestic_b2b",  False, False, "DIY retailer"),
    ("SI-2026-010", "2026-02-12", "Currys PC World",         7800,  TWO, "T1", "domestic_b2b",  False, False, "repeat customer"),
    ("SI-2026-014", "2026-02-22", "Wickes (Travis Perkins)", 4400,  TWO, "T1", "domestic_b2b",  False, False, "trade buyer"),
    ("SI-2026-020", "2026-03-18", "Selfridges & Co",         11250, TWO, "T1", "domestic_b2c",  False, False, "high-end B2C"),
    # ── 零税率 T0 (食品/童装/书籍) ── 4 笔
    ("SI-2026-007", "2026-01-29", "Holland & Barrett",       4800,  ZERO, "T0", "zero_rated",  False, False, "零税率健康食品 (food)"),
    ("SI-2026-013", "2026-02-18", "Waterstones Booksellers", 3200,  ZERO, "T0", "zero_rated",  False, False, "零税率书籍"),
    ("SI-2026-018", "2026-03-05", "M&S Food",                5600,  ZERO, "T0", "zero_rated",  False, False, "零税率食品"),
    ("SI-2026-022", "2026-03-24", "Mothercare UK",           2400,  ZERO, "T0", "zero_rated",  False, False, "零税率童装"),
    # ── 欧盟 B2B reverse charge (T9) ── 5 笔
    ("SI-2026-009", "2026-02-08", "TechDealer GmbH (DE)",   12500, ZERO, "T9", "eu_b2b", True, True,  "DE B2B reverse charge"),
    ("SI-2026-015", "2026-02-26", "ElectroPart SAS (FR)",    7400, ZERO, "T9", "eu_b2b", True, True,  "FR B2B reverse charge"),
    ("SI-2026-016", "2026-03-02", "Nordic Tech ApS (DK)",    5100, ZERO, "T9", "eu_b2b", True, True,  "DK B2B (post-Brexit: 第三方不算 EU acquisiton, 算出口)"),
    ("SI-2026-019", "2026-03-12", "TechDealer GmbH (DE)",    9800, ZERO, "T9", "eu_b2b", True, True,  "DE 复购"),
    ("SI-2026-021", "2026-03-20", "ElectroPart SAS (FR)",    6300, ZERO, "T9", "eu_b2b", True, True,  "FR 复购"),
    # ── 集团内部销售 (中国母公司 → UK 子公司, T9 reverse charge) ── 2 笔
    ("SI-2026-IC-001", "2026-01-05", "Shenzhen ZK Smart Mfg (parent, CN→UK)", 45000, ZERO, "T9", "intra_group", True, True,  "集团内部调拨 (parent sells to UK sub, intra-group transfer)"),
    ("SI-2026-IC-002", "2026-02-15", "Shenzhen ZK Smart Mfg (parent, CN→UK)", 32000, ZERO, "T9", "intra_group", True, True,  "集团内部调拨 2 月"),
    # ── 出口 (USA / Australia, T0 outside scope) ── 2 笔
    ("SI-2026-011", "2026-02-14", "Pacific Trading Inc (USA)", 18500, ZERO, "T0", "export",  False, False, "USA 出口, outside scope"),
    ("SI-2026-017", "2026-03-04", "Aussie Distributors Pty (AU)", 9800,  ZERO, "T0", "export",  False, False, "AU 出口, outside scope"),
    # ── Credit note (退货，红字发票) ── 1 笔
    ("CN-2026-001",  "2026-02-20", "Currys PC World (credit note for SI-2026-001)", 2500, TWO, "T1", "credit_note", False, False, "退货 - 200 件"),
]

# ════════════════════════════════════════════════════════════
# 3. 采购发票（20 笔）
# ════════════════════════════════════════════════════════════
# (id, date, counterparty, net, vat_rate, tax_code, type, is_recoverable, is_eu_acq, note)

PURCHASE_INVOICES = [
    # ── UK 本地采购 (T1, recoverable) ── 8 笔
    ("PI-2026-001", "2026-01-10", "Office Supplies Co Ltd",        850,   TWO, "T1", "domestic",  True,  False, "办公用品"),
    ("PI-2026-002", "2026-01-14", "British Telecom",               1200,  TWO, "T1", "domestic",  True,  False, "电话费"),
    ("PI-2026-003", "2026-01-20", "Thames Water",                  480,   TWO, "T1", "domestic",  True,  False, "水费 (utilities)"),
    ("PI-2026-004", "2026-01-28", "EDF Energy",                    1750,  TWO, "T1", "domestic",  True,  False, "电费 (warehouse)"),
    ("PI-2026-006", "2026-02-05", "DHL Parcel UK",                 620,   TWO, "T1", "domestic",  True,  False, "本地快递"),
    ("PI-2026-008", "2026-02-12", "Staples UK",                    1450,  TWO, "T1", "domestic",  True,  False, "办公耗材"),
    ("PI-2026-013", "2026-02-28", "SSE Energy",                    2100,  TWO, "T1", "domestic",  True,  False, "电费 (2月)"),
    ("PI-2026-017", "2026-03-15", "Vodafone UK Business",          980,   TWO, "T1", "domestic",  True,  False, "移动通信"),
    # ── 欧盟采购 reverse charge (T2, EU acquisition) ── 3 笔
    ("PI-2026-EU-001", "2026-01-22", "Bremen Steel GmbH (DE)",       8000,  TWO, "T2", "eu_acquisition", True, True,  "DE 钢铁原料"),
    ("PI-2026-EU-002", "2026-02-18", "Milano Components SpA (IT)",   4500,  TWO, "T2", "eu_acquisition", True, True,  "IT 电子元件"),
    ("PI-2026-EU-003", "2026-03-08", "Lyon Logistics SAS (FR)",      3200,  TWO, "T2", "eu_acquisition", True, True,  "FR 物流服务"),
    # ── 从中国母公司进口 (T8, import from non-EU, C79 VAT) ── 4 笔
    ("PI-2026-IMP-001", "2026-01-18", "Shenzhen ZK Smart Mfg (parent, CN→UK)", 22000, TWO, "T8", "import", True,  False, "母公司货物进口 - C79 凭证 VAT £4400"),
    ("PI-2026-IMP-002", "2026-02-08", "Shenzhen ZK Smart Mfg (parent, CN→UK)", 15000, TWO, "T8", "import", True,  False, "母公司货物进口 2月 - C79 VAT £3000"),
    ("PI-2026-IMP-003", "2026-02-25", "Shenzhen ZK Smart Mfg (parent, CN→UK)", 18000, TWO, "T8", "import", True,  False, "母公司货物进口 2月下 - C79 VAT £3600"),
    ("PI-2026-IMP-004", "2026-03-12", "Shenzhen ZK Smart Mfg (parent, CN→UK)", 12500, TWO, "T8", "import", True,  False, "母公司货物进口 3月 - C79 VAT £2500"),
    # ── 豁免/非应税 (T0) ── 2 笔
    ("PI-2026-EX-001", "2026-01-31", "HSBC Bank plc",                 350,   ZERO, "T0", "exempt", False, False, "银行手续费 - 不可抵扣"),
    ("PI-2026-EX-002", "2026-02-28", "Aviva Insurance UK",            1200,  ZERO, "T0", "exempt", False, False, "商业保险 - 不可抵扣"),
    # ── 不可抵扣 (T0 non-recoverable) ── 2 笔
    ("PI-2026-NR-001", "2026-02-14", "The Ritz Hotel London",        2500,  TWO, "T0", "non_recoverable", False, False, "客户招待 entertainment - VAT 不可抵扣"),
    ("PI-2026-NR-002", "2026-03-10", "Fortnum & Mason (entertainment)",  1200,  TWO, "T0", "non_recoverable", False, False, "礼品采购 - VAT 不可抵扣"),
    # ── 资本货物 (T1, capital goods scheme 适用) ── 1 笔
    ("PI-2026-CAP-001", "2026-02-20", "Mercedes-Benz Retail UK Ltd",  32000, TWO, "T1", "capital", True,  False, "商用 van (Capital Goods Scheme 触发点)"),
]

# ════════════════════════════════════════════════════════════
# 4. 集团内部往来（跨境 B2B 关联方，transfer pricing 留痕）
# ════════════════════════════════════════════════════════════

INTRA_GROUP = [
    {
        "id": "IG-2026-001",
        "date": "2026-01-31",
        "type": "management_fee",  # 管理服务费
        "from": "TechFlow UK Ltd",
        "to":   "Shenzhen ZK Smart Manufacturing Co., Ltd",
        "net": 6500,
        "vat": 0,
        "note": "Group management fee - transfer pricing study on file (mark-up 8%)",
    },
    {
        "id": "IG-2026-002",
        "date": "2026-02-28",
        "type": "royalty",  # 特许权使用费
        "from": "TechFlow UK Ltd",
        "to":   "Shenzhen ZK Smart Manufacturing Co., Ltd",
        "net": 4200,
        "vat": 0,
        "note": "Brand royalty - transfer pricing study on file (royalty rate 4%)",
    },
    {
        "id": "IG-2026-003",
        "date": "2026-03-31",
        "type": "management_fee",
        "from": "TechFlow UK Ltd",
        "to":   "Shenzhen ZK Smart Manufacturing Co., Ltd",
        "net": 6500,
        "vat": 0,
        "note": "Group management fee Q1 - arm's length basis",
    },
]

# ════════════════════════════════════════════════════════════
# 5. 费用报销 (expense_claims)
# ════════════════════════════════════════════════════════════

EXPENSE_CLAIMS = [
    {"id": "EX-2026-001", "date": "2026-01-15", "employee": "J. Smith (sales rep)", "category": "travel",
     "net": 285, "vat": 57, "recoverable": True,  "note": "Train tickets to client meeting"},
    {"id": "EX-2026-002", "date": "2026-01-22", "employee": "J. Smith", "category": "subsistence",
     "net": 42,  "vat": 0, "recoverable": False, "note": "Lunch with client (entertainment)"},
    {"id": "EX-2026-003", "date": "2026-02-08", "employee": "K. Chen (warehouse mgr)", "category": "travel",
     "net": 320, "vat": 64, "recoverable": True,  "note": "Hotel + train for supplier visit"},
    {"id": "EX-2026-004", "date": "2026-02-19", "employee": "J. Smith", "category": "entertainment",
     "net": 180, "vat": 36, "recoverable": False, "note": "Client dinner - non-recoverable"},
    {"id": "EX-2026-005", "date": "2026-03-12", "employee": "K. Chen", "category": "travel",
     "net": 410, "vat": 82, "recoverable": True,  "note": "Trade show Birmingham"},
]

# ════════════════════════════════════════════════════════════
# 6. 原始凭证占位（每张关键发票对应的文档引用）
# ════════════════════════════════════════════════════════════

SOURCE_DOCS = [
    {"doc_id": "INV-CN-2026-001", "type": "commercial_invoice",  "ref": "PI-2026-IMP-001", "issuer": "Shenzhen ZK Smart Mfg", "issued": "2026-01-10", "amount_gbp": 26400, "customs_ref": "C79-2026-001"},
    {"doc_id": "C79-2026-001",     "type": "c79_certificate",      "ref": "PI-2026-IMP-001", "period": "2026-01", "vat_paid": 4400, "importer_eori": "GB123456789000"},
    {"doc_id": "INV-CN-2026-002", "type": "commercial_invoice",  "ref": "PI-2026-IMP-002", "issuer": "Shenzhen ZK Smart Mfg", "issued": "2026-02-01", "amount_gbp": 18000, "customs_ref": "C79-2026-002"},
    {"doc_id": "C79-2026-002",     "type": "c79_certificate",      "ref": "PI-2026-IMP-002", "period": "2026-02", "vat_paid": 3000, "importer_eori": "GB123456789000"},
    {"doc_id": "INV-CN-2026-003", "type": "commercial_invoice",  "ref": "PI-2026-IMP-003", "issuer": "Shenzhen ZK Smart Mfg", "issued": "2026-02-20", "amount_gbp": 21600, "customs_ref": "C79-2026-003"},
    {"doc_id": "C79-2026-003",     "type": "c79_certificate",      "ref": "PI-2026-IMP-003", "period": "2026-02", "vat_paid": 3600, "importer_eori": "GB123456789000"},
    {"doc_id": "INV-CN-2026-004", "type": "commercial_invoice",  "ref": "PI-2026-IMP-004", "issuer": "Shenzhen ZK Smart Mfg", "issued": "2026-03-08", "amount_gbp": 15000, "customs_ref": "C79-2026-004"},
    {"doc_id": "C79-2026-004",     "type": "c79_certificate",      "ref": "PI-2026-IMP-004", "period": "2026-03", "vat_paid": 2500, "importer_eori": "GB123456789000"},
    {"doc_id": "PO-CN-2026-Q1",   "type": "purchase_order",       "ref": "PI-2026-IMP-001..004", "total_gbp": 67500, "currency": "GBP", "incoterm": "FOB Shenzhen"},
    {"doc_id": "TP-2026-Q1",      "type": "transfer_pricing_study", "ref": "IG-2026-001..003", "method": "TNMM", "markup_pct": 8.0, "study_date": "2025-12-15"},
    {"doc_id": "BNK-2026-Q1-01",  "type": "bank_statement",        "ref": "all", "period": "Q1 2026", "opening_balance_gbp": 125000, "closing_balance_gbp": 152340},
    {"doc_id": "VAT-MTD-2025-Q4", "type": "vat_return_previous",   "ref": "Q4 2025", "net_vat_due": 8920, "submitted_date": "2026-02-05"},
]


# ════════════════════════════════════════════════════════════
# 7. 计算 T.A.X.I. 9-Box（与 reconcile.compute_taxi_nine_box 同源）
# ════════════════════════════════════════════════════════════

def compute_expected_nine_box(sales, purchases, expense_claims, intra_group=None):
    """手算 + 算法双验的预期 9-Box（口径与 backend/erp/reconcile.compute_taxi_nine_box 完全一致）。

    算法 v0 限制（来自 reconcile.py）：
      - box1: sum(vat_amount where vat_rate > 0)，含 credit note 的正数 vat
      - box4: sum(vat_amount where is_recoverable)，不读 expense_claims
      - box6/7/8/9: 无脑 sum net（box6 含 credit note 的 net）

    注：case 里如果想"正确"扣减 credit note，erp_import.json 不应包含它（让它走 sales side 的反向调整）。
    本案例的做法：把 credit note 移到 erp_import.json 的 metadata 里（不参与算法），体现
    "ERP 漏处理 credit note" 这个真实场景。
    """
    # 销售侧 — 与算法一致：只看 vat_rate > 0
    box1 = sum((gbp(s["net"]) * D(str(s["vat_rate"])) for s in sales if s["vat_rate"] > 0), ZERO)
    # 采购侧 - box2 (EU acquisition vat)
    box2 = sum((gbp(p["net"]) * D(str(p["vat_rate"])) for p in purchases if p.get("is_eu_acquisition")), ZERO)
    # 采购侧 - box4 (recoverable vat) - 与算法一致
    box4 = sum(
        (gbp(p["net"]) * D(str(p["vat_rate"])) for p in purchases if p.get("is_recoverable", False)),
        ZERO,
    )
    box3 = box1 + box2
    box5 = abs(box3 - box4)
    box6 = int(sum((gbp(s["net"]) for s in sales), ZERO))
    box7 = int(sum((gbp(p["net"]) for p in purchases), ZERO))
    box8 = int(sum((gbp(s["net"]) for s in sales if s.get("is_eu", False)), ZERO))
    box9 = int(sum((gbp(p["net"]) for p in purchases if p.get("is_eu_acquisition", False)), ZERO))
    return {
        "box1_vat_due_sales":      str(box1.quantize(D("0.01"))),
        "box2_vat_due_acquisitions": str(box2.quantize(D("0.01"))),
        "box3_total_vat_due":      str(box3.quantize(D("0.01"))),
        "box4_vat_reclaimed":      str(box4.quantize(D("0.01"))),
        "box5_net_vat_due":        str(box5.quantize(D("0.01"))),
        "box6_total_sales_ex_vat": box6,
        "box7_total_purchases_ex_vat": box7,
        "box8_total_goods_supplied_eu": box8,
        "box9_total_goods_acquired_eu": box9,
    }


# ════════════════════════════════════════════════════════════
# 8. 主流程
# ════════════════════════════════════════════════════════════

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SOURCE_DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # ── 8.1 转换为完整 sales / purchases dict ──
    sales_full = []
    for (sid, dt, cp, net, rate, code, typ, is_eu, is_rc, note) in SALES_INVOICES:
        net_d = gbp(net)
        vat_d = (net_d * rate).quantize(D("0.01"))
        gross_d = net_d + vat_d
        sales_full.append({
            "id": sid, "txn_date": dt, "counterparty": cp,
            "net": float(net_d), "vat": float(vat_d), "gross": float(gross_d),
            "net_gbp": float(net_d), "vat_gbp": float(vat_d), "gross_gbp": float(gross_d),
            "vat_rate": float(rate), "tax_code": code, "type": typ,
            "currency": "GBP",
            "is_eu": is_eu, "is_reverse_charge": is_rc,
            "scenario_note": note,
        })

    purchases_full = []
    for (pid, dt, cp, net, rate, code, typ, is_rec, is_eu, note) in PURCHASE_INVOICES:
        net_d = gbp(net)
        vat_d = (net_d * rate).quantize(D("0.01"))
        gross_d = net_d + vat_d
        # 兼容 business_analyzer 字段命名
        rec = {
            "id": pid, "txn_date": dt, "counterparty": cp,
            "net": float(net_d), "vat": float(vat_d), "gross": float(gross_d),
            "net_gbp": float(net_d), "vat_gbp": float(vat_d), "gross_gbp": float(gross_d),
            "vat_rate": float(rate), "tax_code": code, "type": typ,
            "currency": "GBP",
            "recoverable": is_rec, "is_recoverable": is_rec,
            "is_eu_acquisition": is_eu,
            "scenario_note": note,
        }
        # EU acquisition: business_analyzer 用 'acquisition_vat'
        if typ == "eu_acquisition":
            rec["acquisition_vat"] = float(vat_d)
        purchases_full.append(rec)

    # ── 8.2 transactions.json（business_analyzer / agent 输入） ──
    transactions = {
        "company": COMPANY,
        "sales_invoices": sales_full,
        "purchase_invoices": purchases_full,
        "expense_claims": EXPENSE_CLAIMS,
        "reverse_charge_transactions": [],  # 跨境服务 RC 不在 9-Box, v0 留空
        "vat_adjustments": [],  # v0 暂不演示 bad debt relief
        "intra_group_transactions": INTRA_GROUP,
        "source_documents": SOURCE_DOCS,
        "metadata": {
            "case_id": "cn_parent_uk_sub_q1_2026",
            "description": "TechFlow UK Ltd Q1 2026 VAT Return - 母公司 Shenzhen ZK Smart Mfg",
            "group_structure": "CN parent (100%) → UK sub (TechFlow UK Ltd)",
            "expected_nine_box": "see expected_nine_box.json",
            "ledger_csv": "ledger.csv",
            "currency": "GBP",
            "tax_period": "Q1 2026 (Jan 1 - Mar 31)",
            "filing_deadline": "2026-05-07",
        },
    }
    (OUT_DIR / "transactions.json").write_text(
        json.dumps(transactions, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ── 8.3 ledger.csv（CSV parser 通用格式） ──
    # credit note 不在 CSV 里：算法 v0 假设 ERP 喂入的 sales 列表是"已净额化"的
    sales_for_ledger = [s for s in sales_full if s["type"] != "credit_note"]
    credit_notes = [s for s in sales_full if s["type"] == "credit_note"]
    csv_lines = ["txn_date,txn_type,counterparty,net,vat,gross,vat_rate,tax_code"]
    for s in sales_for_ledger:
        csv_lines.append(f"{s['txn_date']},sale,\"{s['counterparty']}\",{s['net']},{s['vat']},{s['gross']},{s['vat_rate']},{s['tax_code']}")
    for p in purchases_full:
        csv_lines.append(f"{p['txn_date']},purchase,\"{p['counterparty']}\",{p['net']},{p['vat']},{p['gross']},{p['vat_rate']},{p['tax_code']}")
    (OUT_DIR / "ledger.csv").write_text("\n".join(csv_lines) + "\n", encoding="utf-8")

    # ── 8.4 expected_nine_box.json ──
    expected = compute_expected_nine_box(sales_for_ledger, purchases_full, EXPENSE_CLAIMS, INTRA_GROUP)
    expected_full = {
        **expected,
        "scheme_flags": [
            "Capital Goods Scheme (PI-2026-CAP-001, van > £50k threshold - 5yr adjustment)",
            "Reverse Charge on intra-group B2B services (IG-2026-* - not in 9-Box, EC Sales List disclosure required)",
            "C79 import VAT (PI-2026-IMP-001..004) - Box 4 reclaim subject to >£1k/month rule",
        ],
    }
    (OUT_DIR / "expected_nine_box.json").write_text(
        json.dumps(expected_full, indent=2), encoding="utf-8"
    )

    # ── 8.5 erp_import.json（模拟 ERP 系统的 9-Box 自报值，带故意小差异） ──
    # 真实场景的常见错误：ERP 把 credit note 漏处理，box1 算重 +500 / box6 算重 +2500
    #
    # 案例建模：credit note 不出现在 erp_import.json 的 sales 列表里（已净额化的"干净"销售流）
    #   → T.A.X.I. 算法 box1 = 23290（仅 10 笔 T1 sales VAT）
    #   → ERP 报   box1 = 23790（漏扣 credit note VAT 500）→ 差异 +500
    #   → T.A.X.I. 算法 box6 = 278850
    #   → ERP 报   box6 = 281350（漏扣 credit note net 2500）→ 差异 +2500
    #
    sales_for_erp = [s for s in sales_full if s["type"] != "credit_note"]
    credit_notes = [s for s in sales_full if s["type"] == "credit_note"]

    erp_boxes = dict(expected)
    # T.A.X.I. 算法口径：算法会自动把 credit note 不算进来（它不在 sales 里），
    # 所以 expected box1=23290 / box6=278850
    # ERP 报"漏扣"值：+500 / +2500
    erp_boxes["box1_vat_due_sales"] = str(
        (D("23290.00") + D("500.00")).quantize(D("0.01"))
    )
    erp_boxes["box6_total_sales_ex_vat"] = 278850 + 2500  # = 281350

    erp_import = {
        "sales": [
            {
                "id": s["id"], "txn_date": s["txn_date"], "counterparty": s["counterparty"],
                "net_amount": str(D(s["net"]).quantize(D("0.01"))),
                "vat_amount": str(D(s["vat"]).quantize(D("0.01"))),
                "gross_amount": str(D(s["gross"]).quantize(D("0.01"))),
                "vat_rate": str(D(s["vat_rate"]).quantize(D("0.01"))),
                "tax_code": s["tax_code"],
                "is_eu": s["is_eu"], "is_reverse_charge": s["is_reverse_charge"],
            } for s in sales_for_erp
        ],
        "purchases": [
            {
                "id": p["id"], "txn_date": p["txn_date"], "counterparty": p["counterparty"],
                "net_amount": str(D(p["net"]).quantize(D("0.01"))),
                "vat_amount": str(D(p["vat"]).quantize(D("0.01"))),
                "gross_amount": str(D(p["gross"]).quantize(D("0.01"))),
                "vat_rate": str(D(p["vat_rate"]).quantize(D("0.01"))),
                "tax_code": p["tax_code"],
                "is_recoverable": p["is_recoverable"],
                "is_eu_acquisition": p["is_eu_acquisition"],
            } for p in purchases_full
        ],
        "erp_provided_boxes": {
            **{k: (v if not isinstance(v, str) else v) for k, v in erp_boxes.items()},
            "scheme_flags": [
                "Capital Goods Scheme (van > £50k threshold)",
                "C79 import VAT reclaim",
                "Intra-group B2B transfer pricing (not in 9-Box)",
            ],
        },
        "source_profile": "demo",
        "source_filename": "cn_parent_uk_sub_q1_2026.json",
        "source_hash": "cn-uk-q1-2026-v1",
        "warnings": [
            "ERP box1 calculation: credit note CN-2026-001 was NOT netted off (suspense posting under review)",
            "ERP box6 calculation: credit note CN-2026-001 net still in box6 total",
        ],
        "rejected_rows": [],
        "credit_notes_excluded": [
            {"id": c["id"], "date": c["txn_date"], "net": c["net"], "vat": c["vat"], "reason": "ERP rejected the row - not in 9-Box input"}
            for c in credit_notes
        ],
        "metadata": {
            "company": COMPANY,
            "intra_group_transactions": INTRA_GROUP,
            "source_documents": SOURCE_DOCS,
        },
    }
    # 把 scheme_flags 单独抽出来 (ERPNineBox.scheme_flags 字段)
    erp_import["erp_provided_boxes"]["scheme_flags"] = [
        "Capital Goods Scheme (van > £50k threshold)",
        "C79 import VAT reclaim",
        "Intra-group B2B transfer pricing (not in 9-Box)",
    ]
    (OUT_DIR / "erp_import.json").write_text(
        json.dumps(erp_import, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ── 8.6 source_docs/*.json（每张关键凭证） ──
    for doc in SOURCE_DOCS:
        (SOURCE_DOCS_DIR / f"{doc['doc_id']}.json").write_text(
            json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # ── 8.7 case_summary.json（机器可读的案例摘要，给 agent / 文档用） ──
    summary = {
        "case_id": "cn_parent_uk_sub_q1_2026",
        "title": "中资跨境 VAT Q1 2026 — Shenzhen ZK Smart Mfg 母公司 → TechFlow UK Ltd 子公司",
        "company": COMPANY["name"],
        "vrn": COMPANY["vrn"],
        "period": COMPANY["period"]["label"],
        "period_key": COMPANY["period"]["period_key"],
        "filing_deadline": COMPANY["period"]["due"],
        "counts": {
            "sales_invoices": len(sales_full),
            "purchase_invoices": len(purchases_full),
            "expense_claims": len(EXPENSE_CLAIMS),
            "intra_group_transactions": len(INTRA_GROUP),
            "source_documents": len(SOURCE_DOCS),
        },
        "scenarios_covered": [
            "T1 domestic standard 20% (B2B + B2C)",
            "T0 zero-rated (food/books/children clothing)",
            "T9 EU B2B reverse charge (DE/FR/DK)",
            "Intra-group transfer (parent CN→UK sub)",
            "Export outside scope (USA/AU)",
            "T2 EU acquisition reverse charge (DE/IT/FR)",
            "T8 import from third country (CN→UK) with C79 reclaim",
            "T0 exempt purchases (bank fees, insurance) - non-recoverable",
            "T0 non-recoverable (entertainment)",
            "T1 capital goods scheme (van > £50k threshold)",
            "Credit note (sales return)",
            "Transfer pricing (management fee, royalty) - disclosure",
        ],
        "expected_nine_box": expected,
        "expected_files": [
            "transactions.json (raw business data for business_analyzer)",
            "ledger.csv (CSV parser input)",
            "erp_import.json (ImportResult with ERP-provided 9-Box + small discrepancy)",
            "expected_nine_box.json (T.A.X.I. computed 9-Box)",
            "source_docs/*.json (12 source documents)",
        ],
    }
    (OUT_DIR / "case_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ── 8.8 Print human summary ──
    print("=" * 70)
    print(f"案例生成: {OUT_DIR}")
    print("=" * 70)
    print(f"销售发票:   {len(sales_full)} 笔  (T1/T0/T9/出口/集团/credit note)")
    print(f"采购发票:   {len(purchases_full)} 笔 (T1/T2/T8/T0/资本/非抵扣)")
    print(f"费用报销:   {len(EXPENSE_CLAIMS)} 笔 (可抵扣/不可抵扣)")
    print(f"集团内部:   {len(INTRA_GROUP)} 笔 (管理费 + 特许权使用费)")
    print(f"原始凭证:   {len(SOURCE_DOCS)} 份 (C79 / 商业发票 / PO / TP / 银行)")
    print("-" * 70)
    print("预期 9-Box (T.A.X.I. 算法):")
    for k, v in expected.items():
        if isinstance(v, str):
            print(f"  {k:35s} = £{v}")
        else:
            print(f"  {k:35s} = {v:,}")
    print("-" * 70)
    print("ERP 9-Box (故意小差异: box1 未扣 credit note):")
    erp_box1 = erp_boxes["box1_vat_due_sales"]
    expected_box1 = expected["box1_vat_due_sales"]
    print(f"  box1  ERP=£{erp_box1}  T.A.X.I.=£{expected_box1}  Δ=£{D(erp_box1) - D(expected_box1)}")
    print(f"  box4  ERP=£{erp_boxes['box4_vat_reclaimed']}  T.A.X.I.=£{expected['box4_vat_reclaimed']}  Δ=£0.00")


if __name__ == "__main__":
    main()
