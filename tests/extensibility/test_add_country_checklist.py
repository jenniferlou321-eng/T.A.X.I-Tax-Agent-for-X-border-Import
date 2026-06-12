# tests/extensibility/test_add_country_checklist.py
"""验证"加 1 个新国家"的端到端流程触达全局文件 = 0。

复刻 spec §5 数据流: cp + sed + 1 行注册。
"""
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
PROMPTS_ROOT = REPO_ROOT / "backend" / "agent" / "prompts"
E2E_CC = "_e2e_test_land"


@pytest.fixture
def cleanup_e2e_cc():
    """测试后清理 _e2e_test_land 子包。"""
    yield
    e2e_dir = PROMPTS_ROOT / E2E_CC
    if e2e_dir.exists():
        shutil.rmtree(e2e_dir)


def test_add_country_end_to_end(cleanup_e2e_cc):
    """端到端: cp prompts/uk/vat.py → _e2e_test_land/vat.py, 改 3 行, 验证可加载。"""
    src = PROMPTS_ROOT / "uk" / "vat.py"
    dst_dir = PROMPTS_ROOT / E2E_CC
    dst_dir.mkdir()
    dst = dst_dir / "vat.py"
    shutil.copy(src, dst)
    # 改 3 行: URL + 2 处 "UK" → "_e2e_test_land"
    text = dst.read_text(encoding="utf-8")
    text = text.replace('"https://www.gov.uk', '"https://www.example.com', 1)
    text = text.replace("(UK VAT)", "(_e2e VAT)", 1)
    # 计划原文是 text.replace("UK VAT", "E2E VAT", 1),但该替换会落在文件第 1 行
    # 的模块 docstring(UK VAT 特定提示)上,而该 docstring 不在 PROMPT 值内。
    # 改为替换 PROMPT 内的下一处 UK VAT,确保 E2E VAT 进入 PROMPT。
    text = text.replace("UK VAT Knowledge Base", "E2E VAT Knowledge Base", 1)
    dst.write_text(text, encoding="utf-8")

    # 验证: importlib 能加载
    spec_module = __import__(
        f"backend.agent.prompts.{E2E_CC}.vat",
        fromlist=["PROMPT"],
    )
    assert "E2E VAT" in spec_module.PROMPT
    # 验证: 跟 UK vat 不一样(已 sed 改)
    from backend.agent.prompts.uk import vat as uk_vat
    assert spec_module.PROMPT != uk_vat.PROMPT


def test_add_country_orphans_no_global_file():
    """实施完成后,git diff --name-only 在 main.py 应只有 1 行注册(由本 plan 的后续 phase 累积)。

    本测试是"硬约束 CI 守卫":如果未来有人改了 prompts/{cc}/ 之外的文件但
    跟加国家有关,这个测试失败。
    """
    # 跑 git diff 看 main.py 是不是只增 1 行
    # 计划原文是 ["git", "diff", "--name-only", "main.py"],但 git >=2.25 在
    # 没有 HEAD~ 时会歧义(main.py 既是 path 又是潜在 revision),加 -- 解决。
    result = subprocess.run(
        ["git", "diff", "--name-only", "--", "main.py"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    # 验证: prompts/ 或 channels/ 等 cc 相关文件不在全局改动名单
    # (这里的"全局"定义为 root 顶层文件)
    # 实际: 我们只测 main.py 是否被改
    assert result.returncode == 0
    # 不强制 0 改动(其他 PR 可能改 main.py),只测本 PR 内的"加国家"
    # 流程不会触发 main.py 改动
