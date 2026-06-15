"""UK VAT — Postponed VAT Accounting (PVA) 回归测试

覆盖 HMRC Notice 702/9 的 PVA 处理：非欧盟进口 VAT 递延后，
必须在 VAT Return 中双向申报(Box 1 VAT due + Box 4 input VAT)，
对净 Box 5 自对冲(net zero)。

嘉汉 UK 案例 C1-103: 从中国进口机械设备零部件，
CIF £157,500 × 20% = Import VAT £33,075 走 PVA。

两条计算路径都测：
- calculator.calculate_uk_vat 的 `pva_import_vat` line-item 类别
  (agent 直接调 calculate_vat_return 的场景)
- business_analyzer.analyze_business_data 的 `import_pva` 分支
  (agent 从原始发票数据算 9-Box 的场景，PVA flag 自动检测)
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

import pytest

from backend.models.tax_data import (
    TaxData, TaxpayerInfo, FiscalPeriod, TaxType, LineItem, PeriodType,
)
from backend.jurisdictions.uk.vat.calculator import calculate_uk_vat
from backend.agent.business_analyzer import analyze_business_data


# ── Helpers ──

def _li(category: str, amount) -> LineItem:
    return LineItem(category=category, amount=Decimal(str(amount)), currency="GBP")


def _period() -> FiscalPeriod:
    return FiscalPeriod(
        year=2023,
        period_type=PeriodType.QUARTERLY,
        period_key="23A1",
        start_date=date(2023, 1, 1),
        end_date=date(2023, 3, 31),
    )


def _taxpayer() -> TaxpayerInfo:
    return TaxpayerInfo(name="Jiahang UK Holdings Ltd", tax_id="960606228", tax_id_type="vrn")


def _boxes(calc) -> dict[str, Decimal]:
    return {b.category: b.amount for b in calc.breakdown}


# ── calculator path: pva_import_vat line item ──

def test_calculator_pva_adds_to_box1_and_box4():
    """pva_import_vat 同时加到 Box 1 与 Box 4，Box 5 自对冲不变。

    Q1 口径: 销项 £60,000 + EU RC £10,200(Box 2)
             进项 £10,200(EU RC 对冲) + PVA £33,075
    => Box 1 = 60,000 + 33,075 = 93,075
       Box 4 = 10,200 + 33,075 = 43,275
       Box 5 = |103,275 - 43,275| = 60,000
    """
    data = TaxData(
        tax_type=TaxType.VAT,
        period=_period(),
        taxpayer=_taxpayer(),
        line_items=[
            _li("vat_due_sales", 60000),
            _li("vat_due_acquisitions", 10200),
            _li("vat_reclaimed_purchases", 10200),
            _li("pva_import_vat", 33075),
        ],
    )
    boxes = _boxes(calculate_uk_vat(data))

    assert boxes["vat_due_sales"] == Decimal("93075")
    assert boxes["vat_due_acquisitions"] == Decimal("10200")
    assert boxes["total_vat_due"] == Decimal("103275")
    assert boxes["vat_reclaimed_purchases"] == Decimal("43275")
    assert boxes["net_vat_due"] == Decimal("60000")


def test_calculator_pva_emits_warning():
    """PVA 触发时应附带 HMRC Notice 702/9 说明性 warning。"""
    data = TaxData(
        tax_type=TaxType.VAT,
        period=_period(),
        taxpayer=_taxpayer(),
        line_items=[_li("vat_due_sales", 60000), _li("pva_import_vat", 33075)],
    )
    calc = calculate_uk_vat(data)
    assert any("PVA" in w and "33,075" in w for w in calc.warnings)


def test_calculator_no_pva_unchanged():
    """无 pva_import_vat 时行为与改造前一致(回归保护)。"""
    data = TaxData(
        tax_type=TaxType.VAT,
        period=_period(),
        taxpayer=_taxpayer(),
        line_items=[_li("vat_due_sales", 60000), _li("vat_reclaimed_purchases", 10200)],
    )
    calc = calculate_uk_vat(data)
    boxes = _boxes(calc)
    assert boxes["vat_due_sales"] == Decimal("60000")
    assert boxes["net_vat_due"] == Decimal("49800")
    assert not any("PVA" in w for w in calc.warnings)


def test_calculator_pva_net_zero_invariant():
    """PVA 数额无论多大，对 Box 5 的影响恒为 0(自对冲不变量)。"""
    base = [_li("vat_due_sales", 60000), _li("vat_reclaimed_purchases", 10200)]
    box5_no_pva = _boxes(calculate_uk_vat(TaxData(
        tax_type=TaxType.VAT, period=_period(), taxpayer=_taxpayer(), line_items=base,
    )))["net_vat_due"]

    for pva_amt in (1, 33075, 999999):
        boxes = _boxes(calculate_uk_vat(TaxData(
            tax_type=TaxType.VAT, period=_period(), taxpayer=_taxpayer(),
            line_items=base + [_li("pva_import_vat", pva_amt)],
        )))
        assert boxes["net_vat_due"] == box5_no_pva, f"PVA {pva_amt} 改变了 Box 5"


# ── analyzer path: import_pva branch ──

def test_analyzer_pva_eligible_flag_detected():
    """ImportResult 风格 + pva_eligible 标志 → import_pva 分支，
    递延 Import VAT 进 Box 1 + Box 4。"""
    payload = {
        "company": "Jiahang UK Holdings Ltd",
        "sales": [
            {"id": "S1", "tax_code": "T1-UK-STANDARD", "net_amount": 300000,
             "vat_amount": 60000, "is_eu": False},
        ],
        "purchases": [
            {"id": "C1-103", "tax_code": "T8-UK-IMPORT", "net_amount": 150000,
             "vat_amount": 0, "pva_eligible": True, "pva_import_vat": 33075,
             "is_recoverable": True},
            {"id": "P2", "tax_code": "T1-UK-DOMESTIC-PURCHASE", "net_amount": 50000,
             "vat_amount": 10000, "is_recoverable": True},
        ],
    }
    r = analyze_business_data(json.dumps(payload))
    assert r["success"] is True
    nb = r["nine_box"]
    # Box 1 = 60,000 (sales) + 33,075 (PVA)
    assert nb["vat_due_sales"] == 93075.0
    # Box 4 = 33,075 (PVA) + 10,000 (domestic)
    assert nb["vat_reclaimed_purchases"] == 43075.0
    # Box 5 = |93,075 - 43,075| = 50,000
    assert nb["net_vat_due"] == 50000.0


def test_analyzer_pva_used_alias_detected():
    """realCaseData.json 命名 `pva_used: true` 也应触发 import_pva。"""
    payload = {
        "company": "TechFlow Distribution Ltd",
        "sales": [],
        "purchases": [
            {"id": "PI-003", "tax_code": "T8", "net_amount": 85000,
             "vat_amount": 0, "pva_used": True, "pva_import_vat": 17000,
             "is_recoverable": True},
        ],
    }
    r = analyze_business_data(json.dumps(payload))
    nb = r["nine_box"]
    assert nb["vat_due_sales"] == 17000.0       # Box 1
    assert nb["vat_reclaimed_purchases"] == 17000.0  # Box 4
    assert nb["net_vat_due"] == 0.0             # 自对冲


def test_analyzer_pva_compliance_note_present():
    """PVA 触发时合规注释里应有 Notice 702/9 条目。"""
    payload = {
        "company": "Jiahang UK Holdings Ltd",
        "sales": [],
        "purchases": [
            {"id": "C1-103", "tax_code": "T8-UK-IMPORT", "net_amount": 150000,
             "vat_amount": 0, "pva_eligible": True, "pva_import_vat": 33075,
             "is_recoverable": True},
        ],
    }
    r = analyze_business_data(json.dumps(payload))
    pva_notes = [n for n in r["compliance_notes"] if "PVA" in n["rule"]]
    assert pva_notes, "缺少 PVA compliance note"
    assert "Box 1" in pva_notes[0]["applies_to"]
    assert "Box 4" in pva_notes[0]["applies_to"]


def test_analyzer_import_without_pva_flag_is_plain_import():
    """带 T8 但无 PVA flag → 走普通 import 分支(C79 口径，只进 Box 4)。"""
    payload = {
        "company": "Test Ltd",
        "sales": [],
        "purchases": [
            {"id": "IMP", "tax_code": "T8", "net_amount": 100000,
             "vat_amount": 20000, "is_recoverable": True},
        ],
    }
    r = analyze_business_data(json.dumps(payload))
    nb = r["nine_box"]
    # 普通 import: VAT 只进 Box 4, 不进 Box 1
    assert nb["vat_due_sales"] == 0.0
    assert nb["vat_reclaimed_purchases"] == 20000.0
