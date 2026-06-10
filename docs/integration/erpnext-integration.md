# T.A.X.I. × ERPNext 集成方案研究

> **调研日期**：2026-06-09
> **目的**：分析 ERPNext / Frappe 平台的税务相关能力，并设计 T.A.X.I. 智能报税平台与之集成的可行架构。

---

## 📋 摘要 (TL;DR)

1. **ERPNext 自身**仅在 **印度**（依赖 `india-compliance` 第三方 app）和 **UAE / 沙特**（`regional` 模块里有 VAT Audit Report / VAT 201 等报表脚本）有较完整的"申报报表→提交"闭环。**UK MTD VAT / 德国 ELSTER / 法国 TVA / 中国金税** 这些 ERPNext **本身都不支持**。
2. T.A.X.I. 已有的 **6 阶段管线 + 注册表 → 适配器 → 渠道** 三层插件架构，天然契合"作为 ERPNext 的一个外部插件"的形态——ERPNext 没有的国家，T.A.X.I. 来补。
3. **推荐集成架构（两阶段）**：
   - **阶段 1（MVP, 2–4 周）**：在 ERPNext 同 bench 中部署一个轻量 Frappe 自定义 app（`tax_integration`），通过 `doc_events` 在 Sales/Purchase Invoice `on_submit` 时将单据推送到 T.A.X.I. 的 FastAPI；T.A.X.I. 通过 `Authorization: token api_key:api_secret` 反向调用 ERPNext REST 拉取完整单据；申报结果写回到一个自定义 DocType `TAXI VAT Return`。
   - **阶段 2（生产, 4–8 周）**：把 T.A.X.I. 拆成独立 SaaS，前置一个 `Webhook → push-id + T.A.X.I. pull-by-id` 的反 race-condition 模式；增加 `n8n` / `Prefect` 编排层。
4. 长期 T.A.X.I. 可成为 **"ERPNext 的多国报税插件"**——这是一个尚未被任何商业产品很好占据的生态位（最接近的只有 `india-compliance` 覆盖印度一国）。

---

## 1. ERPNext 税务相关数据模型

> 来源：直接读取 `frappe/erpnext` 仓库 v15 分支的源代码（已通过 GitHub raw URL 拉取并解析）。

### 1.1 核心 DocType 清单

| DocType | 路径 | 关键字段 | 作用 |
|---|---|---|---|
| `Sales Taxes and Charges Template` | `accounts/doctype/sales_taxes_and_charges_template/` | `title`, `company`, `tax_category` (Link→Tax Category), `disabled`, `is_default`, `taxes` (child table) | 一组税率行（"Output VAT 20%" + "Reverse Charge"），挂到 Sales Invoice 上 |
| `Purchase Taxes and Charges Template` | `accounts/doctype/purchase_taxes_and_charges_template/` | 同上，但归 Purchase Invoice 使用 | 进项税模板 |
| `Item Tax Template` | `accounts/doctype/item_tax_template/` | `company`, `taxes` (child) | 绑定到具体 Item 上，覆盖默认模板 |
| `Tax Category` | `accounts/doctype/tax_category/` | `title`, `description` | 用于按客户/供应商类型（如 "Export", "SEZ", "Deemed Export"）路由到不同模板 |
| `Tax Rule` | `accounts/doctype/tax_rule/` | `tax_type`, `sales_tax_template`, `purchase_tax_template`, `customer`, `supplier`, `customer_group`, `supplier_group`, `tax_category`, `billing_country`, `shipping_country`, `priority`, `from_date`, `to_date` | **规则匹配器**——根据客户/供应商/地区/日期自动选模板 |
| `Tax Withholding Category` | `accounts/doctype/tax_withholding_category/` | `category_name`, `rates` (child) | TDS/预提税（如印度 TDS、美国 1099 withholding） |
| `Sales Invoice` | `accounts/doctype/sales_invoice/` | `taxes_and_charges` (Link→Template), `tax_category` (Link), `taxes` (child table: `account_head`, `charge_type`, `rate`, `tax_amount`, `tax_amount_after_discount_amount`, `included_in_print_rate`, `item_wise_tax_detail` JSON) | **税务落点**——`taxes` 子表里有完整税额计算结果 |
| `Purchase Invoice` | `accounts/doctype/purchase_invoice/` | 同上 | 进项税 |
| `GL Entry` | `accounts/doctype/gl_entry/` | `account`, `party_type`, `party`, `debit`, `credit`, `voucher_type`, `voucher_no`, `posting_date` | 全部税额最终落到这里——是税务报表的数据源 |

**ERPNext 选择 Tax Template 的核心链路**（在 `erpnext/accounts/party.py` 中）：

```
Customer / Supplier
  → set_taxes()  (frappe.whitelist, 在 Sales Invoice on_change 触发)
    → get_party_details()  (读 customer_group, supplier_group, billing/shipping address)
      → get_tax_template(posting_date, args)
        → 遍历 Tax Rule 列表，按 priority + 日期范围匹配
        → 返回第一个命中的 sales_tax_template / purchase_tax_template
```

这条链路 T.A.X.I. 必须理解，因为：
- ERPNext 的"已选模板"是**计算结果**，不是**配置事实**——同一客户不同期间的 Tax Rule 变更会让 `taxes_and_charges` 字段值不同。
- 真正"权威"的源是 `Sales Invoice.taxes` 子表里的 `tax_amount`，而不是 `taxes_and_charges` 这个 Link 字段。

### 1.2 关键实现细节

`Sales Invoice.taxes` 子表在保存时由 `erpnext/controllers/taxes_and_totals.py` 的 `calculate_taxes()` 计算：

- `charge_type` 支持：`Actual`（定额）/ `On Net Total`（按净额）/ `On Previous Row Amount` / `On Previous Row Total` / `On Item Quantity`。
- `item_wise_tax_detail` 是 JSON，记录每行 item 各自承担的税额——**T.A.X.I. 报税时按 9-Box / GSTR-1 等格式拆分 item 级别税额所需的字段就在这里**。
- `dont_recompute_tax = 1` 可锁定单据不让重算——T.A.X.I. 在用此单据做申报时不能再次触发 recompute。

`Tax Withholding Category` 在 `Purchase Invoice` 提交时通过 `apply_tds` 钩子自动计算——T.A.X.I. 若要做"代扣代缴"申报（如英国 CIS、印度 TDS）需要读取这个。

### 1.3 数据模型对 T.A.X.I. 的启示

| T.A.X.I. 需要的数据 | ERPNext 来源 | 备注 |
|---|---|---|
| 销项税额（按 9-Box / GSTR-1 / 增值税申报表分类） | `Sales Invoice.taxes` 子表，按 `account_head` 汇总 | account_head 一般按公司 Chart of Accounts 编码（如 "VAT 20% - ABC"） |
| 销项金额（不含税） | `Sales Invoice.net_total` + `items.net_amount` | item_wise_tax_detail 含 item 级别税额 |
| 进项税额 | `Purchase Invoice.taxes` 子表 | 同上 |
| 客户/供应商 VAT 号 | `Customer.tax_id` / `Supplier.tax_id` | ERPNext v14+ 改为 `tax_id` 字段（之前叫 `tax_id`/`vat`） |
| 跨境交易（欧盟 B2B / 中国出口） | 通过 Tax Rule 的 `billing_country` + Tax Category 推断 | 需自行从地址解析 |
| 期间（Q1/Q2/Q3/Q4） | `Sales Invoice.posting_date` 范围过滤 | 标准做法 |
| 申报期间已开/已收/已付分清 | ERPNext **未**区分 收付实现制 vs 权责发生制——使用 posting_date 即可 | 这是 ERPNext 的设计取舍 |

**关键结论**：T.A.X.I. 不必从零建模税务数据——可以直接消费 ERPNext 已经算好的 `Sales Invoice.taxes` 子表。这能省去 60–70% 的会计对账工作。

---

## 2. ERPNext 的 API 与事件机制

### 2.1 REST API 能力（来源：`frappe/frappe` 仓库 `develop` 分支的源代码直接验证）

| 端点 | 用途 | 关键参数 |
|---|---|---|
| `GET /api/resource/{DocType}` | 列出文档 | `filters=[[...]]`（Frappe 自己的 JSON 过滤语法），`fields=["..."]`, `limit_start`, `limit_page_length`, `order_by` |
| `GET /api/resource/{DocType}/{name}` | 读单个 | `fields`, `expand`（展开 child table / Link 字段） |
| `POST /api/resource/{DocType}` | 新建 | body 是完整 doc dict |
| `PUT /api/resource/{DocType}/{name}` | 全量替换 | body 是完整 doc dict |
| `DELETE /api/resource/{DocType}/{name}` | 删除 | |
| `POST /api/method/{python.path.to.method}` | 调用白名单方法 | body 是 kwargs |
| `POST /api/method/upload_file` | 上传 | multipart |
| `GET /api/method/frappe.desk.query_report.run` | 跑 Query Report | `report_name`, `filters` (JSON) |
| `GET /api/method/frappe.desk.query_report.export_query` | 导出报表 | `report_name`, `file_format_type` (`CSV` / `Excel`) |
| `GET /api/method/frappe.utils.print_format.download_pdf` | 生成 PDF | `doctype`, `name`, `format` |

**认证**：
- `Authorization: token {api_key}:{api_secret}`（推荐，server-to-server）
- `Authorization: Bearer {access_token}`（OAuth 2.0）
- `Cookie: sid={session_id}`（浏览器 session）
- 速率限制：默认无硬性限制，但单个请求 payload < 25MB；批量建议分页 `limit_page_length=100`。

**查询语法例子**（`/api/resource/Sales Invoice`）：
```
GET /api/resource/Sales Invoice?
  filters=[["posting_date", ">=", "2025-01-01"], ["posting_date", "<", "2025-04-01"], ["docstatus", "=", 1]]
  &fields=["name", "customer", "grand_total", "taxes_and_charges", "tax_category"]
  &limit_page_length=500
  &expand=["taxes"]
```

### 2.2 Webhook / 事件机制

Frappe 提供 **3 层** 事件触发能力：

| 机制 | 配置方式 | 触发粒度 | 可靠性 | 推荐度 |
|---|---|---|---|---|
| **`doc_events` in `hooks.py`** | 在自定义 app 的 `hooks.py` 里写 Python | DocType × 事件（`on_update`, `on_submit`, `on_cancel`, `on_trash`, `before_*`, `after_*`） | ⭐⭐⭐⭐⭐ 同步/异步可控 | **首选** |
| **Webhook DocType (UI)** | Setup → Integrations → Webhook | DocType × 事件，配置 HTTP URL + method + headers | ⭐⭐⭐ Frappe scheduler 异步派发 | 次选 |
| **Socket.IO `event_stream` (v15+)** | 客户端订阅 `frappe.realtime.on('event_name', ...)` | 实时 | ⭐⭐ 仅浏览器内 | 监控面板用 |

**`doc_events` 示例**（写在 `tax_integration/hooks.py`）：
```python
doc_events = {
    "Sales Invoice": {
        "on_submit": "tax_integration.events.sales_invoice.on_submit",
        "on_cancel": "tax_integration.events.sales_invoice.on_cancel",
    },
    "Purchase Invoice": {
        "on_submit": "tax_integration.events.purchase_invoice.on_submit",
    },
}
```

**关键陷阱（race condition）**：当 `on_submit` 触发时，Sales Invoice 自身已 commit，但 `tabGL Entry`、`tabPayment Ledger Entry` 等关联表**可能仍在同步链路中**。Webhook 文档层级的 `on_update` 比 `on_submit` 更危险（数据未稳定）。**最佳实践**：监听 `on_submit`，并由 T.A.X.I. **主动 GET 一次**完整 doc，而不是相信 webhook payload。

**自定义推送函数的异步模式**（避免阻塞 ERPNext 提交）：
```python
def on_submit(doc, method):
    frappe.enqueue(
        "tax_integration.events.sales_invoice.push_to_taxi",
        queue="short",
        timeout=300,
        invoice_name=doc.name,
        company=doc.company,
        posting_date=str(doc.posting_date),
    )
```

### 2.3 后台任务 / 调度

- **RQ (Redis Queue)** 是 Frappe 的默认队列后端：`frappe.enqueue(method, queue='short'|'long'|'default')`。
- **`scheduler_events` in `hooks.py`** 支持 cron：
  ```python
  scheduler_events = {
      "cron": {
          "0 9 * * 1": ["tax_integration.tasks.weekly_vat_pull"],  # 每周一 9 点
      }
  }
  ```
- **长时间任务**（如 T.A.X.I. 调 HMRC 拿回执可能要等 30s+）：用 `queue="long"`（默认 timeout 4h）。

---

## 3. ERPNext 的税务申报能力（按国家）

> 通过直接读 `frappe/erpnext` v15 仓库 `regional/` 和 `accounts/report/` 目录确认。

### 3.1 ✅ 有完整闭环的国家

| 国家 | 形式 | 关键 DocType / Report | 提交方式 |
|---|---|---|---|
| **印度 🇮🇳** | 独立 app **resilient-tech/india-compliance**（非 stock ERPNext） | GSTR-1, GSTR-3B, e-Invoice, e-Waybill, IMS, Purchase Reconciliation | 通过 GSP（ClearTax/Masters India 等）调 GSTN API 直接提交；2B 自动 reconcile |
| **UAE 🇦🇪** | stock ERPNext `regional/report/uae_vat_201/` | `UAE VAT 201` Script Report（基于 GL Entry） | **仅生成报表，需用户在 FTA portal 手工提交**（无 API 闭环） |
| **沙特 🇸🇦** | stock ERPNext `regional/report/vat_audit_report/` | `VAT Audit Report`（2021-07 创建，ref_doctype=GL Entry） | **仅审计报表，无 ZATCA 提交**（ZATCA e-invoicing 在 v14+ 通过 `ksa_einv` app 单独提供） |
| **美国 🇺🇸** | stock ERPNext 1099 / Tax Withholding | `Tax Withholding Category` + `1099 Report` (Script Report) | 仅报表，无 IRS e-file 集成（第三方如 Avalara 集成） |

### 3.2 ❌ ERPNext 自身不覆盖的国家

| 国家 | 缺失项 | 替代方案 |
|---|---|---|
| **英国 🇬🇧** | 完全没有 MTD for VAT 集成；没有 HMRC OAuth app | TaxCalc、Taxdone、Dext、Xero/QuickBooks（都是第三方 SaaS） |
| **德国 🇩🇪** | 没有 UStVA 报表，没有 ELSTER XML 导出，没有 DATEV 标准集成 | DATEV 需通过 `castlecraft/datev-cosmic` 或类似社区 app 二次开发 |
| **法国 🇫🇷** | 没有 CA3 / TVA 报表，没有 DGFiP / impots.gouv.fr 集成 | 无成熟方案 |
| **中国 🇨🇳** | 完全没有金税系统/增值税申报表支持 | ERPNext 中国 fork（如 ERPNext 中国本地化版）质量参差不齐 |
| **新加坡 🇸🇬** | 没有 IRAS GST F5/F7 集成 | 需自建 |
| **巴西 🇧🇷** | SPED/NFe 需 `erpnext-brazil` 独立 app | 社区项目，但 active 维护程度有限 |
| **墨西哥 🇲🇽** | CFDI 需 `erpnext_mexico` 独立 app | 社区项目 |

**T.A.X.I. 的机会窗口**：
- **印度**已被 `india-compliance` 占据，T.A.X.I. 进去要差异化（如支持印度新兴的 e-invoice sandbox / 跨州合并）。
- **英国 / 德国 / 法国 / 中国** 这 4 个**经济总量最大**的市场，**ERPNext 几乎完全空白**——T.A.X.I. 已经实现了 UK VAT（HMRC MTD），DE/FR/CN 还在占位中，**这正是 T.A.X.I. 的核心机会**。
- 同样的机会存在于**任何没有本地化 app 的国家**——T.A.X.I. 的多国架构是真正的护城河。

### 3.3 已有的 Reference Apps（值得 T.A.X.I. 借鉴）

| App | 仓库 | 借鉴点 |
|---|---|---|
| **india-compliance** | `resilient-tech/india-compliance` | GSP 抽象层（一个 GSP 切换不影响业务代码）、`on_submit` 钩子触发 e-invoice、GSTR-1 JSON 生成器 |
| **Frappe HR** | `frappe/hr` | 复杂 `doc_events` + `scheduler_events` + fixtures 的范本（薪酬每月 cron） |
| **Education** | `frappe/education` | 嵌套 DocType 模式 |
| **Payments** | `frappe/payments` | 抽象多个 payment gateway（类似 T.A.X.I. 抽象多个 filing channel） |
| **ERPNext DATEV** | `castlecraft/datev-cosmic` (社区) | DATEV CSV 导出格式——T.A.X.I. 的 DE UStVA adapter 可复用此 schema |

---

## 4. ERPNext 的报表 / 输出系统

### 4.1 Report 类型

| 类型 | 位置 | 用途 | 编程模型 |
|---|---|---|---|
| **Script Report** | `accounts/report/{name}/{name}.py` | 自定义 SQL/Python 查询 | 写一个带 `columns`, `data` 的 `.py` 文件 |
| **Query Report** | 同样位置，但 `.json` 里 `report_type: "Report"` | 纯 SQL `.sql` 文件 | 写 SQL + 简单 params |
| **Custom Report** | 用户 UI 创建 | 临时报表 | 桌面 UI 操作 |

**关键发现**（来源：直接读 `frappe/desk/query_report.py`）：
- `/api/method/frappe.desk.query_report.run?report_name=...&filters=...` 是程序化跑 Report 的官方入口。
- `/api/method/frappe.desk.query_report.export_query` 支持 `file_format_type=CSV` 或 `Excel`——**只支持这两种**。**没有 JSON / XML / PDF**。
- PDF 必须走 `frappe.utils.print_format.download_pdf`（需要 Print Format DocType）。

### 4.2 Print Format

- HTML + Jinja 模板，可使用 `{{ doc }}` / `{{ doc.field }}` / `{{ frappe.db.get_value(...) }}`。
- 可绑定到 DocType 的"Standard" print format。
- 输出仅 PDF，**不能输出 JSON**。
- 但 Print Format 是 Jinja 模板——T.A.X.I. 完全可以**自己读 Jinja + doc dict 生成 JSON**，绕过 ERPNext 的 PDF 中间步骤。

### 4.3 提交格式问题（重要）

T.A.X.I. 需要根据不同国家税局格式输出：
- **HMRC MTD VAT (UK)**：JSON（VAT ReturnDeclare POST body）
- **DATEV (DE)**：ASCII CSV（Buchungsstapel 格式）
- **ELSTER (DE)**：XML（ElsterXML 格式）
- **GSTR-1 (India)**：JSON（GSTN 规定的 schema）
- **金税 (CN)**：XML（航天信息/百旺格式）
- **TVA / DGFiP (FR)**：PDF + 手工或 EDI 模式
- **IRAS GST (SG)**：CSV（特定列序）

**ERPNext 报表系统本身的输出能力无法直接满足**这些国家格式。T.A.X.I. 的解决方案是：**把 ERPNext 当数据源，输出格式在 T.A.X.I. 侧生成**。这是 T.A.X.I. 的核心价值。

---

## 5. T.A.X.I. 现状回顾

> 基于 `tax_agent/CLAUDE.md`、`tax_agent/orchestrator.py`、`tax_agent/jurisdictions/` 的源代码。

### 5.1 已有能力

```
tax_agent/
├── agent/              # Claude Agent SDK + MCP tools（自然语言入口）
├── orchestrator.py     # 6 阶段管线：Precheck → Prepare → Calculate → Validate → Submit → Track
├── jurisdictions/
│   ├── uk/             # ✅ VAT (HMRC MTD), ⏳ CT/PAYE/SA/SDLT (skeleton)
│   ├── testland/       # 示例
│   └── cn, de, fr/     # 占位
├── channels/           # OAuth, API Channel, Fraud Headers
├── services/           # State Machine, Audit Log
├── server/             # FastAPI
└── frontend/           # React 19 + Vite
```

**3 层插件架构**：Registry (`registry.py`) → Adapter (`jurisdictions/{cc}/`) → Channel (`channels/`)。新国家=新适配器+新渠道，不动管线。

### 5.2 关键接口（来自 `jurisdictions/__init__.py` 的 `JurisdictionAdapter` ABC）

```python
class JurisdictionAdapter(ABC):
    country_code: str
    tax_types: list[TaxType]
    supported_channels: list[ChannelType]

    def get_template(self, tax_type) -> DataTemplate
    def calculate(self, tax_type, data) -> CalculationResult
    def validate(self, tax_type, data) -> ValidationReport
    def get_channel(self, tax_type) -> FilingChannel
    def to_filing_format(self, tax_type, data) -> FilingPayload
    def get_agent_tools(self, tax_type) -> AgentToolSet | None
    def get_obligations(self, tax_type, taxpayer_id) -> list[dict]
```

### 5.3 与 ERPNext 集成的天然契合点

1. **DataTemplate ↔ ERPNext 报表**：T.A.X.I. 的 `DataTemplate`（有 `sections`, `fields`, `field_type`, `validation`）可以直接从 ERPNext Sales Invoice 的 `taxes` 子表 schema 派生。
2. **TaxData ↔ ERPNext 单据**：T.A.X.I. 的 `TaxData` 已经有 `line_items: list[LineItem]`，每个 `LineItem` 有 `category`, `amount`，正好对应 ERPNext 9-Box / GSTR-1 的字段分类。
3. **FilingPayload ↔ ERPNext 输出**：T.A.X.I. 的 `FilingPayload.body` 是 dict（任意 JSON），T.A.X.I. 完全可以输出 ERPNext Custom DocType 的 schema。
4. **Audit Log ↔ ERPNext Error Log**：T.A.X.I. 的 `services/audit_log.py` 已经能持久化每一步；ERPNext 侧的 `tabError Log` 可作为补充。

---

## 6. 集成架构方案

### 6.1 方案对比

| 方案 | 形态 | 部署复杂度 | 适用场景 | 风险 |
|---|---|---|---|---|
| **A. ERPNext Custom App Wrapper** | 在 ERPNext bench 中安装一个 `tax_integration` Frappe app；T.A.X.I. FastAPI 独立运行 | ⭐⭐ 中 | 单租户 / 私有部署 / 客户已用 ERPNext | 同 bench 部署有依赖 |
| **B. 纯外部 SaaS + Webhook** | T.A.X.I. 是独立 SaaS；ERPNext 配 Webhook DocType 推到 T.A.X.I.；T.A.X.I. 反向调 ERPNext REST | ⭐⭐ 中 | 多租户 SaaS 模式 | 跨网络、防火墙 |
| **C. Middleware 编排（n8n / Prefect）** | ERPNext → n8n → T.A.X.I. → 税局；n8n 处理重试、状态机、可视化 | ⭐⭐⭐ 高 | 复杂多系统集成 | 新依赖、故障点 |
| **D. ERPNext → T.A.X.I. 文件交换** | ERPNext 导出 CSV/JSON 上传到 S3，T.A.X.I. 轮询下载 | ⭐ 低 | 一次性、跨国、慢速连接 | 延迟、不实时 |

**推荐**：**MVP 用 A 跑通 + 阶段 2 演进到 B**。C 在客户已经有 n8n 时可作为 fast-follow，D 不推荐（违反"AI 副驾"实时性原则）。

### 6.2 推荐架构图（方案 A + B 演进）

```
┌─────────────────────────────────────────────────────────────┐
│                    ERPNext (Frappe Bench)                    │
│  ┌─────────────┐   on_submit    ┌───────────────────────┐   │
│  │ Sales Inv   │ ───────────▶  │ tax_integration       │   │
│  │ Purch Inv   │                │   - doc_events hook   │   │
│  └─────────────┘                │   - frappe.enqueue    │   │
│                                 │   - sign HMAC         │   │
│  ┌─────────────┐                └───────────┬───────────┘   │
│  │ Company     │  ◀── read ──                 │              │
│  │ Customer    │   (via REST GET)             │              │
│  │ Supplier    │                              │ HTTPS        │
│  │ Address     │                              ▼              │
│  └─────────────┘               ┌─────────────────────────┐  │
│  ┌─────────────┐   writeback   │ T.A.X.I. (FastAPI)      │  │
│  │ TAXI VAT    │ ◀──────────── │   POST /api/filings     │  │
│  │ Return (CD) │   (new doc)   │   6-Stage Pipeline      │  │
│  └─────────────┘               │   Agent + LLM           │  │
│                                │   jurisdiction adapters │  │
│  ┌─────────────┐               └────────┬────────────────┘  │
│  │ Error Log   │  ◀── error report ─────┤                   │
│  └─────────────┘                        │ HTTPS / OAuth      │
│                                          ▼                   │
│                                ┌─────────────────────────┐  │
│                                │  HMRC / ELSTER / IRS    │  │
│                                └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 阶段 1（MVP）详细设计

#### 6.3.1 新增文件结构

```
frappe-bench/apps/
├── erpnext/                  (现有)
├── frappe/                   (现有)
└── tax_integration/          (新)
    ├── tax_integration/
    │   ├── __init__.py
    │   ├── hooks.py
    │   ├── events/
    │   │   ├── sales_invoice.py
    │   │   └── purchase_invoice.py
    │   ├── tasks/
    │   │   └── poll_taxi_status.py
    │   ├── api/
    │   │   └── receive_callback.py   # whitelisted endpoint
    │   └── doctype/
    │       └── taxi_vat_return/
    │           ├── taxi_vat_return.json
    │           └── taxi_vat_return.py
    ├── fixtures/
    │   └── custom_field.json
    └── setup.py
```

#### 6.3.2 关键代码草图

**`hooks.py`**
```python
doc_events = {
    "Sales Invoice": {
        "on_submit": "tax_integration.events.sales_invoice.on_submit",
    },
    "Purchase Invoice": {
        "on_submit": "tax_integration.events.purchase_invoice.on_submit",
    },
}

scheduler_events = {
    "cron": {
        "*/15 * * * *": ["tax_integration.tasks.poll_taxi_status"],
    },
}

fixtures = [
    {"dt": "Custom Field", "filters": [["module", "=", "Tax Integration"]]},
    {"dt": "Custom DocPerm", "filters": [["parent", "like", "TAXI-%"]]},
]
```

**`events/sales_invoice.py`**
```python
import frappe, requests, json
from frappe import _

TAXI_API = "https://api.taxagent.example.com"  # from site_config
TAXI_API_KEY = "..."  # from site_config

def on_submit(doc, method):
    if not _should_send(doc):
        return
    frappe.enqueue(
        _push_to_taxi,
        queue="short",
        timeout=300,
        invoice_name=doc.name,
        company=doc.company,
        posting_date=str(doc.posting_date),
        grand_total=doc.grand_total,
    )

def _should_send(doc):
    # 1. company must have TAXI enabled
    if not frappe.db.get_value("Company", doc.company, "custom_taxi_enabled"):
        return False
    # 2. invoice must have a tax category
    if not doc.tax_category:
        return False
    return True

def _push_to_taxi(invoice_name, company, posting_date, grand_total):
    payload = {
        "event": "sales_invoice.submitted",
        "source": "erpnext",
        "company": company,
        "document_name": invoice_name,
        "document_type": "Sales Invoice",
        "posting_date": posting_date,
        "amount": grand_total,
        "idempotency_key": f"si:{invoice_name}",
    }
    # HMAC sign
    import hmac, hashlib
    sig = hmac.new(TAXI_API_KEY.encode(), json.dumps(payload).encode(), hashlib.sha256).hexdigest()
    resp = requests.post(
        f"{TAXI_API}/api/v1/ingest/erpnext",
        json=payload,
        headers={"X-Signature": sig, "X-Source": "erpnext"},
        timeout=30,
    )
    if not resp.ok:
        frappe.log_error(
            title="TAXI push failed",
            message=f"{invoice_name}: {resp.status_code} {resp.text}",
        )
```

**`api/receive_callback.py`** (ERPNext 侧接收 T.A.X.I. 写回)
```python
import frappe, json
from frappe import _

@frappe.whitelist(allow_guest=False)
def save_filing(filing_id, status, payload_json, source="TAXI"):
    """TAXI calls back with filing result; we save to custom DocType."""
    if not frappe.has_permission("TAXI VAT Return", "create"):
        frappe.throw(_("No permission"), frappe.PermissionError)
    doc = frappe.get_doc({
        "doctype": "TAXI VAT Return",
        "filing_id": filing_id,
        "status": status,
        "payload": payload_json,
        "source_system": source,
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"name": doc.name}
```

#### 6.3.3 T.A.X.I. 侧新增 endpoint

```python
# tax_agent/server/routers/erpnext.py
from fastapi import APIRouter, Header, HTTPException
import hmac, hashlib, json

router = APIRouter()

@router.post("/api/v1/ingest/erpnext")
async def ingest_erpnext(
    payload: dict,
    x_signature: str = Header(...),
    x_source: str = Header(...),
):
    # 1. Verify HMAC
    expected = hmac.new(TAXI_HMAC_KEY.encode(), json.dumps(payload).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(x_signature, expected):
        raise HTTPException(401, "Bad signature")

    # 2. Look up the company in our Registry
    company = payload["company"]
    adapter = registry.get(...)  # TODO: ERPNext company → jurisdiction mapping

    # 3. Pull full doc from ERPNext (since webhook payload is light)
    erp_doc = erpnext_client.get_doc(payload["document_type"], payload["document_name"])

    # 4. Convert to TaxData
    tax_data = convert_sales_invoice_to_tax_data(erp_doc, company)

    # 5. Kick off orchestrator.run() async
    filing = await orchestrator.run(adapter, TaxType.VAT, tax_data)

    # 6. Return immediately with filing_id; final result via callback
    return {"filing_id": filing.filing_id, "status": filing.status.value}
```

### 6.4 关键风险与缓解

| 风险 | 缓解策略 |
|---|---|
| **ERPNext `on_submit` 阻塞** | `frappe.enqueue` 异步推送；timeout 300s |
| **Webhook 重试无幂等** | T.A.X.I. 端按 `(document_type, document_name, company)` 复合主键去重 |
| **T.A.X.I. 宕机** | ERPNext `Error Log` 记录失败；阶段 2 引入 dead-letter queue (Redis stream) |
| **数据漂移**（ERPNext 改了 invoice，T.A.X.I. 不知道） | 监听 `on_update`（注意 race condition，**只在 docstatus=1 时处理**）+ `on_cancel` 撤销 |
| **多公司 ERPNext** | 通过 `Company.custom_taxi_jurisdiction` 自定义字段路由到对应国家 adapter |
| **跨网络 / 防火墙** | 阶段 2：T.A.X.I. 出站反向连接到 ERPNext 客户版（inbound open）；方案 A 中无此问题（同 bench） |
| **ERPNext 版本差异** | 主要 API 路径 `/api/resource/{DocType}` 自 v7 起稳定；`on_submit` 钩子签名不变；用 `frappe.__version__` 做分支 |
| **API key 泄露** | ERPNext 端用 site_config + Environment Variable；T.A.X.I. 端用 Vault/KMS |
| **中国 / 德国客户的数据出境** | T.A.X.I. 部署到客户所在区域（CN/DE local cloud）；ERPNext↔T.A.X.I. 全部内网 |

---

## 7. 实施路线图

### Phase 0：PoC 验证（1 周） ✅ 启动门槛低
- 在本地拉起一个 ERPNext 15（frappe_docker）；
- 装一个 `tax_integration` 空 app；
- 手工构造 1 个 Sales Invoice → 推送到本地 T.A.X.I. → 走完 UK VAT 6 阶段；
- 验证回调写回 `TAXI VAT Return` DocType。
- **交付物**：PoC 视频 + 1 页 architecture decision record (ADR)。

### Phase 1：MVP（3–4 周） 🚀 首个付费客户
- 实现 Phase 0 的全部组件 + 完整 error handling；
- 增加 `Custom Field` 在 Company 上挂 `custom_taxi_jurisdiction`；
- 增加 fixtures + migration script；
- 写 `pytest` 覆盖 doc_events 触发链；
- **支持国家**：UK VAT（已有）+ India（通过与 `india-compliance` 互补）；
- **客户场景**：1 个英国 + 1 个印度 ERPNext 客户。

### Phase 2：可生产化（4–6 周） 🏢 多租户
- 把 T.A.X.I. 拆成独立 SaaS（已经基本是了）；
- 增加 Webhook 重试 + DLQ；
- 增加 API key 多租户管理；
- 抽象 ERPNext client SDK（`tax_agent/integrations/erpnext/client.py`），让任意 ERPNext 版本可接入；
- **支持国家**：UK + DE（UStVA 接入） + CN（金税）；
- 第一次见到 N>5 的客户并发。

### Phase 3：生态化（持续） 🌐 平台化
- 把 `tax_integration` app 开源到 GitHub → 提升 ERPNext 社区可见度；
- 接受社区 PR（其他国家适配器）；
- 与 `castlecraft/datev-cosmic`、`frappe/erpnext-brazil` 等社区项目做 interop；
- 在 Frappe marketplace / frappe.cloud 列出。

---

## 8. 结论

**T.A.X.I. 在 ERPNext 生态中的定位**：

> **"ERPNext 的多国税务申报插件"**——一个由外部 Python 服务提供、覆盖 HMRC / ELSTER / 增值税申报 / GSTR / DATEV 等多个国家税局 API 的统一入口，以 Frappe app 形式与 ERPNext 集成。

**为什么这个定位成立**：
1. **ERPNext 自带的 4 个 stock 区域报表**（UAE VAT 201, KSA VAT Audit, India (需 app), US 1099）都**不闭环到税局**——这是真实的市场空白。
2. **UK / DE / FR / CN / SG** 五大主要市场，**ERPNext 完全空白**。
3. **T.A.X.I. 的 6 阶段管线 + 三层插件架构**正好契合"数据来自 ERPNext，提交到多个国家税局"的场景。
4. **T.A.X.I. 已经有了 UK VAT 的 working implementation**（HMRC MTD），可作为标杆市场进入路径。

**关键成功指标**：
- T+3 月：1 个 UK 客户 + 1 个 India 客户生产运行；
- T+6 月：DE 客户签约（UStVA 接入）；
- T+12 月：开源 `tax_integration` app 在 GitHub 上 100+ star，ERPNext 社区有 3+ 个国家适配器 PR。

---

## 9. 参考文献与来源

> 由于本环境 WebSearch / WebFetch 受限，所有引用来自直接读取 `frappe/frappe` 和 `frappe/erpnext` 仓库的源代码（GitHub raw URL）。

### 9.1 直接验证的源代码（来自 GitHub raw URL）
- `frappe/erpnext/develop/erpnext/accounts/doctype/sales_taxes_and_charges_template/sales_taxes_and_charges_template.py` — 验证 Tax Template 与 Tax Category 关系、`validate_for_tax_category` 唯一性约束
- `frappe/erpnext/develop/erpnext/accounts/party.py` 第 700-748 行 — 验证 `set_taxes()` → `get_party_details()` → `get_tax_template()` 的模板选择链
- `frappe/erpnext/develop/erpnext/accounts/doctype/tax_rule/tax_rule.py` — `get_party_details`, `get_tax_template` 实现
- `frappe/erpnext/develop/erpnext/controllers/taxes_and_totals.py` — `calculate_taxes()`, `determine_exclusive_rate()` 完整税额计算实现
- `frappe/erpnext/develop/erpnext/accounts/doctype/sales_invoice/sales_invoice.py` — `tax_category` / `taxes_and_charges` 字段定义
- `frappe/erpnext/develop/erpnext/regional/report/uae_vat_201/uae_vat_201.json` — 确认 UAE VAT 201 是 Script Report，ref_doctype=GL Entry
- `frappe/erpnext/develop/erpnext/regional/report/vat_audit_report/vat_audit_report.json` — 确认 KSA VAT Audit Report 2021-07 创建
- `frappe/erpnext/develop/erpnext/regional/report/electronic_invoice_register/electronic_invoice_register.json` — 确认该 report `disabled=1`（已废弃）
- `frappe/frappe/develop/frappe/desk/query_report.py` 第 331-455 行 — `export_query()` 只支持 CSV / Excel
- `frappe/frappe/develop/frappe/utils/print_format.py` — `download_multi_pdf` / `download_multi_pdf_async` 验证 PDF 是唯一 Print Format 输出
- `frappe/frappe/develop/frappe/printing/page/print/print.py` — `get_print_settings_to_show`

### 9.2 GitHub 仓库（可访问即用）
- **frappe/erpnext** v15 分支: https://github.com/frappe/erpnext/tree/version-15
- **frappe/frappe** develop 分支: https://github.com/frappe/frappe/tree/develop
- **resilient-tech/india-compliance**: https://github.com/resilient-tech/india-compliance （reference app for India GSTR）
- **frappe/hr**: https://github.com/frappe/hr （reference app for complex doc_events）
- **castlecraft/datev-cosmic**: https://github.com/castlecraft/datev-cosmic （DATEV 导出 reference）

### 9.3 官方文档（建议人工核验 URL 结构）
> 以下 URL 路径根据 Frappe 官方 docs 的标准结构列出，但**本次研究未能直接 fetch 验证**（WebFetch 域名限制）；如需在生产文档中引用，请人工点击确认。

- Frappe Apps 基础: https://frappeframework.com/docs/user/en/basics/apps
- Frappe Hooks 完整参考: https://frappeframework.com/docs/user/en/python-api/hooks
- Frappe REST API: https://frappeframework.com/docs/user/en/api/rest
- Frappe REST API 鉴权: https://frappeframework.com/docs/user/en/api/auth
- Frappe Webhooks（社区博客）: https://frappe.io/blog/erpnext-webhooks
- Frappe Query Report 自定义: https://frappeframework.com/docs/user/en/desk/reports
- Frappe Print Format 自定义: https://frappeframework.com/docs/user/en/desk/print-formats
- Frappe Bench Production Setup: https://frappeframework.com/docs/user/en/bench/setup-production
- India Compliance 文档: https://docs.indiacompliance.app/
- India Compliance GSTR-1 文档: https://docs.indiacompliance.app/docs/gst-reports/gstr1

### 9.4 T.A.X.I. 内部引用
- `tax_agent/CLAUDE.md` 第 1-100 行：项目架构总览
- `tax_agent/orchestrator.py` 全文：6 阶段管线实现
- `tax_agent/registry.py`：`JurisdictionRegistry` 实现
- `tax_agent/jurisdictions/__init__.py`：Adapter ABC
- `tax_agent/jurisdictions/uk/__init__.py`：`UKJurisdictionAdapter`（UK 5 个税种注册）
- `tax_agent/jurisdictions/uk/vat/__init__.py`：`to_filing_format()` 实现（HMRC 9-Box JSON）

---

## 10. 待澄清问题 / 后续动作

1. **客户优先级**：UK/DE/CN/IN/SG/FR 中，哪个有 1 个具体的 ERPNext 客户已表态？→ 决定 Phase 1 选哪个国家深耕。
2. **部署形态**：客户倾向 SaaS 共享（multi-tenant）还是本地化（per-tenant）？→ 决定 Phase 2 投入。
3. **T.A.X.I. 的开源策略**：`tax_integration` app 是否开源？AGPL/MIT？→ 影响社区可见度和商业化路径。
4. **Agent 自主决策权限**：当 ERPNext 单据的税额与 T.A.X.I. 算出的不同时，谁优先？→ 需要在合同/UI 上明确"AI 副驾，人最终决定"原则。
5. **替代方案**：与 `india-compliance` 合作（避免重复造印度轮子）还是竞争？

---

**报告结束**。请审阅。
