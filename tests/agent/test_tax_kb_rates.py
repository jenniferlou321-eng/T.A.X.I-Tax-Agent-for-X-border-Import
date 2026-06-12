"""验证 KB md 都有 ## Rates 段 + JSON 合法。"""
import re
import json
from pathlib import Path

import pytest

KB_ROOT = Path(__file__).parent.parent.parent / "data" / "tax_knowledge"

# (cc, tt, expected_rates_dict)
EXPECTED = [
    ("uk", "vat", {"standard": 0.20, "reduced": 0.05, "zero": 0.00}),
    ("uk", "corporation_tax", {"small_profits_rate": 0.19, "main_rate": 0.25}),
    # SA 没有 1 个标准税率, rates 段是空 dict + rates_only_for_CIT
    ("uk", "self_assessment", {}),
    ("uk", "paye", {}),
    ("uk", "stamp_duty", {}),
    ("testland", "vat", {"standard": 0.21, "reduced": 0.09, "zero": 0.00}),
]


def _extract_rates(md_path: Path) -> dict | None:
    text = md_path.read_text(encoding="utf-8")
    match = re.search(
        r"##\s+Rates\s*\n+(.*?)(?=\n##\s|\Z)",
        text, re.DOTALL,
    )
    if not match:
        return None
    body = match.group(1)
    json_match = re.search(r"```json\s*(\{.*?\})\s*```", body, re.DOTALL)
    if not json_match:
        return {}  # 段存在但无 JSON 块(允许,例如 SA)
    return json.loads(json_match.group(1))


@pytest.mark.parametrize("cc,tt,expected", EXPECTED)
def test_kb_has_rates_section(cc, tt, expected):
    md = KB_ROOT / cc / f"{tt}.md"
    assert md.exists(), f"missing {md}"
    rates = _extract_rates(md)
    assert rates is not None, f"{md} has no ## Rates section"
    for k, v in expected.items():
        assert rates.get(k) == v, f"{md}: rates[{k}] = {rates.get(k)} != {v}"


def test_de_kb_has_no_rates_section():
    """de 没 ## Rates 段 — 走 fallback 'not yet available'(向后兼容)。"""
    md = KB_ROOT / "de" / "vat.md"
    if not md.exists():
        pytest.skip("de KB md not yet seeded")
    rates = _extract_rates(md)
    assert rates is None or rates == {}
