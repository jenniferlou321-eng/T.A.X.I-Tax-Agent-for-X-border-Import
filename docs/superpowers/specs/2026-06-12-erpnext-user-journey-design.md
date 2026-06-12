# T.A.X.I. — 用户使用 ERPNext 接入 v1 设计

> **状态**：设计中
> **日期**：2026-06-12
> **作者**：T.A.X.I. 团队
> **范围**：单一子项目 — ERPNext 用户旅程 v1（手动 Pull 模式）

---

## Context（背景）

T.A.X.I. v0 已实现：
- 6 阶段报税管线 + 3 层插件架构
- UK VAT 端到端（HMRC MTD API + sandbox）
- LLM 驱动的 Agent 入口
- ERP 集成 v0：`docs/superpowers/specs/2026-06-10-erp-integration-v0-design.md`
- ERPNext push hook 链路（2026-06-11 实装，E2E 测试通过）

**当前缺口**：
1. ERPNext 接入的**用户旅程**不清晰——已有 push 实现，但用户视角下"我从 T.A.X.I. 怎么把数据拉进来"的流程未梳理
2. v0 设计里 ERPNext 是 "Coming soon" 占位
3. v0 push 模式（on_submit 自动）是"被动接收"，不符合会计"主动控制报税节奏"的工作习惯
4. 没有为"代账会计 / 财务经理"这个用户角色设计专属路径
5. ERPNext 端的引导缺失（用户在 ERPNext 里不知道有 T.A.X.I. 这个工具）

**目标（v1）**：
- 用户**手动**从 T.A.X.I. Pull 数据（不再自动 push）
- T.A.X.I. 新增 **Import Hub** 页面作为外部数据统一入口
- ERPNext 端加 Web Form 跳转链接作为引导
- 支持会计"本季全量"粒度的报税周期
- 支持 Cancel + Credit Note 两套错账冲红机制

**时间预算**：v1 在 1-2 周内交付（基于 v0 已有大量基础）。
**显式不做**（v1 之外）：见 §6。

---

## 1. Architecture

### 1.1 总体方案

**方案 A — T.A.X.I. 仪表板中心**(已选)

T.A.X.I. 是"控制塔",ERPNext 是"数据源"。所有外部数据**手动**从 T.A.X.I. 发起 Pull,ERPNext 不主动推。

```
┌────────────────────────────────────────────────────┐
│   T.A.X.I. Dashboard (/)                            │
│   ┌────────────────────────────────────────────┐  │
│   │ [⬇ 导入外部数据]   [清空数据]                │  │
│   │                                            │  │
│   │ 已加载: TechFlow Q1 2026 (24+ 22)          │  │
│   │                                            │  │
│   │ 5 张预存 Case 网格                          │  │
│   └────────────────────────────────────────────┘  │
│            │                                        │
│            ▼                                        │
│   Import Hub (/import)                              │
│   ┌────────────────────────────────────────────┐  │
│   │ [Period: Q1 2026 ▾]                         │  │
│   │                                            │  │
│   │ ┌──────────┐  ┌──────────┐                  │  │
│   │ │ 📥  从    │  │ 📤  上传 │                  │  │
│   │ │ ERPNext   │  │ CSV      │                  │  │
│   │ │ 手动拉取  │  │ 离线导入  │                  │  │
│   │ └──────────┘  └──────────┘                  │  │
│   │                                            │  │
│   │ [✓ 准备报税,继续到 Preview]                │  │
│   └────────────────────────────────────────────┘  │
│            │                                        │
│            ▼                                        │
│   Preview Page (/import/preview)                    │
│   ┌────────────────────────────────────────────┐  │
│   │ 本期: 24 销售 + 22 采购                    │  │
│   │ (可展开明细表)                              │  │
│   │                                            │  │
│   │ ┌─────────────┐ ┌──────────────┐            │  │
│   │ │ 与Agent对话  │ │ 手动报税      │           │  │
│   │ └─────────────┘ └──────────────┘            │  │
│   └────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────┘

        ERPNext Desk (my.local:8000)
        ┌──────────────────────────────────┐
        │ 右上角 [🌐 T.A.X.I. ↗]            │  ← Web Form 跳转
        │ 用户点 → 跳 T.A.X.I. /import     │
        └──────────────────────────────────┘
```

**关键决策**：
- **取消自动 push**(on_submit hook 默认关)
- **凭证明文**存 demoStore(本期 demo 限制,生产前必须改)
- **2 个 Import Hub 卡片**,不 3 个(Pull + CSV)
- **统一 store** `ImportHubStore(period)`,3 个数据源都进这里
- **Preview 页面**作为 Hub → 双路径的中间层
- **ERPNext 侧 0 集成**,只加 Web Form 链接

### 1.2 三种数据流的合并模型

```
                 ┌──────────────────────┐
   ERPNext Pull  │                      │
   ──────────────┤                      │
                 │  ImportHubStore      │  key: (period, docname)
   CSV upload    │  (in-memory)         │  - id, txn_date, counterparty
   ──────────────┤                      │  - net/vat/gross
                 │  dedup by (period,   │  - cancelled: bool
   ~~Push~~      │  docname)            │  - is_amend: bool
   (本期关)      │                      │  - parent: docname?
                 └─────────┬────────────┘
                           │
                           ▼
                    Preview / Agent / 9-Box
                    (3 个 consumer 同源)
```

### 1.3 关键模块位置

```
backend/
├── erp/
│   ├── csv_parser.py              # 已有,扩 ERPNextExportProfile
│   ├── profiles.py                # 已有,扩 ERPNextExportProfile
│   ├── reconcile.py               # 已有,+cancelled 过滤 + amend 合并
│   ├── erpnext_connector.py       # 已有(push 通路保留,默认关)
│   └── erpnext_pull.py            # NEW — REST API 拉取逻辑
├── services/
│   ├── erpnext_buffer.py          # 改名为 imported_data_buffer.py
│   └── imported_data_buffer.py    # NEW — 按 period 隔离的统一 store
├── routers/
│   └── erp.py                     # 已有,+POST /erpnext/pull
└── jurisdictions/uk/vat/
    └── agent_tools.py             # ingest_erp_data 加 period + from_hub

frontend/src/
├── pages/
│   ├── ImportHubPage.tsx          # NEW — /import 路由
│   └── ImportPreviewPage.tsx      # NEW — /import/preview 路由
├── components/
│   ├── ErpConnectionToggle.tsx    # 已有,改:展示"凭证已配"而非 "Live Push"
│   ├── ImportHubCardErpNext.tsx   # NEW
│   ├── ImportHubCardCsv.tsx       # NEW
│   └── ImportPreviewTable.tsx     # NEW
└── stores/
    └── demoStore.ts               # 已有,+erpnextCredentials + hubDataByPeriod

frappe-bench/apps/tax_integration/
├── tax_integration/hooks.py       # 改:doc_events 注释,默认关
└── tax_integration/integration/
    └── web_form/taxi_link/        # NEW — Web Form 跳转链接
```

---

## 2. Components

### 2.1 Import Hub 页面(2 张卡片)

#### Card A — 📥 从 ERPNext 导入(手动 Pull)

**职责**:从 T.A.X.I. 主动调 ERPNext REST API 拉本期内已 submit 的发票。

**Props**(伪代码):
```typescript
<ImportHubCardErpNext
  period={currentPeriod}            // e.g., "Q1_2026"
  credentials={erpnextCredentials}  // {url, apiKey, apiSecret}
  onPulled={(result) => void}       // 回调:写入 hub store
/>
```

**关键状态**:
- `idle` — 未拉过 / 凭证未配
- `pulling` — 后端请求中(显示 spinner + 预估时间)
- `ok` — 拉取成功(显示本期内 N 笔 + 上次拉取时间)
- `error` — 拉取失败(显示错误 + 重试按钮)

**首次凭证配置**:`[修改]` 按钮弹 modal:
```typescript
{
  url: string;        // e.g., "http://my.local:8000"
  apiKey: string;     // ERPNext API Key
  apiSecret: string;  // ERPNext API Secret
}
```
存 `useDemoStore().erpnextCredentials`(localStorage 明文)。

**Pull 行为**:
- 增量:`modified >= last_pull_at`(首次拉 = 全量)
- 范围:`posting_date ∈ [period_start, period_end]`
- 状态:`docstatus ∈ {1, 2}`(拉 submit + cancel 的)
- 后端:`POST /api/erp/erpnext/pull {period_start, period_end, since: last_pull_at}`
- 拉回后 → dedup → 写 `ImportHubStore(period)`

#### Card B — 📤 上传 CSV(离线导入)

**职责**:用户从 ERPNext export CSV → 上传到 T.A.X.I.。**补漏/离线场景**。

**复用**:
- 现有 `CsvImportWizard` 流程
- 现有 `POST /api/erp/import` endpoint
- 现有 `GenericProfile`(本期保持)
- 新增 `ERPNextExportProfile`(自动检测)

**支持格式**:
- Generic 8 列(txn_date, txn_type, counterparty, net, vat, gross, vat_rate, tax_code)
- ERPNext 导出(列名带 Item Code / Customer / Posting Date 等)

### 2.2 Preview 页面

**职责**:展示本 period 已导入的数据,**只读**,提供 2 个出口。

**布局**:
```
┌─────────────────────────────────────────────────────┐
│ Q1 2026 导入数据预览                                  │
├─────────────────────────────────────────────────────┤
│ 销售 24 笔  £30,000 净额  £6,000 销项税            │
│ 采购 22 笔  £18,000 净额  £3,600 进项税            │
│ 已冲红 1 笔  Credit Note CN-2026-0001 ↔ SINV-0142   │
│                                                     │
│ ▼ 明细表(前 10 行)                                   │
│   SINV-2026-0142  03-15  ACME Ltd  £1,200 £240  ✓  │
│   PINV-2026-0089  03-20  Office Co £450   £90   ✓  │
│   ...                                               │
│                                                     │
│ ┌─────────────┐ ┌──────────────┐                    │
│ │ 与 Agent 对话│ │ 手动报税     │                    │
│ └─────────────┘ └──────────────┘                    │
└─────────────────────────────────────────────────────┘
```

**Props**:
```typescript
<ImportPreviewPage
  period={currentPeriod}
  hubData={hubDataByPeriod[currentPeriod]}  // 从 store 读
/>
```

**关键不变量**:
- **只读**(无 edit 按钮)
- 数据来自 `ImportHubStore(period)`,不是 `NewFilingPage` 的 9-Box
- 2 个 CTA 都把同一份数据传给下游

### 2.3 统一数据 Store: `ImportHubStore`

**位置**:`backend/services/imported_data_buffer.py`

**数据结构**:
```python
@dataclass
class HubInvoice:
    id: str                    # docname (SINV-2026-0142)
    txn_date: date
    counterparty: str
    net_amount: Decimal
    vat_amount: Decimal
    gross_amount: Decimal
    vat_rate: Decimal
    tax_code: str
    cancelled: bool = False    # ERPNext docstatus=2
    is_amend: bool = False     # ERPNext Credit/Debit Note
    parent: Optional[str]      # 原发票 docname(若 amend)
    source: str                # "erpnext_pull" | "csv" | "erpnext_push"
    pulled_at: datetime

class ImportHubStore:
    """按 period 隔离的 hub 导入数据."""
    _data: dict[str, dict[str, HubInvoice]]  # period → {docname → invoice}

    def add(period, invoices):  # dedup by docname
    def list(period):           # 返 list[HubInvoice]
    def clear(period=None):     # 清一个 period 或全清
    def count(period):          # 返 dict {sales, purchases, cancelled, amends}
```

**去重规则**:
- 同一 `(period, docname)`:后写覆盖前
- Cancel(原 docstatus=1 → 2)不算新 docname,**只改 cancelled 字段**

### 2.4 9-Box 计算集成(扩展 `reconcile.py`)

**新增过滤**:
```python
def compute_taxi_nine_box(sales, purchases, *, filter_cancelled=True):
    if filter_cancelled:
        sales = [s for s in sales if not s.cancelled]
        purchases = [p for p in purchases if not p.cancelled]
    # ... 原有逻辑
```

**Amend 合并**:
- 原发票 + Credit Note(同 parent)同 period → 9-Box 算时**同 box 数字相加**(Credit Note 是负,自然抵减)
- 跨期 amend:9-Box 计算时**只**包含本 period 内的发票(原 period 已报过的不动)

---

## 3. Data Flow

### 3.1 完整用户旅程

```
1. 用户进 T.A.X.I. Dashboard
   │
2. 看到 "[⬇ 导入外部数据]" 按钮(在 case 网格上方)
   │
3. 点 → 跳 /import
   │
4. 顶部 Period selector:默认 Q1 2026(当前季度)
   │
5. Card A 显示 "凭证未配 / 凭证已配 / 上次拉取 N 分钟前"
   │
6. 用户点 [🔄 拉取本季度]
   │
7. 后端:POST /api/erp/erpnext/pull {period, since}
   │
8. 拉回 N 张发票 → dedup → 写 ImportHubStore("Q1_2026")
   │
9. 卡片显示 "本期内 24 销售 + 22 采购,✓"
   │
10. 底部 [✓ 准备报税] 启用 → 点 → 跳 /import/preview?period=Q1_2026
   │
11. Preview 展示汇总 + 明细 + 2 个 CTA
   │
12a. 点 [与 Agent 对话] → 跳 /agent,数据塞 session.uploaded_data
       (传递机制:route state + demoStore.hubDataByPeriod[period])
   │
12b. 点 [手动报税] → 跳 /filings/new,数据预填 9-Box
       (传递机制:demoStore.hubDataByPeriod[period] → 9-Box initial values)
   │
13. Agent 引导 或 9-Box 填写 → Submit
   │
14. HMRC 回执(继续 mock)
```

### 3.2 ERPNext 侧引导

```
用户在 ERPNext 任何页面
   │
   └── 右上角 [🌐 T.A.X.I. ↗]  ← Web Form(无深度集成)
              │
              ▼
   跳 http://localhost:9000/import
   │
   T.A.X.I. 自动按 ERPNext 当前 company 选 period
   (本期 demo 仅 1 company,v1.1 加公司选择器)
```

**实现**:Frappe Web Form,1 个 DocType,字段只 1 个 url 字段。**不**挂任何 doc_events。

### 3.3 错账冲红(两套机制)

#### Cancel 路径
```
[ERPNext] SINV-2026-0142 → Cancel (docstatus 1 → 2)
[下次 Pull] 拉回 docstatus=2 的该发票
[ImportHubStore] cancelled=true
[Preview] 该行红条 + 划线
[9-Box] compute_taxi_nine_box 过滤掉 cancelled
```

#### Credit Note 路径
```
[ERPNext] 新建 CN-2026-0001,is_return=1,return_against=SINV-2026-0142
[下次 Pull] 拉到 CN-2026-0001 (is_amend=true, parent=SINV-2026-0142)
[ImportHubStore] is_amend=true, parent="SINV-2026-0142"
[Preview] 原发票 + CN 同显示,用 ↳ 关联,负数红字
[9-Box] 原 + CN 同 box 数字相加(自然抵减)
```

---

## 4. State Machine

### 4.1 Hub 状态机

```
                    ┌────────────┐
                    │  Hub Idle  │  ← 用户进 /import 初始
                    └─────┬──────┘
                          │ 点 Pull
                          ▼
                    ┌────────────┐
                    │  Pulling   │  (3-30s,显示 spinner)
                    └─────┬──────┘
                       ┌──┴──┐
                       ▼     ▼
                 ┌────────┐ ┌──────┐
                 │  OK    │ │Error │
                 └───┬────┘ └──┬───┘
                     │        │ 重试
                     │        ▼
                     │   ┌────────────┐
                     │   │  Hub Idle  │
                     │   └────────────┘
                     ▼
              ┌──────────────────────┐
              │   Hub Reviewing      │  ← 有 N 笔已导入
              └──┬────────────────┬──┘
                 │ 切 period      │ 点 [✓ 准备报税]
                 ▼                ▼
          ┌────────────┐    ┌──────────────┐
          │  Hub Idle  │    │  Preview     │
          │ (新 period)│    │  Page        │
          └────────────┘    └──────┬───────┘
                                  │ 2 个 CTA
                                  ▼
                          ┌──────────────┐
                          │ Agent / 9-Box│
                          └──────────────┘
```

### 4.2 不变量(代码 review 时核对)

| # | 不变量 |
|---|---|
| 1 | `ImportHubStore(period)` 写入 = (key 唯一) + (cancelled 字段可改) |
| 2 | `Pull` 永远**不**删数据(只 merge 增量 + 标 cancelled) |
| 3 | Period 切换 = 视图切换,**不**删 store 数据(切回原 period 还在) |
| 4 | Preview 永远**只读**(不允许 edit 任何行) |
| 5 | 9-Box 计算**不**包含 cancelled = true 的发票 |
| 6 | Amend 与原发票**同 period**才合并到 9-Box;跨期 amend 显式标"⚠️ 跨期冲红" |
| 7 | 凭证明文存 demoStore,**绝不**写日志/audit_log |
| 8 | 切换 period 后,底部 CTA 文案反映"为 Q1 2026 准备" |
| 9 | Push 通路(原 Phase 2/3)**保留代码**,但默认关(用 feature flag) |
| 10 | 多 period 同时打开(多 tab)会数据串——本期 demo 不防 |

---

## 5. Error Handling

| 错误 | 触发条件 | 用户看到 | 恢复路径 |
|---|---|---|---|
| **ERPNext URL 不可达** | DNS 错/服务挂 | Card A 红条 + 网络图标 | [修改 URL] 按钮 |
| **ERPNext 401** | API key 错/被 revoke | Card A 红条 + 凭证图标 | [修改凭证] 按钮 |
| **ERPNext 403** | 角色权限不足 | Card A 红条 + 文档链接 | 引导去 ERPNext 改 role |
| **Pull 拉空** | 期间内无 docstatus=1 发票 | Card A 灰底 "0 张" | 不算错,继续 |
| **CSV 列缺失** | wizard 解析失败 | Card B 表格行级红条 | 下载错误 CSV |
| **CSV 头污染** | 第 1 行非 header | Card B 红条 "文件格式错" | 重导出 |
| **Hub 切 period 后忘记再拉** | — | CTA 按钮 hover 提示 | 切后**不**自动拉 |
| **预览数据 > 1000 行** | 大账套 | Preview 默认折叠 + 分页 | 导出 CSV 选项 |
| **Store 数据持久化丢失** | 后端重启 | 顶部警告 "session 重启" | 重新 Pull |
| **凭证写错大小写** | 用户输错 | ERPNext 401 | 提示"大小写敏感" |
| **跨期 invoice** | posting_date 在上期 | Hub 顶部警告条 "拉到 2 张属于上期" | 用户可忽略或切 period |
| **Pull 中途取消** | 用户点 [取消] 按钮 | 卡片回到 Hub Idle,store 保留已写入部分 | 用户可手动再拉一次(增量续传) |
| **后端 Pull 超时(>60s)** | 大账套 | 卡片显示 "后端超时,重试" 红条 | store 保留已写入部分,再拉一次续传 |

**严格不静默 fallback**(沿用 v0 原则):任何错误立即红条 + 明确信息 + 用户手动恢复。

---

## 6. Out of Scope (v1 明确不做)

- ❌ **ERPNext on_submit 自动 push**(改为手动 Pull;v1.1 可加 toggle 切回)
- ❌ **多 ERPNext 实例** / 多公司切换
- ❌ **多用户 / 权限** / 团队协作
- ❌ **凭证加密 / KMS / Vault**(本期 demo 明文存 demoStore)
- ❌ **大账套异步 Pull**(本期同步等 1-2 分钟,v1.1 加 worker)
- ❌ **ERPNext 自定义 Page / Desk 嵌入**(改为 Web Form 跳转)
- ❌ **双向同步**(T.A.X.I. 写回 ERPNext)
- ❌ **除 UK VAT 外的国家**(DE / FR / CN 待 v1.1)
- ❌ **真 HMRC sandbox 提交**(继续 mock)
- ❌ **PDF / Excel 报表导出**
- ❌ **审计合规 6 年留存**
- ❌ **多 period 合并申报**

---

## 7. Testing

| # | 测试 | 类型 | 工具 |
|---|---|---|---|
| 1 | Pull 单张销售发票 | E2E (mock ERPNext) | `pytest-httpx` mock REST |
| 2 | Pull 单张采购 | E2E (mock ERPNext) | 同上 |
| 3 | Pull 已 cancel 的发票 | E2E | mock docstatus=2,验 cancelled=true |
| 4 | Pull Credit Note | E2E | mock is_return=1,验 is_amend + parent |
| 5 | CSV Generic 8 列 | 单元 | parse_csv 解析 bundled template |
| 6 | CSV ERPNext 导出格式 | 单元 | 新 Profile |
| 7 | Period 过滤 | 单元 | 期间外发票不入 store |
| 8 | 凭证 401 | E2E | mock 401,验前端不写 store |
| 9 | 去重(同名 Push + Pull) | 单元 | dedup_by(docname) |
| 10 | Preview 表格渲染 | 组件 | RTL + mock store |
| 11 | 9-Box 排除 cancelled | 单元 | reconcile.py 加 cancelled 过滤 |
| 12 | Amend 同 period 合并 | 单元 | 原 + CN 合并后 Box 正确 |
| 13 | Hub 切 period UI | 组件 | RTL,验证 store 切换 + 文案 |
| 14 | 凭证明文 demoStore | 单元 | 验证 erpnextCredentials 存在(故意不加密) |
| 15 | 完整 E2E: Hub → Preview → 9-Box | E2E | playwright 或 RTL 模拟 |

**覆盖率目标**:`backend/erp/` ≥ 70%,新增 `erpnext_pull.py` ≥ 80%。

---

## 8. Risks & Mitigations

| # | 风险 | 影响 | 缓解 |
|---|---|---|---|
| 1 | 凭证泄露(明文 demoStore) | demo 数据落到截图/视频 | 顶部红色 "⚠️ 凭证不加密" 警告 |
| 2 | 大账套 Pull 超时(>500 张) | 用户以为卡死 | Pull 加进度条 + 后台 worker(v1.1) |
| 3 | ERPNext 时区错位 | posting_date 跨天 | Hub hint 标时区;Pull 用 posting_date 字面量 |
| 4 | 同发票多次 Pull 重复 | 9-Box 翻倍 | store dedup_by(docname) |
| 5 | 切 period 后忘记再拉 | Submit 错 | CTA 文案带 period;Submit 前强制 preview |
| 6 | Cancel 后未重新 Pull | 9-Box 含已冲红 | 提交前 "再拉一次" 按钮 |
| 7 | CSV 字符集(GBK 导出) | 中文乱码 | 解析 utf-8 → gbk → latin1 fallback |
| 8 | ERPNext 多个 Company | Pull 拉到错公司 | 公司选择器(v1.1) |
| 9 | 多 tab 打开不同 period | store 串数据 | 本期 demo 不防 |
| 10 | 跳过 Hub 直接去 NewFilingPage | 没数据报错 | NewFilingPage 顶部检查 hubData 为空时提示 |

---

## 9. References

**项目内**:
- `docs/superpowers/specs/2026-06-10-erp-integration-v0-design.md` — v0 设计
- `backend/erp/erpnext_connector.py` — push payload → ImportResult(已实现,本期复用,默认关)
- `backend/services/erpnext_buffer.py` — push in-memory store(扩为 `imported_data_buffer.py`)
- `backend/erp/csv_parser.py` + `profiles.py` — CSV 解析(扩 ERPNextExportProfile)
- `backend/erp/reconcile.py` — `compute_taxi_nine_box`(加 cancelled 过滤 + amend 合并)
- `backend/jurisdictions/uk/vat/agent_tools.py::ingest_erp_data` — 已有 source 字段(扩 period + from_hub)
- `frontend/src/components/ErpConnectionToggle.tsx` — 5s 轮询 UI 模式(复用)
- `frontend/src/stores/demoStore.ts` — persist 模式(扩 `erpnextCredentials`)
- `docs/erp_integration.md` — v0 用户/开发者文档
- `frappe-bench/apps/tax_integration/` — Frappe app(hooks.py 改默认关;加 web_form/taxi_link)

**项目外**:
- HMRC MTD VAT API — period_key 格式
- ERPNext REST API — `GET /api/resource/Sales%20Invoice` filters 语法

---

**Spec 状态**:等待用户审阅。
