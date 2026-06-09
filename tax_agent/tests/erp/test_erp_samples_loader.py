"""erp_samples_loader 测试"""
import pytest
from tax_agent.erp.erp_samples_loader import (
    load_demo_case, list_demo_cases, DemoCaseNotFoundError,
)


def test_list_demo_cases_returns_list():
    cases = list_demo_cases()
    assert isinstance(cases, list)
    assert "techflow_q1_2026" in cases or len(cases) >= 1  # 至少有 1 个


def test_load_demo_case_techflow_returns_import_result():
    result = load_demo_case("techflow_q1_2026")
    assert result.source_profile == "demo"
    assert len(result.sales) >= 1
    assert len(result.purchases) >= 1
    assert result.erp_provided_boxes.box1_vat_due_sales > 0


def test_load_demo_case_not_found_raises():
    with pytest.raises(DemoCaseNotFoundError, match="nonexistent_case"):
        load_demo_case("nonexistent_case")
