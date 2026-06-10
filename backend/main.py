"""FastAPI Server — TaxAgent Global REST API"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import JurisdictionRegistry, Orchestrator
from backend.jurisdictions.uk import UKJurisdictionAdapter
from backend.jurisdictions.testland import TestlandJurisdictionAdapter
from backend.agent import TaxAgentEngine


def create_app() -> FastAPI:
    app = FastAPI(
        title="TaxAgent Global",
        description="Multi-country automated tax filing API with Claude Agent",
        version="0.1.0",
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
    registry.register(TestlandJurisdictionAdapter())  # 示例国家
    app.state.registry = registry
    app.state.orchestrator = Orchestrator()

    # 注入 Registry 到 Agent 工具层（使 MCP Server 能动态发现各国工具）
    from backend.agent.tools import set_registry as set_tools_registry
    set_tools_registry(registry)

    # 初始化 Agent 引擎（注入路由层，传入 Registry 实现多管辖地支持）
    from .routers import agent as agent_router
    agent_engine = TaxAgentEngine(
        registry=registry,
        cwd=os.getcwd(),
        permission_mode=os.environ.get("AGENT_PERMISSION_MODE", "default"),
    )
    agent_router.set_engine(agent_engine)

    # 注册路由
    from .routers import jurisdictions, filings, channel, users
    from .erp_router import router as erp_router
    app.include_router(jurisdictions.router, prefix="/api")
    app.include_router(filings.router, prefix="/api")
    app.include_router(channel.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(agent_router.router, prefix="/api")
    app.include_router(erp_router)  # 新加这一行 (router 自带 prefix="/erp")

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
