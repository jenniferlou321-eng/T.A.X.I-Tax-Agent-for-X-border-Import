"""erp_samples_loader 测试 — 3 个新 case 的加载路径"""
import pytest
from backend.erp.erp_samples_loader import (
    load_demo_case, list_demo_cases, DemoCaseNotFoundError,
)


# ── 列表 ──

def test_list_demo_cases_includes_3_new_cases():
    cases = list_demo_cases()
    assert isinstance(cases, list)
    # 三个新 case 必须在
    for cid in ("case-x-uk-standard", "case-a-uk-subsidiary", "case-b-cn-parent"):
        assert cid in cases, f"{cid} missing from {cases}"


# ── Case X: 入门 ──

def test_load_case_x_uk_standard():
    result = load_demo_case("case-x-uk-standard")
    assert result.source_profile == "demo"
    assert len(result.sales) == 7
    assert len(result.purchases) == 6
    # 9-Box: Box 1 = 250 (small teaching case)
    assert float(result.erp_provided_boxes.box1_vat_due_sales) == 250.00
    assert float(result.erp_provided_boxes.box5_net_vat_due) == 180.00
    assert result.erp_provided_boxes.box6_total_sales_ex_vat == 1250


# ── Case A: 跨境 UK 子 ──

def test_load_case_a_uk_subsidiary():
    result = load_demo_case("case-a-uk-subsidiary")
    assert result.source_profile == "demo"
    assert len(result.sales) == 27
    assert len(result.purchases) == 24
    # 与前端卡片 9-Box 数字严格一致
    assert float(result.erp_provided_boxes.box1_vat_due_sales) == 41523.50
    assert float(result.erp_provided_boxes.box2_vat_due_acquisitions) == 13700.00
    assert float(result.erp_provided_boxes.box5_net_vat_due) == 7611.50
    assert result.erp_provided_boxes.box6_total_sales_ex_vat == 282750
    assert result.erp_provided_boxes.box8_total_goods_supplied_eu == 42450
    assert result.erp_provided_boxes.box9_total_goods_acquired_eu == 68500


# ── Case B: 跨境 CN 母 ──

def test_load_case_b_cn_parent():
    result = load_demo_case("case-b-cn-parent")
    assert result.source_profile == "demo"
    # CN 视角简化版:22 sales + 10 purchases
    assert len(result.sales) == 22
    assert len(result.purchases) == 10
    # CN 不是 9-Box 体系,9 盒全 0;真实数字在 expected_outputs.json
    assert float(result.erp_provided_boxes.box1_vat_due_sales) == 0.00
    assert result.erp_provided_boxes.box6_total_sales_ex_vat == 0
    # scheme_flags 包含 CN 关键 flag
    flags = result.erp_provided_boxes.scheme_flags
    assert any("CN VAT 13%" in f for f in flags)
    assert any("Transfer pricing" in f for f in flags)
    assert any("BEPS 2.0" in f for f in flags)


# ── 错误路径 ──

def test_load_demo_case_not_found_raises():
    with pytest.raises(DemoCaseNotFoundError, match="nonexistent_case"):
        load_demo_case("nonexistent_case")


# ── Case 隔离:不再有旧 ID ──

def test_no_legacy_case_ids_in_list():
    """case 精简后,3 个旧 ID 都不应再出现"""
    cases = list_demo_cases()
    for old_id in ("techflow_q1_2026", "cross_border_eu_2026", "cn_parent_uk_sub_q1_2026"):
        assert old_id not in cases, f"legacy {old_id} still present in {cases}"
