"""CSV 解析器 + Generic Profile 测试"""
import io
import pytest
from decimal import Decimal
from tax_agent.erp.csv_parser import (
    parse_csv, CsvParseError, detect_profile, REQUIRED_COLUMNS,
)
from tax_agent.erp.profiles import GenericProfile


def test_required_columns_constant():
    assert "txn_date" in REQUIRED_COLUMNS
    assert "txn_type" in REQUIRED_COLUMNS
    assert "counterparty" in REQUIRED_COLUMNS
    assert "net" in REQUIRED_COLUMNS
    assert "vat" in REQUIRED_COLUMNS
    assert "gross" in REQUIRED_COLUMNS
    assert "vat_rate" in REQUIRED_COLUMNS
    assert "tax_code" in REQUIRED_COLUMNS


def test_detect_profile_generic_exact_match():
    headers = REQUIRED_COLUMNS
    profile, confidence = detect_profile(headers)
    assert profile == "generic"
    assert confidence == 1.0


def test_detect_profile_generic_partial_match():
    headers = ["txn_date", "txn_type", "counterparty", "net", "vat", "gross", "vat_rate", "tax_code", "extra_col"]
    profile, confidence = detect_profile(headers)
    assert profile == "generic"
    assert confidence >= 0.7


def test_detect_profile_no_match_returns_generic_low_confidence():
    headers = ["random_col1", "random_col2"]
    profile, confidence = detect_profile(headers)
    assert profile == "generic"
    assert confidence < 0.7


def test_parse_csv_generic_valid():
    csv_bytes = (
        b"txn_date,txn_type,counterparty,net,vat,gross,vat_rate,tax_code\n"
        b"2026-01-15,sale,ACME Corp,1000.00,200.00,1200.00,0.20,T1\n"
        b"2026-01-20,purchase,Office Ltd,500.00,100.00,600.00,0.20,T1\n"
    )
    result = parse_csv(csv_bytes, profile="generic")
    assert result.source_profile == "generic"
    assert len(result.sales) == 1
    assert len(result.purchases) == 1
    assert result.sales[0].id.startswith("SALE-")
    assert result.sales[0].counterparty == "ACME Corp"
    assert result.sales[0].net_amount == Decimal("1000.00")
    assert result.purchases[0].counterparty == "Office Ltd"


def test_parse_csv_bom_strip():
    csv_bytes = b"\xef\xbb\xbf" + (
        b"txn_date,txn_type,counterparty,net,vat,gross,vat_rate,tax_code\n"
        b"2026-01-15,sale,ACME,100,20,120,0.20,T1\n"
    )
    result = parse_csv(csv_bytes, profile="generic")
    assert len(result.sales) == 1


def test_parse_csv_missing_required_column_raises():
    csv_bytes = b"txn_date,txn_type,counterparty,net\n2026-01-15,sale,ACME,100\n"
    with pytest.raises(CsvParseError, match="missing required column"):
        parse_csv(csv_bytes, profile="generic")


def test_parse_csv_rejected_rows_with_bad_data():
    csv_bytes = (
        b"txn_date,txn_type,counterparty,net,vat,gross,vat_rate,tax_code\n"
        b"2026-01-15,sale,ACME,1000.00,200.00,1200.00,0.20,T1\n"
        b"not-a-date,sale,Bad Inc,100,20,120,0.20,T1\n"
    )
    result = parse_csv(csv_bytes, profile="generic")
    assert len(result.sales) == 1
    assert len(result.rejected_rows) == 1
    assert result.rejected_rows[0]["row_index"] == 2


def test_parse_csv_header_corrupt_raises():
    csv_bytes = b"this is not,valid csv header at all\nrandom,data\n"
    with pytest.raises(CsvParseError, match="header"):
        parse_csv(csv_bytes, profile="generic")
