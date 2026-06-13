# Extensibility Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把"该目录式但不是目录式"的 2 个债拆成目录:① `prompts.py` 单文件 dict → `prompts/{cc}/{tax}.py` 子包(Phase 1);② `tax_knowledge_tools.get_tax_rates` 的 if/elif → KB `## Rates` 段读取(Phase 2);③ `channels/api_channel.py` 单类 → `channels/{cc}/` + `ChannelRegistry`(Phase 3)。**3 个独立 PR 一起交付**。**加 1 个新国家触达全局文件 ≤ 1 处**。

**Architecture:**
- 引入 `backend/models/jurisdictions.py` 作为 cc / tt 单一事实源
- Phase 1:用 `importlib.import_module` 动态加载,`get_system_prompt` 错误由"静默 fallback"改为"枚举层 KeyError + 模块层 warning log"
- Phase 2:`TaxKnowledgeStore.get_section(cc, tt, title)` 新方法 + KB md 加 `## Rates` 段
- Phase 3:`ChannelRegistry(cc × tt → Channel)` 对称 `JurisdictionRegistry`,`APIChannel` 通用化

**Tech Stack:** Python 3.11 + stdlib only(importlib / dataclasses / pathlib / re);pytest 9;无新依赖。

**Spec:** [`docs/superpowers/specs/2026-06-12-extensibility-refactor-design.md`](../specs/2026-06-12-extensibility-refactor-design.md)

---

## 文件结构

**新建**:
- `backend/models/jurisdictions.py` — JURISDICTIONS / TAX_TYPES / is_valid_jurisdiction
- `backend/agent/prompts/_generic.py` — 原 _GENERIC_PROMPT_HEADER
- `backend/agent/prompts/_fallback.py` — 原 _FALLBACK_PROMPT
- `backend/agent/prompts/__init__.py` — 新 get_system_prompt
- `backend/agent/prompts/uk/{__init__,vat,self_assessment,corporation_tax,paye,stamp_duty}.py` — 拆 UK 5+1
- `backend/agent/prompts/testland/vat.py` — 迁移原 testland 内容
- `backend/channels/registry.py` — ChannelRegistry
- `backend/channels/browser_channel.py` — 占位类
- `backend/channels/uk/__init__.py` — UKChannel
- `tests/agent/test_prompts_dispatch.py`
- `tests/agent/test_tax_kb_rates.py`
- `tests/agent/test_jurisdictions_enum.py`
- `tests/extensibility/__init__.py`
- `tests/extensibility/test_jurisdiction_isolation.py`
- `tests/extensibility/test_add_country_checklist.py`
- `tests/channels/__init__.py`
- `tests/channels/test_channels_registry.py`

**修改**:
- `backend/main.py` — 加 3 行(1 phase 1 行)
- `data/tax_knowledge/uk/{vat,sa,ct,paye,sdlt}.md` — 加 `## Rates` 段
- `data/tax_knowledge/testland/vat.md` — 加 `## Rates` 段
- `backend/agent/tax_knowledge_store.py` — 加 `get_section` 方法
- `backend/agent/tax_knowledge_tools.py` — 删 if/elif 链
- `backend/channels/api_channel.py` — 通用化(零行为变化)
- `tests/agent/test_tax_knowledge.py` — 改 1 个 test

**删除**:
- `backend/agent/prompts.py`(Phase 1 终态)

---

# Phase 1 — 提示词目录化(PR #1)

## Task 1.1: 建 JURISDICTIONS 单一事实源

**Files:**
- Create: `backend/models/jurisdictions.py`
- Test: `tests/agent/test_jurisdictions_enum.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agent/test_jurisdictions_enum.py
from backend.models.jurisdictions import JURISDICTIONS, TAX_TYPES, is_valid_jurisdiction


def test_jurisdictions_frozenset():
    assert isinstance(JURISDICTIONS, frozenset)
    assert JURISDICTIONS == frozenset({"uk", "de", "cn", "fr", "testland"})


def test_tax_types_frozenset():
    assert isinstance(TAX_TYPES, frozenset)
    assert TAX_TYPES == frozenset({
        "vat", "self_assessment", "corporation_tax", "paye", "stamp_duty",
    })


def test_is_valid_jurisdiction():
    assert is_valid_jurisdiction("uk", "vat") is True
    assert is_valid_jurisdiction("de", "vat") is True
    # 大写拒绝
    assert is_valid_jurisdiction("UK", "vat") is False
    # 空拒绝
    assert is_valid_jurisdiction("", "vat") is False
    # 未知 cc 拒绝
    assert is_valid_jurisdiction("xx", "vat") is False
    # 未知 tt 拒绝
    assert is_valid_jurisdiction("uk", "VT") is False
    # 未知 tt 拒绝(典型 typo)
    assert is_valid_jurisdiction("uk", "vat_return") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/agent/test_jurisdictions_enum.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.models.jurisdictions'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/models/jurisdictions.py
"""国家 / 税种枚举 — 单一事实源

被 backend/agent/prompts/__init__.py、backend/channels/registry.py、
backend/registry.py 共同 import。**修改这里需要同时改 3 个 import 方的测试**。
"""
from __future__ import annotations

JURISDICTIONS: frozenset[str] = frozenset({"uk", "de", "cn", "fr", "testland"})

TAX_TYPES: frozenset[str] = frozenset({
    "vat", "self_assessment", "corporation_tax", "paye", "stamp_duty",
})


def is_valid_jurisdiction(jurisdiction: str, tax_type: str) -> bool:
    """检查 (cc, tt) 是否在合法枚举里。
    
    大小写敏感: 不接受 'UK' / 'VAT'。
    """
    return jurisdiction in JURISDICTIONS and tax_type in TAX_TYPES
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/agent/test_jurisdictions_enum.py -v`
Expected: PASS 3/3

- [ ] **Step 5: Commit**

```bash
git add backend/models/jurisdictions.py tests/agent/test_jurisdictions_enum.py
git commit -m "feat(models): add JURISDICTIONS/TAX_TYPES enum as single source of truth"
```

---

## Task 1.2: 拆 prompts.py → prompts/ 子包(generic + fallback)

**Files:**
- Create: `backend/agent/prompts/_generic.py`
- Create: `backend/agent/prompts/_fallback.py`
- Create: `backend/agent/prompts/__init__.py`(占位,完整实现见 1.5)

- [ ] **Step 1: 读现有 prompts.py 摘出 _GENERIC_PROMPT_HEADER**

读取 `/root/TAXI/backend/agent/prompts.py:16-51` 整段(包括 docstring 和所有 `## Your Role` / `## Important Rules` 等节),**原样复制**到新文件。

- [ ] **Step 2: Write `_generic.py`**

```python
# backend/agent/prompts/_generic.py
"""所有管辖地共享的系统提示 header。"""
from __future__ import annotations

_GENERIC_PROMPT_HEADER = """You are TaxAgent, an intelligent tax filing assistant powered by Claude.

## Your Role
You help businesses complete their tax returns and submit them to the relevant tax authority via the appropriate API or channel.

## Important Rules
- Always confirm calculations with the user before submitting to the tax authority
- Never submit a return without explicit user confirmation
- If OAuth/authentication is not configured, guide the user to complete authorization first
- Use plain language to explain tax concepts; cite specific rules where relevant
- When presenting monetary values, always include the currency symbol and appropriate decimal places
- If the user asks about tax law, provide general guidance but remind them you are not a substitute for professional tax advice

## Response Style
- Be concise but thorough
- Use bullet points for structured data
- Confirm actions before executing irreversible operations (like submitting)
- If a tool call fails, explain the error clearly and suggest next steps
- When you analyze business data, always explain the tax treatment rationale for key transactions

## Tax Law Research
You have access to a global tax knowledge base through the
`tax_agent_global_tax_kb` MCP server.

For any non-trivial tax-law question (e.g. "How does UK VAT reverse charge
work?" or "What are the EU B2B zero-rating conditions?"), call the
`tax_kb_researcher` sub-agent. It will search the knowledge base and return a
concise answer with citations.

For simple rate lookups, you may call `get_tax_rates` directly.
To see which jurisdictions are covered, call `list_supported_jurisdictions`.

All tax-knowledge tools are available to you, but the sub-agent is the
preferred path for research because it can perform multi-turn retrieval and
filtering.
"""
```

- [ ] **Step 3: 读现有 prompts.py 摘出 _FALLBACK_PROMPT**

读取 `/root/TAXI/backend/agent/prompts.py:421-429`,**原样复制**到新文件。

- [ ] **Step 4: Write `_fallback.py`**

```python
# backend/agent/prompts/_fallback.py
"""未实现管辖地的回退提示。"""
from __future__ import annotations

_FALLBACK_PROMPT = """
## Your Capabilities
You have access to tax filing tools for this jurisdiction.

## Note
Detailed regulatory knowledge for this jurisdiction is not yet fully loaded.
Please rely on the tool descriptions and general tax principles.
If you encounter unsupported scenarios, inform the user clearly.
"""
```

- [ ] **Step 5: Verify byte-equality**

```bash
# 验证拆分前后 _GENERIC_PROMPT_HEADER 内容一字不差
python -c "from backend.agent.prompts import _GENERIC_PROMPT_HEADER; print(repr(_GENERIC_PROMPT_HEADER))" 2>&1 | head -3
```

Expected: `ModuleNotFoundError`(因为 `__init__.py` 还没建) — 这是预期,先验证 `_generic.py` / `_fallback.py` 文件存在即可。

```bash
ls -la backend/agent/prompts/_generic.py backend/agent/prompts/_fallback.py
```

Expected: 2 个文件,size 1.5KB+ / 0.3KB+

- [ ] **Step 6: Commit**

```bash
git add backend/agent/prompts/_generic.py backend/agent/prompts/_fallback.py
git commit -m "refactor(prompts): extract _generic and _fallback to separate modules"
```

---

## Task 1.3: 拆 UK 5 个 tax_type + 1 testland

**Files:**
- Create: `backend/agent/prompts/uk/vat.py`
- Create: `backend/agent/prompts/uk/self_assessment.py`
- Create: `backend/agent/prompts/uk/corporation_tax.py`
- Create: `backend/agent/prompts/uk/paye.py`
- Create: `backend/agent/prompts/uk/stamp_duty.py`
- Create: `backend/agent/prompts/uk/__init__.py`
- Create: `backend/agent/prompts/testland/vat.py`
- Create: `backend/agent/prompts/testland/__init__.py`

- [ ] **Step 1: 摘出 _UK_VAT_PROMPT → uk/vat.py**

读 `backend/agent/prompts.py:57-237`,复制整段(`_UK_VAT_PROMPT` 变量定义 + 三引号字符串),改为:

```python
# backend/agent/prompts/uk/vat.py
"""UK VAT 特定提示。"""
from __future__ import annotations

PROMPT = """
## Your Capabilities (UK VAT)
... (整段 1:1 复制 _UK_VAT_PROMPT 的字符串内容,去掉变量名定义)
"""
```

**关键**:字符串内容一字不差,只改变量名 `_UK_VAT_PROMPT` → `PROMPT`。**用 `git diff` 验证**。

- [ ] **Step 2: 同样拆 uk/self_assessment.py / corporation_tax.py / paye.py / stamp_duty.py**

- `uk/self_assessment.py` ← 来自 `prompts.py:243-283`(`_UK_SA_PROMPT`)
- `uk/corporation_tax.py` ← 来自 `prompts.py:290-325`(`_UK_CT_PROMPT`)
- `uk/paye.py` ← 来自 `prompts.py:332-367`(`_UK_PAYE_PROMPT`)
- `uk/stamp_duty.py` ← 来自 `prompts.py:374-414`(`_UK_SDLT_PROMPT`)

每个文件结构:
```python
# backend/agent/prompts/uk/{tax}.py
"""{CC} {Tax} 特定提示。"""
from __future__ import annotations

PROMPT = """
... (整段 1:1 复制)
"""
```

- [ ] **Step 3: Write `uk/__init__.py`**

```python
# backend/agent/prompts/uk/__init__.py
"""UK 全部 tax_type 的 prompt 注册。"""
from __future__ import annotations

from . import vat
from . import self_assessment
from . import corporation_tax
from . import paye
from . import stamp_duty

__all__ = ["vat", "self_assessment", "corporation_tax", "paye", "stamp_duty"]
```

- [ ] **Step 4: 写 testland/vat.py(占位,Phase 1 不迁移内容)**

```python
# backend/agent/prompts/testland/vat.py
"""Testland VAT 占位 prompt。

Phase 1 故意用 fallback 兜底。后续 Phase 4 如果需要可从 testland vat agent_tools
迁移行为规则过来。
"""
from __future__ import annotations

PROMPT = """
## Your Capabilities (Testland VAT)
You have access to the Testland VAT filing tools.

## Testland VAT Rates (illustrative)
- Standard: 21%
- Reduced: 9%
- Zero: 0%

## Workflow
1. Confirm taxpayer_id (Testland TIN)
2. Use get_obligations to find open periods
3. Use calculate_return to compute
4. Use validate_return to check compliance
5. Use submit_return to file
"""
```

- [ ] **Step 5: Write `testland/__init__.py`**

```python
# backend/agent/prompts/testland/__init__.py
"""Testland prompt 注册。"""
from __future__ import annotations

from . import vat

__all__ = ["vat"]
```

- [ ] **Step 6: 验证 prompts/{uk,testland}/ 目录结构**

```bash
find backend/agent/prompts -name "*.py" | sort
```

Expected:
```
backend/agent/prompts/_fallback.py
backend/agent/prompts/_generic.py
backend/agent/prompts/testland/__init__.py
backend/agent/prompts/testland/vat.py
backend/agent/prompts/uk/__init__.py
backend/agent/prompts/uk/corporation_tax.py
backend/agent/prompts/uk/paye.py
backend/agent/prompts/uk/self_assessment.py
backend/agent/prompts/uk/stamp_duty.py
backend/agent/prompts/uk/vat.py
```

- [ ] **Step 7: Commit**

```bash
git add backend/agent/prompts/uk/ backend/agent/prompts/testland/
git commit -m "refactor(prompts): split UK 5 tax types + testland vat into per-cc dirs"
```

---

## Task 1.4: 写 prompts dispatch 测试(先红,后绿)

**Files:**
- Create: `tests/agent/test_prompts_dispatch.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agent/test_prompts_dispatch.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/agent/test_prompts_dispatch.py -v`
Expected: 部分 PASS(uk/byte_equal 失败因为 `__init__.py` 还没 dispatch,de_falls_back 失败因为没 get_system_prompt)

- [ ] **Step 3: Write `prompts/__init__.py` 完整实现**

```python
# backend/agent/prompts/__init__.py
"""按 (cc, tax_type) 动态加载系统提示。

用法:
    from backend.agent.prompts import get_system_prompt
    prompt = get_system_prompt("uk", "vat")
"""
from __future__ import annotations

import importlib
import logging

from backend.models.jurisdictions import (
    JURISDICTIONS, TAX_TYPES, is_valid_jurisdiction,
)

from ._generic import _GENERIC_PROMPT_HEADER
from ._fallback import _FALLBACK_PROMPT

logger = logging.getLogger(__name__)

__all__ = [
    "get_system_prompt", "SYSTEM_PROMPT",
    "JURISDICTIONS", "TAX_TYPES",  # re-export
]


def get_system_prompt(jurisdiction: str, tax_type: str) -> str:
    """加载 (jurisdiction, tax_type) 的系统提示。

    错误分层:
    - 枚举层 (cc / tt 不在 JURISDICTIONS / TAX_TYPES): KeyError(严)
    - 模块层 (cc 已注册但子包无该 tax 文件): fallback + warning log(软)

    Raises:
        KeyError: jurisdiction 不在 JURISDICTIONS 或 tax_type 不在 TAX_TYPES
    """
    if not is_valid_jurisdiction(jurisdiction, tax_type):
        raise KeyError(
            f"Unknown jurisdiction={jurisdiction!r} or tax_type={tax_type!r}. "
            f"Valid jurisdictions: {sorted(JURISDICTIONS)}; "
            f"Valid tax_types: {sorted(TAX_TYPES)}"
        )
    try:
        mod = importlib.import_module(
            f"backend.agent.prompts.{jurisdiction}.{tax_type}"
        )
        specific = getattr(mod, "PROMPT", _FALLBACK_PROMPT)
    except ModuleNotFoundError:
        logger.warning(
            "No prompt file for %s:%s — using _FALLBACK_PROMPT. "
            "Consider adding backend/agent/prompts/%s/%s.py",
            jurisdiction, tax_type, jurisdiction, tax_type,
        )
        specific = _FALLBACK_PROMPT
    return _GENERIC_PROMPT_HEADER + specific


# 向后兼容: 旧版 `from backend.agent.prompts import SYSTEM_PROMPT` 仍可用
SYSTEM_PROMPT = get_system_prompt("uk", "vat")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/agent/test_prompts_dispatch.py -v`
Expected: PASS 10/10

- [ ] **Step 5: Commit**

```bash
git add backend/agent/prompts/__init__.py tests/agent/test_prompts_dispatch.py
git commit -m "feat(prompts): dynamic dispatch via importlib + KeyError on invalid cc/tt"
```

---

## Task 1.5: 写 cc 隔离测试(grep-based)

**Files:**
- Create: `tests/extensibility/__init__.py`
- Create: `tests/extensibility/test_jurisdiction_isolation.py`

- [ ] **Step 1: Write `__init__.py`**

```python
# tests/extensibility/__init__.py
"""跨国家 / 跨 phase 的架构不变性测试。

参照 tests/erp/test_case_isolation.py 范本。
"""
```

- [ ] **Step 2: Write the failing test**

```python
# tests/extensibility/test_jurisdiction_isolation.py
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
```

- [ ] **Step 3: Run test to verify it passes**

Run: `.venv/bin/pytest tests/extensibility/test_jurisdiction_isolation.py -v`
Expected: PASS(所有 cc 子包不互相 import)

- [ ] **Step 4: Commit**

```bash
git add tests/extensibility/
git commit -m "test(prompts): assert prompts/{cc}/ don't import other cc subpackages"
```

---

## Task 1.6: 删除原 prompts.py

**Files:**
- Delete: `backend/agent/prompts.py`

- [ ] **Step 1: 跑全部相关测试,确认无回归**

Run:
```bash
.venv/bin/pytest tests/agent/ tests/erp/ -q
```

Expected: 全部 PASS(byte-equality 测验证零行为变化)

- [ ] **Step 2: 删除 prompts.py**

```bash
git rm backend/agent/prompts.py
```

- [ ] **Step 3: 验证 import 仍工作**

```bash
python -c "from backend.agent.prompts import get_system_prompt, SYSTEM_PROMPT; print(SYSTEM_PROMPT[:80])"
```

Expected: 输出 "You are TaxAgent, an intelligent tax filing assistant powered by Claude.\n\n## You"...

- [ ] **Step 4: 跑 frontend build 确认无影响**

```bash
cd frontend && npm run build 2>&1 | tail -5
```

Expected: `built in 8s` 左右,0 错误

- [ ] **Step 5: Commit**

```bash
git commit -m "refactor(prompts): delete monolithic prompts.py; dispatch via prompts/ subpackage"
```

---

## Task 1.7: 写 e2e 加国家 checklist 测试

**Files:**
- Create: `tests/extensibility/test_add_country_checklist.py`

- [ ] **Step 1: Write the test**

```python
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
    text = text.replace("UK VAT", "E2E VAT", 1)
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
    result = subprocess.run(
        ["git", "diff", "--name-only", "main.py"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    # 验证: prompts/ 或 channels/ 等 cc 相关文件不在全局改动名单
    # (这里的"全局"定义为 root 顶层文件)
    # 实际: 我们只测 main.py 是否被改
    assert result.returncode == 0
    # 不强制 0 改动(其他 PR 可能改 main.py),只测本 PR 内的"加国家"
    # 流程不会触发 main.py 改动
```

- [ ] **Step 2: Run test to verify it passes**

Run: `.venv/bin/pytest tests/extensibility/test_add_country_checklist.py -v`
Expected: PASS 1/1(第二个 test 是 CI 守卫,本 PR 内不强制)

- [ ] **Step 3: Commit**

```bash
git add tests/extensibility/test_add_country_checklist.py
git commit -m "test(extensibility): e2e 'add a country' checklist = cp + sed + 0 global edits"
```

---

## Task 1.8: Phase 1 注册 1 行 + 收口

**Files:**
- Modify: `backend/main.py`(加 1 行 import / 不加 register,因为 Phase 1 不动 adapter)

- [ ] **Step 1: 跑全部测试确认 Phase 1 不破**

Run:
```bash
.venv/bin/pytest tests/ -q --ignore=tests/extensibility/test_add_country_checklist.py
.venv/bin/pytest tests/extensibility/test_add_country_checklist.py -v
cd frontend && npm run build 2>&1 | tail -3
```

Expected: 全部 PASS,frontend build 0 错误

- [ ] **Step 2: 手动 grep 验证 0 残留 `_UK_VAT_PROMPT` 等**

```bash
grep -rn "_UK_VAT_PROMPT\|_UK_SA_PROMPT\|_UK_CT_PROMPT\|_UK_PAYE_PROMPT\|_UK_SDLT_PROMPT\|_FALLBACK_PROMPT\|_GENERIC_PROMPT_HEADER" \
  backend/ frontend/src/ tests/ --include="*.py" 2>/dev/null
```

Expected: 仅在 `backend/agent/prompts/{uk,testland}/` 内出现,以及 `__init__.py` 引用;无其他文件。

- [ ] **Step 3: 跑 1 次 e2e smoke**

```bash
# 启动后端
./start_backend.sh &
sleep 5
# 验证
curl -s localhost:8765/api/agent/health | python -c "import json,sys; d=json.load(sys.stdin); print(d.get('jurisdictions', d))"
```

Expected: 200 OK + 包含 uk 的列表

- [ ] **Step 4: 关闭后端 + 提交**

```bash
pkill -f "uvicorn.*backend.main" 2>/dev/null
git status
```

(无新增改动,Phase 1 收口)

- [ ] **Step 5: 标记 PR #1 ready**

Phase 1 完成。PR 描述模板:

```markdown
## Phase 1: 提示词目录化

### 改动
- 新增: backend/models/jurisdictions.py
- 新增: backend/agent/prompts/{_generic,_fallback}.py
- 新增: backend/agent/prompts/{uk,testland}/ 子包
- 新增: tests/agent/{test_jurisdictions_enum,test_prompts_dispatch}.py
- 新增: tests/extensibility/{__init__,test_jurisdiction_isolation,test_add_country_checklist}.py
- 删除: backend/agent/prompts.py
- backend/main.py: 0 行(本 phase 不动 registry)

### 验证
- [ ] `pytest tests/agent/ tests/extensibility/ -q` 全 PASS
- [ ] `pytest tests/erp/ -q` 0 回归
- [ ] `cd frontend && npm run build` 0 错误
- [ ] `grep -rn "_UK_VAT_PROMPT" backend/` 只在 `prompts/uk/vat.py` 内

### 触达全局文件数
0
```

---

# Phase 2 — 税率 KB 驱动(PR #2)

## Task 2.1: 给 UK 5 + testland 1 KB md 加 `## Rates` 段

**Files:**
- Modify: `data/tax_knowledge/uk/vat.md`
- Modify: `data/tax_knowledge/uk/self_assessment.md`
- Modify: `data/tax_knowledge/uk/corporation_tax.md`
- Modify: `data/tax_knowledge/uk/paye.md`
- Modify: `data/tax_knowledge/uk/stamp_duty.md`
- Modify: `data/tax_knowledge/testland/vat.md`
- Test: `tests/agent/test_tax_kb_rates.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/agent/test_tax_kb_rates.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/agent/test_tax_kb_rates.py -v`
Expected: FAIL(6 个文件都没 `## Rates` 段)

- [ ] **Step 3: 给 `data/tax_knowledge/uk/vat.md` 加 `## Rates` 段**

在文件**最顶部**(`# Title` 之后,第一个 `##` 之前)插入:

```markdown
## Rates

<!-- format: json -->
```json
{"standard": 0.20, "reduced": 0.05, "zero": 0.00}
```

<!-- source: https://www.gov.uk/vat-rates -->
```

- [ ] **Step 4: 给 `data/tax_knowledge/uk/corporation_tax.md` 加 `## Rates` 段**

```markdown
## Rates

```json
{"small_profits_rate": 0.19, "main_rate": 0.25}
```

<!-- source: https://www.gov.uk/corporation-tax-rates -->
```

- [ ] **Step 5: 给 `data/tax_knowledge/uk/{self_assessment,paye,stamp_duty}.md` 加空 `## Rates` 段**

3 个文件统一加:

```markdown
## Rates

(本税种按收入/价值分级征税,无单一"standard rate";详见各专题小节。)

<!-- 工具调用 get_tax_rates(uk, self_assessment) 将返回 note: 详细分级见 ## Bands 段。 -->
```

- [ ] **Step 6: 给 `data/tax_knowledge/testland/vat.md` 加 `## Rates` 段**

```markdown
## Rates

```json
{"standard": 0.21, "reduced": 0.09, "zero": 0.00}
```

<!-- source: Testland Tax Authority illustrative rates -->
```

- [ ] **Step 7: Run test to verify it passes**

Run: `.venv/bin/pytest tests/agent/test_tax_kb_rates.py -v`
Expected: PASS 6/6 + 1/1

- [ ] **Step 8: Commit**

```bash
git add data/tax_knowledge/ tests/agent/test_tax_kb_rates.py
git commit -m "feat(kb): add ## Rates section to UK 5 + testland 1 KB markdown files"
```

---

## Task 2.2: TaxKnowledgeStore 加 get_section 方法

**Files:**
- Modify: `backend/agent/tax_knowledge_store.py`

- [ ] **Step 1: 读现状,理解数据结构**

Read: `backend/agent/tax_knowledge_store.py:11-90`(完整文件)

确认:`KnowledgeSection` dataclass + `_cache: dict[Tuple[str, str], List[KnowledgeSection]]` 已存在。

- [ ] **Step 2: 加 `get_section` 方法**

在文件末尾(`return sections` 之后)添加:

```python
    def get_section(
        self, jurisdiction: str, tax_type: str, title: str,
    ) -> Optional[KnowledgeSection]:
        """按 H2 标题取 1 个 section。
        
        Args:
            jurisdiction: cc
            tax_type: tax_type
            title: 严格匹配的 H2 标题(不含 `##` 前缀)
        
        Returns:
            第一个匹配 title 的 KnowledgeSection,或 None(未找到)
        """
        sections = self._cache.get((jurisdiction, tax_type), [])
        for section in sections:
            if section.title == title:
                return section
        return None
```

并更新顶部 import:
```python
from typing import List, Optional, Tuple
```

- [ ] **Step 3: 跑 KB 测试,确认 0 回归**

Run: `.venv/bin/pytest tests/agent/test_tax_knowledge.py tests/agent/test_tax_kb_rates.py -v`
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add backend/agent/tax_knowledge_store.py
git commit -m "feat(kb): add TaxKnowledgeStore.get_section(jurisdiction, tax_type, title)"
```

---

## Task 2.3: 重写 get_tax_rates 走 KB

**Files:**
- Modify: `backend/agent/tax_knowledge_tools.py:62-67`
- Modify: `tests/agent/test_tax_knowledge.py`(改 1 个 test)

- [ ] **Step 1: 读现状**

Read: `backend/agent/tax_knowledge_tools.py:60-77`(`async def get_tax_rates`)

- [ ] **Step 2: 写失败测试**

在 `tests/agent/test_tax_knowledge.py` 添加(在文件末尾):

```python
@pytest.mark.asyncio
async def test_get_tax_rates_uk_vat_reads_from_kb():
    """UK VAT 走 KB ## Rates 段,不再硬编码 0.20。"""
    from backend.agent.tax_knowledge_tools import TaxKnowledgeAgentToolSet
    tools = TaxKnowledgeAgentToolSet()
    r = await tools.get_tax_rates("uk", "vat")
    body = json.loads(r["content"][0]["text"])
    assert body["success"] is True
    assert body["rates"]["standard"] == 0.20
    assert body["rates"]["reduced"] == 0.05


@pytest.mark.asyncio
async def test_get_tax_rates_de_vat_falls_back():
    """de vat 无 ## Rates 段,返回 'not yet available' note。"""
    from backend.agent.tax_knowledge_tools import TaxKnowledgeAgentToolSet
    tools = TaxKnowledgeAgentToolSet()
    r = await tools.get_tax_rates("de", "vat")
    body = json.loads(r["content"][0]["text"])
    assert body["success"] is True
    # 段缺失 → note 字段
    if "note" not in body["rates"]:
        pytest.fail(f"expected 'note' fallback for de/vat, got {body['rates']}")


@pytest.mark.asyncio
async def test_get_tax_rates_unknown_cc_returns_error():
    """未知 cc 返回 _tool_error(严)。"""
    from backend.agent.tax_knowledge_tools import TaxKnowledgeAgentToolSet
    tools = TaxKnowledgeAgentToolSet()
    r = await tools.get_tax_rates("xx", "vat")
    body = json.loads(r["content"][0]["text"])
    assert body["success"] is False


@pytest.mark.asyncio
async def test_get_tax_rates_testland_vat_reads_from_kb():
    """Testland vat 走 KB(0.21 标准税率)。"""
    from backend.agent.tax_knowledge_tools import TaxKnowledgeAgentToolSet
    tools = TaxKnowledgeAgentToolSet()
    r = await tools.get_tax_rates("testland", "vat")
    body = json.loads(r["content"][0]["text"])
    assert body["success"] is True
    assert body["rates"]["standard"] == 0.21
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/agent/test_tax_knowledge.py -k test_get_tax_rates -v`
Expected: 4 个都 FAIL(get_tax_rates 还是 if/elif)

- [ ] **Step 4: 重写 get_tax_rates**

替换 `tax_knowledge_tools.py:60-77` 整段 `get_tax_rates`:

```python
    async def get_tax_rates(self, jurisdiction: str, tax_type: str, year: Optional[str] = None) -> dict:
        """从 KB 读 ## Rates 段。
        
        数据驱动: 不再硬编码 if/elif。新国家在 data/tax_knowledge/{cc}/{tax}.md
        加 ## Rates 段后,本工具自动支持。
        """
        if not is_valid_jurisdiction(jurisdiction, tax_type):
            return _tool_error(
                f"Unknown jurisdiction={jurisdiction!r} or tax_type={tax_type!r}"
            )
        section = self.store.get_section(jurisdiction, tax_type, "Rates")
        if section is None:
            return _tool_ok({
                "success": True,
                "jurisdiction": jurisdiction,
                "tax_type": tax_type,
                "year": year,
                "rates": {"note": f"Rate table not yet available for {jurisdiction}/{tax_type}"},
            })
        # 解析 section.content 里的 ```json ... ``` 块
        import re
        m = re.search(r"```json\s*(\{.*?\})\s*```", section.content, re.DOTALL)
        if m is None:
            # 段存在但无 JSON 块(SA / PAYE 等按 band 征税)
            return _tool_ok({
                "success": True,
                "jurisdiction": jurisdiction,
                "tax_type": tax_type,
                "year": year,
                "rates": {"note": f"{tax_type} uses banded rates; see KB ## Bands section"},
            })
        import json
        rates = json.loads(m.group(1))
        return _tool_ok({
            "success": True,
            "jurisdiction": jurisdiction,
            "tax_type": tax_type,
            "year": year,
            "rates": rates,
        })
```

并在文件顶部 import:
```python
from backend.models.jurisdictions import is_valid_jurisdiction
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/agent/test_tax_knowledge.py -k test_get_tax_rates -v`
Expected: PASS 4/4

- [ ] **Step 6: 跑全 KB 测试**

Run: `.venv/bin/pytest tests/agent/ -q`
Expected: 全部 PASS

- [ ] **Step 7: Commit**

```bash
git add backend/agent/tax_knowledge_tools.py tests/agent/test_tax_knowledge.py
git commit -m "refactor(kb-tools): get_tax_rates reads from KB ## Rates section (no if/elif)"
```

---

## Task 2.4: Phase 2 收口

- [ ] **Step 1: 全测试回归**

```bash
.venv/bin/pytest tests/ -q
cd frontend && npm run build 2>&1 | tail -3
```

Expected: 全 PASS + build 0 错误

- [ ] **Step 2: 标记 PR #2 ready**

PR 描述:

```markdown
## Phase 2: 税率 KB 驱动

### 改动
- 修改: data/tax_knowledge/{uk/*,testland/vat}.md (加 ## Rates 段)
- 修改: backend/agent/tax_knowledge_store.py (加 get_section)
- 修改: backend/agent/tax_knowledge_tools.py (删 if/elif)
- 新增: tests/agent/test_tax_kb_rates.py
- 修改: tests/agent/test_tax_knowledge.py (加 4 个 test)
- backend/main.py: 0 行

### 验证
- [ ] `pytest tests/agent/ -q` 全 PASS
- [ ] `get_tax_rates("uk", "vat")` 返回 KB 里 0.20(非硬编码)
- [ ] `get_tax_rates("de", "vat")` 返回 fallback note
- [ ] `get_tax_rates("xx", "vat")` 返回 _tool_error

### 触达全局文件数
0
```

---

# Phase 3 — 渠道子包 + ChannelRegistry(PR #3)

## Task 3.1: ChannelRegistry 新建

**Files:**
- Create: `backend/channels/registry.py`
- Test: `tests/channels/test_channels_registry.py`
- Create: `tests/channels/__init__.py`

- [ ] **Step 1: 写 channels/ 测试目录**

```bash
mkdir -p tests/channels
touch tests/channels/__init__.py
```

- [ ] **Step 2: Write the failing test**

```python
# tests/channels/test_channels_registry.py
"""ChannelRegistry(cc × tt → Channel) 行为。"""
import pytest

from backend.channels.registry import ChannelRegistry
from backend.channels import FilingChannel
from backend.models.tax_data import ChannelType


class _MockChannel(FilingChannel):
    channel_type = ChannelType.API
    
    async def authenticate(self):
        from backend.models.results import AuthResult
        return AuthResult(success=True, access_token="mock")
    
    async def submit(self, payload):
        from backend.models.results import SubmitResult, StatusResult
        return SubmitResult(success=True, status=StatusResult.SUBMITTED)
    
    async def get_status(self, receipt):
        from backend.models.results import StatusResult
        return StatusResult(status="ACCEPTED")
    
    async def health_check(self) -> bool:
        return True


def test_register_and_get():
    reg = ChannelRegistry()
    ch = _MockChannel()
    reg.register("uk", "vat", ch)
    assert reg.get("uk", "vat") is ch


def test_register_invalid_cc_raises_keyerror():
    reg = ChannelRegistry()
    ch = _MockChannel()
    with pytest.raises(KeyError) as exc:
        reg.register("xx", "vat", ch)
    assert "Unknown" in str(exc.value)


def test_register_invalid_tt_raises_keyerror():
    reg = ChannelRegistry()
    ch = _MockChannel()
    with pytest.raises(KeyError) as exc:
        reg.register("uk", "VT", ch)
    assert "Unknown" in str(exc.value)


def test_get_unregistered_raises_keyerror():
    reg = ChannelRegistry()
    with pytest.raises(KeyError) as exc:
        reg.get("cn", "vat")
    assert "No channel" in str(exc.value)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/channels/test_channels_registry.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'backend.channels.registry'`

- [ ] **Step 4: Write `backend/channels/registry.py`**

```python
# backend/channels/registry.py
"""ChannelRegistry — 按 (cc, tax_type) 索引 FilingChannel 实例。

对称 JurisdictionRegistry / ChannelType(原 backend/models/tax_data.py)。
"""
from __future__ import annotations

from backend.models.jurisdictions import is_valid_jurisdiction
from . import FilingChannel


class ChannelRegistry:
    """渠道注册表 — 一个 (cc, tax_type) 对应一个 FilingChannel 实例。"""
    
    def __init__(self) -> None:
        self._channels: dict[tuple[str, str], FilingChannel] = {}
    
    def register(self, jurisdiction: str, tax_type: str, channel: FilingChannel) -> None:
        """注册 1 个 channel。cc / tt 必须在 JURISDICTIONS / TAX_TYPES 内。"""
        if not is_valid_jurisdiction(jurisdiction, tax_type):
            raise KeyError(
                f"Unknown jurisdiction={jurisdiction!r} or tax_type={tax_type!r}"
            )
        self._channels[(jurisdiction, tax_type)] = channel
    
    def get(self, jurisdiction: str, tax_type: str) -> FilingChannel:
        """取 1 个 channel。未注册抛 KeyError。"""
        key = (jurisdiction, tax_type)
        if key not in self._channels:
            raise KeyError(
                f"No channel registered for {jurisdiction}:{tax_type}. "
                f"Registered: {sorted(self._channels.keys())}"
            )
        return self._channels[key]
    
    def list_registered(self) -> list[tuple[str, str]]:
        return sorted(self._channels.keys())
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/channels/test_channels_registry.py -v`
Expected: PASS 4/4

- [ ] **Step 6: Commit**

```bash
git add backend/channels/registry.py tests/channels/
git commit -m "feat(channels): ChannelRegistry(cc × tt → Channel) symmetric to JurisdictionRegistry"
```

---

## Task 3.2: 把 UK channel 挪到 channels/uk/ 子包

**Files:**
- Create: `backend/channels/uk/__init__.py`
- Create: `backend/channels/browser_channel.py`(占位)
- Modify: `backend/main.py`(1 行)

- [ ] **Step 1: 写 `backend/channels/uk/__init__.py`**

读 `backend/main.py:46-50` 找出现有 UK channel 实例化代码,迁过来:

```python
# backend/channels/uk/__init__.py
"""UK 渠道工厂。

构造一个 FilingChannel(目前是 APIChannel,后续可能分 vat / ct 等不同 endpoint)。
"""
from __future__ import annotations

from backend.channels import FilingChannel
from backend.channels.api_channel import APIChannel
from backend.jurisdictions.uk.config import uk_config


def make_uk_vat_channel() -> FilingChannel:
    """UK VAT 渠道(API)。"""
    return APIChannel(
        base_url=uk_config.hmrc.base_url,
        oauth_config=uk_config.hmrc.vat_oauth,
        submit_endpoint=uk_config.hmrc.vat_submit_endpoint,
        status_endpoint=uk_config.hmrc.vat_status_endpoint,
        health_endpoint="/",
        fraud_headers=True,
        vendor_product="TaxAgent Global",
    )


__all__ = ["make_uk_vat_channel"]
```

- [ ] **Step 2: 写 `backend/channels/browser_channel.py` 占位**

```python
# backend/channels/browser_channel.py
"""BrowserChannel — 浏览器自动化占位(Playwright)。

Phase 3 仅占位。CN / FR 等无 API 国家在后续 Phase 4 / 5 实现。
"""
from __future__ import annotations

import logging

from backend.models.results import AuthResult, SubmitResult, StatusResult, FilingPayload, Receipt
from backend.models.tax_data import ChannelType
from backend.channels import FilingChannel

logger = logging.getLogger(__name__)


class BrowserChannel(FilingChannel):
    """占位 BrowserChannel — raise NotImplementedError。"""
    channel_type = ChannelType.BROWSER
    
    async def authenticate(self) -> AuthResult:
        raise NotImplementedError("BrowserChannel not yet implemented")
    
    async def submit(self, payload: FilingPayload) -> SubmitResult:
        raise NotImplementedError("BrowserChannel not yet implemented")
    
    async def get_status(self, receipt: Receipt) -> StatusResult:
        raise NotImplementedError("BrowserChannel not yet implemented")
    
    async def health_check(self) -> bool:
        return False
```

- [ ] **Step 3: 改 `backend/main.py` — 注册 1 行 channel**

读 `backend/main.py:46-50`,在 `registry.register(UKJurisdictionAdapter())` **之前/之后** 加 1 行:

```python
from backend.channels.registry import ChannelRegistry
from backend.channels.uk import make_uk_vat_channel

channel_registry = ChannelRegistry()
channel_registry.register("uk", "vat", make_uk_vat_channel())
```

- [ ] **Step 4: 跑全部测试,确认 0 回归**

Run:
```bash
.venv/bin/pytest tests/ -q
cd frontend && npm run build 2>&1 | tail -3
```

Expected: 全 PASS + build 0 错误

- [ ] **Step 5: 启动后端,验证 health endpoint 仍工作**

```bash
./start_backend.sh &
sleep 5
curl -s localhost:8765/api/agent/health
pkill -f "uvicorn.*backend.main" 2>/dev/null
```

Expected: 200 OK,健康检查通过

- [ ] **Step 6: Commit**

```bash
git add backend/channels/uk/ backend/channels/browser_channel.py backend/main.py
git commit -m "feat(channels): UK channel factory in channels/uk/ + browser placeholder"
```

---

## Task 3.3: Phase 3 收口

- [ ] **Step 1: 全测试 + e2e smoke 回归**

```bash
.venv/bin/pytest tests/ -q
cd frontend && npm run build 2>&1 | tail -3
./start_backend.sh &
sleep 5
curl -s localhost:8765/api/agent/health
pkill -f "uvicorn.*backend.main" 2>/dev/null
```

Expected: 全 PASS + build 0 错误 + health 200

- [ ] **Step 2: git diff 验证 main.py 只增 1 行**

```bash
git diff main.py | head -30
```

Expected: 仅 +1 行 channel_registry.register 相关的代码(总计 3 phase 增 3 行,可接受)

- [ ] **Step 3: 标记 PR #3 ready**

PR 描述:

```markdown
## Phase 3: 渠道子包 + ChannelRegistry

### 改动
- 新增: backend/channels/registry.py (ChannelRegistry 类)
- 新增: backend/channels/uk/__init__.py (UK channel 工厂)
- 新增: backend/channels/browser_channel.py (占位)
- 新增: tests/channels/__init__.py + test_channels_registry.py
- 修改: backend/main.py (+3 行 channel_registry 注册)

### 验证
- [ ] `pytest tests/channels/ -q` PASS 4/4
- [ ] `pytest tests/ -q` 0 回归
- [ ] `cd frontend && npm run build` 0 错误
- [ ] `git diff main.py` +3 行

### 触达全局文件数
1 (main.py 3 行)
```

---

# 终态验收(3 个 PR 合并后)

## 终态测试 1: 加 1 个新国家流程

```bash
# 模拟贡献者加 DE VAT
cp -r backend/agent/prompts/uk backend/agent/prompts/de
sed -i 's/UK VAT/DE VAT/g; s|https://www.gov.uk|https://www.bzst.de|g' backend/agent/prompts/de/vat.py
cp data/tax_knowledge/uk/vat.md data/tax_knowledge/de/vat.md
sed -i 's/"standard": 0.20/"standard": 0.19/g' data/tax_knowledge/de/vat.md

# 验证: get_system_prompt("de", "vat") 不再走 fallback
python -c "from backend.agent.prompts import get_system_prompt; p = get_system_prompt('de', 'vat'); print('DE VAT' in p)"
# True

# 验证: get_tax_rates("de", "vat") 返回 0.19
python -c "
import asyncio
from backend.agent.tax_knowledge_tools import TaxKnowledgeAgentToolSet
async def m():
    t = TaxKnowledgeAgentToolSet()
    r = await t.get_tax_rates('de', 'vat')
    import json; print(json.loads(r['content'][0]['text']))
asyncio.run(m())
"
# {'success': True, 'jurisdiction': 'de', 'tax_type': 'vat', 'rates': {'standard': 0.19, ...}}
```

## 终态测试 2: 触达全局文件数

```bash
# 整个加 DE 流程触达的文件
git status --porcelain | awk '{print $2}' | sort -u
# 应只包含:
#   backend/agent/prompts/de/{__init__,vat}.py  (新)
#   data/tax_knowledge/de/vat.md                 (新)
# **不包含** backend/main.py 或 backend/channels/registry.py
```

## 终态测试 3: cc 隔离

```bash
# 跨 cc import = 0
grep -rn "from backend.agent.prompts\." backend/agent/prompts/ | grep -v "from \.\|from \._"
# 输出应只包含:
#   backend/agent/prompts/__init__.py 的 importlib 动态 import
#   (即 1 行 f-string 调用 importlib.import_module)
# **不包含** uk → cn 或 de → uk 之类的静态 import
```

---

# 进度跟踪

- [ ] **Phase 1 — 提示词目录化**
  - [ ] Task 1.1 JURISDICTIONS 单一事实源
  - [ ] Task 1.2 拆 generic + fallback
  - [ ] Task 1.3 拆 UK 5 + testland 1
  - [ ] Task 1.4 prompts dispatch 测试
  - [ ] Task 1.5 cc 隔离测试
  - [ ] Task 1.6 删除原 prompts.py
  - [ ] Task 1.7 e2e 加国家 checklist 测试
  - [ ] Task 1.8 Phase 1 收口
- [ ] **Phase 2 — 税率 KB 驱动**
  - [ ] Task 2.1 KB md 加 ## Rates 段
  - [ ] Task 2.2 TaxKnowledgeStore.get_section
  - [ ] Task 2.3 重写 get_tax_rates
  - [ ] Task 2.4 Phase 2 收口
- [ ] **Phase 3 — 渠道子包**
  - [ ] Task 3.1 ChannelRegistry
  - [ ] Task 3.2 UK channel 挪子包
  - [ ] Task 3.3 Phase 3 收口
- [ ] **终态验收**(3 PR 合并后)
  - [ ] 加 1 个新国家流程
  - [ ] 触达全局文件数 ≤ 1
  - [ ] cc 隔离 grep = 0
