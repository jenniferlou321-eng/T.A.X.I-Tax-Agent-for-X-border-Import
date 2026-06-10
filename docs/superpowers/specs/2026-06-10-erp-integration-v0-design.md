# T.A.X.I. — ERP 集成 v0 设计

> **状态**：设计中
> **日期**：2026-06-10
> **作者**：T.A.X.I. 团队
> **范围**：单一子项目 — ERP 集成 v0（demo 演示导向）

---

## Context（背景）

T.A.X.I. 是面向跨境中国企业的多国智能税务申报 SaaS 平台，已经实现：
- 6 阶段报税管线（`tax_agent/orchestrator.py`）
- 3 层插件架构（Registry → Adapter → Channel）
- UK VAT 端到端（HMRC MTD API + 沙盒验证）
- LLM 驱动的 Agent 入口（Claude Agent SDK）

**当前缺口**：真实用户的数据在哪？没有 ERPNext / Xero / QBO / Excel 任何形式的接入；sample 数据是 `tax_agent/data/realCaseData.json` 的硬编码 JSON。**这意味着 demo 只能"展示给一个固定 TechFlow Q1 2026 案例"**，无法让用户感受到"自己公司数据进来"的价值。

**目标（v0）**：把 demo 变成"选案例 → 一键看见 T.A.X.I. 处理真实交易数据 → 9-Box 复核 → 提交" 的端到端体验，**让潜在客户 / 投资人在 5 分钟内 get 到 T.A.X.I. 的核心价值**："你给我数据，我帮你算对、报对"。

**时间预算**：v0 在 2-3 周内交付（一线开发）。超出 3 周的需求一律推到 v1。

**显式不做**（v0 之外）：
- ❌ 真 ERPNext 凭证管理（OAuth 2、api_key 持久化、多租户） — 推到 v1
- ❌ Sage / Xero / QBO 多 Profile 适配 — 推到 v1，先 Generic CSV
- ❌ FRS / Cash / Annual / Margin 等非标准 scheme — 推到 v1
- ❌ 真 HMRC 提交（sandbox user 注册） — 继续走 mock

---

## 1. Architecture

### 1.1 总体方案

**方案 A — Linear Pipeline 插入 + Agent 主导申报**

`Orchestrator` 6 阶段最前面**新增** `_stage_import`；CALCULATE / VALIDATE 阶段**改由 Agent 在 chat 里主动调 MCP 工具**完成（不强制全管线贯通）；用户点 "Submit" 时 Orchestrator 才一次性跑完 PRECHECK + PREPARE + SUBMIT + TRACK 4 阶段。

```
                    ┌──────────────────────────────────────┐
                    │   Agent Chat (主导申报)                │
                    │   user → Agent → MCP tools            │
                    │     ├─ ingest_erp_data  (IMPORT)       │
                    │     ├─ calculate_vat_return            │
                    │     ├─ validate_vat_return             │
                    │     └─ submit_vat_return               │
                    └──────────┬───────────────────────────┘
                               │ user 点 "Submit to HMRC"
                               ▼
┌────────────────────────────────────────────────────┐
│  Orchestrator (单次贯通执行)                       │
│  PRECHECK → PREPARE → SUBMIT → TRACK               │
│  (CALCULATE / VALIDATE 由 Agent 已做，跳过)        │
└────────────────────────────────────────────────────┘

        _stage_import (v0 新增) — 解析数据
        ┌──────────────┐  ┌──────────────┐
        │ Demo case    │  │ CSV upload   │  (二选一)
        │ (json 预置)  │  │ (Generic)    │
        └──────┬───────┘  └──────┬───────┘
               │                 │
               └────────┬────────┘
                        ▼
              ImportResult → TaxData.metadata
```

**关键决策**：
- Agent 是**核心入口**，不是辅助
- Orchestrator 退化为"按用户确认后的一次性贯通执行器"
- 9-Box 复核（reconcile）由 Agent 在 chat 里展示，用户看完点 Submit
- **Dashboard 是 case 切换 + ERP 接入 + 数据清空的唯一入口**（v0 修订 ③）
- **AgentChatPage 不再选 case**——只选 case 中的"相关数据"（v0 暂定勾选多张发票）发送给 Agent 分析（v0 修订 ④）

### 1.2 与 ERPNext 集成的 2 种导入模式（v0）

经用户确认：v0 重点做 **A + B 融合**（demo 案例 + CSV），ERPNext 真连只作 v0 末尾 "Coming soon" 占位。

| 模式 | 触发方式 | 后端动作 | demo 演示友好度 |
|---|---|---|---|
| **A+B 融合** | Dashboard 顶部 `casePresets` 网格 + ERP on/off toggle（v0 修订 ②） | 后端从 `tax_agent/data/erp_samples/<case>.json` 读 `ImportResult`（**复用 _stage_import 统一路径**） | ⭐⭐⭐⭐⭐ |
| **B 单独** | CsvImportWizard drag-drop CSV | `parse_csv()` 解析 Generic Profile | ⭐⭐⭐⭐ |
| **C. 真连 ERPNext** | v0 不做 — 仅在 `ConnectErpCard` 留 "Coming soon" 标识 | — | — |

**现状复用 + 扩展**：
- `useDemoStore`（Zustand）+ `casePresets.ts` + `CasePresetCard.tsx` 已存在并工作，v0 不重写
- `DashboardPage.tsx` 顶部 case 网格保留 + **加 3 个新控件**（v0 修订 ①②③）：
  1. **Case 切换器**（保留现有 CasePresetCard 网格，添加"已加载"高亮 + "切换"按钮）
  2. **ERP 接入 toggle**（"接入 ERP" on/off，off=走 demo case，on=未来走真连）
  3. **"清空当前数据"按钮**（一键清 demo store + chat session.uploaded_data，方便切 case）
- `AgentChatPage.tsx` **不加 case picker**（v0 修订 ①）——case 已在 Dashboard 选好

### 1.3 关键模块位置

```
tax_agent/
├── orchestrator.py                     # + `_stage_import` 方法
├── erp/                                # NEW 包
│   ├── __init__.py
│   ├── csv_parser.py                   # Generic CSV 解析（stdlib csv）
│   ├── profiles.py                     # 1 个 Profile: GenericProfile
│   ├── reconcile.py                    # compute_taxi_nine_box + ReconciliationDelta
│   └── audit_events.py                 # 5 个 audit action 常量
├── jurisdictions/uk/vat/calculator.py  # + `mode` 形参, reconcile 分支
├── jurisdictions/uk/vat/agent_tools.py # + `ingest_erp_data` + `filter_invoices` MCP tools
├── server/erp.py                       # NEW router: /api/erp/*
├── server/routers/filings.py           # 响应补 audit_trail
└── data/erp_samples/                   # NEW
    ├── techflow_q1_2026.json           # 已有的 realCaseData 转格式
    ├── cross_border_eu_2026.json       # 跨境案例（已添加）
    └── generic_sales_template.csv      # CSV demo 模板

tax_agent/frontend/src/
├── components/
│   ├── CasePresetCard.tsx              # 已存在，复用
│   ├── ErpConnectionToggle.tsx         # NEW — Dashboard 上"接入 ERP" toggle
│   ├── ClearDataButton.tsx             # NEW — Dashboard 上"清空数据"按钮
│   ├── InvoiceMultiSelectPanel.tsx     # NEW — AgentChatPage 里的"勾选发票发送"面板
│   └── CsvImportWizard.tsx             # NEW — drag-drop CSV
├── pages/
│   ├── DashboardPage.tsx               # +Case 切换高亮 + ErpConnectionToggle + ClearDataButton
│   └── AgentChatPage.tsx               # +InvoiceMultiSelectPanel (不选 case)
├── stores/demoStore.ts                 # 已存在，扩展 source 字段
└── data/casePresets.ts                 # 扩展 metadata {erp_case_id}
```

---

## 2. Components

5 个新组件 + 2 个 Dashboard 增强控件，**每个有单一职责**：

| # | 组件 | 职责 | 文件 |
|---|---|---|---|
| 1 | **`tax_agent/erp/`** | ERP 数据接入包（解析 + reconcile） | `erp/csv_parser.py`, `erp/profiles.py`, `erp/reconcile.py`, `erp/audit_events.py` |
| 2 | **`_stage_import`** | Orchestrator 新阶段，解析 → 写 TaxData | `tax_agent/orchestrator.py`（修改） |
| 3 | **`/api/erp/*` router** | 独立 REST 端点供 wizard / agent 调用 | `tax_agent/server/erp.py`（NEW） |
| 4 | **`ErpConnectionToggle` + `ClearDataButton` + `CsvImportWizard`** | 前端 UI 组件（Dashboard 控件） | `tax_agent/frontend/src/components/`（NEW × 3） |
| 5 | **`InvoiceMultiSelectPanel` + `ingest_erp_data`/`filter_invoices` MCP tools** | AgentChatPage 里的"勾选发票发送" 面板 | `tax_agent/frontend/src/components/InvoiceMultiSelectPanel.tsx`（NEW） + `tax_agent/jurisdictions/uk/vat/agent_tools.py`（修改） |

每个组件都**有清晰边界**：
- `erp/csv_parser.py` 不依赖 httpx（不碰网络）
- `erp/reconcile.py` 纯函数（不读网络/不写 DB）
- `_stage_import` 只调 erp/ 包的函数，不自己解析 CSV
- 前端 wizard 调 `/api/erp/*` router，不直连 ERPNext（CORS / 凭证安全）
- Agent `ingest_erp_data` MCP tool 调 `/api/erp/import` 不自己实现解析
- Agent `filter_invoices` MCP tool 接收发票 ID 列表，返这些发票的汇总/详情
- `InvoiceMultiSelectPanel` 调 `filter_invoices` 拿到可选发票列表，用户勾完后**把勾选 ID 作为下一次 chat 消息的附件**发给 Agent

### 2.1 Dashboard 三件套（v0 修订 ①②③ 核心）

**`ErpConnectionToggle`**
- 位置：Dashboard 顶部 case 网格上方
- 状态：`off` (默认，v0 走 demo case) / `on` (未来 v1 接 ERPNext)
- 行为：
  - `off`：隐藏所有 ERPNext 相关 UI（credentials 输入、连接测试），只显示 demo case 网格
  - `on`：未来 v1 显示凭证输入 → 但 v0 仍然显示 "Coming soon" 占位

**`ClearDataButton`**
- 位置：Dashboard 顶部右侧
- 行为：点击后弹确认 dialog（"清空所有 demo 数据 + Agent 上传数据？此操作不可撤销"）
  - 清 `useDemoStore.selectedPreset = null`
  - 清 AgentChatPage `session.uploaded_data = null`（通过 store event）
  - 清 `localStorage` 里所有 T.A.X.I. demo 相关的缓存
- 二次确认后才执行
- **作用**：让用户在切 case 之前**显式 reset**，避免"上一个 case 的数据残留到下一个"

**`CasePresetCard` 增强（v0 修订 ②）**
- 复用现有 `CasePresetCard.tsx`，加 1 个状态：
  - 选中的 case 卡片**外框变蓝色高亮** + 右上角 "已加载" 徽章
  - 顶部加 "切换 Case" 按钮（仅在有选中的情况下显示，点击后弹 dialog 确认）
- 作用：让用户**一眼看到当前 demo 是哪个 case**，方便切

---

## 3. Data Flow（Agent 主导，Demo 流畅版）

> v0 调整说明（用户已确认）：
> 1. §1.2 模式 A + B 融合（demo 案例 + CSV 都走 _stage_import）
> 2. 申报阶段由 Agent 在 chat 里主导（不强制 Orchestrator 全管线贯通）
> 3. 保留数据 Preview 功能
> 4. **Dashboard 是 case 切换 + ERP 接入 + 数据清空的唯一入口**；AgentChatPage 只在数据已加载后用 `InvoiceMultiSelectPanel` 勾选 case 中"相关数据"发送
> 5. ERP on/off toggle 决定数据源是 demo case 还是未来真连 ERPNext
> 6. **Agent 主动引导** + chat 顶部**两个一键输入按钮**（"帮我分析目前的财务数据"、"帮我计算本年增值税并申报"）
> 7. 错误用**简单错误表格**展示（v0 不做 form-based 错误高亮）
> 8. v0 **不区分多 case 上下文**——只记一个当前 case 数据
> 9. Chat 进入计算后**锁定数据**——用户想改需回 Dashboard 清空

### 阶段 0：Dashboard 选 case + ERP 设置（v0 唯一入口）

**环节 ①** 用户进 `/`（Dashboard）→ 顶部三件套布局
```
┌──────────────────────────────────────────────────┐
│ [ErpConnectionToggle off/on]    [清空数据]         │
├──────────────────────────────────────────────────┤
│ 已加载：TechFlow Q1 2026  [切换 Case]             │  ← 仅当选中 case 时显示
├──────────────────────────────────────────────────┤
│ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐              │
│ │Case│ │Case│ │Case│ │Case│ │Case│ ← 5 个网格     │
│ │ 1  │ │ 2  │ │ 3  │ │ 4  │ │ 5  │              │
│ └────┘ └────┘ └────┘ └────┘ └────┘              │
└──────────────────────────────────────────────────┘
```

**环节 ②** 用户点 `TechFlow Q1 2026` 卡 → `useDemoStore.selectedPreset = 'techflow_q1_2026'`
- 卡片高亮 + 顶部出现 "已加载：TechFlow Q1 2026 [切换 Case]"

**环节 ③** 用户点 "加载此 Case"（或 "切换 Case"）→ 后端调 `ingest_erp_data` MCP tool
- 数据写入 `session.uploaded_data`
- 用户自动 navigate 到 `/filings/new`（preset 已存 demoStore）

**环节 ④** 切 case 前用户可点 "清空数据" 按钮
- 弹确认 dialog → 清 `demoStore` + `session.uploaded_data` + `localStorage`
- 切到新 case 不被旧数据污染

### 阶段 1：NewFilingPage（数据流过 Pipeline）

**环节 ⑤** NewFilingPage Step 1-2 (jurisdiction + obligation) 走完后，Step 3 顶部自动显示**"已从 Demo 案例加载 · TechFlow Distribution Ltd Q1 2026 · 26 销售 + 22 采购"** + "数据 Preview" 折叠面板
- **作用**：让观众看到 T.A.X.I. 真在用数据，不是空表格（**Preview 功能保留**）
- **Preview 面板**：默认折叠到 10 行，点展开看全部 48 条交易明细

**环节 ⑥** Step 4 (Preview) 9-Box side-by-side 对比（打磨点 ①）
- **作用**：demo 核心 wow 画面

**环节 ⑦** Step 5 提交 → Orchestrator 跑 PRECHECK + PREPARE + SUBMIT + TRACK 4 阶段
- **作用**：Agent 已在 chat 里做过 CALCULATE / VALIDATE，Orchestrator 不重做

### 阶段 2：AgentChatPage（Agent 主导路径，v0 修订 ④）

**环节 ⑧** 用户进 `/agent` → 看到 **顶部 3 个 UI 元素**：
1. **当前 case 摘要 banner**（"📂 TechFlow Q1 2026 · 26 销售 + 22 采购"）
2. **两个一键输入按钮**（"🔍 帮我分析目前的财务数据"、"📊 帮我计算本年增值税并申报"）
3. **chat 输入框**（用户自由输入）
- **设计理由**：一键按钮让 demo 主持人快速演示 + 新用户快速上手；同时保留 chat 输入框不限制高级用法

**环节 ⑨** 用户点 "🔍 帮我分析目前的财务数据" → Agent 主动引导对话
- Agent："TechFlow Q1 2026 共 26 张销售 + 22 张采购发票，要我展示一下吗？"
- 用户回 "是" → Agent 调 `filter_invoices` 工具
- 弹 `InvoiceMultiSelectPanel`（多选 checkbox 列表）
- 用户勾几张 → 点 "发送选中的发票" → 这些发票作为附件进入下次 LLM 消息

**环节 ⑩** Agent 收到附件后**主动问**："您勾了 3 张进项发票，总共 £2,340 VAT。要我把这 3 张纳入进项税计算吗？"
- 用户回 "是" → Agent 调 `calculate_vat_return` 工具（reconcile 模式）
- 后端：
  - 走 `_stage_import` 把 `uploaded_data` 转 `ImportResult`
  - `calculate_uk_vat(data, mode="reconcile")` 算出 T.A.X.I. 的 9-Box
  - 与 ERP（demo case 预存的 9-Box）对比
  - 返 `ReconciliationDelta`（per-box 差异、tolerance、notes）
- Agent 在 chat 流里展示 **9-Box 表格** + **差异表格**（如有不一致）
- **Preview 功能保留**在 chat 流里

**环节 ⑪** （如有差异）Agent **主动解释**：
- "Box 1 差异 +£3.50 > tolerance £0.50，可能是您标记的 INV-2026-014 算的税不对。要查看具体哪条吗？"
- 用户可以问 Agent："找出导致差异的那条" → Agent 调 `filter_invoices` 找到

**环节 ⑫** 用户对 9-Box 满意 → 在 chat 流里点 "Continue to validation" 按钮
- Agent 调 `validate_vat_return` → 后端 `validate_uk_vat` 校验
- Agent 报告："9-Box 数据合规，无错误。"

**环节 ⑬** 用户点 "📊 帮我计算本年增值税并申报" 一键按钮 → 跳过 ⑨-⑫ 直接进入法律声明

**环节 ⑭** Agent 展示 **HMRC 法律声明**（红色 banner + 复选框）
- 文字："I declare that the information given on this return is correct and complete to the best of my knowledge..."
- 用户**必须勾选**才能继续

**环节 ⑮** 用户点 "**Submit to HMRC**" 按钮
- 触发 Orchestrator 一次性跑 PRECHECK + PREPARE + SUBMIT + TRACK
- chat 流里**实时滚动** audit log（"PRECHECK ✓ / PREPARE ✓ / SUBMIT 调 HMRC / TRACK 等待回执"）
- 几秒后显示 **HMRC 回执卡片**（打磨点 ③）

**环节 ⑯** 用户点 chat 里 "**Try a different case**" 链接
- 跳回 Dashboard → 用户选另一个 case
- **新决策**：根据用户"v0 不区分多上下文"指示，chat **不保留历史**——重新开始
- 重复步骤 ①-⑮

### 阶段 3：错误恢复（v0 修订 ②）

**环节 ⑰** 工具调用失败 → Agent 重试 1 次 → 仍失败 → 在 chat 流里展示**简单错误表格**：
```
┌──────────────────────────────────────────┐
│ ❌ 计算出错                               │
├──────────────────────────────────────────┤
│ 错误码    | INVALID_PAYLOAD              │
│ 错误信息  | Box 1 must be 2dp            │
│ 工具      | calculate_vat_return         │
│ 时间      | 2026-06-10T14:23:18Z         │
├──────────────────────────────────────────┤
│ 💡 建议操作：                              │
│ • 检查源数据是否有非标准税率              │
│ • 或回 Dashboard 清空后重选 case         │
└──────────────────────────────────────────┘
```
- **不**做 form-based 高亮（v0 简化）

**环节 ⑱** Chat 中数据**锁定**——一旦进入计算/校验阶段，用户想改数据必须：
- 点 chat 里的 "回到 Dashboard" 链接 → 弹"清空确认"dialog → 清空 → 重新选 case
- **不**允许在 chat 里直接改 line item

### 入口 C — CsvImportWizard

**环节 ①-②** 用户在 NewFilingPage Step 3 点 "Upload CSV" 按钮 → 打开 wizard
**环节 ③-④** wizard 2 步：drag-drop → 列映射（Generic profile）→ preview discrepancy
**环节 ⑤-⑥** 用户确认 → 走和阶段 1 相同的 Orchestrator 路径

**v0 不做真 ERPNext 凭证验证**（C 模式 ERPNext 真连只作 v0 末尾 "Coming soon" 占位，ErpConnectionToggle 切 on 后显示占位）。

---

## 3.1 Agent 交互的 5 个关键设计原则

1. **Agent 主动引导** —— 用户问问题后 Agent 主动建议下一步，不被动等命令
2. **自然语言 + 一键按钮并存** —— 一键按钮降低 demo 门槛，chat 输入保留高级用法
3. **chat 流里展示一切** —— 9-Box 表格 / 错误表格 / 回执卡片都渲染在 chat 流（不开新 modal）
4. **数据锁定** —— 进入计算后改数据需回 Dashboard 清空（v0 安全）
5. **Copilot 哲学** —— Agent 给建议 + 计算 + 解释，**用户点 Submit 才真提交**

---

## 4. Error Handling（严格报错，不静默 fallback）

> 调整说明：经用户确认，v0 demo **不做自动 fallback**。任何错误立即红条 + 明确信息 + 用户手动恢复。

| 错误场景 | 用户看到的 | T.A.X.I. 行为 |
|---|---|---|
| **Demo case JSON 文件损坏** | Agent chat 红条 + "Demo case 加载失败，请选另一个 case 或联系维护" | 抛 `ImportCaseError`，Chat 重置 session |
| **CSV 缺必填列** | wizard 红条 + 表格行级错误（"Row 14: 缺少 tax_code"） | `parse_csv` 返回 `ImportResult` 带 `rejected_rows`，wizard 展示但**不阻塞**用户决定 |
| **CSV 头污染** | wizard 红条："文件第 1 行不像 CSV header" | 抛 `CsvParseError`，wizard 停在 upload 步 |
| **9-Box reconcile 超 tolerance** | chat 或 Step 4 顶部红色 banner："Box 1 差异 £3.50 > £0.50 tolerance，请检查" | 阻止 Submit 按钮直到用户勾 "我已查看差异"。tolerance £0.50 是 HMRC 官方 rounding 容差 |
| **HMRC 4xx** | 红条 + 错误 detail（"INVALID_PAYLOAD: Box 1 must be 2dp"） | FilingResult.status=ERROR, errors[] 完整返前端/chat |
| **Agent 调用 `ingest_erp_data` 时 case 不存在** | Agent 在 chat 里回答："对不起，我没找到这个 case，可选的有：..." | 工具返 404 + 推荐 case 列表 |

**所有错误都有 stack trace 写入 audit_log**，方便 debug。**v0 demo 不做自动 fallback**：case 坏就让用户换，CSV 坏就让用户改，没有"静默切 mock"这种事。

---

## 5. Testing（先 Excel/CSV 完备，ERPNext e2e 后续）

> 调整说明：经用户确认，v0 先把 CSV/Excel 测试做扎实，ERPNext 真连 e2e 推到 v1。

| # | 测试 | 工具 | 目标 |
|---|---|---|---|
| 1 | **HMRC 提交 mock** | `pytest-httpx` | mock `POST /organisations/vat/{vrn}/returns` 返 201 + formBundleNumber |
| 2 | **CSV golden-file** | `pytest` + `csv.DictReader` | bundled `generic_sales_template.csv` 解析 → 9-Box 与手算 9-Box 一致（容差 £0.01） |
| 3 | **Demo case JSON 加载** | `pytest` + 真实 `data/erp_samples/*.json` | 5 个 case 都加载成功，ImportResult 字段完整 |
| 4 | **Agent chat 端到端** | `pytest-asyncio` + 真实 TaxAgentEngine | 模拟用户输入"加载 techflow_q1_2026"→ 验证 `ingest_erp_data` tool 被调、session.uploaded_data 被填 |
| 5 | **Orchestrator 端到端** | `pytest-asyncio` | 跳过 IMPORT / CALCULATE / VALIDATE，只跑 PRECHECK + PREPARE + SUBMIT + TRACK 4 阶段，验 FilingResult.success=True |

**覆盖目标**：`tax_agent/erp/` 包 ≥ 70% line coverage。

**v1 再补**：frappe_docker 起真 ERPNext → T.A.X.I. → HMRC mock 完整 e2e（只在 CI 跑，本地跳过）。

---

## 6. UX Demo 打磨点（关键 3 个 wow 画面）

为了让 5 分钟 demo 抓住观众，三个画面必须打磨到像素级：

1. **9-Box diff 对比动画**（Step 4）：左列 ERPNext 数字"打字机"效果出现 → 右列 T.A.X.I. 数字同步出现 → 差异行加红色脉冲高亮 200ms
2. **Audit trail 时间线**（Step 4 底部）：横向时间轴，6 个阶段作为节点，hover 显示该阶段详情
3. **HMRC 回执卡片**（Step 6）：模拟"信封打开"动画，显示 formBundleNumber 大字 + 处理时间 + 完整 JSON payload（默认折叠，点展开）

这些**不是必要功能**，但 demo 演示中能**让人立刻 get 到 T.A.X.I. 的差异化价值**。

---

## 7. Risks & Mitigations

| 风险 | 缓解 |
|---|---|
| Demo 沙箱 ERPNext 频繁挂 | 默认走 demo store 模式，ERPNext 真连只作"可演示可不演示" |
| 用户不知道 demo 案例数据从哪来 | Step 3 顶部明确标注"此案例：TechFlow Distribution Ltd Q1 2026，来源：anonymized sample" |
| 9-Box 差异让观众误以为有 bug | 故意在 demo 案例中埋 1-2 个小差异，配 explainer "T.A.X.I. 帮你抓 ERP 计算错误" |
| 9-Box 完全一致 → 没 wow 效果 | 同上，demo 数据刻意不完美 |
| HMRC mock 端点 404 | pytest-httpx 默认 fallback，CI 必跑 |
| 切 demo 案例后状态不清空 | demo store 切换时调 `clearFiling()` 统一清空 |

---

## 8. Out of Scope (v0 明确不做)

为了 v0 在 2-3 周内交付，明确以下推到 v1：

- 真 ERPNext 凭证管理（OAuth 2、api_key 持久化）
- ERPNext `erpnext_client.py` 实际实现（v0 留空，C 模式只显示 "Coming soon"）
- 多 Profile 适配（Sage / Xero / QBO）— v0 只 Generic CSV
- FRS / Cash / Annual / Margin scheme 调整
- 真 HMRC sandbox user 注册
- 多租户、权限层级
- 双向同步（ERPNext on_submit hook 主动推 T.A.X.I.）
- ERPNext 端写回（TAXI VAT Return DocType）
- FR/CN/DE 国家的 ERP 集成

---

## 9. References

- `tax_agent/docs/integration/erpnext-integration.md` — 前期 ERPNext 调研
- `tax_agent/docs/architecture/pipeline.md` — 6 阶段管线详解
- `tax_agent/orchestrator.py` — `_stage_precheck/prepare/calculate/validate/submit/track` 实现参考
- `tax_agent/jurisdictions/uk/vat/calculator.py` — UK 9-Box 算法参考
- `tax_agent/vat_return_payload.json` — HMRC 提交 JSON schema 参考
- `tax_agent/data/realCaseData.json` — 现有 sample 数据，将转为 demo 案例

---

**Spec 状态**：等待用户审阅。
