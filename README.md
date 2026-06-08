# T.A.X.I.

## **T**ax **A**gent for **X**-border & **I**mport

> **多国税务，一键叫车** — Your AI Copilot for Cross-Border Tax Filing, on Autopilot.

[![License: MIT](https://img.shields.io/badge/License-MIT-success.svg)](LICENSE)
[![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%2B%20Python%203.10-blue)](tax_agent/)
[![Frontend: React 19](https://img.shields.io/badge/Frontend-React%2019%20%2B%20TypeScript-blue)](tax_agent/frontend/)
[![Agent: claude-agent-sdk](https://img.shields.io/badge/LLM-claude--agent--sdk-orange)](tax_agent/agent/)

---

## 🌍 这是什么

**T.A.X.I.** 是一个面向**跨境中资企业**的多国家 AI 报税平台。

它把两件事做到无缝衔接：

| 你想怎么用 | T.A.X.I. 怎么响应 |
|---|---|
| 💬 **聊天探索**：跟 AI 助手说"帮我看一下 Q1 该报多少税" | 对话式触发，AI 自动调工具算给你看 |
| 📋 **正式申报**：填表单 → 预览 → 提交 | 走 6 阶段管线，端到端打到 HMRC |

**底层共用同一条管线**——聊天和表单不是两个产品，是同一个产品的两个入口。

**Copilot 哲学**：AI 是你的副驾，**最终决定权在你**——报税必须人确认提交，AI 不替你在法律意义上"按下按钮"。

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

## 🏗️ 仓库结构

```
T.A.X.I. 仓库根
│
├── README.md                  ← 你正在读的产品概览
├── LICENSE                    ← MIT
├── CLAUDE.md                  ← 开发者指南（指向 tax_agent/CLAUDE.md）
├── .gitignore                 ← 全面排除：构建产物 / 凭证 / 缓存
│
├── tax_agent/                 ← ⭐ 核心项目（后端 + 前端 + 文档）
│   ├── README.md              ← 产品级 README（详细功能介绍）
│   ├── CLAUDE.md              ← 项目级开发文档（架构、模块、命令）
│   ├── agent/                 ← LLM 引擎 + MCP 工具工厂
│   ├── server/                ← FastAPI 路由
│   ├── jurisdictions/         ← 各国适配器
│   ├── channels/              ← 提交渠道（OAuth + API）
│   ├── services/              ← 状态机 + 审计日志
│   ├── orchestrator.py        ← 6 阶段管线
│   ├── frontend/              ← React 19 + Vite
│   ├── docs/                  ← 架构 + 各国流程文档
│   ├── data/                  ← 示例企业数据（脱敏）
│   ├── tests/  scripts/  models/
│   ├── start_backend.sh       ← 后端启动脚本
│   ├── run_backend.py         ← 启动 wrapper
│   └── vat_return_payload.json← 示例申报 payload
│
└── design-system/             ← 设计系统 spec（颜色、字体、间距）
    └── taxagent-global/
        └── MASTER.md
```

> 完整技术细节、模块说明、命令清单 → 见 **[`tax_agent/CLAUDE.md`](tax_agent/CLAUDE.md)**

---

## 🚀 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/GTC2333/T.A.X.I-Tax-Agent-for-X-border-Import.git
cd T.A.X.I-Tax-Agent-for-X-border-Import

# 2. 后端（conda 环境 taxagent，Python ≥ 3.10）
cd tax_agent
pip install -e ".[server,dev]"
./start_backend.sh        # 端口 8765
# 或:  python run_backend.py

# 3. 前端（新终端）
cd tax_agent/frontend
npm install
npm run dev               # 端口 5173

# 4. 打开浏览器
open http://localhost:5173
```

API 文档：<http://localhost:8765/docs>

### 一键体验
打开 <http://localhost:5173> → 选 "VAT 申报" 案例卡片 → 预填好一家英国公司 → 一键提交到 HMRC 沙盒。

---

## 🧭 6 阶段管线

```
PRECHECK  →  PREPARE  →  CALCULATE  →  VALIDATE  →  SUBMIT  →  TRACK
   │            │            │             │            │          │
 模板校验    OAuth认证     计算9-Box     合规检查    POST到税局   轮询状态
   ↓            ↓            ↓             ↓            ↓          ↓
   FilingResult 状态机：PENDING → IN_PROGRESS → SUBMITTED → ACCEPTED/REJECTED
```

详细：[`tax_agent/docs/architecture/pipeline.md`](tax_agent/docs/architecture/pipeline.md)

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

[MIT](LICENSE) © 2026

---

<p align="center">
  <b>T.A.X.I.</b> — Cross-Border Tax, on Autopilot. ✈️
</p>
