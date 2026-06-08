"""FilingConfig — Orchestrator 配置"""

from dataclasses import dataclass


@dataclass
class FilingConfig:
    """申报管线配置"""
    warn_policy: str = "continue"       # "strict"(遇warning中止) | "continue"(仅记录)
    max_retries: int = 3
    track_timeout_hours: int = 72
    track_poll_interval_seconds: int = 300  # 每 5 分钟轮询一次状态