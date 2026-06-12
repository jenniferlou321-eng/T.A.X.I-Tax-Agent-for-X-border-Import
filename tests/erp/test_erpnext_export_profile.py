"""ERPNext 导出 CSV Profile 测试 (Task 6)"""
from decimal import Decimal
import pytest
from backend.erp.profiles import ERPNextExportProfile
from backend.erp.csv_parser import parse_csv, CsvParseError


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


def test_erpnext_csv_parses_end_to_end():
    """完整流程: ERPNext CSV → parse_csv → ImportResult 包含正确的 sales/purchases。

    这是 Task 6 spec 评审发现的 blocker 修复后的回归测试：
    之前 csv_parser 的全局 REQUIRED_COLUMNS 检查会让 ERPNext CSV
    在 header 阶段就被拒，ERPNextExportProfile 永远不会被调用。
    """
    csv_bytes = (
        b"Name,Posting Date,Customer,Net Total,Total Taxes,Grand Total,Docstatus\n"
        b"SINV-2026-0142,2026-03-15,ACME,1000,200,1200,1\n"
        b"PINV-2026-0089,2026-03-20,Office Co,450,90,540,1\n"
    )
    result = parse_csv(csv_bytes, profile="erpnext_export")
    assert result.source_profile == "erpnext_export"
    assert len(result.sales) == 1
    assert result.sales[0].id == "SINV-2026-0142"
    assert result.sales[0].net_amount == Decimal("1000")
    assert len(result.purchases) == 1
    assert result.purchases[0].id == "PINV-2026-0089"
    assert result.purchases[0].counterparty == "Office Co"
