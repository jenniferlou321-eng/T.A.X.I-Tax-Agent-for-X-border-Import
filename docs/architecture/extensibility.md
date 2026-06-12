# 可拓展性分析 — 按国家分离的知识库 / 工具 / skills / 流程

> 目标:评估 T.A.X.I. 对"新国家 / 新税种"的承载力,识别已经按国家分离的部分
> 和仍混在全局命名空间的债,给出改造路径。

## TL;DR

| 层 | 现状 | 拓展新国家时是否隔离 | 评分 |
|---|---|---|---|
| **L1 知识库** `data/tax_knowledge/{cc}/{tax}.md` | ✅ 完美目录式 | **零代码** | 10/10 |
| **L2 渠道** `backend/channels/*` | ⚠️ 单 `APIChannel` 类 | 需新建 `channels/{cc}/` | 5/10 |
| **L3 适配器** `backend/jurisdictions/{cc}/` | ✅ 目录式 + Registry | 走子包 | 9/10 |
| **L4 Agent 工具** `agent_tools.py` per (cc, tax) | ✅ 走 ABC 多态 | 走子包 | 9/10 |
| **L5 提示词** `backend/agent/prompts.py` | ❌ 单文件硬编码 dict | **需改全局文件** | 3/10 |

**加权平均 7.2/10** — 数据层和适配器层做对了,**提示词和渠道是债**。

---

## 1. 已经做对的事

### 1.1 知识库 = 100% 数据驱动
`backend/agent/tax_knowledge_store.py:34-46` 走 `rglob("*.md")` 自动索引。`de/vat.md` / `cn/vat.md` / `fr/vat.md` 三个**完全无对应适配器**的国家,已经能查税率 — 这是 100% 隔离的范本。

### 1.2 适配器目录式 + Registry 注入
- `JurisdictionRegistry` 用 `dict[str, JurisdictionAdapter]` 按 `country_code` 索引
- 新增国家 = 新建子包 + `registry.register(...)` 1 行
- `testland/` 已证明这是 ~300 行最小可行实现

### 1.3 Agent Tool 走 ABC 多态
`AgentToolSet` ABC 定义 6 个 async 方法 + `get_tool_metadata()`。`tools.py:106-128` 的 `_resolve_method_name` + `_DICT_PARAM_NAMES` 白名单处理了 LLM 视角的语义命名(`get_vat_obligations`)与实现名(`get_obligations`)的脱钩。

### 1.4 MCP Server 按 `(cc, tax)` 一对一创建
`create_mcp_servers(registry)` 走 registry 自动建 `tax_agent_uk_vat` / `tax_agent_de_vat` / `tax_agent_cn_cit` 等独立 MCP server,物理上互不污染。

### 1.5 测试隔离范本
`tests/erp/test_case_isolation.py` 用 `grep` 证明 3 个 case 目录互不引用,可直接复用为"国家间隔离"测试模板。

---

## 2. 仍然欠的债

### 2.1 提示词不是目录式 — `prompts.py:435-441`
```python
_PROMPT_REGISTRY: dict[str, str] = {
    "uk:vat": _UK_VAT_PROMPT,
    "uk:self_assessment": _UK_SA_PROMPT,
    # 5 个键全硬编码; de/cn/fr 在 _FALLBACK_PROMPT 里兜底 = 静默退化
}
```

加 DE VAT 要改 3 个文件(`prompts.py` + 2 个 import);加 DE CT 要改 4 个。**无 testland 这种"最小模板"**。

### 2.2 税率表硬编码 — `tax_knowledge_tools.py:62-67`
```python
if jurisdiction == "uk" and tax_type == "vat":
    rates = {"standard": 0.20, "reduced": 0.05, "zero": 0.00}
elif jurisdiction == "uk" and tax_type == "corporation_tax":
    rates = {"small_profits_rate": 0.19, "main_rate": 0.25}
else:
    rates = {"note": f"Rate table not yet available for {jurisdiction}/{tax_type}"}
```
if/elif 链。de/cn/fr VAT 调 `get_tax_rates` 拿到的全是 "not yet available",**表面看像支持,实际是降级**。

### 2.3 渠道无 cc 隔离
只有 `APIChannel` + OAuth + FraudHeaders,**没有** `backend/channels/{cc}/...` 子目录。
CN(浏览器)+ UK(API)+ DE(EDI 混合)三种渠道如果共存,会变成 `api_channel.py` 一个文件 500+ 行 if/elif。

### 2.4 业务分析器没走 cc
UK-only 9-Box 编码进 `business_analyzer.py:200+` 行。CN Case B 的"集团服务费 / CIT / WHT"逻辑是另一套,**目前没有 CN 版 analyzer**。

### 2.5 模板 + Prompt 字符串拼接,无枚举校验
- `DataTemplate.jurisdiction` 是裸 string
- `_PROMPT_REGISTRY` 的 key 是 `f"{cc}:{tt}"` 拼字符串

不存在"哪些 cc 是合法的"枚举中心。`prompts.get("uk:VT")` 拼写错误会**静默**走 fallback,不被发现。

---

## 3. 目标架构

```
data/tax_knowledge/                         ← L1(已是)
├── {cc}/{tax}.md                          ← 每国家独立
└── taxonomy/{concepts,jurisdictions,tax_types}.yaml

backend/channels/                           ← L2(改造)
├── __init__.py                            ← 公共 ABC
├── api_channel.py                         ← 通用 API 实现
├── browser_channel.py                     ← 通用 Playwright 实现
└── {cc}/                                  ← 国家特化
    ├── cn_session.py
    └── de_edi_bridge.py

backend/jurisdictions/{cc}/                 ← L3(已对)
├── __init__.py                            ← {CC}JurisdictionAdapter
├── config.py
└── {tax}/
    ├── __init__.py
    ├── template.py
    ├── calculator.py
    ├── validator.py
    ├── channel.py                         ← 走 channels/{cc}/
    └── agent_tools.py                     ← L4(已对)

backend/agent/prompts/                      ← L5(改造,目录式)
├── __init__.py                            ← get_system_prompt(cc, tt)
├── _generic.py
├── _fallback.py
├── uk/
│   ├── __init__.py
│   ├── vat.py
│   ├── corporation_tax.py
│   ├── self_assessment.py
│   ├── paye.py
│   └── stamp_duty.py
├── de/                                    ← 同结构
├── cn/
└── (其他国家同)
```

### 3.1 关键设计原则

1. **每个国家一个文件夹** — 添加 DE = `cp -r prompts/uk prompts/de && sed`
2. **提示词可被 markdown 化** — 税率表 / Band 表 / Special Schemes 全部放
   `data/tax_knowledge/{cc}/{tax}.md`,prompts 文件只写"工具指南 + 工作流"骨架
3. **单一枚举源** — `backend/models/jurisdictions.py` 定义
   `JURISDICTIONS = {"uk", "de", "cn", "fr", "testland"}`,被 prompts / 渠道 / 适配器 / KB 共同 import
4. **测试模板** — 仿照 `testland/`,每个新国家的 `agent_tools.py` 必须通过
   `pytest tests/jurisdictions/{cc}_contract_test.py` 一组 contract test
5. **CC 隔离硬约束** — 借 `test_case_isolation.py` 的 grep 套路,加
   `tests/extensibility/test_jurisdiction_isolation.py`:任何 `prompts/uk/` 的文件
   不允许 import `prompts/cn/`

---

## 4. 添加 DE 必改的清单(对比现状/目标)

| 步骤 | 现状(债重) | 目标(零债) |
|---|---|---|
| 1 | 新建 `jurisdictions/de/vat/...` 5 文件 | 同 |
| 2 | 新建 `de/config.py` | 同 |
| 3 | 改 `main.py:46` 加 `register(DEJurisdictionAdapter())` | 同 |
| 4 | **改 `prompts.py` 加 1 个键 + 1 个常量** | **新建 `prompts/de/__init__.py` + `prompts/de/vat.py`** |
| 5 | **改 `tax_knowledge_tools.py:62-67` 加 if/elif** | **新建 `data/tax_knowledge/de/vat.md`**(KB 驱动) |
| 6 | 新建 `jurisdictions/de/vat/agent_tools.py` | 同 |
| 7 | 改 `channels/api_channel.py` 加 DE URL | **新建 `channels/de/` 子包** |
| 8 | `tax_knowledge_store` 自动拾取 KB | 同 |
| 9 | 写 `de/vat/calculator.py` | 同 |
| 10 | 写 `de/vat/validator.py` | 同 |

**改造后,DE 新增触达 0 处全局文件**(全部在自己目录下)。

---

## 5. 改造路线图(3 阶段)

### Phase 1 — 提示词目录化(无行为变化,2-3 天)
- 把 `prompts.py` 拆成 `prompts/{_generic,_fallback}.py` + `prompts/uk/{vat,sa,ct,paye,sdlt}.py` + `prompts/testland/vat.py`
- `prompts/__init__.py` 暴露 `get_system_prompt(cc, tt)`,内部用 `importlib` 动态 import
- **风险**:零。`grep _UK_VAT_PROMPT` 已确认只在 `prompts.py` 自家 + 1 个 legacy `SYSTEM_PROMPT` 引用
- **测试**:把 `tests/agent/test_tax_knowledge.py` 复制一份成 `test_prompts_dispatch.py`,断言 5 个 UK key + 1 个 testland key 都能 load

### Phase 2 — `get_tax_rates` 走 KB(消除 if/elif,1 天)
- 把 `tax_knowledge_tools.py:62-67` 改为读 `data/tax_knowledge/{cc}/{tax}.md` 的 H2 `## Rates` 段
- 在所有 KB md 里加 `## Rates` 节
- UK VAT 提示词里的"Rates"段去掉,改从 KB 读
- **风险**:KB md 结构变 → 写一个 `test_kb_rates_consistency.py` 防退化

### Phase 3 — `channels/{cc}/` 子包 + ChannelRegistry(2-3 天)
- 新建 `backend/channels/registry.py`,跟 `JurisdictionRegistry` 对称
- 把 `APIChannel` 变"通用",通过 `oauth_config` 注入 cc 差异
- CN Browser Channel 走 `backend/channels/cn/session.py`
- **风险**:5 个 UK 测试需要小改 import 路径

---

## 6. 风险与不做的事

| 风险 | 缓解 |
|---|---|
| 改造期间 prompts 行为漂移(LLM 输出变化) | Phase 1 是纯 refactor,先在 staging 跑 5 个 case 提示词 diff 0 变化再发 |
| `testland` 用作"提示词目录式"模板 | 已是 ~300 行最小实现,可直接复制为 `prompts/de/` 起点 |
| 改 `_py_type_to_json` 可能影响 schema 导出 | Phase 1 不动 `tools.py`,只动 `prompts/` |
| CN Case B 没有 analyzer 债 | 此次不动(超出"按国家分离"目标,属于"按国家多产品"债务) |

**不在本期范围**:
- 新增真实 CN/CIT 计算器(产品债)
- 渠道性能优化(Playwright session 池等)
- KB 自动从 PDF/法规网 sync(产品债)

---

## 7. 验证矩阵

| 维度 | 改造前 | 改造后 |
|---|---|---|
| 加 1 个新国家需改全局文件数 | **3-4 个** | **0-1 个**(`main.py` 注册 1 行) |
| `prompts.get("uk:VT")` typo 行为 | 静默走 fallback | `KeyError` |
| 税率 if/elif 链 | 4 个分支 | 0,全走 KB |
| 渠道 cc 隔离 | 0(`APIChannel` 单类) | `channels/{cc}/` 子包 |
| 测试可加的国家 contract test | 无 | `tests/jurisdictions/{cc}_contract_test.py` 模板 |

---

## 8. 相关文档

- [`docs/architecture/adding-new-jurisdiction.md`](./adding-new-jurisdiction.md) — 现有
  "添加新国家" 步骤指南(代码层面)
- [`docs/architecture/pipeline.md`](./pipeline.md) — 6 阶段管线
- [`backend/agent/prompts.py`](../../backend/agent/prompts.py) — 当前提示词中心(待改造)
- [`backend/agent/tax_knowledge_store.py`](../../backend/agent/tax_knowledge_store.py) — KB loader
- [`backend/registry.py`](../../backend/registry.py) — 适配器注册中心
- [`tests/erp/test_case_isolation.py`](../../tests/erp/test_case_isolation.py) — 隔离测试范本
