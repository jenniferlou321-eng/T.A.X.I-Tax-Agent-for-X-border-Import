# 仓库重构架构设计

> **状态**：设计中，待你审阅 · **不含迁移动作**
> **目标**：把 `/root/TAXI/tax_agent/` 里的东西全部"拿出来"并精简——后端代码统一收进 `backend/` 包，根目录只留配置 + 资源 + 前端

---

## 1. 决策回顾（你已确认）

| # | 决策 | 选择 |
|---|---|---|
| ① | 包结构 | **所有后端 Python 代码收进 `backend/`**，import 写 `from backend.agent.X`、`from backend.erp.X` |
| ② | 冲突文件 | **合并**（CLAUDE.md / README.md / .gitignore） |
| ③ | 环境/缓存产物 | **删**构建/缓存（`__pycache__`、`.pytest_cache`、`egg-info`、`.coverage`、运行时 `logs/`），**留** `venv/`、`.venv/` |
| ④ | 撞名问题 | **自动消除**——`erp`/`server` 不再裸挂根，都在 `backend.` 底下，**无需改名** |
| ⑤ | 流程 | **先定架构（本文档）→ 再迁移 → 再改 import** |

---

## 2. 关键收益：撞名问题消失

上一版裸挂方案里 `erp`、`server` 与环境第三方包撞名，需要改名。
**改成全部进 `backend/` 后**：import 变 `from backend.erp.X`、`from backend.server.X`，命名空间唯一，**`erp`/`server` 不必改名**，模块名全部原样保留。实测 `import backend` 不撞第三方包。

---

## 3. 目标仓库结构

```
/root/TAXI/                          ← 仓库根 = 项目根
│
├── README.md                        ← 合并：根产品版 + tax_agent 版
├── CLAUDE.md                        ← 合并：根仓库导航 + tax_agent 技术细节
├── LICENSE                          ← 上移
├── .gitignore                       ← 合并（并集）
│
├── pyproject.toml                   ← 上移；packages=["backend"]，去掉 py-modules=tax_agent
├── setup.py / setup.cfg             ← 上移
├── run_backend.py                   ← 上移并简化；uvicorn target → backend.server.main:app
├── start_backend.sh                 ← 上移；uvicorn target → backend.server.main:app
├── vat_return_payload.json          ← 上移
│
├── backend/                         ← ⭐ 全部后端 Python 代码（唯一 import 根）
│   ├── __init__.py                  ←   暴露 JurisdictionRegistry / Orchestrator
│   ├── config.py
│   ├── registry.py
│   ├── orchestrator.py
│   ├── agent/                       ←   engine.py tools.py prompts.py business_analyzer.py session_store.py
│   ├── channels/                    ←   api_channel.py oauth.py fraud_headers.py
│   ├── erp/                         ←   csv_parser.py profiles.py reconcile.py erp_samples_loader.py ...
│   ├── jurisdictions/               ←   uk/{vat,paye,self_assessment,corporation_tax,stamp_duty} · testland/vat
│   ├── models/
│   ├── services/                    ←   state_machine.py audit_log.py
│   └── server/                      ←   main.py erp.py routers/{agent,channel,filings,jurisdictions,users}.py
│                                    ←   (FastAPI 层；import 路径 backend.server.main:app)
│
├── frontend/                        ← React 前端（裸挂根；URL 路由 /api/erp/* 不变）
│
├── data/                            ← 资源裸挂到根
│   └── erp_samples/
├── docs/                            ← 文档裸挂到根
│   └── {architecture,deployment,integration,jurisdictions,superpowers}/
├── scripts/                         ← 脚本裸挂到根
├── tests/                           ← 测试裸挂到根
│   └── erp/
│
├── design-system/                   ← 本就在根，保留
│
├── venv/  .venv/                    ← 保留
└── .git/  .claude/                  ← 保留
```

**删除**（不进 git 的产物）：各级 `__pycache__/`、`.pytest_cache/`、`tax_agent.egg-info/`、`.coverage`、运行时 `logs/`（audit + backend.log）。

### 为什么 data/docs/scripts/tests 留在根、不进 backend/？
- 它们不是 Python 包代码（`data` 是 JSON 样本、`docs` 是 markdown、`scripts` 是独立可执行脚本、`tests` 是测试套件）。
- 主流布局就是「包目录 + 顶层 tests/docs/scripts」。`tests/` 里 `from backend.X import` 干净；`pytest` 从根跑能 import 到 `backend`。
- 如你更想把 `tests/` 也收进 `backend/`，可在 §7 说明，我调整。

---

## 4. import 改写规则

迁移后对 **48 个 .py 文件** + 配置/脚本统一改写。规则简单划一——**`tax_agent` → `backend`**：

| 旧写法 | 新写法 |
|---|---|
| `from tax_agent.<任意>` | `from backend.<任意>` |
| `import tax_agent.<任意>` | `import backend.<任意>` |
| `from tax_agent import X` | `from backend import X` |
| `import tax_agent` | `import backend` |

> 比裸挂方案更简单：不需要按模块名分情况、不需要去前缀、不需要处理 `erp`/`server` 特例——全仓 `tax_agent` 字样统一替换为 `backend`（代码 import 部分）。

**`backend/__init__.py`**（原 `tax_agent/__init__.py`）内部：
`from tax_agent.registry import ...` → `from backend.registry import ...`

**非 .py 引用点**（已定位，必须同步改）：

| 文件 | 旧 | 新 |
|---|---|---|
| `run_backend.py` | `tax_agent.server.main:app` + PKG_PARENT 注入 | `backend.server.main:app`；sys.path 注入可简化（根即 import 根） |
| `start_backend.sh` | `python -m uvicorn tax_agent.server.main:app` | `uvicorn backend.server.main:app` |
| `scripts/start_with_real_api.py` | `from tax_agent.server.main import create_app` | `from backend.server.main import create_app` |
| `tests/erp/test_erp_router.py` | `from tax_agent.server.erp import router` | `from backend.server.erp import router` |
| 各测试/脚本里 `from tax_agent.erp.` | | `from backend.erp.` |
| `pyproject.toml` | `py-modules=["tax_agent"]` | 删该行；`[tool.setuptools.packages.find]` 或 `packages=["backend"]` |
| `agent/tools.py:45` 注释 | `injected by server/main.py` | 不必改（注释，且 `server/main.py` 相对路径仍成立） |

前端 `frontend/src/api/client.ts` 的 `/api/erp/*` **不改**（URL ≠ 模块名）。

---

## 5. 冲突文件合并方案

| 文件 | 骨架 | 并入 | 策略 |
|---|---|---|---|
| `CLAUDE.md` | 根版（仓库导航 + 部署拓扑） | tax_agent 版（3 层架构、6 阶段、Agent 层、Common Tasks） | 根版骨架 + 技术细节并入；路径前缀 `tax_agent/server/` → `backend/server/`、`tax_agent/orchestrator.py` → `backend/orchestrator.py` 等 |
| `README.md` | 根版（产品 pitch） | tax_agent 版独有段落 | 去重合并（前几行本就相同） |
| `.gitignore` | 根版 | tax_agent 版（.env.testuser 等） | 取并集、按类别归并 |
| `LICENSE` | （根无） | MIT | 上移 |
| `logs/` | 空 | audit/ + backend.log | 都删，.gitignore 挡 |

合并后文档内所有路径引用同步从 `tax_agent/<x>` 更新为 `backend/<x>`（代码）或 `<x>`（data/docs/scripts/tests/frontend）。

---

## 6. 迁移与验证顺序（设计批准后才执行）

1. `git mv tax_agent backend`（一步把整个包目录改名，历史完整保留）
2. 把 `backend/` 里的**非代码资源**再 `git mv` 上移到根：`backend/{data,docs,scripts,tests,frontend}` → `/root/TAXI/{...}`；`backend/{LICENSE,README.md,setup.py,setup.cfg,pyproject.toml,run_backend.py,start_backend.sh,vat_return_payload.json,.gitignore}` → 根
3. 删除构建/缓存产物
4. 合并冲突文件（CLAUDE.md / README.md / .gitignore）+ 更新文档内路径
5. 全仓 import 改写：`tax_agent` → `backend`（§4 规则）
6. 改打包配置 + 启动脚本 + uvicorn target
7. 验证：`python -c "import backend.server.main"` 冒烟 → `pytest` → `ruff check .` → `pip install -e .` 重装 → 启动后端冒烟

---

## 7. 待你定（默认值已选）

- `tests/` 留根（默认）还是收进 `backend/tests/`？
- `scripts/` 留根（默认）还是收进 `backend/scripts/`？
- 是否需要旧 import 兼容 shim？默认**不做**。

---

## 8. 风险

| 风险 | 缓解 |
|---|---|
| import 改写误伤字符串里的 `tax_agent` | 改后全仓 `grep -rn tax_agent` 确认仅剩文档/无害处 |
| `git mv tax_agent backend` 与已有空 `backend` 名冲突 | 实测根下无 `backend/`，且 `import backend` 不撞——安全 |
| venv 里旧 `tax_agent` egg-link 指向旧路径 | `pip install -e .` 重装（验证步） |
| 前端 dist/ 旧构建引用旧路径 | URL 未变，只改 .ts 源；dist 无需动 |
| `git mv` 后历史断裂 | 全程 `git mv`，不 `rm`+`add` |
```
