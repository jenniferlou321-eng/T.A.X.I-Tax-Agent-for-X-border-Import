# T.A.X.I. — Tax Agent for X-border & Import

> **多国税务，一键叫车** — Your AI Copilot for Cross-Border Tax Filing, on Autopilot.

This file provides guidance to Claude Code when working on the **T.A.X.I.** backend (the Python FastAPI + LLM agent system).

For high-level product overview, see [`README.md`](./README.md).

---

## What This Project Is

**T.A.X.I.** is a multi-country automated tax filing platform. It couples:
- A **chat-style AI agent** (using `claude-agent-sdk`) that can trigger filing workflows via natural language
- A **deterministic 6-stage pipeline** (`orchestrator.py`) that all jurisdictions share
- A **plugin architecture** (Registry → Adapter → Channel) for adding new countries/tax types

Currently live: **UK VAT** via HMRC Making Tax Digital API. UK SA / CT / PAYE / SDLT adapter slots are registered; DE / FR / CN are placeholders.

---

## Backend Layout

```
tax_agent/
├── agent/                  # LLM engine + skills factory
│   ├── engine.py           # TaxAgentEngine (SDK + Mock modes)
│   ├── tools.py            # MCP server factory from AgentToolSet subclasses
│   ├── prompts.py          # per-jurisdiction system prompts
│   ├── business_analyzer.py# raw invoices → 9-Box VAT
│   └── session_store.py    # SDK session JSONL reader
├── server/                 # FastAPI
│   ├── main.py             # app factory + lifespan (registers adapters)
│   └── routers/            # jurisdictions, filings, channel, users, agent
├── jurisdictions/          # per-country adapters
│   └── uk/
│       ├── __init__.py     # UKJurisdictionAdapter
│       └── vat/            # UK VAT (template + calculator + validator + agent_tools)
├── channels/               # submission channels
│   ├── api_channel.py      # REST API generic channel
│   ├── oauth.py            # OAuth 2.0 manager
│   └── fraud_headers.py    # HMRC fraud prevention headers
├── services/               # cross-cutting
│   ├── state_machine.py    # FilingStatus transitions
│   └── audit_log.py        # per-filing audit trail
├── orchestrator.py         # 6-stage pipeline
├── models/                 # Pydantic domain models
├── frontend/               # React 19 + TS + Vite (separate dev server)
├── docs/                   # architecture + per-country docs
└── data/                   # sample business data (anonymized)
```

---

## Development Commands

```bash
# Backend (FastAPI, port 8765)
cd tax_agent
./start_backend.sh                  # path-agnostic — works on macOS dev and Linux servers
# or, if the `python -c "import tax_agent"` smoke check fails:
python run_backend.py
# Honour $PORT and $HOST env vars to override (e.g. PORT=9001).

# Frontend (port 9000)
# In dev (HMR + /api proxy to 8765):
cd tax_agent/frontend && npm run dev
# Production-like (built dist/, no proxy — use a public tunnel to forward /api):
cd tax_agent && ./scripts/serve_frontend_9000.sh

# Lint
ruff check .

# Tests
pytest                              # tests/ — currently minimal
```

API docs: <http://localhost:8765/docs>
Frontend: <http://localhost:9000> (Vite dev server, vite preview, or `scripts/serve_frontend_9000.sh` all use this port)

---

## 3-Layer Plugin Architecture

The whole backend follows **Registry → Adapter → Channel**. New countries plug in without touching the LLM or pipeline.

### Layer 1 — Registry (`registry.py`)
`JurisdictionRegistry` holds all `JurisdictionAdapter` instances keyed by `country_code`. New countries are registered in `server/main.py` lifespan:
```python
registry = JurisdictionRegistry()
registry.register(UKJurisdictionAdapter())
```

### Layer 2 — Adapter (`jurisdictions/{cc}/__init__.py`)
Abstract base class `JurisdictionAdapter` defines per-country contract:
- `get_template(tax_type)` → `DataTemplate` (form schema)
- `calculate(tax_type, data)` → `CalculationResult`
- `validate(tax_type, data)` → `ValidationReport`
- `get_channel(tax_type)` → `FilingChannel`
- `to_filing_format(tax_type, data)` → `FilingPayload`
- `get_agent_tools(tax_type)` → `AgentToolSet | None` (for LLM skill registration)

UK implementation delegates per-tax-type to `jurisdictions/uk/vat/`.

### Layer 3 — Channel (`channels/api_channel.py`)
Abstract `FilingChannel` defines: `authenticate()`, `submit(payload)`, `get_status(receipt)`, `health_check()`.
- `APIChannel` is the REST implementation (HMRC).
- Future: `BrowserChannel` for China's 电子税务局 (Playwright).

---

## The 6-Stage Orchestrator (`orchestrator.py`)

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

`StateMachine` (`services/state_machine.py`):
```
PENDING → IN_PROGRESS → SUBMITTED → ACCEPTED  (terminal)
                  │           │
                  │           └──→ REJECTED → PENDING (resubmit after fix)
                  └──→ ERROR ──┴──→ SUBMITTED / PENDING
```

---

## Agent Layer

### Engine (`agent/engine.py`)
`TaxAgentEngine` exposes `async chat(session_id, message, ...) -> AsyncIterator[str]`.
- **SDK mode**: `ANTHROPIC_API_KEY` set + `claude-agent-sdk` installed → uses `ClaudeSDKClient`
- **Mock mode**: keyword matching fallback for demos (no API key needed)

`AgentSession` is per-conversation state (jurisdiction, taxpayer_id, period_key, line_items, messages, cached SDK clients).

### Skills Factory (`agent/tools.py`)
`create_mcp_servers(registry)` walks the registry, builds one MCP server per `(country, tax_type)` pair, each hosting that jurisdiction's `AgentToolSet` methods.
- Tool names use MCP namespace: `mcp__tax_agent_uk_vat__get_vat_obligations`
- Defensive: tools that fail to resolve (e.g., SA metadata/method mismatch) are skipped, not fatal

### UK VAT Skills (`jurisdictions/uk/vat/agent_tools.py`)
Six tools wrapping HMRC MTD for VAT:
| Tool | Wraps |
|---|---|
| `get_vat_obligations` | HMRC `GET /organisations/vat/{vrn}/obligations` |
| `calculate_vat_return` | local 9-Box calculator |
| `validate_vat_return` | local compliance validator |
| `submit_vat_return` | HMRC `POST /organisations/vat/{vrn}/returns` |
| `get_vat_return` | HMRC `GET .../returns/{periodKey}` |
| `analyze_business_data` | `agent/business_analyzer.py` |

LLM-facing field names (`vrn`, `period_key`, etc.) are mapped to the internal `taxpayer_id` automatically.

### Agent Router (`server/routers/agent.py`)
- WebSocket `/api/agent/ws/chat` (primary, used by frontend)
- SSE `/api/agent/chat` (HTTP fallback)
- Session listing: `/api/agent/sessions` (reads SDK's JSONL files)
- Health: `/api/agent/health`

---

## Models

All domain models are Pydantic in `models/`:
- `tax_data.py` — `TaxData`, `TaxType`, `FiscalPeriod`, `LineItem`, `ChannelType`
- `template.py` — `DataTemplate`, `TemplateSection`, `TemplateField`
- `results.py` — `FilingResult`, `FilingStatus`, `StageResult`, `CalculationResult`, `ValidationReport`, `Receipt`
- `agent_tools.py` — abstract `AgentToolSet` base class

Import from `tax_agent.models`.

---

## Common Tasks

| Task | File |
|---|---|
| Add a new country | New `jurisdictions/{cc}/__init__.py` adapter + `register()` in `server/main.py` |
| Add a new tax type | Add to `TaxType` enum + implement per-type adapter under `jurisdictions/{cc}/{tax_type}/` |
| Change pipeline retry/timeout | `config.py` (`FilingConfig`) |
| Change HMRC base URL | `jurisdictions/uk/config.py` (`hmrc_config`) |
| Add an agent tool | Add async method to `AgentToolSet` subclass + entry in `get_tool_metadata()` |
| Add a frontend page | Route in `frontend/src/App.tsx` + page in `frontend/src/pages/` |
| Read HMRC OAuth helper | `scripts/` (manual OAuth flow) |
| **Deploy frontend on port 9000 with public access** | [`docs/deployment/port-9000.md`](./docs/deployment/port-9000.md) — covers Vite proxy config, the `serve_frontend_9000.sh` static server, and Cloudflare Tunnel / nginx recipes. |
| **Add CSV profile** | `tax_agent/erp/profiles.py` (新 class + 注册到 `_PROFILES`) |
| **Add demo case** | 写 JSON 到 `data/erp_samples/<id>.json` |

---

## Environment & Secrets

- Backend secrets live in `tax_agent/.env` and `tax_agent/.env.testuser` — **never commit**
- HMRC OAuth tokens cached per-VRN in `./.tokens/{vrn}.json` — also gitignored
- Frontend has no `.env`; API base URL is `http://localhost:8765` (overridable via `VITE_API_BASE_URL`)
- CORS in `server/main.py` allows `localhost:5173/5174` + `CORS_ORIGINS` env var

---

## Notes

- The `frontend/` and `src/` directories at the repo **root** (one level above `tax_agent/`) are not used — the active frontend is here at `tax_agent/frontend/`.
- `tax_auto/` (also at repo root) is a legacy Playwright browser-automation prototype, not part of T.A.X.I.
- Tests in `tax_agent/tests/` are minimal. Use `pytest` once added.
- When uvicorn `--reload` fails to import the package after a restructure, use `run_backend.py` (it injects the parent dir into `sys.path`).
