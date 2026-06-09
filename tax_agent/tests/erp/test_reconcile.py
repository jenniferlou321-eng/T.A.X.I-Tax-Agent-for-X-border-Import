"""reconcile.py 测试"""
from decimal import Decimal
from tax_agent.erp.reconcile import (
    compute_taxi_nine_box, ReconciliationDelta, reconcile,
)
from tax_agent.models.erp_models import (
    ERPNineBox, SalesTransaction, PurchaseTransaction,
)
from datetime import date


def make_sale(net, vat, rate="0.20", code="T1"):
    return SalesTransaction(
        id="S-1", txn_date=date(2026, 1, 1), counterparty="X",
        net_amount=Decimal(net), vat_amount=Decimal(vat), gross_amount=Decimal(net) + Decimal(vat),
        vat_rate=Decimal(rate), tax_code=code,
    )


def make_purchase(net, vat, rate="0.20", code="T1", recoverable=True):
    return PurchaseTransaction(
        id="P-1", txn_date=date(2026, 1, 1), counterparty="Y",
        net_amount=Decimal(net), vat_amount=Decimal(vat), gross_amount=Decimal(net) + Decimal(vat),
        vat_rate=Decimal(rate), tax_code=code, is_recoverable=recoverable,
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
