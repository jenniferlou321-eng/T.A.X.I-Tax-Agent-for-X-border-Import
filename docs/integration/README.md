# TAXI 集成扩展路线图（2026-06-14 调研输出）

> **基于**: PayPal Sandbox、报税提醒、电商平台接入三项调研
> **关联**: `JIAHANG_TAX_ROADMAP.md`, `docs/erp_integration.md`

## 调研完成项

| # | 调研主题 | 输出文档 | 状态 |
|---|---------|---------|------|
| 1 | PayPal Sandbox 集成 | `docs/integration/paypal-sandbox.md` | ✅ |
| 2 | 多国报税提醒系统 | `docs/integration/tax-filing-reminders.md` | ✅ |
| 3 | 电商平台数据接入 | `docs/integration/ecommerce-integration.md` | ✅ |

---

## 核心发现

### 1. PayPal Sandbox

PayPal 有完善的官方 Sandbox，开发者可零成本创建测试账号并调用全套 REST API。

**对 TAXI 最有价值的能力**：
- `GET /v1/reporting/transactions` — 拉取历史交易（收款/退款），按日期范围查询
- OAuth2 Client Credentials 认证（可复用现有 `OAuth2Manager`）
- 交易事件代码（T0001=收款, T1107=退款, T1201=争议）可用于自动分类

**关键演示场景**：
> Agent 拉取 PayPal 收款 → 与 Shopify 销售数据比对 → 差异报告 → 确认无误后报税

**缺失架构组件**：
- `PaymentChannel` ABC（与现有 `FilingChannel` 平行）
- `PaymentTransaction` 数据模型
- 三方对账引擎（PayPal vs Shopify vs ERP）

### 2. 报税提醒功能

跨境企业每年需要管理 20-40 个不同的报税截止日。仅嘉汉案例（UK+CN）就有 60+ 个时间节点。

**各国关键差异**：

| 国家 | VAT/GST 频率 | CIT 频率 | 特色规则 |
|------|-------------|---------|----------|
| UK | 季度（次月7日） | 年度（12个月后） | PAYE 每次发薪即报 |
| DE | 月度/季度（次月10日） | 年度（7个月后） | 年税额<€7,500可季度报 |
| FR | 月度/季度/年度 | 年度+季度预缴 | 按年税额分档决定频率 |
| CN | 月度/季度（次月15日） | 季度预缴+年度汇算（5次/年） | 附加税与VAT同期 |
| SG | 季度（次月结束1个月） | 年度ECI+Form C | ECI 3个月,Form C 11月 |

**竞争分析**：Avalara 在多国提醒方面做得最好（50+国家税务日历 + SMS + Email），Xero/QuickBooks 次之。TAXI 的差异化优势：与 Agent 深度集成（截止日自动触发申报流程）。

**核心设计**：
- `DeadlineRule` 数据模型（内置规则：`offset_months + day_of_month`）
- `DeadlineScheduler`（APScheduler 每日检查）
- `NotificationService`（Email + In-App + SMS 三通道）
- 前端 `DeadlineCalendar.tsx` + 角标

### 3. 电商平台数据接入

Shopify 是接入优先级最高的电商平台（API 最成熟、文档最好、沙盒完善）。

**Shopify 关键发现**：
- **不存在 "SessionStart" hook** — 这可能是第三方 ERP 桥接工具的配置概念，非 Shopify 原生
- 正确的数据接入方式：
  - **实时**：Webhooks（`orders/create`, `refunds/create`）
  - **批量**：GraphQL Bulk Operation（月度对账）
  - **按需**：GraphQL Admin API 查询（Agent 触发）
- Shopify 订单字段可直接映射到 UK VAT 9-Box
- 多币种支持（`shopMoney` vs `presentmentMoney`）

**电商平台接入优先级**：Shopify (P0) > WooCommerce (P1) > Amazon SP-API (P1) > eBay (P2)

---

## 对 CLAUDE.md 的建议更新

建议在 CLAUDE.md 中新增以下内容：

### Repo Layout 新增
```
├── backend/channels/ecommerce/       ← 电商平台渠道
│   ├── __init__.py                   ← EcommerceChannel ABC
│   └── shopify.py                    ← ShopifyChannel (GraphQL)
├── backend/channels/payment/         ← 支付网关渠道
│   ├── __init__.py                   ← PaymentChannel ABC
│   └── paypal.py                     ← PayPalChannel
├── backend/services/
│   ├── deadline_calculator.py        ← 截止日计算引擎
│   ├── deadline_scheduler.py         ← 提醒调度器
│   ├── notification.py               ← 多渠道通知
│   └── calendar_export.py            ← .ics 导出
├── backend/models/
│   ├── deadline.py                   ← 截止日/提醒模型
│   └── ecommerce.py                  ← 电商订单模型
├── backend/routers/
│   ├── deadlines.py                  ← /api/deadlines/*
│   └── webhooks.py                   ← /api/webhooks/*
```

### Common Tasks 新增
| Task | File |
|---|---|
| 接入新电商平台 | `backend/channels/ecommerce/{platform}.py` + 实现 `EcommerceChannel` ABC |
| 接入新支付网关 | `backend/channels/payment/{gateway}.py` + 实现 `PaymentChannel` ABC |
| 添加新国家报税规则 | `backend/services/deadline_calculator.py` + `DEADLINE_RULES` dict |
| 配置提醒策略 | `backend/models/deadline.py` → `ReminderConfig` |
| 处理电商 Webhook | `backend/routers/webhooks.py` |

### 新增文档索引
| 主题 | 链接 |
|---|---|
| PayPal Sandbox 集成 | `docs/integration/paypal-sandbox.md` |
| 报税提醒系统设计 | `docs/integration/tax-filing-reminders.md` |
| 电商平台数据接入 | `docs/integration/ecommerce-integration.md` |

---

## 建议实施顺序

基于 TAXI 当前能力和嘉汉案例需求，建议按以下优先级推进：

### Sprint 1 (本周) — 基础设施
1. `EcommerceChannel` ABC + `EcommerceOrder` 数据模型
2. `PaymentChannel` ABC + `PaymentTransaction` 数据模型
3. `DeadlineRule` + `FilingDeadline` 数据模型

### Sprint 2 (下周) — 渠道实现
4. `ShopifyChannel` (GraphQL orders query)
5. `PayPalChannel` (Transactions API)
6. `DeadlineCalculator` (内置 5 国规则)

### Sprint 3 (两周后) — 对账与提醒
7. 三方对账引擎 (Shopify vs PayPal vs ERP)
8. `DeadlineScheduler` + Email 通知
9. 前端 `DeadlineCalendar` 组件

### Sprint 4 (一月后) — 完善
10. Shopify Webhook 接收
11. SMS 提醒 + .ics 导出
12. Amazon SP-API / WooCommerce adapter
