"""测试 prompts/ 子包的 dispatch 行为。

Phase 1 红线: 5 个 UK key + 1 个 testland key 输出与原 prompts.py byte-equality。
"""
import importlib
from pathlib import Path

import pytest

# 原 prompts.py 路径(待删除前用作 oracle)
_ORACLE_PATH = Path(__file__).parent.parent.parent / "backend" / "agent" / "prompts.py"


@pytest.fixture
def oracle_prompts() -> dict[str, str]:
    """从原 prompts.py 直接 exec 拿 _UK_*_PROMPT 字符串。"""
    if not _ORACLE_PATH.exists():
        pytest.skip("原 prompts.py 已删除(Phase 1 终态)")
    namespace: dict = {}
    exec(_ORACLE_PATH.read_text(encoding="utf-8"), namespace)
    return {
        "uk:vat": namespace["_UK_VAT_PROMPT"],
        "uk:self_assessment": namespace["_UK_SA_PROMPT"],
        "uk:corporation_tax": namespace["_UK_CT_PROMPT"],
        "uk:paye": namespace["_UK_PAYE_PROMPT"],
        "uk:stamp_duty": namespace["_UK_SDLT_PROMPT"],
    }


def test_uk_vat_byte_equal_to_oracle(oracle_prompts):
    """UK VAT prompt 与原版 byte-equality。"""
    from backend.agent.prompts.uk import vat as uk_vat_mod
    assert uk_vat_mod.PROMPT == oracle_prompts["uk:vat"]


def test_uk_self_assessment_byte_equal_to_oracle(oracle_prompts):
    from backend.agent.prompts.uk import self_assessment as mod
    assert mod.PROMPT == oracle_prompts["uk:self_assessment"]


def test_uk_corporation_tax_byte_equal_to_oracle(oracle_prompts):
    from backend.agent.prompts.uk import corporation_tax as mod
    assert mod.PROMPT == oracle_prompts["uk:corporation_tax"]


def test_uk_paye_byte_equal_to_oracle(oracle_prompts):
    from backend.agent.prompts.uk import paye as mod
    assert mod.PROMPT == oracle_prompts["uk:paye"]


def test_uk_stamp_duty_byte_equal_to_oracle(oracle_prompts):
    from backend.agent.prompts.uk import stamp_duty as mod
    assert mod.PROMPT == oracle_prompts["uk:stamp_duty"]


def test_de_falls_back_when_no_module():
    """de 没注册时走 _FALLBACK_PROMPT。"""
    from backend.agent.prompts._fallback import _FALLBACK_PROMPT
    from backend.agent.prompts import get_system_prompt
    full = get_system_prompt("de", "vat")
    assert _FALLBACK_PROMPT in full


def test_typo_tax_type_raises_keyerror():
    """大小写 / typo 抛 KeyError(不再静默 fallback)。"""
    from backend.agent.prompts import get_system_prompt
    with pytest.raises(KeyError) as exc_info:
        get_system_prompt("uk", "VAT")  # 大写
    assert "Unknown" in str(exc_info.value)
    assert "tax_type" in str(exc_info.value)


def test_unknown_cc_raises_keyerror():
    from backend.agent.prompts import get_system_prompt
    with pytest.raises(KeyError) as exc_info:
        get_system_prompt("xx", "vat")
    assert "Unknown" in str(exc_info.value)
    assert "jurisdiction" in str(exc_info.value)


def test_testland_vat_loadable():
    from backend.agent.prompts.testland import vat as testland_vat
    assert "Testland" in testland_vat.PROMPT
    assert "21%" in testland_vat.PROMPT


def test_backward_compat_system_prompt_constant():
    """旧 `from backend.agent.prompts import SYSTEM_PROMPT` 仍可用。"""
    from backend.agent.prompts import SYSTEM_PROMPT
    assert "UK VAT" in SYSTEM_PROMPT
