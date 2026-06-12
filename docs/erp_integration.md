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
