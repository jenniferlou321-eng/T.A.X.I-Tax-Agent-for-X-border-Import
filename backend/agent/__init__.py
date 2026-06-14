"""TaxAgent Claude Agent SDK 集成

智能报税助手 — 基于 Claude Agent SDK 的自动化税务申报 Agent

用法:
    from backend.agent import TaxAgentEngine

    # Provider api_key/base_url/model 固定从 repo-root agent_provider.local.json 读取,
    # 不读父 shell 的 ANTHROPIC_* 环境变量。
    engine = TaxAgentEngine(
        cwd="/path/to/project",
        permission_mode="default",
    )

    async for chunk in engine.chat("session-1", "帮我计算 VAT"):
        print(chunk, end="")
"""

from .engine import TaxAgentEngine

__all__ = ["TaxAgentEngine"]
