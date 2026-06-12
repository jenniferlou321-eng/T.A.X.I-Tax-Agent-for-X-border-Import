"""Case B 的 expected_outputs.json 数字完整性 + 与 erp_import.json 数字对账"""
import json
from pathlib import Path


CASE_B_DIR = Path(__file__).parent.parent.parent / "data" / "erp_samples" / "case-b-cn-parent"


def _load_json(name: str) -> dict:
    with (CASE_B_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)


def test_expected_outputs_has_required_sections():
    data = _load_json("expected_outputs.json")
    for key in ("vat_outputs", "cit_outputs", "withholding_tax", "transfer_pricing", "dac6_disclosures", "expected_filings"):
        assert key in data, f"missing section: {key}"


def test_vat_outputs_match_erp_import_sales_totals():
    """CN VAT 13% + 6% 销项税总额 应等于 erp_import.json 中 13% + 6% 销项税之和"""
    outputs = _load_json("expected_outputs.json")["vat_outputs"]
    erp = _load_json("erp_import.json")
    sales = erp["sales"]

    actual_13 = sum(float(s["vat_amount"]) for s in sales if abs(float(s["vat_rate"]) - 0.13) < 1e-6)
    actual_6 = sum(float(s["vat_amount"]) for s in sales if abs(float(s["vat_rate"]) - 0.06) < 1e-6)

    assert actual_13 == outputs["output_vat_13_cny"], \
        f"Box 13% VAT 数字不一致: erp {actual_13} vs expected {outputs['output_vat_13_cny']}"
    assert actual_6 == outputs["output_vat_6_cny"], \
        f"Box 6% VAT 数字不一致: erp {actual_6} vs expected {outputs['output_vat_6_cny']}"


def test_cit_payable_25pct_of_pretax():
    """CIT 应缴 = 25% × 应纳税所得额"""
    outputs = _load_json("expected_outputs.json")["cit_outputs"]
    expected_cit = outputs["pretax_income_cny"] * outputs["effective_rate"]
    assert abs(outputs["cit_payable_cny"] - expected_cit) < 0.01, \
        f"CIT 不等于 25% × 应纳税所得额: {outputs['cit_payable_cny']} vs {expected_cit}"


def test_wht_total_equals_sum_of_components():
    """预提税合计 = 特许权 7% + 管理费 5% + 股息 0%"""
    wht = _load_json("expected_outputs.json")["withholding_tax"]
    expected = wht["royalty_tax_cny"] + wht["mgmt_fee_tax_cny"]
    assert wht["total_wht_cny"] == expected, \
        f"WHT 合计不一致: total {wht['total_wht_cny']} vs sum {expected}"


def test_dac6_hallmark_c1b_triggered_with_rod():
    """DAC6 C1(b) 触发 + 跨境 RoD 金额 > 0"""
    dac6 = _load_json("expected_outputs.json")["dac6_disclosures"]
    assert dac6["hallmark_C1b_cross_border"] is True
    assert dac6["cross_border_rod_cny"] > 0
