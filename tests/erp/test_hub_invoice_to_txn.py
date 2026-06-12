"""Tests for backend.erp.hub_to_txn.hub_invoices_to_txn helper."""
from datetime import date
from decimal import Decimal

import pytest

from backend.models.erp_models import HubInvoice
from backend.erp.hub_to_txn import hub_invoices_to_txn


def test_hub_to_txn_filters_cancelled():
    invs = [
        HubInvoice(id="S1", txn_date=date(2026, 3, 15), counterparty="A",
                   net_amount=Decimal("1000"), vat_amount=Decimal("200"),
                   gross_amount=Decimal("1200"), vat_rate=Decimal("0.20"), tax_code="T1"),
        HubInvoice(id="S2", txn_date=date(2026, 3, 16), counterparty="B",
                   net_amount=Decimal("500"), vat_amount=Decimal("100"),
                   gross_amount=Decimal("600"), vat_rate=Decimal("0.20"), tax_code="T1",
                   cancelled=True),  # 应被过滤
    ]
    sales, purchases = hub_invoices_to_txn(invs, filter_cancelled=True)
    assert len(sales) == 1
    assert sales[0].id == "S1"


def test_hub_to_txn_split_sale_vs_purchase():
    invs = [
        HubInvoice(id="S1", txn_date=date(2026, 3, 15), counterparty="A",
                   net_amount=Decimal("1000"), vat_amount=Decimal("200"),
                   gross_amount=Decimal("1200"), vat_rate=Decimal("0.20"), tax_code="T1"),
        HubInvoice(id="P1", txn_date=date(2026, 3, 16), counterparty="B",
                   net_amount=Decimal("500"), vat_amount=Decimal("100"),
                   gross_amount=Decimal("600"), vat_rate=Decimal("0.20"), tax_code="T2"),
    ]
    sales, purchases = hub_invoices_to_txn(invs)
    assert len(sales) == 1 and sales[0].id == "S1"
    assert len(purchases) == 1 and purchases[0].id == "P1"


def test_hub_to_txn_keeps_amend_negative_amounts():
    """Credit Note (is_amend, net<0) 应该保留,9-Box 自然抵减。"""
    invs = [
        HubInvoice(id="S1", txn_date=date(2026, 3, 15), counterparty="A",
                   net_amount=Decimal("1000"), vat_amount=Decimal("200"),
                   gross_amount=Decimal("1200"), vat_rate=Decimal("0.20"), tax_code="T1"),
        # id 以 S 开头(真实 ERPNext 销售贷项通知单命名),自然归到 sales
        HubInvoice(id="SINV-CN-2026-0001", txn_date=date(2026, 3, 20), counterparty="A",
                   net_amount=Decimal("-1000"), vat_amount=Decimal("-200"),
                   gross_amount=Decimal("-1200"), vat_rate=Decimal("0.20"), tax_code="T1",
                   is_amend=True, parent="S1"),
    ]
    sales, _ = hub_invoices_to_txn(invs)
    # SINV-CN-2026-0001 应该被识别为 sales(id 以 S 开头)
    assert len(sales) == 2
    assert sum(s.net_amount for s in sales) == Decimal("0")


def test_hub_to_txn_unknown_prefix_raises():
    """未知 id 前缀必须抛 ValueError,不能静默归到 sales。"""
    invs = [
        HubInvoice(id="X-001", txn_date=date(2026, 3, 15), counterparty="A",
                   net_amount=Decimal("1000"), vat_amount=Decimal("200"),
                   gross_amount=Decimal("1200"), vat_rate=Decimal("0.20"), tax_code="T1"),
    ]
    with pytest.raises(ValueError, match="does not start with S or P"):
        hub_invoices_to_txn(invs)
