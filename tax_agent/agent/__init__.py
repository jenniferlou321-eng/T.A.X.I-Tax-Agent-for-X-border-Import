"""TaxAgent Claude Agent SDK 集成

智能报税助手 — 基于 Claude Agent SDK 的自动化税务申报 Agent

用法:
    from tax_agent.agent import TaxAgentEngine

    engine = TaxAgentEngine(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        cwd="/path/to/project",
        permission_mode="default",
    )

    async for chunk in engine.chat("session-1", "帮我计算 VAT"):
        print(chunk, end="")
"""

from .engine import TaxAgentEngine

__all__ = ["TaxAgentEngine"]
