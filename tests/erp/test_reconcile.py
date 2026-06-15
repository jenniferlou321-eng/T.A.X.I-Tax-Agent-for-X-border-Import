"""reconcile.py 测试"""
from decimal import Decimal
from backend.erp.reconcile import (
    compute_taxi_nine_box, ReconciliationDelta, reconcile,
)
from backend.models.erp_models import (
    ERPNineBox, SalesTransaction, PurchaseTransaction,
)
from datetime import date


def make_sale(net, vat, rate="0.20", code="T1"):
    return SalesTransaction(
        id="S-1", txn_date=date(2026, 1, 1), counterparty="X",
        net_amount=Decimal(net), vat_amount=Decimal(vat), gross_amount=Decimal(net) + Decimal(vat),
        vat_rate=Decimal(rate), tax_code=code,
    )


def make_purchase(net, vat, rate="0.20", code="T1", recoverable=True,
                  is_eu=False, is_reverse_charge=False, is_eu_acquisition=False):
    return PurchaseTransaction(
        id="P-1", txn_date=date(2026, 1, 1), counterparty="Y",
        net_amount=Decimal(net), vat_amount=Decimal(vat), gross_amount=Decimal(net) + Decimal(vat),
        vat_rate=Decimal(rate), tax_code=code, is_recoverable=recoverable,
        is_eu=is_eu, is_reverse_charge=is_reverse_charge, is_eu_acquisition=is_eu_acquisition,
    )


def test_compute_taxi_nine_box_from_transactions():
    sales = [make_sale("1000", "200")]
    purchases = [make_purchase("500", "100")]
    box = compute_taxi_nine_box(sales, purchases)
    assert box.box1_vat_due_sales == Decimal("200")
    assert box.box4_vat_reclaimed == Decimal("100")
    assert box.box3_total_vat_due == Decimal("200")
    assert box.box5_net_vat_due == Decimal("100")
    assert box.box6_total_sales_ex_vat == 1000  # int
    assert box.box7_total_purchases_ex_vat == 500  # int


def test_compute_taxi_nine_box_excludes_zero_rated_from_box1():
    sales = [make_sale("1000", "200", "0.20"), make_sale("500", "0", "0.00", "T0")]
    box = compute_taxi_nine_box(sales, [])
    assert box.box1_vat_due_sales == Decimal("200")  # only standard
    assert box.box6_total_sales_ex_vat == 1500  # both included


def test_reconcile_identical_boxes_within_tolerance():
    a = ERPNineBox(box1_vat_due_sales=Decimal("100"))
    delta = reconcile(erp_boxes=a, taxi_boxes=a, erp_source="test")
    assert delta.total_abs_diff == Decimal("0")
    assert delta.within_tolerance is True


def test_reconcile_detects_box1_diff():
    erp = ERPNineBox(box1_vat_due_sales=Decimal("100.00"))
    taxi = ERPNineBox(box1_vat_due_sales=Decimal("103.50"))
    delta = reconcile(erp_boxes=erp, taxi_boxes=taxi, erp_source="test")
    assert delta.box_diffs["box1"] == Decimal("3.50")
    assert delta.within_tolerance is False
    assert delta.total_abs_diff == Decimal("3.50")
    assert any("box1" in n for n in delta.notes)


def test_reconcile_tolerance_boundary():
    """£0.50 内算 within_tolerance（HMRC 官方 rounding 容差）"""
    erp = ERPNineBox(box1_vat_due_sales=Decimal("100.00"))
    taxi = ERPNineBox(box1_vat_due_sales=Decimal("100.50"))
    delta = reconcile(erp_boxes=erp, taxi_boxes=taxi, erp_source="test")
    assert delta.box_diffs["box1"] == Decimal("0.50")
    assert delta.within_tolerance is True


def test_reconcile_aggregates_diffs_across_boxes():
    erp = ERPNineBox(
        box1_vat_due_sales=Decimal("100"),
        box4_vat_reclaimed=Decimal("50"),
    )
    taxi = ERPNineBox(
        box1_vat_due_sales=Decimal("102"),
        box4_vat_reclaimed=Decimal("50"),
    )
    delta = reconcile(erp_boxes=erp, taxi_boxes=taxi, erp_source="test")
    assert delta.total_abs_diff == Decimal("2.00")
    assert delta.within_tolerance is False
    assert len(delta.notes) == 1  # only box1 flagged


# ── EU Reverse Charge (回归: 嘉汉 case 的 T2-UK-EU-RC 约定) ──
# Bug 修复前: compute_taxi_nine_box 只认 is_eu_acquisition 字段,
# 而 RC 行只标 is_reverse_charge + is_eu, 导致 Box 2 / Box 9 漏算为 0,
# 进而在 reconcile 时报出假性差异。

def test_compute_box2_box9_from_explicit_eu_acquisition():
    """显式 is_eu_acquisition=True → Box 2 (VAT due) + Box 4 (reclaim) + Box 9 (net)。"""
    purchases = [make_purchase("51000", "10200", is_eu_acquisition=True, is_eu=True)]
    box = compute_taxi_nine_box([], purchases)
    assert box.box2_vat_due_acquisitions == Decimal("10200")
    assert box.box4_vat_reclaimed == Decimal("10200")  # is_recoverable 默认 True
    assert box.box9_total_goods_acquired_eu == 51000


def test_compute_box2_box9_from_reverse_charge_flag():
    """REGRESSION: is_reverse_charge=True + is_eu=True(无 is_eu_acquisition)
    也必须进 Box 2 / Box 9 — 这是嘉汉 C1-106 / C1-128a 的真实约定。"""
    purchases = [
        make_purchase("51000", "10200", code="T2-UK-EU-RC", is_reverse_charge=True, is_eu=True),
        make_purchase("33200", "6640", code="T2-UK-EU-RC", is_reverse_charge=True, is_eu=True),
    ]
    box = compute_taxi_nine_box([], purchases)
    assert box.box2_vat_due_acquisitions == Decimal("16840")
    assert box.box9_total_goods_acquired_eu == 84200
    # RC 进项已通过 is_recoverable 计入 Box 4, 不应被重复加
    assert box.box4_vat_reclaimed == Decimal("16840")


def test_domestic_reverse_charge_not_treated_as_eu():
    """国内 CIS 反向征收 (is_reverse_charge=True, is_eu=False) 不进 Box 2 / Box 9。"""
    purchases = [make_purchase("10000", "2000", is_reverse_charge=True, is_eu=False)]
    box = compute_taxi_nine_box([], purchases)
    assert box.box2_vat_due_acquisitions == Decimal("0")
    assert box.box9_total_goods_acquired_eu == 0


def test_reverse_charge_does_not_create_false_reconcile_diff():
    """端到端: ERP 自报含 RC 的正确 9-Box, TAXI 重算应一致 (within tolerance)。

    修复前: TAXI 把 Box 2 / Box 9 算成 0, 与 ERP 报的 16840 / 84200
    产生假性差异 → within_tolerance=False。修复后应 0 差异。
    """
    purchases = [
        make_purchase("51000", "10200", code="T2-UK-EU-RC", is_reverse_charge=True, is_eu=True),
        make_purchase("33200", "6640", code="T2-UK-EU-RC", is_reverse_charge=True, is_eu=True),
    ]
    taxi = compute_taxi_nine_box([], purchases)
    erp = ERPNineBox(
        box2_vat_due_acquisitions=Decimal("16840"),
        box3_total_vat_due=Decimal("16840"),
        box4_vat_reclaimed=Decimal("16840"),
        box5_net_vat_due=Decimal("0"),
        box7_total_purchases_ex_vat=84200,
        box9_total_goods_acquired_eu=84200,
    )
    delta = reconcile(erp_boxes=erp, taxi_boxes=taxi, erp_source="test")
    assert delta.within_tolerance is True, f"假性差异: {delta.notes}"
