# Extensibility Refactor — 按国家分离的知识库 / 工具 / Skills / 报税流程

> **Spec 状态**:待用户审阅
> **日期**:2026-06-12
> **作者**:Claude (brainstorming → writing-spec 流程)
> **前置文档**:`docs/architecture/extensibility.md`(现状分析)、`docs/architecture/adding-new-jurisdiction.md`(旧指南,本次不引用)

## 0. 摘要(1 段)

把"该目录式但不是目录式"的 2 个债拆成目录:把 `backend/agent/prompts.py` 单文件 dict 拆为 `prompts/{cc}/{tax}.py` 子包 + importlib 动态加载(Phase 1);把 `tax_knowledge_tools.get_tax_rates` 的 if/elif 链替换为 KB `## Rates` 段读取(Phase 2);把 `channels/api_channel.py` 单类拆为 `channels/{cc}/` 子包 + `ChannelRegistry`(Phase 3)。引入 `JURISDICTIONS` / `TAX_TYPES` 单一枚举。**3 个独立 PR 一起交付**。**加 1 个新国家触达全局文件 ≤ 1 处**(仅 `backend/main.py` 注册 1 行)。

## 1. 目标与非目标

### 1.1 目标
1. **加 1 个新国家(以 DE 为例)的端到端流程触达全局文件 ≤ 1 处**
2. 加新国家的开发者只需要 `cp -r prompts/uk de && sed -i 's/UK/DE/g' prompts/de/vat.py` 这类"复制-改 5 行"操作
3. 错误处理从"静默 fallback"改为"已注册国家严 / 未注册国家软"
4. 加新国家的成功标准:能跑出第 6 个 MCP server

### 1.2 非目标(YAGNI)
- 不做 KB 自动从 PDF/法规网 sync(产品债)
- 不做 Playwright session 池等渠道性能优化
- 不实现 CN/CIT 等真实计算器(产品功能债,非架构债)
- 不把 prompt 全部 markdown 化(行为规则 vs 数据,边界不清)
- 不实现 LLM 视角的"国家切换"自动检测

## 2. 范围(scope)

**In**:
- L5 提示词:目录化(Phase 1)
- L2 工具:税率 KB 驱动(Phase 2)
- L2 渠道:子包 + Registry(Phase 3)
- `JURISDICTIONS` / `TAX_TYPES` 单一枚举
- 错误处理分层(已注册严 / 未注册软)
- 测试套件 ~30 个新 case

**Out**:
- 改 `tools.py:106-128` 的 `_resolve_method_name` 行为
- 改 `tools.py:_DICT_PARAM_NAMES` 之类的 wrapper 逻辑
- 改 `agent_tools.py` 的 ABC 签名
- 改 `JurisdictionRegistry` 的核心协议(`register` / `get` / `list_jurisdictions`)
- 改 `data/tax_knowledge/taxonomy/*.yaml`(本次不动)
- 改前端(完全无关)

## 3. 架构

### 3.1 Layer 拓扑对比

| Layer | 现状 | 目标 |
|---|---|---|
| L5 提示词 | `prompts.py` 单文件 + 5 个 UK 字符串常量 | `prompts/{cc}/{tax}.py` 子包 |
| L4 工具 | `jurisdictions/{cc}/{tax}/agent_tools.py` | **不变** |
| L3 适配器 | `jurisdictions/{cc}/...` | **不变** |
| L2 工具 | `tax_knowledge_tools.py` if/elif | KB `## Rates` 段读取 |
| L2 渠道 | `channels/api_channel.py` 单类 | `channels/{cc}/` + `registry.py` |
| L1 KB | `data/tax_knowledge/{cc}/{tax}.md` | **不变**(加 `## Rates` 段) |

### 3.2 关键新概念

#### `backend/models/jurisdictions.py`(新)
```python
from __future__ import annotations

JURISDICTIONS: frozenset[str] = frozenset({"uk", "de", "cn", "fr", "testland"})
TAX_TYPES: frozenset[str] = frozenset({
    "vat", "self_assessment", "corporation_tax", "paye", "stamp_duty",
})

def is_valid_jurisdiction(cc: str, tt: str) -> bool:
    return cc in JURISDICTIONS and tt in TAX_TYPES
```

被 `prompts/__init__.py` / `channels/registry.py` / `JurisdictionRegistry.register` 共同 import。**单一事实源**。

#### 提示词加载机制
```
get_system_prompt("uk", "vat")
  ↓
is_valid_jurisdiction("uk", "vat") == True  # 枚举校验
  ↓
importlib.import_module("backend.agent.prompts.uk.vat")
  ↓
mod.PROMPT
  ↓
return _GENERIC_PROMPT_HEADER + mod.PROMPT
```

错误处理分 2 层:
- **枚举层**:未知 cc 或 tt → `KeyError`(严)
- **模块层**:已注册 cc 但子包无该 tax 文件 → 走 `_FALLBACK_PROMPT` + warning log(软)

## 4. 组件

### 4.1 `backend/agent/prompts/` 目录结构

```
prompts/
├── __init__.py          ← get_system_prompt(cc, tt), importlib + KeyError
├── _generic.py          ← 原 _GENERIC_PROMPT_HEADER (零改)
├── _fallback.py         ← 原 _FALLBACK_PROMPT (零改)
├── uk/
│   ├── __init__.py      ← UK_PROMPTS = {"vat": ..., "self_assessment": ..., ...}
│   ├── vat.py           ← 原 _UK_VAT_PROMPT 内容(变量名改 PROMPT)
│   ├── self_assessment.py
│   ├── corporation_tax.py
│   ├── paye.py
│   └── stamp_duty.py
└── testland/
    └── vat.py           ← 原 testland/vat 内容(占位)
```

### 4.2 `prompts/__init__.py` 核心实现
```python
import importlib
import logging
from backend.models.jurisdictions import is_valid_jurisdiction, _FALLBACK_PROMPT
from ._generic import _GENERIC_PROMPT_HEADER

logger = logging.getLogger(__name__)

def get_system_prompt(jurisdiction: str, tax_type: str) -> str:
    """加载 (jurisdiction, tax_type) 的系统提示。
    
    Raises:
        KeyError: cc 不在 JURISDICTIONS 或 tt 不在 TAX_TYPES
    """
    if not is_valid_jurisdiction(jurisdiction, tax_type):
        raise KeyError(
            f"Unknown jurisdiction={jurisdiction!r} or tax_type={tax_type!r}. "
            f"Valid: cc ∈ {sorted(JURISDICTIONS)}, tt ∈ {sorted(TAX_TYPES)}"
        )
    try:
        mod = importlib.import_module(f"backend.agent.prompts.{jurisdiction}.{tax_type}")
        specific = getattr(mod, "PROMPT", _FALLBACK_PROMPT)
    except ModuleNotFoundError:
        logger.warning(
            "No prompt file for %s:%s — using _FALLBACK_PROMPT. "
            "Consider adding backend/agent/prompts/%s/%s.py",
            jurisdiction, tax_type, jurisdiction, tax_type,
        )
        specific = _FALLBACK_PROMPT
    return _GENERIC_PROMPT_HEADER + specific

# 向后兼容: 旧版直接导入
SYSTEM_PROMPT = get_system_prompt("uk", "vat")
```

### 4.3 KB `## Rates` 段 schema

每个 `data/tax_knowledge/{cc}/{tax}.md` 头部加(UK 5 个 + testland 1 个):
```markdown
## Rates

<!-- format: json -->
```json
{"standard": 0.20, "reduced": 0.05, "zero": 0.00}
```

<!-- source: https://www.gov.uk/vat-rates -->
```

未加 `## Rates` 段的 md(de/cn/fr)行为: `get_tax_rates` 返回 "not yet available" (向后兼容)。

### 4.4 `tax_knowledge_tools.py` 改造
原:
```python
if jurisdiction == "uk" and tax_type == "vat":
    rates = {"standard": 0.20, ...}
elif ...:
    ...
else:
    rates = {"note": f"Rate table not yet available..."}
```

新:
```python
def get_tax_rates(self, jurisdiction, tax_type, year=None):
    if not is_valid_jurisdiction(jurisdiction, tax_type):
        return _tool_error(f"Unknown {jurisdiction}:{tax_type}")
    section = self.store.get_section(jurisdiction, tax_type, "Rates")
    if section is None:
        return _tool_ok({
            "success": True,
            "jurisdiction": jurisdiction, "tax_type": tax_type, "year": year,
            "rates": {"note": f"Rate table not yet available for {jurisdiction}/{tax_type}"},
        })
    # 解析 section.content 里的 ```json ... ``` 块
    rates = _parse_rates_block(section.content)
    return _tool_ok({
        "success": True, "jurisdiction": jurisdiction, "tax_type": tax_type, "year": year,
        "rates": rates,
    })
```

需要 `TaxKnowledgeStore.get_section(jurisdiction, tax_type, title)` 新方法 —— 严格按 H2 标题返回 `KnowledgeSection` 或 None。

### 4.5 渠道子包结构
```
backend/channels/
├── __init__.py         ← FilingChannel ABC(原,零改)
├── api_channel.py      ← 通用化(参数化 oauth_config)
├── browser_channel.py  ← 占位类(Phase 3 留空)
├── registry.py         ← ChannelRegistry(cc × tt → Channel)
└── uk/
    ├── __init__.py     ← UKChannel(APIChannel 实例化,迁移原 uk/config.py 引用)
    └── (de/cn/fr 留空,等真要做时再写子包)
```

`channels/registry.py`:
```python
class ChannelRegistry:
    def __init__(self):
        self._channels: dict[tuple[str, str], FilingChannel] = {}
    
    def register(self, cc: str, tt: str, channel: FilingChannel) -> None:
        if not is_valid_jurisdiction(cc, tt):
            raise KeyError(f"Unknown {cc}:{tt}")
        self._channels[(cc, tt)] = channel
    
    def get(self, cc: str, tt: str) -> FilingChannel:
        key = (cc, tt)
        if key not in self._channels:
            raise KeyError(f"No channel registered for {cc}:{tt}")
        return self._channels[key]
```

`backend/main.py`:
```python
channel_registry = ChannelRegistry()
channel_registry.register("uk", "vat", UKVATChannel())
# 未来: channel_registry.register("cn", "vat", CNBrowserChannel())
```

## 5. 数据流("加 DE VAT" 端到端)

```
1. dev 执行:
   cp -r backend/agent/prompts/uk backend/agent/prompts/de
   # 改 5 行: 文件头 description + URL + 3 处 "UK" → "Germany/DE"
   cp data/tax_knowledge/uk/vat.md data/tax_knowledge/de/vat.md
   # 改 5 行: 加 ## Rates {standard: 0.19, reduced: 0.07, zero: 0.00}

2. backend 自动拾取:
   backend/main.py:
     registry.register(GermanyJurisdictionAdapter())  # 加 1 行
   backend/agent/prompts/__init__.py:
     importlib.import_module("backend.agent.prompts.de.vat")  # 自动发现
   backend/agent/tax_knowledge_store.py:
     _load_all 扫到 data/tax_knowledge/de/vat.md 入索引
   backend/channels/registry.py:
     de/__init__.py 里的 channel() 工厂被调(若存在)

3. Agent 启动时:
   create_mcp_servers(registry) 走德国 adapter.get_agent_tools("vat")
   → 多 1 个 mcp__tax_agent_de_vat__* 工具
   get_system_prompt("de", "vat") 返回新 prompt

4. 用户 /api/agent/chat 提到 "DE VAT":
   Engine 推断 jurisdiction=de, 调 get_system_prompt("de", "vat")
   prompt 含 de 工具说明 + KB 含 de 税率
   LLM 能调 mcp__tax_agent_de_vat__get_vat_obligations
```

**整个流程触达全局文件 = 0**(只有 main.py 注册 1 行)。

## 6. 错误处理

| 错误场景 | 现状 | 目标 |
|---|---|---|
| `get_system_prompt("uk:VT")` typo(tt 错) | 静默 fallback | **`KeyError`**(枚举校验) |
| `get_system_prompt("xx", "vat")` 未知 cc | 静默 fallback | **`KeyError`**(枚举校验) |
| `get_system_prompt("uk", "vat")` 文件缺失 | 静默 fallback | **fallback + warning log**(已注册国家) |
| `import_module("...de.vat")` 失败(未注册) | (无) | **fallback + warning log**(允许) |
| `kb.get_section("de", "vat", "Rates")` 段缺失 | "not yet available" | 同(向后兼容) |
| KB 段 JSON 解析失败 | (无) | **`ValueError` + 列出 KB md 路径** |
| `JurisdictionRegistry.register("XX", ...)` 未知 cc | (无) | **`ValueError` at import** |
| `channels.get("cn", "vat")` 未注册 | (无) | **`KeyError`** |

**核心原则**:**已注册国家**(在 `JurisdictionRegistry` 里)错误 = 严;**未注册国家** = 软(fallback)。

## 7. 测试

### 7.1 单元测试(7 个新文件,共 ~30 个 test case)

| 文件 | Cases | 覆盖 |
|---|---|---|
| `tests/agent/test_prompts_dispatch.py` | 10 | 5 UK + 1 testland byte-equality + 1 de fallback + 2 typo KeyError |
| `tests/agent/test_tax_kb_rates.py` | 5 | 5 UK + 1 testland KB md 都有 `## Rates` 段 + JSON 合法 |
| `tests/agent/test_jurisdictions_enum.py` | 3 | 枚举 + is_valid 接受/拒绝 |
| `tests/agent/test_tax_knowledge.py`(改) | 1 | `get_tax_rates("de", "vat")` 行为 |
| `tests/extensibility/test_jurisdiction_isolation.py` | 3 | `prompts/uk/` 不 import 任何 `prompts/{other}/` |
| `tests/extensibility/test_add_country_checklist.py` | 2 | "复制-改 5 行" 端到端 + 触达文件 = 0 |
| `tests/channels/test_channels_registry.py` | 4 | register / get / 错误 / 多 cc 隔离 |

### 7.2 回归测试(零改)
```bash
.venv/bin/pytest tests/erp/ tests/agent/ -q
cd frontend && npm run build
```

### 7.3 端到端 smoke
```bash
# 1. 加 1 个 e2e-test 国家
cp -r backend/agent/prompts/uk backend/agent/prompts/_e2e
# 改 3 行(URL, "UK" → "_e2e_country", 1 个税率)

# 2. 注册
echo 'registry.register(E2EJurisdictionAdapter())' >> backend/main.py

# 3. 启动
./start_backend.sh &

# 4. 验证
curl localhost:8765/api/agent/health | jq .supported_jurisdictions | grep "_e2e"
# 应出现 "_e2e"
```

## 8. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| importlib 字符串路径 IDE 跳转失效 | 高 | 中(开发体验) | `prompts/__init__.py` 顶部加 type-hint 注释 + 显式 `from .uk import vat as _uk_vat` 让 IDE 看到 |
| LLM prompt byte-equality 测试脆弱 | 中 | 高(Phase 1 红线) | 改用"语义等价"比较:正则去除多余空行,或对比"前 100 token 的 hash" |
| cc 枚举跟 `JurisdictionRegistry` 双重事实源 | 中 | 中 | `JurisdictionRegistry.register` 加 assert(cc in JURISDICTIONS) |
| Phase 3 渠道子包拖期,挡 Phase 1/2 上线 | 中 | 中 | Phase 3 独立 PR,可在 Phase 1/2 落地后**数周**再做 |
| `_FALLBACK_PROMPT` 仍被 placeholder 国家用 | 高(已知) | 低 | 加 warning 日志 |
| 6 个新 prompt file 重复 UK 模式 80% | 高(已知) | 中 | 接受(简洁优先)。后续 Phase 4 再考虑 "prompt 模板继承" |

## 9. 实施计划(由 writing-plans skill 生成)

3 个独立 PR:
- **PR #1 (Phase 1)**: 提示词目录化
- **PR #2 (Phase 2)**: 税率 KB 驱动
- **PR #3 (Phase 3)**: 渠道子包

每个 PR 必须通过:
- `pytest tests/agent/ tests/extensibility/ tests/channels/ -q` 100% 通过
- `pytest tests/erp/ -q` 0 回归
- `cd frontend && npm run build` 0 错误
- `git diff --name-only main.py` 只增 1 行(每个 PR 加 1 行,共 3 行)

## 10. 关键文件改动清单

| 文件 | 改动类型 | Phase |
|---|---|---|
| `backend/models/jurisdictions.py` | 新建 | 1 |
| `backend/agent/prompts/__init__.py` | 改造(原 prompts.py) | 1 |
| `backend/agent/prompts/_generic.py` | 新建(拆分) | 1 |
| `backend/agent/prompts/_fallback.py` | 新建(拆分) | 1 |
| `backend/agent/prompts/uk/{__init__,vat,sa,ct,paye,sdlt}.py` | 新建(拆分) | 1 |
| `backend/agent/prompts/testland/vat.py` | 新建(迁移) | 1 |
| `backend/agent/prompts.py` | **删除** | 1 |
| `data/tax_knowledge/uk/{vat,sa,ct,paye,sdlt}.md` | 加 `## Rates` 段 | 2 |
| `data/tax_knowledge/testland/vat.md` | 加 `## Rates` 段 | 2 |
| `backend/agent/tax_knowledge_store.py` | 加 `get_section` 方法 | 2 |
| `backend/agent/tax_knowledge_tools.py` | 删 if/elif 链 | 2 |
| `backend/channels/api_channel.py` | 通用化(零行为变化) | 3 |
| `backend/channels/browser_channel.py` | 占位类 | 3 |
| `backend/channels/registry.py` | 新建 | 3 |
| `backend/channels/uk/__init__.py` | 新建(迁移 uk channel 引用) | 3 |
| `backend/main.py` | 加 3 行注册(1 phase 1 行) | 1+2+3 |
| `tests/agent/test_prompts_dispatch.py` | 新建 | 1 |
| `tests/agent/test_tax_kb_rates.py` | 新建 | 2 |
| `tests/agent/test_jurisdictions_enum.py` | 新建 | 1 |
| `tests/extensibility/test_jurisdiction_isolation.py` | 新建 | 1 |
| `tests/extensibility/test_add_country_checklist.py` | 新建 | 3 |
| `tests/channels/test_channels_registry.py` | 新建 | 3 |
| `tests/agent/test_tax_knowledge.py` | 改 1 个 test | 2 |

**总计**:3 个新 Python 包、5 个新 md 段、1 个文件删除、22 个文件改动、6 个新测试文件、~30 个新 test case。

## 11. 开放问题(无)

所有设计决策在 brainstorming 阶段已确认,无 TBD 项。

## 12. 关联文档

- `docs/architecture/extensibility.md` — 现状分析(本 spec 的来源)
- `docs/architecture/adding-new-jurisdiction.md` — 旧指南(本次不修改,后续可增量)
- `docs/architecture/pipeline.md` — 6 阶段管线(本设计不动)
- `backend/agent/prompts.py` — 现状单文件(Phase 1 目标:删除)
- `backend/agent/tax_knowledge_tools.py` — 现状 if/elif(Phase 2 目标:替换)
- `backend/channels/api_channel.py` — 现状单类(Phase 3 目标:拆子包)
