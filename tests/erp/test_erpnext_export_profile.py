"""ERPNext 导出 CSV Profile 测试 (Task 6)"""
from decimal import Decimal
from backend.erp.profiles import ERPNextExportProfile


def test_detect_erpnext_headers():
    """ERPNext 导出 header 含 'Posting Date' / 'Customer' / 'Net Total' → 命中。"""
    p = ERPNextExportProfile()
    headers = ["Name", "Posting Date", "Customer", "Net Total", "Total Taxes", "Grand Total", "Docstatus"]
    score = p.detect(headers)
    assert score >= 0.7


def test_transform_sales_row():
    """ERPNext 行 → SalesTransaction(net=1000, vat=200)。"""
    p = ERPNextExportProfile()
    txn, err = p.transform_row({
        "Name": "SINV-2026-0142",
        "Posting Date": "2026-03-15",
        "Customer": "ACME Ltd",
        "Net Total": "1000",
        "Total Taxes": "200",
        "Grand Total": "1200",
        "Docstatus": "1",
    }, row_index=1)
    assert err is None
    assert txn.id == "SINV-2026-0142"
    assert txn.net_amount == Decimal("1000")
    assert txn.vat_amount == Decimal("200")
    # 应该是 SalesTransaction
    from backend.models.erp_models import SalesTransaction
    assert isinstance(txn, SalesTransaction)


def test_transform_purchase_row():
    p = ERPNextExportProfile()
    txn, err = p.transform_row({
        "Name": "PINV-2026-0089",
        "Posting Date": "2026-03-20",
        "Supplier": "Office Co",
        "Net Total": "450",
        "Total Taxes": "90",
        "Grand Total": "540",
        "Docstatus": "1",
    }, row_index=2)
    assert err is None
    from backend.models.erp_models import PurchaseTransaction
    assert isinstance(txn, PurchaseTransaction)
    assert txn.counterparty == "Office Co"
