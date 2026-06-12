# T.A.X.I. — ERP Integration v0 用户/开发者文档

> **状态**：v0 demo 可用
> **日期**：2026-06-10

## 概述

T.A.X.I. v0 的 ERP 集成层让用户从 Demo Case / CSV / 未来真连 ERPNext 拉取数据，
走 T.A.X.I. 6 阶段管线（其中 CALCULATE/VALIDATE 由 Agent 主导），最后
用户点 Submit 一键提交到 HMRC mock。

## 用户流程

1. **Dashboard 选 Case** → "🔍 帮我分析目前的财务数据" 一键按钮
2. **Agent 弹发票多选面板** → 勾选要分析的发票
3. **Agent 调 calculate_vat_return** → 在 chat 流展示 9-Box 差异表
4. **Agent 调 validate_vat_return** → 报告校验结果
5. **用户点 "Submit to HMRC"** → 法律声明勾选 → 提交
6. **Agent 显示 HMRC 回执卡片**

## 开发者文档

### 关键模块

| 模块 | 路径 | 职责 |
|---|---|---|
| 数据模型 | `tax_agent/models/erp_models.py` | Pydantic ImportResult 等 |
| CSV 解析 | `tax_agent/erp/csv_parser.py` | bytes → ImportResult |
| Profile | `tax_agent/erp/profiles.py` | GenericProfile (v0 唯一) |
| Reconcile | `tax_agent/erp/reconcile.py` | compare 9-Box, £0.50 tolerance |
| Sample loader | `tax_agent/erp/erp_samples_loader.py` | data/erp_samples/*.json |
| Audit | `tax_agent/erp/audit_events.py` | action 常量 |
| Router | `tax_agent/server/erp.py` | /api/erp/* |
| Orchestrator | `tax_agent/orchestrator.py::_stage_import` | 新阶段 |
| UK calc | `tax_agent/jurisdictions/uk/vat/calculator.py` | +reconcile mode |
| Agent tool | `tax_agent/jurisdictions/uk/vat/agent_tools.py` | +ingest_erp_data |

### 添加新 CSV Profile (v1)

1. `tax_agent/erp/profiles.py` 加新 class
2. `_PROFILES` dict 注册
3. 加 unit test

### 添加新 Demo Case

1. 构造 JSON 写 `data/erp_samples/<id>.json` (用 `ImportResult.model_dump()` schema)
2. 后端自动发现（`list_demo_cases()` 扫目录）

## 已知限制 (v0 显式不做)

- ❌ Sage / Xero / QBO 多 Profile — v1
- ❌ FRS / Cash / Annual / Margin scheme — v1
- ❌ 真 ERPNext 凭证 — v1
- ❌ 真 HMRC sandbox — 继续走 mock
- ❌ 多租户 — v1

## HMRC Production 注册清单 (v1 必做)

- [ ] 在 HMRC MTD Software Register 注册 T.A.X.I.
- [ ] 申请 sandbox user
- [ ] 6 年 audit retention 实现
- [ ] API key 加密存储
- [ ] 用户授权页面合规

---

## v1 Update (2026-06-12): Pull-Only Mode

T.A.X.I. v1 ERPNext 接入改为**手动 Pull 模式**:

- ❌ **ERPNext on_submit 自动 push 已关闭** (`frappe-bench/apps/tax_integration/tax_integration/hooks.py`)
- ✅ **用户从 T.A.X.I. Dashboard → Import Hub 手动拉取**(见 `docs/superpowers/specs/2026-06-12-erpnext-user-journey-design.md`)
- ✅ **ERPNext 端 Web Form 跳转**作为引导(右上角 "T.A.X.I. ↗")

## Why Pull-Only?

代账会计 / 财务经理**主动控制报税节奏**比"被动接收"更符合工作习惯。手动 Pull 让用户在"已收集完本季度所有发票、准备报税"时一次性拉取,避免 ERPNext 提交时数据零散涌入。

## 重新启用自动 Push

如需切换回 push 模式,取消 `hooks.py` 中 `doc_events` 注释并重启 bench。

## Web Form `taxi-link` 实装状态(2026-06-13)

通过 `frappe.get_doc({"doctype": "Web Form", ...}).insert()` 在 DB 写入,使用 `is_standard=0` 绕开 Frappe v15 的 `validate()` 检查(`is_standard=1` 需要 `developer_mode=1`,而 `developer_mode=0` 时新 Web Form 的 `self.reload()` 在 `validate` 钩子里会抛 `DoesNotExistError`)。

访问 `http://my.local:9001/taxi-link` → 301 → `/taxi-link/new` → 200 OK,X-Page-Name=`taxi-link/new`。显示 TAXI URL 字段 + 简介文字 + 提交按钮。

注意: 这个 Web Form `is_standard=0`,意味着它**不会**作为 fixture 在 `bench migrate` 时被自动重装(只有 `is_standard=1` 的会被 fixtures 机制导出/导入)。如果未来需要重装站点,要手动跑 8 行 Python 重新创建。

## 1-Click Auto-Login (2026-06-13)

**开启** `common_site_config.json` 加 `"developer_mode": 1` + `tax_integration` app 的 `www/welcome.py::login_as_admin` 端点(developer_mode-only)。

**用户流**:
1. 访问 `http://my.local:9001/` → 看到欢迎页
2. 点击"🚀 进入 ERPNext"按钮 → 后端 `LoginManager.login_as("Administrator")` 免密登录 → 302 → `/app` → 200 OK
3. 用户已经在 ERPNext Desk 内部

**验证**:
- `curl /api/method/tax_integration.www.welcome.login_as_admin` → 302 + `Set-Cookie: sid=...`
- 用 sid 访问 `/app` → HTTP 200, `X-Page-Name: app`
- `frappe.auth.get_logged_user` → `"Administrator"`

**安全 trade-off**:
- ✅ 优点: 1-click 进 desk,演示/开发零摩擦
- ❌ 风险: `developer_mode=1` 期间,**任何公网访问者**点 1 下都能以 Administrator 身份进 ERPNext
- 🔒 缓解: `developer_mode=0` 时端点主动抛 `PermissionError`;生产前要么关掉 `developer_mode`,要么删 `login_as_admin` 函数

**关闭方法**:
- 选项 A: `common_site_config.json` 设 `"developer_mode": 0` (端点拒绝访问,欢迎页自动退回 "🔐 登录" 按钮)
- 选项 B: 直接删除 `tax_integration/www/welcome.py` 中的 `login_as_admin` 函数
