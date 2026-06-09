"""erp_models 数据模型测试"""
from datetime import date
from decimal import Decimal
from tax_agent.models.erp_models import (
    SalesTransaction, PurchaseTransaction, ERPNineBox, ImportResult,
)


def test_sales_transaction_fields():
    t = SalesTransaction(
        id="INV-2026-001",
        txn_date=date(2026, 1, 15),
        counterparty="ACME Corp",
        net_amount=Decimal("1000.00"),
        vat_amount=Decimal("200.00"),
        gross_amount=Decimal("1200.00"),
        vat_rate=Decimal("0.20"),
        tax_code="T1",
    )
    assert t.id == "INV-2026-001"
    assert t.vat_rate == Decimal("0.20")
    assert t.is_eu is False  # default
    assert t.is_reverse_charge is False  # default


def test_purchase_transaction_fields():
    t = PurchaseTransaction(
        id="PIN-2026-001",
        txn_date=date(2026, 1, 20),
        counterparty="Office Supplies Ltd",
        net_amount=Decimal("500.00"),
        vat_amount=Decimal("100.00"),
        gross_amount=Decimal("600.00"),
        vat_rate=Decimal("0.20"),
        tax_code="T1",
    )
    assert t.is_recoverable is True  # default
    assert t.is_eu_acquisition is False  # default


def test_erp_nine_box_defaults():
    box = ERPNineBox()
    assert box.box1_vat_due_sales == Decimal("0")
    assert box.box6_total_sales_ex_vat == 0  # int
    assert box.scheme_flags == []  # list default


def test_import_result_required_fields():
    r = ImportResult(
        sales=[],
        purchases=[],
        erp_provided_boxes=ERPNineBox(),
        source_profile="generic",
        source_filename="test.csv",
        source_hash="abc123",
    )
    assert r.warnings == []  # default
    assert r.rejected_rows == []  # default
    assert r.erp_provided_boxes is not None