"""FastAPI Server — TaxAgent Global REST API"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import JurisdictionRegistry, Orchestrator
from backend.jurisdictions.uk import UKJurisdictionAdapter
from backend.jurisdictions.cn import CNJurisdictionAdapter
from backend.jurisdictions.testland import TestlandJurisdictionAdapter
from backend.agent import TaxAgentEngine
from backend.agent.session_store import cleanup_old_sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan hook — 启动时清理累积的 SDK 会话,只保留最近 10 个。

    避免 `~/.claude/projects/<proj>/` 单项目累积数百 MB JSONL。
    运行时还会由 TaxAgentEngine.chat() 在每轮对话后异步清理。
    """
    try:
        deleted = cleanup_old_sessions(keep=10)
        if deleted:
            import logging
            logging.getLogger(__name__).info(
                "[startup] cleaned %d old SDK sessions (kept latest 10)", deleted
            )
    except Exception as e:  # 启动时清理失败不影响启动
        import logging
        logging.getLogger(__name__).debug("startup session cleanup failed: %s", e)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="TaxAgent Global",
        description="Multi-country automated tax filing API with Claude Agent",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — 允许前端开发服务器
    origins = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        # Default Vite dev/preview port for T.A.X.I. (port 9000).
        "http://localhost:9000",
        "http://127.0.0.1:9000",
        # ERPNext web (Frappe) is on 9001 (was 8000 before 2026-06-12).
        "http://my.local:9001",
        "http://localhost:9001",
        "http://127.0.0.1:9001",
    ]
    # 允许从环境变量追加额外 origin（生产环境把公网域名加进来，逗号分隔）
    # 例：CORS_ORIGINS="https://tax.example.com,https://tax-staging.example.com"
    extra = os.environ.get("CORS_ORIGINS", "")
    if extra:
        origins.extend([o.strip() for o in extra.split(",") if o.strip()])

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 初始化核心组件
    registry = JurisdictionRegistry()
    registry.register(UKJurisdictionAdapter())
    registry.register(CNJurisdictionAdapter())  # 中国:CN_VAT + CN_CIT
    registry.register(TestlandJurisdictionAdapter())  # 示例国家
    app.state.registry = registry
    app.state.orchestrator = Orchestrator()

    # 注入 Registry 到 Agent 工具层（使 MCP Server 能动态发现各国工具）
    from backend.agent.tools import set_registry as set_tools_registry
    set_tools_registry(registry)

    # 创建全局 TaxKnowledgeStore 并存到 app.state,以便 corpus sync router
    # 在合并镜像后能调用 store.reload() 让 in-memory 索引立刻反映新文件。
    from backend.agent.tax_knowledge_store import TaxKnowledgeStore
    knowledge_store = TaxKnowledgeStore()
    app.state.knowledge_store = knowledge_store

    # 初始化 Agent 引擎（注入路由层，传入 Registry 实现多管辖地支持）
    from .routers import agent as agent_router
    agent_engine = TaxAgentEngine(
        registry=registry,
        cwd=os.getcwd(),
        permission_mode=os.environ.get("AGENT_PERMISSION_MODE", "default"),
        kb_store=knowledge_store,
    )
    agent_router.set_engine(agent_engine)

    # 注册路由
    from .routers import jurisdictions, filings, channel, users, deadlines, corpus_sync
    from .erp_router import router as erp_router
    app.include_router(jurisdictions.router, prefix="/api")
    app.include_router(filings.router, prefix="/api")
    app.include_router(channel.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(corpus_sync.router, prefix="/api")
    app.include_router(agent_router.router, prefix="/api")
    app.include_router(deadlines.router, prefix="/api")
    app.include_router(erp_router, prefix="/api")  # router 自带 prefix="/erp" → /api/erp/*

    # ── Optional: PayPal Payment Channel (PoC) ──
    paypal_client_id = os.environ.get("PAYPAL_CLIENT_ID", "")
    if paypal_client_id:
        from backend.channels.payment.paypal import PayPalChannel
        app.state.paypal_channel = PayPalChannel.from_env()
        import logging as _logging
        _logging.getLogger(__name__).info("[startup] PayPal payment channel initialized")
    else:
        app.state.paypal_channel = None

    # ── Optional: Shopify Ecommerce Channel (PoC) ──
    shopify_domain = os.environ.get("SHOPIFY_SHOP_DOMAIN", "")
    if shopify_domain:
        from backend.channels.ecommerce.shopify import ShopifyChannel
        app.state.shopify_channel = ShopifyChannel.from_env()
        import logging as _logging
        _logging.getLogger(__name__).info("[startup] Shopify ecommerce channel initialized")
    else:
        app.state.shopify_channel = None

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
