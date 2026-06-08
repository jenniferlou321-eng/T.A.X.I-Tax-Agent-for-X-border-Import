# T.A.X.I. — Tax Agent for X-border & Import

> **多国税务，一键叫车** — Your AI Copilot for Cross-Border Tax Filing, on Autopilot.

This file is the **repo-level** developer guide. For the product pitch, see [`README.md`](./README.md). For **technical details** (architecture, modules, commands, all country adapters), see **[`tax_agent/CLAUDE.md`](./tax_agent/CLAUDE.md)**.

---

## Repo Layout

```
T.A.X.I. 仓库根
│
├── README.md                  ← 产品概览
├── LICENSE                    ← MIT
├── CLAUDE.md                  ← 你正在读的仓库级开发者指南
├── .gitignore                 ← 全面排除
│
├── tax_agent/                 ← ⭐ 核心项目
│   ├── CLAUDE.md              ← 项目级技术文档（⭐ 从这里开始）
│   ├── README.md              ← 产品级 README
│   ├── agent/                 ← LLM engine + MCP tools
│   ├── server/                ← FastAPI
│   ├── jurisdictions/         ← 各国适配器
│   ├── channels/              ← 提交渠道
│   ├── services/              ← 状态机 + 审计日志
│   ├── orchestrator.py        ← 6 阶段管线
│   ├── frontend/              ← React 19 + Vite
│   ├── docs/                  ← 架构 + 各国流程
│   ├── tests/  scripts/  models/  data/
│   ├── start_backend.sh       ← 启动脚本
│   ├── run_backend.py
│   └── vat_return_payload.json
│
└── design-system/             ← 设计系统 spec
    └── taxagent-global/
        └── MASTER.md
```

---

## Where to Start

| 你想做 | 去哪里 |
|---|---|
| 了解产品定位 | [`README.md`](./README.md) |
| 跑起来 / 部署 | [`tax_agent/CLAUDE.md` → Quick Start](./tax_agent/CLAUDE.md) |
| 加一个新国家 | [`tax_agent/docs/architecture/adding-new-jurisdiction.md`](./tax_agent/docs/architecture/adding-new-jurisdiction.md) |
| 加一个新税种 | [`tax_agent/CLAUDE.md` → Common Tasks](./tax_agent/CLAUDE.md) |
| 理解 6 阶段管线 | [`tax_agent/docs/architecture/pipeline.md`](./tax_agent/docs/architecture/pipeline.md) |
| 改 UI 设计 | [`design-system/taxagent-global/MASTER.md`](./design-system/taxagent-global/MASTER.md) |
| 改 Agent 工具 | [`tax_agent/CLAUDE.md` → Agent Layer](./tax_agent/CLAUDE.md) |

---

## Quick Commands

```bash
# 后端
cd tax_agent && ./start_backend.sh

# 前端
cd tax_agent/frontend && npm run dev

# 测试
cd tax_agent && pytest

# Lint
cd tax_agent && ruff check .
```

---

## What Was Removed vs. Kept

To keep the public repo clean, the following have been **excluded from version control** (or removed entirely):

| Was | Why excluded |
|---|---|
| `tax_auto/` (legacy Playwright) | Superseded by API channel; contained `cookies.json` and 14MB browser profile |
| `data/oauth_token.json` | HMRC OAuth token — credential leak risk |
| `frontend/` and `src/` (repo root) | Empty Vite/React shells, never used (real frontend lives in `tax_agent/frontend/`) |
| `claude_docs/`, `claude_docs_searcher/` | Copies of `claude-agent-sdk` reference docs (146 files, 4.1 MB) — should come from the SDK itself |
| `logs/`, `.claude/` | Runtime artifacts and local Claude Code config |
| All `node_modules/`, `__pycache__/`, `.pytest_cache/`, `tax_agent.egg-info/` | Build/dependency artifacts |

**Sensitive content is also `.gitignore`d** (in case it's recreated): `.env`, `.env.*`, `tax_agent/.tokens/`, `*.pem`, `*.key`, `secrets/`.

---

## Notes

- **Two README files exist by design**: root `README.md` (product pitch) and `tax_agent/README.md` (TAXI's product doc inside the core project). Same for `CLAUDE.md`.
- **Cross-border nature**: T.A.X.I. was designed from day one to handle the **3 hardest things** in cross-border tax:
  1. **Different forms per country** (UK 9-Box vs DE Umsatzsteuer vs CN 增值税)
  2. **Different auth flows** (UK OAuth vs future DE/FR/CN)
  3. **Different submission channels** (API vs Browser automation)
  The 3-layer plugin architecture (Registry → Adapter → Channel) keeps adding a new country to **a few hundred lines of code, not a rewrite**.
