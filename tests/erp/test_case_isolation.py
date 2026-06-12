"""3 个 case 严格隔离 — 互不引用文件 / 数字不冲突"""
import json
from pathlib import Path


SAMPLES = Path(__file__).parent.parent.parent / "data" / "erp_samples"
THREE_CASES = ("case-x-uk-standard", "case-a-uk-subsidiary", "case-b-cn-parent")


def test_three_case_directories_exist():
    for cid in THREE_CASES:
        d = SAMPLES / cid
        assert d.is_dir(), f"missing case dir: {d}"


def test_each_case_has_minimum_files():
    """每个 case 目录至少有 case_summary / erp_import / expected_* + source_docs/"""
    for cid in THREE_CASES:
        d = SAMPLES / cid
        assert (d / "case_summary.json").is_file()
        assert (d / "erp_import.json").is_file()
        assert (d / "source_docs").is_dir()
        assert len(list((d / "source_docs").iterdir())) > 0


def test_source_docs_do_not_cross_reference_other_cases():
    """source_docs/ 下任何文件不能引用其他 case 的 ID"""
    for cid in THREE_CASES:
        source_docs = SAMPLES / cid / "source_docs"
        for f in source_docs.iterdir():
            text = f.read_text(encoding="utf-8", errors="ignore")
            for other_cid in THREE_CASES:
                if other_cid == cid:
                    continue
                assert other_cid not in text, \
                    f"{cid}/{f.name} 跨 case 引用了 {other_cid}"


def test_case_x_9_box_is_teaching_tiny():
    """Case X 是教学用小数字"""
    with (SAMPLES / "case-x-uk-standard" / "erp_import.json").open() as f:
        erp = json.load(f)
    box1 = float(erp["erp_provided_boxes"]["box1_vat_due_sales"])
    assert box1 < 1000, f"Case X Box 1 should be tiny (teaching): got {box1}"


def test_case_a_9_box_strictly_matches_frontend():
    """Case A 9-Box 数字与前端 case-a-uk-subsidiary 卡片一致(41,523.50 等)"""
    with (SAMPLES / "case-a-uk-subsidiary" / "erp_import.json").open() as f:
        erp = json.load(f)
    b = erp["erp_provided_boxes"]
    assert b["box1_vat_due_sales"] == "41523.50"
    assert b["box6_total_sales_ex_vat"] == 282750
    assert b["box8_total_goods_supplied_eu"] == 42450
    assert b["box9_total_goods_acquired_eu"] == 68500


def test_case_b_9_box_zero_cn_not_9box():
    """Case B 9-Box 全 0(中国不是 9-Box 体系)"""
    with (SAMPLES / "case-b-cn-parent" / "erp_import.json").open() as f:
        erp = json.load(f)
    b = erp["erp_provided_boxes"]
    for k in ("box1_vat_due_sales", "box2_vat_due_acquisitions", "box3_total_vat_due",
              "box4_vat_reclaimed", "box5_net_vat_due"):
        assert float(b[k]) == 0.0, f"Case B {k} should be 0: got {b[k]}"
    for k in ("box6_total_sales_ex_vat", "box7_total_purchases_ex_vat",
              "box8_total_goods_supplied_eu", "box9_total_goods_acquired_eu"):
        assert int(b[k]) == 0, f"Case B {k} should be 0: got {b[k]}"
