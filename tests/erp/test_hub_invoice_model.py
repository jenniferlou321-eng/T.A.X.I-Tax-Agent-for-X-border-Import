"""HubInvoice 数据模型测试 — Import Hub 内部统一发票表示"""
from datetime import date
from decimal import Decimal
from backend.models.erp_models import HubInvoice


def test_hub_invoice_required_fields():
    """HubInvoice needs id/date/amounts/vat_rate, optional cancel/amend."""
    inv = HubInvoice(
        id="SINV-2026-0142",
        txn_date=date(2026, 3, 15),
        counterparty="ACME Ltd",
        net_amount=Decimal("1000"),
        vat_amount=Decimal("200"),
        gross_amount=Decimal("1200"),
        vat_rate=Decimal("0.20"),
        tax_code="T1",
    )
    assert inv.cancelled is False
    assert inv.is_amend is False
    assert inv.parent is None
    assert inv.source == "erpnext_pull"  # default


def test_hub_invoice_cancel_and_amend():
    inv = HubInvoice(
        id="CN-2026-0001",
        txn_date=date(2026, 3, 20),
        counterparty="ACME Ltd",
        net_amount=Decimal("-1000"),
        vat_amount=Decimal("-200"),
        gross_amount=Decimal("-1200"),
        vat_rate=Decimal("0.20"),
        tax_code="T1",
        cancelled=False,
        is_amend=True,
        parent="SINV-2026-0142",
        source="erpnext_pull",
    )
    assert inv.is_amend is True
    assert inv.parent == "SINV-2026-0142"
