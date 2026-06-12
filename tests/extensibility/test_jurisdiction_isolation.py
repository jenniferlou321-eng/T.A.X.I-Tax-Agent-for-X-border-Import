"""验证 prompts/{cc}/ 之间的 import 隔离。

加 1 个新国家 = 0 全局改的关键不变量。
"""
import re
from pathlib import Path

import pytest

PROMPTS_ROOT = Path(__file__).parent.parent.parent / "backend" / "agent" / "prompts"


def _all_cc_subdirs() -> list[str]:
    return [d.name for d in PROMPTS_ROOT.iterdir()
            if d.is_dir() and d.name not in ("__pycache__",)]


def _scan_imports(py_file: Path) -> list[str]:
    """提取 import 目标 cc 列表。"""
    text = py_file.read_text(encoding="utf-8")
    pattern = re.compile(
        r"backend\.agent\.prompts\.([a-z_]+)\.",
        re.IGNORECASE,
    )
    return list(set(pattern.findall(text)))


@pytest.mark.parametrize("source_cc", _all_cc_subdirs())
def test_prompts_cc_does_not_import_other_cc(source_cc):
    """任何 prompts/{cc}/ 的 .py 不允许 import 其它 cc 子包。"""
    cc_dir = PROMPTS_ROOT / source_cc
    for py_file in cc_dir.glob("**/*.py"):
        imported_ccs = _scan_imports(py_file)
        for other_cc in imported_ccs:
            assert other_cc == source_cc, (
                f"{py_file.relative_to(PROMPTS_ROOT)} imports {other_cc!r} "
                f"subpackage — violates cc isolation"
            )


def test_shared_modules_under_prompts_root():
    """_generic / _fallback 不在 cc 子包内,独立。"""
    assert (PROMPTS_ROOT / "_generic.py").exists()
    assert (PROMPTS_ROOT / "_fallback.py").exists()
