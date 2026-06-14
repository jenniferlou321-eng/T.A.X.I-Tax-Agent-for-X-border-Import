# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# T.A.X.I. — Tax Agent for X-border & Import

> **多国税务，一键叫车** — Your AI Copilot for Cross-Border Tax Filing, on Autopilot.

This is the **single** developer guide for the repo. For the product pitch, see [`README.md`](./README.md). All backend Python code lives in the `backend/` package at the repo root; resources (`data/`, `docs/`, `scripts/`, `tests/`, `frontend/`) sit at the root.

---

## What This Project Is

**T.A.X.I.** is a multi-country automated tax filing platform. It couples:
- A **chat-style AI agent** (using `claude-agent-sdk`) that can trigger filing workflows via natural language
- A **deterministic 6-stage pipeline** (`backend/orchestrator.py`) that all jurisdictions share
- A **plugin architecture** (Registry → Adapter → Channel) for adding new countries/tax types

Currently live: **UK VAT** via HMRC Making Tax Digital API. UK SA / CT / PAYE / SDLT adapter slots are registered; DE / FR / CN are placeholders.

---

## Repo Layout

```
/root/TAXI/                          ← 仓库根 = 项目根
│
├── README.md                        ← 产品概览
├── CLAUDE.md                        ← 你正在读的开发者指南
├── Case_Roadmap.md                  ← 嘉汉案例驱动的税种实现状态与长期计划
├── LICENSE                          ← MIT
├── .gitignore
│
├── pyproject.toml / setup.py / setup.cfg   ← 打包：packages = ["backend"]
├── run_backend.py                   ← uvicorn launcher（target: backend.main:app）
├── start_backend.sh                 ← 启动脚本
├── vat_return_payload.json
│
├── backend/                         ← ⭐ 全部后端 Python 代码（唯一 import 根）
│   ├── __init__.py                  ←   暴露 JurisdictionRegistry / Orchestrator
│   ├── config.py
│   ├── registry.py
│   ├── orchestrator.py              ←   6 阶段管线
│   ├── main.py                      ←   FastAPI app factory (was server/main.py)
│   ├── erp_router.py                ←   /erp routes (was server/erp.py)
│   ├── routers/                     ←   agent, channel, filings, jurisdictions, users
│   ├── agent/                       ←   engine.py tools.py prompts.py business_analyzer.py session_store.py
│   ├── channels/                    ←   api_channel.py oauth.py fraud_headers.py
│   ├── erp/                         ←   csv_parser.py profiles.py reconcile.py erp_samples_loader.py ...
│   ├── jurisdictions/               ←   uk/{vat,paye,self_assessment,corporation_tax,stamp_duty} · testland/vat
│   ├── models/                      ←   Pydantic domain models
│   └── services/                    ←   state_machine.py audit_log.py
│
├── frontend/                        ← React 19 + TS + Vite
├── data/                            ← 样本业务数据 (anonymized) · erp_samples/
├── docs/                            ← architecture / deployment / integration / jurisdictions
├── scripts/                         ← 独立可执行脚本
├── tests/                           ← pytest 套件 · erp/
│
└── design-system/                   ← 设计系统 spec → taxagent-global/MASTER.md
```

> **Imports** are uniformly `from backend.X import ...`. The FastAPI app target is `backend.main:app`; the ERP router is `from backend.erp_router import router` (note: `backend.erp` is the ERP *package*, `backend.erp_router` is the FastAPI router module — kept distinct on purpose).

---

## Where to Start

| 你想做 | 去哪里 |
|---|---|
| 了解产品定位 | [`README.md`](./README.md) |
| 了解嘉汉案例路线图 / 税种实现状态 | [`Case_Roadmap.md`](./Case_Roadmap.md) |
| 加一个新国家 | [`docs/architecture/adding-new-jurisdiction.md`](./docs/architecture/adding-new-jurisdiction.md) |
| 加一个新税种 | [Common Tasks](#common-tasks) |
| 理解 6 阶段管线 | [`docs/architecture/pipeline.md`](./docs/architecture/pipeline.md) |
| 评估可拓展性 / 改国家隔离架构 | [`docs/architecture/extensibility.md`](./docs/architecture/extensibility.md) |
| 改 UI 设计 | [`design-system/taxagent-global/MASTER.md`](./design-system/taxagent-global/MASTER.md) |
| 改 Agent 工具 | [Agent Layer](#agent-layer) |
| **前端部署到 9000 端口 + 公网可访问** | [`docs/deployment/port-9000.md`](./docs/deployment/port-9000.md) |

---

## Quick Commands

```bash
# 后端 (FastAPI, port 8765) — 从仓库根运行
./start_backend.sh                       # path-agnostic — works on macOS dev and Linux servers
# Or, if start_backend.sh's `python -c "import backend"` smoke check fails:
python run_backend.py                    # ensures repo root is on sys.path

# 前端 (built dist/ served on port 9000, with SPA fallback to /index.html)
./scripts/serve_frontend_9000.sh
# In dev (HMR, proxy to backend):
cd frontend && npm run dev               # 9000 too (vite.config.ts has the proxy)

# 测试 — 从仓库根运行
pytest                                   # 跑全部
pytest tests/path/to/test_file.py -k test_name   # 跑单个测试 / 按关键字

# Lint
ruff check .
```

API 文档：<http://localhost:8765/docs>
前端入口：<http://localhost:9000>
完整部署指南：[`docs/deployment/port-9000.md`](./docs/deployment/port-9000.md)

---

## 3-Layer Plugin Architecture

The whole backend follows **Registry → Adapter → Channel**. New countries plug in without touching the LLM or pipeline.

### Layer 1 — Registry (`backend/registry.py`)
`JurisdictionRegistry` holds all `JurisdictionAdapter` instances keyed by `country_code`. New countries are registered in `backend/main.py`:
```python
registry = JurisdictionRegistry()
registry.register(UKJurisdictionAdapter())
```

### Layer 2 — Adapter (`backend/jurisdictions/{cc}/__init__.py`)
Abstract base class `JurisdictionAdapter` defines per-country contract:
- `get_template(tax_type)` → `DataTemplate` (form schema)
- `calculate(tax_type, data)` → `CalculationResult`
- `validate(tax_type, data)` → `ValidationReport`
- `get_channel(tax_type)` → `FilingChannel`
- `to_filing_format(tax_type, data)` → `FilingPayload`
- `get_agent_tools(tax_type)` → `AgentToolSet | None` (for LLM skill registration)

UK implementation delegates per-tax-type to `backend/jurisdictions/uk/vat/` etc.

### Layer 3 — Channel (`backend/channels/api_channel.py`)
Abstract `FilingChannel` defines: `authenticate()`, `submit(payload)`, `get_status(receipt)`, `health_check()`.
- `APIChannel` is the REST implementation (HMRC).
- Future: `BrowserChannel` for China's 电子税务局 (Playwright).

---

## The 6-Stage Orchestrator (`backend/orchestrator.py`)

Shared pipeline for every jurisdiction:

```
PRECHECK  →  PREPARE  →  CALCULATE  →  VALIDATE  →  SUBMIT  →  TRACK
   │            │            │             │            │          │
template    auth + format  adapter.calc   adapter.val  channel.  channel.
validation   conversion                   (warn_policy  submit    get_status
                                                          controls)  (poll)
```

Each stage:
1. Records to `AuditLog` (per `filing_id`)
2. Updates `FilingResult.stage_results[stage]`
3. Transitions `FilingStatus` via `StateMachine` (illegal transitions raise)

`StateMachine` (`backend/services/state_machine.py`):
```
PENDING → IN_PROGRESS → SUBMITTED → ACCEPTED  (terminal)
                  │           │
                  │           └──→ REJECTED → PENDING (resubmit after fix)
                  └──→ ERROR ──┴──→ SUBMITTED / PENDING
```

---

## Agent Layer

### Engine (`backend/agent/engine.py`)
`TaxAgentEngine` exposes `async chat(session_id, message, ...) -> AsyncIterator[str]`.
- **SDK mode**: `ANTHROPIC_API_KEY` set + `claude-agent-sdk` installed → uses `ClaudeSDKClient`
- **Mock mode**: keyword matching fallback for demos (no API key needed)

`AgentSession` is per-conversation state (jurisdiction, taxpayer_id, period_key, line_items, messages, cached SDK clients).

### Skills Factory (`backend/agent/tools.py`)
`create_mcp_servers(registry)` walks the registry, builds one MCP server per `(country, tax_type)` pair, each hosting that jurisdiction's `AgentToolSet` methods.
- Tool names use MCP namespace: `mcp__tax_agent_uk_vat__get_vat_obligations` (the `tax_agent_*` prefix is the MCP server-name scheme, unrelated to the package path).
- Defensive: tools that fail to resolve (e.g., SA metadata/method mismatch) are skipped, not fatal

### UK VAT Skills (`backend/jurisdictions/uk/vat/agent_tools.py`)
Six tools wrapping HMRC MTD for VAT:
| Tool | Wraps |
|---|---|
| `get_vat_obligations` | HMRC `GET /organisations/vat/{vrn}/obligations` |
| `calculate_vat_return` | local 9-Box calculator |
| `validate_vat_return` | local compliance validator |
| `submit_vat_return` | HMRC `POST /organisations/vat/{vrn}/returns` |
| `get_vat_return` | HMRC `GET .../returns/{periodKey}` |
| `analyze_business_data` | `backend/agent/business_analyzer.py` |

LLM-facing field names (`vrn`, `period_key`, etc.) are mapped to the internal `taxpayer_id` automatically.

### Agent Router (`backend/routers/agent.py`)
- WebSocket `/api/agent/ws/chat` (primary, used by frontend)
- SSE `/api/agent/chat` (HTTP fallback)
- Session listing: `/api/agent/sessions` (reads SDK's JSONL files)
- Health: `/api/agent/health`

### HMRC API 真实状态 (2026-06-13 复核)

| 税种 | HMRC 实际 API 格式 | 当前代码状态 | 备注 |
|------|-------------------|--------------|------|
| **VAT** | **REST** (`/api/service/vat-api/1.0`) | ✅ JSON client 工作 | 唯一 REST MTD API;沙箱 E2E 已通 |
| **Corporation Tax** | **XML** (`/api/xml/Corporation Tax Online`) | ❌ 代码用 JSON 假路径 | CT600 通过 GovTalk XML 提交,需 XML client |
| **PAYE/RTI** | **XML** (`/api/xml/Real Time Information online`) | ❌ 代码用 JSON 假路径 | FPS/EPS/EYU 是 XML 消息类型 |
| **Business Rates** | **REST** (`/api/service/business-rates-api/2.0`) | 🟡 文档未提及 | 仅 VOA 估值/上诉,不包含 council 账单 |
| **Withholding Tax** | 无独立 API (走 CT600 + DTTP1/DT-Company) | 🟡 文档化在 `data/tax_knowledge/uk/withholding_tax.md` | UK 从不预扣股息税 |

要让 CT/PAYE 真正联通 HMRC,需要把 `hmrc_service.py` 中的 `httpx` JSON 调用改为 XML 客户端,POST 到 Government Gateway XML endpoint,并处理 GovTalk 消息包装器。详见 `docs/architecture/govtalk_client.md` (含完整代码骨架、envelope 示例、CT600 body builder 示例、轮询流程)。

### SDK 调研 Subagent(项目级)
- 定义:`.claude/agents/claude-sdk-docs-researcher.md` — 通过 `Agent` 工具用 `subagent_type="general-purpose"` 派发
- 本地文档镜像:`docs/superpowers/reference/code-claude-com/agent-sdk/markdown/`(30 页,~650 KB,从 `https://code.claude.com/docs/en/agent-sdk` 抓取)
- SDK 源码:`$HOME/miniconda3/envs/taxagent/lib/python3.11/site-packages/claude_agent_sdk/`(v0.2.95 / CLI 2.1.170)
- 抓取脚本:`scripts/crawl_agent_sdk_docs.sh`(SDK 升级或文档改版时重跑)
- **硬规则**:任何关于 `claude-agent-sdk` 的问题(query / ClaudeSDKClient / hooks / MCP / subagents / sessions / permissions / structured outputs / cost tracking / 等等)→ **必须派发该 subagent 调研,不许凭记忆回答**。subagent 给出的每条 API 声明都 cite 本地 mirror 或 SDK 源码的 file:line,可直接采信。
- 网络注意:`WebFetch` 工具拒收 `code.claude.com` 域名,subagent 内部用 `curl` 拉缺页。

### SDK 合规性审查(2026-06-12)
- **报告**:`docs/superpowers/audit/2026-06-12-sdk-audit.md`(19 finding, 2 critical / 5 high / 6 medium / 6 nit;**总评 B-**)
- **Top-5 待修**(按 ROI):(1) `ToolAnnotations` 标 destructiveHint/readOnlyHint 修 C2;(2) PreToolUse/PostToolUse hooks 修 C1 部分 + H1 + H3;(3) OTEL env 修 H4;(4) `model_usage` 累加修 H5;(5) `session_store` 改用 SDK 公开 API(`list_sessions` / `get_session_messages`)修 H2
- **C1 完整修复前置**:`routers/agent.py` WS 端点必须改成 `AsyncIterable[dict]` 喂 `client.query()` — `claude_agent_sdk/client.py:173-180` 拒绝 `can_use_tool` + string prompt 组合。属 3-4 天大改,建议独立 PR
- **下次复审触发**:`claude-agent-sdk` 升级 / 后端 SDK 集成层有改动 / Phase 3 重构时

---

## Models

All domain models are Pydantic in `backend/models/`:
- `tax_data.py` — `TaxData`, `TaxType`, `FiscalPeriod`, `LineItem`, `ChannelType`
- `template.py` — `DataTemplate`, `TemplateSection`, `TemplateField`
- `results.py` — `FilingResult`, `FilingStatus`, `StageResult`, `CalculationResult`, `ValidationReport`, `Receipt`
- `agent_tools.py` — abstract `AgentToolSet` base class

Import from `backend.models`.

---

## Common Tasks

| Task | File |
|---|---|
| Add a new country | New `backend/jurisdictions/{cc}/__init__.py` adapter + `register()` in `backend/main.py` |
| Add a new tax type | Add to `TaxType` enum + implement per-type adapter under `backend/jurisdictions/{cc}/{tax_type}/` |
| Change pipeline retry/timeout | `backend/config.py` (`FilingConfig`) |
| Change HMRC base URL | `backend/jurisdictions/uk/config.py` (`hmrc_config`) |
| Add an agent tool | Add async method to `AgentToolSet` subclass + entry in `get_tool_metadata()` |
| Add a frontend page | Route in `frontend/src/App.tsx` + page in `frontend/src/pages/` |
| Read HMRC OAuth helper | `scripts/` (manual OAuth flow) |
| **Deploy frontend on port 9000 with public access** | [`docs/deployment/port-9000.md`](./docs/deployment/port-9000.md) — covers Vite proxy config, the `serve_frontend_9000.sh` static server, and Cloudflare Tunnel / nginx recipes. |
| **Add CSV profile** | `backend/erp/profiles.py` (新 class + 注册到 `_PROFILES`) |
| **Add demo case** | 写 JSON 到 `data/erp_samples/<id>.json` |
| **Ask about `claude-agent-sdk`** | **派发** `claude-sdk-docs-researcher` subagent(见上),不许凭记忆答 |
| **Re-audit SDK compliance** | SDK 升级 / `backend/agent/` 改动后重跑, 报告模板见 `docs/superpowers/audit/2026-06-12-sdk-audit.md` |

---

## Copilot Philosophy

AI 是副驾，**最终决定权在人**——报税必须由人确认提交，AI 不替你在法律意义上"按下按钮"。这条原则在设计 agent 工具、UI 流程、agent 提示词时都要尊重。

---

## Cross-Border Nature

T.A.X.I. 从第一天起就为**跨境场景**设计，要解决 3 件最难的事：
1. **不同国家不同的表单**（UK 9-Box vs DE Umsatzsteuer vs CN 增值税）
2. **不同的认证流程**（UK OAuth vs 未来 DE/FR/CN）
3. **不同的提交渠道**（API vs 浏览器自动化）

**3 层插件架构**（Registry → Adapter → Channel）保证：加一个新国家只需几百行代码，不用重写管线或 LLM。

---

## Environment & Secrets

- Backend secrets live in `.env` and `.env.testuser` at the repo root — **never commit** (gitignored)
- HMRC OAuth tokens cached per-VRN in `./.tokens/{vrn}.json` — also gitignored
- Frontend has no `.env`; API base URL defaults to a same-origin `/api` base (overridable via `VITE_API_BASE_URL`)
- CORS in `backend/main.py` allows `localhost:5173/5174/9000` + `CORS_ORIGINS` env var

---

## What Was Removed vs. Kept

To keep the public repo clean, the following have been **excluded from version control** (or removed entirely):

| Was | Why excluded |
|---|---|
| `tax_auto/` (legacy Playwright) | Superseded by API channel; contained `cookies.json` and 14MB browser profile |
| `data/oauth_token.json` | HMRC OAuth token — credential leak risk |
| `claude_docs/`, `claude_docs_searcher/` | Copies of `claude-agent-sdk` reference docs (146 files, 4.1 MB) — should come from the SDK itself |
| `logs/`, `.claude/` | Runtime artifacts and local Claude Code config |
| All `node_modules/`, `__pycache__/`, `.pytest_cache/`, `*.egg-info/` | Build/dependency artifacts |

**Sensitive content is also `.gitignore`d** (in case it's recreated): `.env`, `.env.*`, `.tokens/`, `*.pem`, `*.key`, `secrets/`.

---

## Notes

- Tests in `tests/` are minimal. Run `pytest` from the repo root; the `pytest-httpx` dev dep is wired in for HMRC HTTP mocking.
- When `uvicorn --reload` fails to import the package after a restructure, fall back to `python run_backend.py` (it ensures the repo root is on `sys.path`).
- **Frontend port is 9000** (Vite dev server, the static `serve_frontend_9000.sh`, and `vite preview` all use it). The frontend defaults to a **same-origin `/api` base**, so the public-internet tunnel/proxy in front of the static server is responsible for forwarding `/api`, `/docs`, `/openapi.json`, `/health` → port 8765. See [`docs/deployment/port-9000.md`](./docs/deployment/port-9000.md).

## Current deployment topology (2026-06)

The repo uses **two conda envs** under one Miniconda install, both auto-activated by the launch scripts.

| Port | Process | Started by | Conda env |
|---|---|---|---|
| `:8765` | `uvicorn` (FastAPI) — `python -m uvicorn backend.main:app` | `nohup ./start_backend.sh` | `taxagent` (Python 3.11 + backend deps) |
| `:9000` | `python3 scripts/serve_frontend_9000.py` (Python 3.6 stdlib, SPA fallback) | `nohup bash scripts/serve_frontend_9000.sh` | system Python (static file server, no deps) |

**Conda envs** (`$HOME/miniconda3/envs/`):

| Env | Python / Node | Contents | Symlink |
|---|---|---|---|
| `taxagent` | Python 3.11.15 | pydantic 2.13.4, fastapi, uvicorn, pytest, claude-agent-sdk, playwright, etc. | `.venv → ../../miniconda3/envs/taxagent` |
| `fe-build`  | Node 20.20.2 | npm 10.8.2 (used to run Vite 4.5.5 + Tailwind v3) | — |

**Why conda**:
- The host runs CentOS 7.9 / glibc 2.17, which can't run the official Node 18+ binaries. `conda-forge` ships Node 20 built against a glibc 2.17-compatible sysroot, which works.
- The system Python is 3.6.8 (too old for pydantic v2 + structural pattern matching). The `taxagent` conda env provides Python 3.11.
- The legacy `/opt/python-musl/python` (pydantic v1) has been removed — pydantic v1 is incompatible with the current code.

**One-shot install** (if the envs don't exist):

```bash
# 1) Miniconda (glibc 2.17-compatible, must be the old 4.10.3 build)
curl -sSLO https://repo.anaconda.com/miniconda/Miniconda3-py39_4.10.3-Linux-x86_64.sh
bash Miniconda3-py39_4.10.3-Linux-x86_64.sh -b -p $HOME/miniconda3

# 2) Backend env
$HOME/miniconda3/bin/conda env create -f environment.yml

# 3) Frontend env
$HOME/miniconda3/bin/conda create -n fe-build -y -c conda-forge nodejs=20
```

**Daily use** — both launchers auto-detect Miniconda (`$HOME/miniconda3`, `/opt/miniconda3`, `$CONDA_BASE` override) and activate the right env:

```bash
./start_backend.sh                # auto-activates `taxagent`
./start_frontend_build.sh         # auto-activates `fe-build` and rebuilds dist
pytest                             # works because .venv is the taxagent env
```

**Frontend build output**:
- Vite 4.5.5 + React 18 + Tailwind **v3** (PostCSS pipeline)
- CSS ~34 KB (Tailwind utilities), JS ~343 KB
- Tailwind v4 / Vite 5 require Node 20+ on a modern host — upgrade only after retiring CentOS 7
- `client.ts` ships the FormData multipart fix (CSV uploads no longer get JSON Content-Type forced)
