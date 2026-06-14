# T.A.X.I. Agent 提示词红队体检报告

> **审查日期**: 2026-06-14
> **审查方式**: 单遍人工红队审查（5 副失效眼镜：指令冲突 / 注意力衰减·位置 / 模糊·二义 / 缺失护栏 / 冗余·可维护性陷阱）
> **审查范围**: prompt 设计 A+B+C 三层 —
>   - **A** System prompt 三层: `backend/agent/prompts/_generic.py` · `__init__.py` · `_fallback.py` · `uk/{vat,corporation_tax,paye,self_assessment,stamp_duty}.py` · `testland/vat.py`
>   - **B** 运行期注入: `backend/agent/engine.py:104` `_build_multi_workspace_reminder()` · `engine.py:149` `_WORKSPACE_INSTRUCTION` · 拼接点 `engine.py:576-577`
>   - **C** 子 agent: `backend/agent/tax_knowledge_prompts.py` `TAX_KB_SUBAGENT_PROMPT`
> **明确不做**: 不改任何 prompt（本次仅诊断）；不核对工具描述与 `agent_tools.py` 的逐字段一致性（D 层，已排除）。
> **对标**: 风格沿用 `docs/superpowers/audit/2026-06-12-sdk-audit.md`。

---

## 0. 总评：**B**

当前 prompt 设计的**骨架很好**：三层分离（共享 header / namespace 路由 / 各国 segment）、`pre_submit_gate()` 工厂把"人按按钮"的 Copilot 哲学 DRY 成一个 4 步硬门、`_FALLBACK_PROMPT` 给未实现国家兜底、子 agent 强制 URL 引用 + 状态警告。这是一套**有意识设计过**的 prompt 系统，不是堆出来的。

但对一个**法律意义的报税平台**，本次体检发现 **1 个 critical**（prompt 在最关键的工具失败路径上命令 agent 调用一个被硬禁的工具）和 **3 个 high**（子 agent 工具清单/turn 预算两处 prompt-vs-运行期不一致 + testland 缺提交门）。这些都不是"agent 跑偏"的现象级 bug，而是**设计层的潜在雷**——符合"预防性体检"的定位。

| 严重等级 | 数量 |
|---|---|
| critical | 1 |
| high | 3 |
| medium | 4 |
| low / nit | 5 |
| **total** | **13** |

**Top 3 修复（按 ROI 排序）**：
1. **C1** — 把 `uk/vat.py:178` 的 `call AskUserQuestion` 改成"向用户提出澄清问题（自然语言）"，或从 `disallowed_tools` 放开 AskUserQuestion（二选一，须与 engine.py:600 的设计意图对齐）。一行改动，消除最危险的指令冲突。
2. **H1+H2** — 让子 agent 的 `AgentDefinition`（engine.py:637-644）与 `TAX_KB_SUBAGENT_PROMPT` 对齐：要么补齐 tools=3 个，要么改 prompt 只声明 1 个；同时把 maxTurns 提到 ≥4 或把"up to 3 times"降到"up to 2 times"。
3. **H3** — 给 `testland/vat.py` 补 `pre_submit_gate(...)`，与其余 5 个税种一致。

---

## 1. CRITICAL

### C1 — prompt 命令 agent 调用一个被硬禁的工具（工具失败路径）

- **位置**: `backend/agent/prompts/uk/vat.py:178` vs `backend/agent/engine.py:600`
- **眼镜**: 指令冲突
- **现状**: UK VAT 的「Tool-Failure Discipline」第 3 步写：
  > 3. Either (a) fix the call and retry, or (b) call `AskUserQuestion` to let the user choose how to proceed.

  但 engine 在构建 SDK options 时：
  > `"disallowed_tools": ["AskUserQuestion"]`（engine.py:600，注释明确说"deny 比 allow 严格，即使 bypassPermissions 也生效"）
- **为什么是问题 / 触发场景**: 当任何 VAT 工具调用失败（HMRC 超时、参数错、obligations 查不到），prompt 显式指示 agent 走 `AskUserQuestion`——而该工具被硬 deny，调用必然失败。此时 agent 行为未定义：可能反复重试该工具、可能放弃护栏自己用通用知识算（**直接违反同一段第 1 条 "Never invent numbers"**）、可能静默卡住导致 SSE 流挂死。这是发生在**最需要纪律的失败路径**上的冲突，且落在法律意义的报税数字上，故定 critical。
- **建议改法**（二选一，须确认 engine.py:596-600 的原始设计意图）:
  - (a) 改 prompt：把 "(b) call `AskUserQuestion`" 改为 "(b) 用自然语言向用户说明失败并请其选择如何继续"——保持 AskUserQuestion 被禁的设计。**推荐**，改动最小且贴合 T.A.X.I."不弹选择题、直接对话"的设计。
  - (b) 改 engine：从 `disallowed_tools` 移除 AskUserQuestion——但这会与"agent 应直接读 workspace 而非反问"的设计意图相悖，不推荐。

---

## 2. HIGH

### H1 — 子 agent 工具清单：prompt 宣称 3 个，运行期只授予 1 个

- **位置**: `backend/agent/tax_knowledge_prompts.py:10-13` vs `backend/agent/engine.py:641`
- **眼镜**: 指令冲突 / 缺失护栏
- **现状**: 子 agent prompt 告诉 `tax_kb_researcher` 它拥有三个工具：
  > `search_tax_knowledge(...)` · `list_supported_jurisdictions()` · `get_tax_rates(...)`

  但 `AgentDefinition` 只授予一个：
  > `tools=["mcp__tax_agent_global_tax_kb__search_tax_knowledge"]`（engine.py:641）
- **为什么是问题**: prompt 让子 agent 在需要时调用 `list_supported_jurisdictions` / `get_tax_rates`，这两个工具子 agent 根本没有授权 → 调用失败。子 agent 的整段"先 list 看覆盖、再 get rates 拿结构化税率"的策略无法执行，研究质量打折。三个工具在 `tax_knowledge_tools.py:56/80/120` 确实都存在，所以这是**授权范围**问题，非工具缺失。
- **建议改法**: 在 `AgentDefinition.tools` 补齐另外两个 MCP 名（`mcp__tax_agent_global_tax_kb__list_supported_jurisdictions`、`mcp__tax_agent_global_tax_kb__get_tax_rates`）；或把 prompt 第 10-13 行裁到只声明 `search_tax_knowledge`。前者更符合 prompt 的检索策略意图。

### H2 — 子 agent turn 预算与检索指令冲突

- **位置**: `backend/agent/tax_knowledge_prompts.py:17` vs `backend/agent/engine.py:642`
- **眼镜**: 指令冲突 / 缺失护栏
- **现状**: prompt 第 2 条："Call search_tax_knowledge **up to 3 times** with refined queries"；而 `AgentDefinition(maxTurns=3)`。
- **为什么是问题**: 若子 agent 真的用满 3 次检索，每次检索通常各占 1 个 assistant turn，第 4 步"合成 < 400 字的引用答案"已无 turn 可用 → 可能在合成前被 maxTurns 截断，返回半成品或空。即使不总触发，这是个**设计上就埋好的上限竞争**。
- **建议改法**: maxTurns 提到 ≥ 4（3 检索 + 1 合成），或把 prompt 的 "up to 3 times" 降到 "up to 2 times"。

### H3 — testland/vat 缺提交前确认门

- **位置**: `backend/agent/prompts/testland/vat.py`（全文，无 `pre_submit_gate`）
- **眼镜**: 缺失护栏 / 冗余·可维护性陷阱
- **现状**: testland/vat 是**唯一**不含 `pre_submit_gate(...)` 的税种 prompt（其余 5 个 UK 税种均含）。它的 Workflow 第 5 步直接 "Use submit_return to file"，prompt 内**没有任何**"提交前重述 + 等显式确认"指令。
- **为什么是问题**: `_GENERIC_PROMPT_HEADER` 的通用规则（"Never submit a return without explicit user confirmation"）措辞宽松、不构成 4 步硬门；pre_submit_gate 那句"submit 前一轮没有重述就是 compliance violation"才是真护栏。testland 缺它 → 该 namespace 下提交护栏强度骤降。虽然 testland 是测试国，但它进的是**同一个生产 prompt 装配管线**，且是"加新税种时照抄的样板"——样板缺门，新税种容易跟着漏。
- **建议改法**: 给 testland/vat 补 `pre_submit_gate(tool_name="submit_return", ...)`，与其余税种统一。

---

## 3. MEDIUM

### M1 — VRN 收集指令与 workspace 规则冲突

- **位置**: `backend/agent/prompts/uk/vat.py:154, 164` vs `backend/agent/engine.py:155`（`_WORKSPACE_INSTRUCTION`）
- **眼镜**: 指令冲突 / 注意力衰减
- **现状**: VAT workflow 两条路径都以 "Ask for their VRN if not provided" 开头；而拼到 system_prompt 尾部的 `_WORKSPACE_INSTRUCTION` 写 "It contains VRN, company name, and period — **never ask the user for this information**"。
- **为什么是问题**: 同一个 system_prompt 里两条指令直接打架，且相隔很远（VAT segment 中部 vs system 末尾）。LLM 需自行判定"workspace 存在时不问 / 不存在时问"的隐含优先级——prompt 没把这个条件显式写出来。workspace 存在却仍反问 VRN，正是"agent 不懂工作流"的典型现象。
- **建议改法**: 把 VAT workflow 的 VRN 步骤改成条件式："若 active workspace 已加载则从 manifest.json 读 VRN，**否则**才向用户索取"，让两条指令在文本上自洽。

### M2 — B 层双重 workspace 注入：措辞不一致 + 同步维护陷阱

- **位置**: `backend/agent/engine.py:149` `_WORKSPACE_INSTRUCTION`（英文，进 system_prompt 尾）vs `engine.py:104` `_build_multi_workspace_reminder`（中文，进用户消息尾）
- **眼镜**: 冗余·可维护性陷阱 / 注意力衰减
- **现状**: 两段表达几乎相同的意图（先读 manifest.json、别枚举旧 case、related_cases 只读当前），但一英一中、结构措辞不同，且分别注入两个不同位置。
- **为什么是问题**: (1) 无任何机制保证两段同步——将来改 workspace 行为，极易改一处漏一处（CLAUDE.md 风格的"双处都得改"陷阱）。(2) 双语 + 双位置传递同一约束，可能给 LLM 制造轻微的"为何说两遍、是否有差异"噪声。这是有意的"抗注意力衰减"双保险，但**代价是维护脆弱性**，需要权衡。
- **建议改法**: 抽出单一**事实源**（一个常量/函数）描述 workspace 规则，两个注入点都引用它（语言可不同但内容派生自同一源）；或评估是否真需要双注入，保留一处。

### M3 — httpx 降级路径不追加 workspace 规则

- **位置**: `backend/agent/engine.py:825-832`（httpx fallback）vs `engine.py:577`（SDK 路径追加 `_WORKSPACE_INSTRUCTION`）
- **眼镜**: 缺失护栏 / 不一致
- **现状**: SDK 路径在 system_prompt 后追加 `_WORKSPACE_INSTRUCTION`；httpx 降级路径只追加一段 "[Tool-Failure Notice]"，**不含** workspace 规则。（注：另一处 httpx 分支 engine.py:443-448 倒是加了简版 workspace 说明，两条 httpx 路径自己也不一致。）
- **为什么是问题**: SDK 不可用而降级到 httpx 时，agent 对 workspace 约定一无所知。影响被"httpx 无 Read 工具、本就读不了 workspace 文件"所限，故 medium 而非 high；但**两条 httpx 路径彼此不一致**本身是设计气味。
- **建议改法**: 统一三条出口（SDK / httpx-460s / httpx-fallback）对 workspace 说明的处理；至少让两条 httpx 路径一致。

### M4 — _FALLBACK_PROMPT 的确认门弱于 pre_submit_gate

- **位置**: `backend/agent/prompts/_fallback.py:9-12`
- **眼镜**: 缺失护栏
- **现状**: 未实现国家走 `_FALLBACK_PROMPT`，其提交护栏只有："re-state the key figures to the user and wait for explicit confirmation"——无 4 步结构、无"提交前一轮没重述=compliance violation"的硬措辞。
- **为什么是问题**: 同一平台内，已实现国家有强 4 步门、未实现国家是弱门，护栏强度随 jurisdiction 漂移。新国家在补 segment 之前的"裸奔期"提交风险偏高。
- **建议改法**: 让 `_FALLBACK_PROMPT` 也复用 `pre_submit_gate` 的精简版（用通用占位参数），保证任何 jurisdiction 的提交门都是同一形态。

---

## 4. LOW / NIT

### N1 — "Be concise but thorough" 无操作性
- `_generic.py:20`。经典自相矛盾指令，LLM 无法据此做取舍。建议改成具体可执行的（如"默认 ≤ 5 个要点，用户要细节再展开"）。

### N2 — "cite specific rules where relevant" 未限定来源
- `_generic.py:14`。主 agent 被鼓励引用规则却没指明从哪引（与 C 层子 agent 强制官方 URL 形成反差），可能诱导编造法规编号。建议指向"通过 tax_kb_researcher 取得带 URL 的引用，不要自行编号"。

### N3 — pre_submit_gate figures 全是 "GBP" 占位，无取值来源
- `_generic.py` 各税种 figures 块。只列字段名 + "GBP"，未告诉 agent 从哪个计算结果/nine_box 字段取值，依赖 LLM 自行映射。建议在 gate 内点明"数值取自最近一次成功的 calculate/validate 工具输出"。

### N4 — 缺"未挂载 slot 的跨域提问"降级话术
- `__init__.py` Namespace Map / 各 segment。用户问一个没出现在 namespace map 里的国家/税种时，prompt 无明确指引（是拒答、还是说明未支持）。建议在 Namespace Map 末尾加一句兜底话术。

### N5 — 主 agent "可直接 call get_tax_rates / list_supported_jurisdictions" 的声明依赖运行期授权
- `_generic.py:34-35`。prompt 声明主 agent 能直接调这两个 KB 工具，但能否调取决于 allowlist 是否含 kb 工具——prompt 声明与运行期授权耦合，未在 A 层闭环。**边界 finding**（贴近被排除的 D 层），仅记录，建议下次做 D 层一致性审计时一并核对。

---

## 5. 复审触发

- prompt 三层任一文件改动后
- 新增 jurisdiction/tax_type 的 segment 时（重点核 pre_submit_gate 是否照样板补全 + workspace 指令是否自洽）
- `engine.py` 的 system_prompt 拼接逻辑（`_sdk_chat` / httpx 出口）或 `disallowed_tools` / `AgentDefinition` 改动后
- 下次若做 D 层（prompt vs `agent_tools.py` 工具一致性）审计，应一并闭环 N5
