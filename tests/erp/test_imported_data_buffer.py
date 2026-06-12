"""Tests for ImportHubStore — period-keyed in-memory dedup store.

Covers the singleton add/list/count/clear API used by the 3 import sources
(ERPNext REST pull, CSV, future push). Tests rely on explicit `clear()` calls
rather than fixtures because the store is a process-local singleton.
"""
from datetime import date
from decimal import Decimal

from backend.models.erp_models import HubInvoice
from backend.services.imported_data_buffer import ImportHubStore


def _make_invoice(docname: str, **overrides) -> HubInvoice:
    base = dict(
        id=docname,
        txn_date=date(2026, 3, 15),
        counterparty="ACME",
        net_amount=Decimal("1000"),
        vat_amount=Decimal("200"),
        gross_amount=Decimal("1200"),
        vat_rate=Decimal("0.20"),
        tax_code="T1",
    )
    base.update(overrides)
    return HubInvoice(**base)


def test_store_add_and_dedup():
    """同一 (period, id) 后写覆盖前(cancelled 字段可改)。"""
    ImportHubStore.clear("Q1_2026")
    ImportHubStore.add("Q1_2026", [_make_invoice("SINV-001")])
    ImportHubStore.add("Q1_2026", [_make_invoice("SINV-001", counterparty="NEW NAME")])
    listed = ImportHubStore.list("Q1_2026")
    assert len(listed) == 1
    assert listed[0].counterparty == "NEW NAME"


def test_store_cancel_update_via_re_add():
    """Cancel 事件:同 id 再 add,只改 cancelled 字段。"""
    ImportHubStore.clear("Q1_2026")
    ImportHubStore.add("Q1_2026", [_make_invoice("SINV-001")])
    ImportHubStore.add("Q1_2026", [_make_invoice("SINV-001", cancelled=True)])
    assert ImportHubStore.list("Q1_2026")[0].cancelled is True


def test_store_period_isolation():
    """不同 period 完全隔离。"""
    ImportHubStore.clear()
    ImportHubStore.add("Q1_2026", [_make_invoice("A")])
    ImportHubStore.add("Q2_2026", [_make_invoice("A")])
    assert len(ImportHubStore.list("Q1_2026")) == 1
    assert len(ImportHubStore.list("Q2_2026")) == 1
    ImportHubStore.clear()


def test_store_count_summary():
    """count 返 sales/purchases/cancelled/amends 字典。"""
    ImportHubStore.clear("Q1_2026")
    ImportHubStore.add("Q1_2026", [
        _make_invoice("S1"),
        _make_invoice("P1", id="P1", tax_code="T2"),
        _make_invoice("S2", cancelled=True),
        _make_invoice("CN1", is_amend=True, parent="S1"),
    ])
    summary = ImportHubStore.count("Q1_2026")
    assert summary["sales"] == 1       # 只算 S1,S2 已 cancel
    assert summary["purchases"] == 1   # P1
    assert summary["cancelled"] == 1   # S2
    assert summary["amends"] == 1      # CN1
    assert summary["total"] == 4
    ImportHubStore.clear()


def test_store_clear_specific_period():
    """clear(period) 只清一个;clear() 清全部。"""
    ImportHubStore.clear()
    ImportHubStore.add("Q1_2026", [_make_invoice("A")])
    ImportHubStore.add("Q2_2026", [_make_invoice("B")])
    ImportHubStore.clear("Q1_2026")
    assert ImportHubStore.list("Q1_2026") == []
    assert len(ImportHubStore.list("Q2_2026")) == 1
    ImportHubStore.clear()
