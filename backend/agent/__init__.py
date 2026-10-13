"""TaxAgent Claude Agent SDK 集成

智能报税助手 — 基于 Claude Agent SDK 的自动化税务申报 Agent

用法:
    from backend.agent import TaxAgentEngine

    # Provider can read explicit TAXI_ANTHROPIC_* environment variables or the
    # local gitignored agent_provider.local.json. Without credentials it uses mock mode.
    engine = TaxAgentEngine(
        cwd="/path/to/project",
        permission_mode="default",
    )

    async for chunk in engine.chat("session-1", "帮我计算 VAT"):
        print(chunk, end="")
"""

from .engine import TaxAgentEngine

__all__ = ["TaxAgentEngine"]
