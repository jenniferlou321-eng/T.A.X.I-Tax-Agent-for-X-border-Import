# T.A.X.I.

## **T**ax **A**gent for **X**-border & **I**mport

> **多国税务，一键叫车** — Your AI Copilot for Cross-Border Tax Filing, on Autopilot.

[![License: MIT](https://img.shields.io/badge/License-MIT-success.svg)](LICENSE)
[![Python: ≥3.10](https://img.shields.io/badge/Python-≥3.10-blue)](pyproject.toml)
[![Node: ≥18](https://img.shields.io/badge/Node-≥18-green)](frontend/package.json)
[![Backend: FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%2B%20Pydantic%20v2-blue)](backend/)
[![Frontend: React 18 + Vite 4](https://img.shields.io/badge/Frontend-React%2018%20%2B%20Vite%204-blue)](frontend/)
[![Agent: claude-agent-sdk](https://img.shields.io/badge/LLM-claude--agent--sdk-orange)](backend/agent/)

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

## 🏗️ 三层插件架构

```
┌──────────────────────────────┐
│  Frontend  (React 19 + Vite) │   ← 聊天 / 表单 / 详情
└──────────────┬───────────────┘
               │
┌──────────────▼───────────────┐
│  FastAPI Backend (backend/)  │
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

## 📁 仓库结构

```
/root/TAXI/                    ← 仓库根 = 项目根
│
├── README.md                  ← 你正在读的产品概览
├── CLAUDE.md                  ← 开发者指南（架构、模块、命令）
├── LICENSE                    ← MIT
├── .gitignore                 ← 全面排除：构建产物 / 凭证 / 缓存
│
├── pyproject.toml / setup.py / setup.cfg
├── run_backend.py             ← 启动 wrapper（target: backend.main:app）
├── start_backend.sh           ← 后端启动脚本
├── vat_return_payload.json    ← 示例申报 payload
│
├── backend/                   ← ⭐ 全部后端 Python 代码
│   ├── main.py                ← FastAPI 入口
│   ├── orchestrator.py        ← 6 阶段管线
│   ├── registry.py / config.py
│   ├── agent/                 ← LLM 引擎 + 工具注册 + 业务分析器
│   │   ├── engine.py          # TaxAgentEngine（SDK + Mock 双模式）
│   │   ├── tools.py           # MCP Server 工厂
│   │   ├── prompts.py         # 按 jurisdiction 加载法规知识
│   │   ├── business_analyzer.py# 原始企业发票 → 9-Box
│   │   └── session_store.py   # SDK 会话历史读取
│   ├── routers/               ← jurisdictions / filings / channel / users / agent
│   ├── erp_router.py          ← ERP /erp 路由
│   ├── jurisdictions/         ← 各国适配器 (uk/vat ...)
│   ├── channels/              ← 提交渠道（OAuth + API）
│   ├── erp/                   ← CSV 解析 / 对账 / 样本加载
│   ├── services/              ← 状态机 + 审计日志
│   └── models/                ← Pydantic 数据模型
│
├── frontend/                  ← React 19 + Vite
├── data/                      ← 示例企业数据（脱敏）· erp_samples/
├── docs/                      ← 架构 + 各国流程文档
├── scripts/  tests/
│
└── design-system/             ← 设计系统 spec（颜色、字体、间距）
    └── taxagent-global/
        └── MASTER.md
```

> 完整技术细节、模块说明、命令清单 → 见 **[`CLAUDE.md`](CLAUDE.md)**

---

## 🚀 快速开始

> 端口约定：后端 **8765**，前端 **9000**。生产模式下前端由
> `scripts/serve_frontend_9000.sh` 提供（带 SPA fallback），开发模式由
> Vite dev server 提供（自带 `/api` 代理到 8765）。
>
> 完整端口 / 反向代理 / 公网暴露细节见 [`docs/deployment/port-9000.md`](docs/deployment/port-9000.md)。

### 0. 前置环境

| 工具 | 最低版本 | 备注 |
|---|---|---|
| Python | **3.10+**（仓库已在 3.11.x 验证） | 后端用 Pydantic v2 + 结构化匹配 |
| Node.js | **18+**（推荐 20 LTS）| Vite 5 / Tailwind v4 需要 20+；旧机器用 16 + `npm run build`（无样式）也跑得通 |
| npm | 9+ | 随 Node 一起装 |
| conda（可选） | 最新 | 用 `environment.yml` 一键建环境 |

### 1. 克隆仓库

```bash
git clone https://github.com/GTC2333/T.A.X.I-Tax-Agent-for-X-border-Import.git
cd T.A.X.I-Tax-Agent-for-X-border-Import
```

### 2. 后端 — 任选一种方式

仓库根目录下提供三种等价的安装方式，挑你顺手的：

**方式 A — Conda（推荐，CentOS 7 / glibc 2.17 主机唯一可行）**

```bash
# 一次性：装 Miniconda (4.10.3 兼容 glibc 2.17)
curl -sSLO https://repo.anaconda.com/miniconda/Miniconda3-py39_4.10.3-Linux-x86_64.sh
bash Miniconda3-py39_4.10.3-Linux-x86_64.sh -b -p $HOME/miniconda3
$HOME/miniconda3/bin/conda env create -f environment.yml   # 建 taxagent env

# 让 .venv 指向 conda env (一次性)
ln -s $HOME/miniconda3/envs/taxagent .venv

# 日常
./start_backend.sh                     # 自动 activate taxagent
```

**方式 B — pip + venv（系统已装 Python 3.10+ 时）**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
./start_backend.sh                     # 端口 8765
```

**方式 C — `uv`（最快，自动管理 Python 版本）**

```bash
uv venv .venv --python 3.11
uv pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python run_backend.py        # 端口 8765
```

> 💡 `start_backend.sh` 会先自动 `conda activate taxagent`（自动探测
> `$HOME/miniconda3` / `/opt/miniconda3` / `$CONDA_BASE`），再尝试走当前
> `python`；如果都用不了，兜底调用 `run_backend.py` 把仓库根塞进
> `sys.path` 再启动 uvicorn。Linux/macOS 通用。

### 3. 前端 — 任选一种方式

**开发模式（HMR + 代理 /api → 8765）**

```bash
cd frontend
npm install                # 装前端依赖
npm run dev                # http://localhost:9000
```

Vite dev server 自己把 `/api`、`/docs`、`/openapi.json`、`/health` 转发到
`127.0.0.1:8765`，WebSocket 握手也走同一条通道（`ws: true`），前端代码默认
走 **same-origin `/api`**，无需任何环境变量。

**生产模式（构建 dist/ + 静态服务）**

```bash
# 一次性：建前端 conda env (Node 20 conda-forge build, 兼容 glibc 2.17)
$HOME/miniconda3/bin/conda create -n fe-build -y -c conda-forge nodejs=20

# 日常：重建 dist/
./start_frontend_build.sh            # 自动 activate fe-build + npm run build
cd ..
./scripts/serve_frontend_9000.sh    # http://localhost:9000
# 端口可通过 PORT=9100 ./scripts/serve_frontend_9000.sh 改
```

`serve_frontend_9000.py` 是纯 Python 标准库的静态服务器，自带 SPA fallback
（任意非资源路径 404 → 退到 `/index.html`），无需 nginx/caddy。

> 📦 `frontend/dist/` 不入 git（`.gitignore` 排除）。换机器部署时需要
> 重新构建 —— 见下方 *FAQ / Node glibc 2.17* 那条。

### 4. 打开浏览器

- 前端：<http://localhost:9000>
- 后端 OpenAPI：<http://localhost:8765/docs>
- 健康检查：<http://localhost:8765/health>

### 一键体验

打开 <http://localhost:9000> → 选 "VAT 申报" 案例卡片 → 预填好一家英国公司 → 一键提交到 HMRC 沙盒。
没配 LLM API key 也能完整体验：聊天走 Mock 引擎，VAT 走 HMRC mock 模式（`HMRC_MODE` 默认 `mock`）。

---

## ❓ 常见问题（FAQ）

### Q1. 启动后端报 `ModuleNotFoundError: No module named 'backend'`

`start_backend.sh` 会自动 `cd` 到仓库根，但如果你手动跑 `uvicorn` 时所在的
工作目录不对就会触发。两个修法：

```bash
# 修法 1：使用仓库自带的启动脚本
./start_backend.sh

# 修法 2：显式把仓库根塞到 PYTHONPATH
PYTHONPATH=$(pwd) python -m uvicorn backend.main:app --port 8765
```

### Q2. `npm run dev` 报 `GLIBC_2.27 / GLIBC_2.28 not found`

宿主机 glibc 太旧（典型如 CentOS 7.x / glibc 2.17）跑不动 Node 18+。
**千万别原地升级系统 glibc**——会把整台机器搞坏，连 ssh 都进不去。
推荐三选一（按工作量从小到大）：

1. **`nvm install 16` + `npm run build:dev`**：用 glibc 2.17 兼容的 Node 16
   跑 Vite 4。代价：不能升 Vite 5 / Tailwind v4，但功能完整。
2. **Docker**：在任意带 glibc 2.28+ 的镜像里 `npm run build`，把
   `frontend/dist/` 拷回来用 `serve_frontend_9000.sh` 跑。
3. **换系统**：迁到 Rocky / Alma 8/9（glibc 2.28/2.34）一劳永逸。

### Q3. 改完代码前端没刷新 / 接口 404

- **开发模式**（`npm run dev`）：HMR 是热的，`.tsx` / `.ts` 改动秒级生效；
  `vite.config.ts` 改了需要重启 dev server。
- **生产模式**（`serve_frontend_9000.sh`）：静态文件无缓存策略，需要重新
  `npm run build` 再启动脚本。`index.html` 自带 `Cache-Control: no-cache`，
  但 `assets/*` 默认按 hash 名缓存。
- **接口 404**：检查后端是否真的在 8765（`curl http://localhost:8765/health`），
  代理规则在 `frontend/vite.config.ts` 顶部注释里。

### Q4. Pydantic v1 vs v2 —— `model_dump` / `dict` 不兼容

仓库代码默认 **Pydantic v2**（`pyproject.toml` 锁 `pydantic>=2.0`）。如果
本地装到了 v1，运行时会报 `'Model' object has no attribute 'model_dump'`。
修法：

```bash
pip install -U "pydantic>=2.0"
# 或用 conda 重建环境
conda env remove -n taxagent && conda env create -f environment.yml
```

> 部署侧如果用 musl-Python 跑在老镜像里、又不想升级，临时 fallback 在
> `pyproject.toml` 里加 `pydantic>=1.10` 即可（但**不推荐**——后续代码
> 不会再写 v1 兼容 shim）。

### Q5. HMRC API 调用 401 / 403

- **沙盒**：`HMRC_MODE=mock`（默认）走 mock 响应，不打真实网络。
- **真实环境**：需要先把 OAuth token 缓存到 `./.tokens/{vrn}.json`——
  用 `scripts/hmrc_oauth_full.py` 跑一次人工授权流；token 自动续期。
- **`FraudPreventionHeaders` 缺失**：沙盒不强制，生产必须有，否则 HMRC
  直接拒。

### Q6. 前端打包后样式丢了 / 页面"裸奔"

Tailwind v4 的 `@tailwindcss/vite` 插件要求 **Node 20+**。仓库
`vite.config.build.ts` 默认禁用该插件以兼容 Node 16 的旧机器，代价是
`dist/` 里没有编译后的 CSS。

修法（任选）：

- **新机器 + Node 20+**：用 `vite.config.ts` 跑 `npm run build`（带
  tailwindcss 插件），或把 `vite.config.build.ts` 里 `plugins: [react()]`
  改成 `plugins: [react(), tailwindcss()]` 再 `npm run build`。
- **继续用 Node 16**：维持 `vite.config.build.ts` 不变，UI 文字 / 交互
  / 路由全能用，只是没有设计系统样式。

### Q7. 杀掉后台进程被沙箱拦下 / `kill` 报 blocked

开发主机上的 Claude Code 沙箱会拒绝 `kill 8765` 之类带端口的命令。绕过：

```bash
# 1. 找到 PID
lsof -i:8765
# 2. 用 PID 而不是端口号
kill <PID>
# 3. 实在不行就分两次跑（一次只能杀一个）
pkill -f "uvicorn backend.main:app"
```

### Q8. `.tokens/` 里的 OAuth token 不小心 commit 了

立刻 rotate：

1. 在 HMRC Developer Hub 撤销该 token 的 client secret。
2. `git rm --cached .tokens/*` 然后提交。
3. 确认 `.gitignore` 里有 `.tokens/`（仓库已经默认排除）。

> **永远不要**把 `.env`、`.env.testuser`、`.tokens/` 提交进 git。仓库
> 默认就排除，但如果你 fork 后改了 `.gitignore` 就要重新检查。

---

## 🛠️ 开发指南

### 项目结构（再读一遍）

```
/root/TAXI/                          ← 仓库根 = 项目根
├── README.md                        ← 产品概览 + FAQ + Dev Guide
├── CLAUDE.md                        ← 给 Claude Code 看的开发者备忘
├── LICENSE                          ← MIT
├── requirements.txt                 ← pip 运行时依赖（与 pyproject 同步）
├── requirements-dev.txt             ← pip 测试/lint 依赖
├── environment.yml                  ← conda 环境定义
├── pyproject.toml / setup.py / setup.cfg
├── run_backend.py                   ← 路径无关的 uvicorn 启动器
├── start_backend.sh                 ← 后端启动脚本（自动 activate conda）
├── vat_return_payload.json
│
├── backend/                         ← 全部后端 Python 代码
│   ├── main.py                      ← FastAPI app factory
│   ├── orchestrator.py              ← 6 阶段管线
│   ├── registry.py / config.py
│   ├── agent/                       ← LLM 引擎 + MCP 工具 + 业务分析器
│   ├── routers/                     ← jurisdictions / filings / channel / users / agent
│   ├── erp_router.py                ← /api/erp/* 路由
│   ├── jurisdictions/               ← 各国适配器 (uk / testland)
│   ├── channels/                    ← 提交渠道 (OAuth + API)
│   ├── erp/                         ← CSV 解析 / 对账 / 样本加载
│   ├── services/                    ← 状态机 + 审计日志
│   └── models/                      ← Pydantic 域模型
│
├── frontend/                        ← React 18 + Vite 4
│   ├── src/                         ← 页面 / 组件 / API client
│   ├── vite.config.ts               ← dev server（带 /api 代理）
│   └── vite.config.build.ts         ← 生产 build（Node 16 兼容）
│
├── data/                            ← 脱敏样本 · erp_samples/
├── docs/                            ← 架构 / 部署 / 各国流程
├── scripts/                         ← 独立可执行脚本 + 9000 端口静态服务
└── tests/                           ← pytest
```

### 本地环境准备

1. **克隆 + 装依赖** — 见上文 [快速开始](#-快速开始)。
2. **`.env` 文件**（可选）—— 后端启动器会自己加载：
   ```bash
   # .env 范例（仓库已 gitignore，请勿提交）
   ANTHROPIC_API_KEY=sk-ant-...
   ANTHROPIC_BASE_URL=https://api.anthropic.com
   ANTHROPIC_MODEL=claude-opus-4-8
   HMRC_MODE=mock
   CORS_ORIGINS=
   ```
   不配 API key 也能跑：Agent 走 Mock 引擎，HMRC 走 mock 模式。
3. **IDE 建议** — VSCode + Python + Pylance（`pydantic` 智能提示）+ ESLint
   + Prettier（前端）。`backend/` 是 `from backend.X import ...` 单一 import
   根，Pylance 别把 `backend` 标红即可。

### 运行测试

```bash
# 从仓库根跑
pytest                                     # 全部
pytest tests/path/to/test_file.py          # 单文件
pytest -k test_calculate_vat               # 按关键字
pytest --co                                # 只列出，不跑
```

测试覆盖：orchestrator 端到端（import → submit）、HMRC API（`pytest-httpx`
mock）、Agent chat MCP tools、ERP 对账容差（£0.50）。

### Lint

```bash
ruff check .                               # 全量
ruff check backend/orchestrator.py         # 单文件
ruff check --fix .                         # 自动修
```

CI 友好：纯命令行，无 IDE 依赖，1 秒内跑完。

### 调试技巧

- **后端热重载**：`UVICORN_RELOAD=1 ./start_backend.sh`（`start_backend.sh`
  检测到就加 `--reload`）。
- **API 探索**：浏览器打开 <http://localhost:8765/docs>（Swagger UI），所有
  endpoint 可直接试。
- **Agent 会话历史**：跑过的 session 存到 SDK 的 JSONL 文件，
  `GET /api/agent/sessions` 列出来。
- **审计日志**：`backend/services/audit_log.py` 写文件，前端有可视化页
  （`/filings/:id`）。
- **WebSocket 调试**：`wscat -c ws://localhost:8765/api/agent/ws/chat`
  手动发消息。

### 添加新税种 / 新国家

| 任务 | 路径 | 关键文件 |
|---|---|---|
| 新国家 | `backend/jurisdictions/{cc}/__init__.py` | 继承 `JurisdictionAdapter` |
| 新税种 | `backend/jurisdictions/{cc}/{tax_type}/` | 继承 `TaxTypeAdapter` |
| 注册 | `backend/main.py` | `registry.register(NewAdapter())` |
| MCP 工具 | `backend/agent/tools.py` | 实现 `AgentToolSet` 子类 |
| 前端页 | `frontend/src/pages/` + `App.tsx` | 加路由 |

详细：[`docs/architecture/adding-new-jurisdiction.md`](docs/architecture/adding-new-jurisdiction.md) /
[`docs/architecture/pipeline.md`](docs/architecture/pipeline.md)。

### 提交规范

仓库用的是简化版约定式 commit，PR 描述参考最近的几个 commit。

```bash
git commit -m "feat(uk-vat): support EC sales list"        # 新功能
git commit -m "fix(orchestrator): null guard on receipt"    # 修 bug
git commit -m "refactor(erp): dedupe nine-box computation"  # 重构
git commit -m "docs: FAQ + dev guide"                      # 文档
```

提交后跑一次 `pytest` + `ruff check .` 再推。

### Copilot 哲学（再强调一次）

AI 是副驾，**最终决定权在人**——报税必须由人确认提交，AI 不替你在法律
意义上"按下按钮"。这条原则在设计 agent 工具、UI 流程、agent 提示词时
都要尊重。

---

## 🧭 6 阶段管线

```
PRECHECK  →  PREPARE  →  CALCULATE  →  VALIDATE  →  SUBMIT  →  TRACK
   │            │            │             │            │          │
 模板校验    OAuth认证     计算9-Box     合规检查    POST到税局   轮询状态
   ↓            ↓            ↓             ↓            ↓          ↓
   FilingResult 状态机：PENDING → IN_PROGRESS → SUBMITTED → ACCEPTED/REJECTED
```

详细：[`docs/architecture/pipeline.md`](docs/architecture/pipeline.md)

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
| 前端 9000 端口部署 | [`docs/deployment/port-9000.md`](docs/deployment/port-9000.md) |

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
