# T.A.X.I.

## **T**ax **A**gent for **X**-border & **I**mport

> **多国税务，一键叫车** — Your AI Copilot for Cross-Border Tax Filing, on Autopilot.

[![Status](https://img.shields.io/badge/UK%20VAT-Live-success)](#)
[![Stack](https://img.shields.io/badge/Backend-FastAPI%20%2B%20Python%203.10-blue)](#)
[![Stack](https://img.shields.io/badge/Frontend-React%2019%20%2B%20TypeScript-blue)](#)
[![Stack](https://img.shields.io/badge/LLM-claude--agent--sdk-orange)](#)

---

## 🌍 这是什么

**T.A.X.I.** 是一个面向**跨境中资企业**的多国家 AI 报税平台。

它把两件事做到无缝衔接：

| 你想怎么用 | T.A.X.I. 怎么响应 |
|---|---|
| 💬 **聊天探索**：跟 AI 助手说"帮我看一下 Q1 该报多少税" | 对话式触发，AI 自动调工具算给你看 |
| 📋 **正式申报**：填表单 → 预览 → 提交 | 走 6 阶段管线，端到端打到 HMRC |

**底层共用同一条管线**——聊天和表单不是两个产品，是同一个产品的两个入口。

---

## ✨ 四大核心能力

### 1. 🧑‍💼 AI 智能体对话
自然语言触发报税全流程，无需记命令、无需点菜单。
- 多会话管理 + 历史回放
- **演示模式**：没配 LLM API key 也能完整体验（Mock 引擎）

### 2. 🛠️ Skills 工具集（MCP 协议）
每个国家/税种有**独立工具集**，LLM 通过命名空间自动发现。
- 新增国家 = 实现 6 个 async 方法 + 注册一下
- 工具调用全部走标准 MCP 信封

### 3. 🇬🇧 英国 VAT 全自动申报
对接 **HMRC Making Tax Digital** API（OAuth 2.0 + 反欺诈头自动注入）：
- 9-Box VAT Return 自动计算与合规校验
- 失败自动重试 + 状态机管理
- 完整审计日志（前端可视化）

### 4. 🌍 多国家路线图
- ✅ **UK VAT** — 端到端可用（含沙盒验证）
- 🟡 **UK SA / CT / PAYE / SDLT** — 工具集已注册，部分待补
- 📋 **DE / FR / CN** — 架构预留

---

## 🏗️ 三层插件架构

```
┌──────────────────────────────┐
│  Frontend  (React 19 + Vite) │   ← 聊天 / 表单 / 详情
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│  FastAPI Backend             │
│                              │
│  Agent  →  Skills (MCP)      │   ← LLM 调工具
│  Orchestrator (6 stages)     │   ← PRECHECK → TRACK
│  Registry → Adapter → Channel│   ← 多国插件
└──────────────┬───────────────┘
               │
       ┌───────▼───────┐
       │ HMRC MTD API  │   ← 当前唯一已对接
       └───────────────┘
```

> **新增一个国家** = 实现一个 `JurisdictionAdapter` + `AgentToolSet` 子类 + 注册。**无需修改 LLM 或管线**。

---

## 🚀 快速开始

### 后端

```bash
conda activate taxagent   # Python ≥ 3.10
cd tax_agent
pip install -e ".[server,dev]"
./start_backend.sh        # 端口 8765
# 或:  python run_backend.py
```

API 文档：<http://localhost:8765/docs>

### 前端

```bash
cd tax_agent/frontend
npm install
npm run dev               # 端口 5173
```

### 一键体验

打开 <http://localhost:5173> → 选 "VAT 申报" 案例卡片 → 预填好一家英国公司 → 一键提交到 HMRC 沙盒。

---

## 🧭 6 阶段管线

```
PRECHECK  →  PREPARE  →  CALCULATE  →  VALIDATE  →  SUBMIT  →  TRACK
   模板校验     OAuth认证     计算9-Box      合规检查     POST到税局     轮询状态
   ↓            ↓            ↓             ↓            ↓            ↓
   FilingResult 状态机：PENDING → IN_PROGRESS → SUBMITTED → ACCEPTED/REJECTED
   每阶段记录审计日志，状态机管控合法转换
```

详细：[`docs/architecture/pipeline.md`](docs/architecture/pipeline.md)

---

## 📁 项目结构

```
tax_agent/
├── agent/                  # LLM 引擎 + 工具注册 + 业务分析器
│   ├── engine.py           # TaxAgentEngine（SDK + Mock 双模式）
│   ├── tools.py            # MCP Server 工厂
│   ├── prompts.py          # 按 jurisdiction 加载法规知识
│   ├── business_analyzer.py# 原始企业发票 → 9-Box
│   └── session_store.py    # SDK 会话历史读取
├── server/                 # FastAPI
│   ├── main.py             # 入口
│   └── routers/            # jurisdictions / filings / channel / users / agent
├── jurisdictions/          # 各国适配器
│   └── uk/
│       └── vat/            # UK VAT 完整实现（含 AgentToolSet）
├── channels/               # 提交渠道
│   ├── api_channel.py      # REST API 通用渠道
│   ├── oauth.py            # OAuth 2.0 管理
│   └── fraud_headers.py    # HMRC 反欺诈头
├── services/               # 横切服务
│   ├── state_machine.py    # FilingStatus 状态机
│   └── audit_log.py        # 审计日志
├── orchestrator.py         # 6 阶段管线编排器
├── models/                 # Pydantic 数据模型
├── frontend/               # React 19 + TS + Vite
├── docs/                   # 架构与各国流程文档
└── data/                   # 示例企业数据（脱敏）
```

---

## 📚 文档索引

| 主题 | 链接 |
|---|---|
| 系统架构总览 | [`docs/architecture/overview.md`](docs/architecture/overview.md) |
| 6 阶段管线详解 | [`docs/architecture/pipeline.md`](docs/architecture/pipeline.md) |
| 扩展新国家指南 | [`docs/architecture/adding-new-jurisdiction.md`](docs/architecture/adding-new-jurisdiction.md) |
| UK VAT 报税流程 | [`docs/jurisdictions/uk/vat-workflow.md`](docs/jurisdictions/uk/vat-workflow.md) |
| UK VAT 9-Box 规则 | [`docs/jurisdictions/uk/vat-rules.md`](docs/jurisdictions/uk/vat-rules.md) |
| HMRC OAuth 2.0 | [`docs/jurisdictions/uk/oauth.md`](docs/jurisdictions/uk/oauth.md) |
| HMRC 沙盒测试 | [`docs/jurisdictions/uk/sandbox-testing.md`](docs/jurisdictions/uk/sandbox-testing.md) |

---

## 🛣️ 路线图

- [x] UK VAT 端到端
- [x] 多国家插件架构
- [x] AI Copilot 对话式触发
- [ ] UK SA / CT / PAYE / SDLT 工具集补齐
- [ ] 德国 VAT（BZSt）
- [ ] 法国 VAT（DGFiP）
- [ ] 中国 增值税/企所税（电子税务局浏览器自动化）
- [ ] 多用户 + 权限隔离
- [ ] 完整 E2E 测试套件

---

## 📜 License

MIT

---

<p align="center">
  <b>T.A.X.I.</b> — Cross-Border Tax, on Autopilot. ✈️
</p>
