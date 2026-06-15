"""UK VAT Validator — 结构性交叉核对回归测试

覆盖 `validate_uk_vat` 中新增的硬规则:
- EU 取得对称性(Box 2 ↔ Box 9)
- 进项 VAT vs 采购额(Box 4 ↔ Box 7)
- Box 3 = Box 1 + Box 2
- Box 5 = |Box 3 − Box 4|
- Box 1 > 0 但 Box 6 = 0(保留)
"""
from decimal import Decimal
from datetime import date

import pytest

from backend.models.tax_data import TaxData, TaxpayerInfo, FiscalPeriod, TaxType, LineItem, PeriodType
from backend.jurisdictions.uk.vat.validator import validate_uk_vat


def _data(boxes: dict) -> TaxData:
    """从 9-Box 字典构造最小 TaxData"""
    return TaxData(
        tax_type=TaxType.VAT,
        period=FiscalPeriod(
            year=2023, period_type=PeriodType.QUARTERLY,
            period_key="23A1", start_date=date(2023, 1, 1), end_date=date(2023, 3, 31),
        ),
        taxpayer=TaxpayerInfo(name="Test", tax_id="123456789", tax_id_type="vrn"),
        line_items=[
            LineItem(category=k, amount=Decimal(str(v)), currency="GBP")
            for k, v in boxes.items()
        ],
    )


def _fields(report) -> set:
    return {w.field for w in report.warnings}


# ── EU Acquisition Symmetry ──

def test_warns_when_box9_positive_but_box2_zero():
    """Box 9 > 0 但 Box 2 = 0 → 反向征收申报侧可能漏填。"""
    d = _data({
        "vat_due_sales": 60000,
        "vat_due_acquisitions": 0,
        "total_vat_due": 60000,
        "vat_reclaimed_purchases": 51840,
        "net_vat_due": 8160,
        "total_sales_ex_vat": 300000,
        "total_purchases_ex_vat": 200000,
        "total_goods_supplied_eu": 0,
        "total_goods_acquired_eu": 51000,  # C1-106 EU RC 进了 Box 9
    })
    r = validate_uk_vat(d)
    assert "vat_due_acquisitions" in _fields(r)
    assert any("Box 9" in w.message and "Box 2" in w.message for w in r.warnings)


def test_warns_when_box2_positive_but_box9_zero():
    """Box 2 > 0 但 Box 9 = 0 → 货物净额未报。"""
    d = _data({
        "vat_due_sales": 60000,
        "vat_due_acquisitions": 10200,
        "total_vat_due": 70200,
        "vat_reclaimed_purchases": 43275,
        "net_vat_due": 26925,
        "total_sales_ex_vat": 300000,
        "total_purchases_ex_vat": 200000,
        "total_goods_supplied_eu": 0,
        "total_goods_acquired_eu": 0,  # 漏报
    })
    r = validate_uk_vat(d)
    assert "total_goods_acquired_eu" in _fields(r)


def test_no_symmetry_warning_when_both_present():
    """Box 2 和 Box 9 都有 → 无警告。"""
    d = _data({
        "vat_due_sales": 60000,
        "vat_due_acquisitions": 10200,
        "total_vat_due": 70200,
        "vat_reclaimed_purchases": 43275,
        "net_vat_due": 26925,
        "total_sales_ex_vat": 300000,
        "total_purchases_ex_vat": 200000,
        "total_goods_supplied_eu": 0,
        "total_goods_acquired_eu": 51000,
    })
    r = validate_uk_vat(d)
    assert "vat_due_acquisitions" not in _fields(r)
    assert "total_goods_acquired_eu" not in _fields(r)


# ── Input VAT vs Purchases ──

def test_warns_when_box4_positive_but_box7_zero():
    """Box 4 > 0 但 Box 7 = 0 → 进项有抵扣但无采购额(除非 100% PVA/RC)。"""
    d = _data({
        "vat_due_sales": 60000,
        "vat_due_acquisitions": 0,
        "total_vat_due": 60000,
        "vat_reclaimed_purchases": 33075,  # PVA only
        "net_vat_due": 26925,
        "total_sales_ex_vat": 300000,
        "total_purchases_ex_vat": 0,       # 漏报采购额
        "total_goods_supplied_eu": 0,
        "total_goods_acquired_eu": 0,
    })
    r = validate_uk_vat(d)
    assert "total_purchases_ex_vat" in _fields(r)
    assert any("Box 7" in w.message for w in r.warnings)


def test_no_purchase_warning_when_box4_is_zero():
    """Box 4 = 0 时 Box 7 = 0 不警告(Nil return)。"""
    d = _data({
        "vat_due_sales": 0,
        "vat_due_acquisitions": 0,
        "total_vat_due": 0,
        "vat_reclaimed_purchases": 0,
        "net_vat_due": 0,
        "total_sales_ex_vat": 0,
        "total_purchases_ex_vat": 0,
        "total_goods_supplied_eu": 0,
        "total_goods_acquired_eu": 0,
    })
    r = validate_uk_vat(d)
    assert "total_purchases_ex_vat" not in _fields(r)


# ── Box 3 = Box 1 + Box 2 ──

def test_warns_when_box3_not_equal_box1_plus_box2():
    d = _data({
        "vat_due_sales": 60000,
        "vat_due_acquisitions": 10200,
        "total_vat_due": 60000,  # 错:应为 70200
        "vat_reclaimed_purchases": 43275,
        "net_vat_due": 16725,
        "total_sales_ex_vat": 300000,
        "total_purchases_ex_vat": 200000,
        "total_goods_supplied_eu": 0,
        "total_goods_acquired_eu": 51000,
    })
    r = validate_uk_vat(d)
    assert "total_vat_due" in _fields(r)
    assert any("Box 1 + Box 2" in w.message for w in r.warnings)


def test_no_warning_when_box3_correct():
    d = _data({
        "vat_due_sales": 60000,
        "vat_due_acquisitions": 10200,
        "total_vat_due": 70200,
        "vat_reclaimed_purchases": 43275,
        "net_vat_due": 26925,
        "total_sales_ex_vat": 300000,
        "total_purchases_ex_vat": 200000,
        "total_goods_supplied_eu": 0,
        "total_goods_acquired_eu": 51000,
    })
    r = validate_uk_vat(d)
    assert "total_vat_due" not in _fields(r)


# ── Box 5 = |Box 3 − Box 4| ──

def test_warns_when_box5_not_absolute_diff():
    d = _data({
        "vat_due_sales": 60000,
        "vat_due_acquisitions": 10200,
        "total_vat_due": 70200,
        "vat_reclaimed_purchases": 43275,
        "net_vat_due": 10000,  # 错:应为 26925
        "total_sales_ex_vat": 300000,
        "total_purchases_ex_vat": 200000,
        "total_goods_supplied_eu": 0,
        "total_goods_acquired_eu": 51000,
    })
    r = validate_uk_vat(d)
    assert "net_vat_due" in _fields(r)
    assert any("Box 3" in w.message and "Box 4" in w.message for w in r.warnings)


# ── Sales vs Box 6 (保留行为) ──

def test_warns_when_box1_positive_but_box6_zero():
    d = _data({
        "vat_due_sales": 60000,
        "vat_due_acquisitions": 0,
        "total_vat_due": 60000,
        "vat_reclaimed_purchases": 0,
        "net_vat_due": 60000,
        "total_sales_ex_vat": 0,
        "total_purchases_ex_vat": 0,
        "total_goods_supplied_eu": 0,
        "total_goods_acquired_eu": 0,
    })
    r = validate_uk_vat(d)
    assert "total_sales_ex_vat" in _fields(r)


# ── 全对账无警告 ──

def test_clean_return_has_no_warnings():
    """嘉汉 Q1 正确值应全绿。"""
    d = _data({
        "vat_due_sales": 60000,
        "vat_due_acquisitions": 10200,
        "total_vat_due": 70200,
        "vat_reclaimed_purchases": 43275,
        "net_vat_due": 26925,
        "total_sales_ex_vat": 300000,
        "total_purchases_ex_vat": 200000,
        "total_goods_supplied_eu": 0,
        "total_goods_acquired_eu": 51000,
    })
    r = validate_uk_vat(d)
    assert r.is_valid is True
    assert len(r.warnings) == 0
