"""Agent provider configuration.

For deployed demos, provider settings can be supplied via TAXI_ANTHROPIC_* environment
variables. A local gitignored ``agent_provider.local.json`` remains supported for
local development. If no provider credentials are configured, the application starts
in its built-in mock/demo mode instead of failing during startup.

Environment variables (all required to enable a real LLM provider):
    TAXI_ANTHROPIC_API_KEY
    TAXI_ANTHROPIC_BASE_URL  (e.g. https://api.deepseek.com/anthropic)
    TAXI_ANTHROPIC_MODEL

Generic ANTHROPIC_* variables are intentionally not read, to avoid accidentally
inheriting credentials or model selection from an unrelated shell environment.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class AgentProviderConfig:
    api_key: str = ""
    base_url: str = ""
    model: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)


def _validate(raw: dict, source: str) -> AgentProviderConfig:
    api_key = str(raw.get("api_key") or "").strip()
    base_url = str(raw.get("base_url") or "").strip().rstrip("/")
    model = str(raw.get("model") or "").strip()

    if not api_key:
        return AgentProviderConfig()

    missing = [
        name for name, value in (("base_url", base_url), ("model", model)) if not value
    ]
    if missing:
        raise RuntimeError(
            f"Incomplete Agent provider configuration in {source}: missing "
            + ", ".join(missing)
            + ". Configure TAXI_ANTHROPIC_API_KEY, TAXI_ANTHROPIC_BASE_URL, "
            "and TAXI_ANTHROPIC_MODEL, or remove the API key to use demo mode."
        )
    return AgentProviderConfig(api_key=api_key, base_url=base_url, model=model)


@lru_cache(maxsize=1)
def get_agent_provider_config() -> AgentProviderConfig:
    """Load environment configuration first, then the local JSON file.

    No credentials configured is a valid state: AgentEngine will use mock mode.
    A configured API key without the base URL/model fails clearly rather than
    silently sending requests to an unintended endpoint.
    """
    env_api_key = os.environ.get("TAXI_ANTHROPIC_API_KEY", "").strip()
    env_base_url = os.environ.get("TAXI_ANTHROPIC_BASE_URL", "").strip()
    env_model = os.environ.get("TAXI_ANTHROPIC_MODEL", "").strip()

    # If the explicit deployment API key is set, environment variables take
    # precedence. Never fall back to local developer credentials in that case.
    if env_api_key:
        return _validate(
            {"api_key": env_api_key, "base_url": env_base_url, "model": env_model},
            "TAXI_ANTHROPIC_* environment variables",
        )

    path = Path(__file__).resolve().parents[2] / "agent_provider.local.json"
    if not path.is_file():
        # Expected for a hosted recruiter demo. The engine chooses its mock path
        # whenever this object has no API key.
        return AgentProviderConfig()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON in agent_provider.local.json: {e}") from e
    if not isinstance(raw, dict):
        raise RuntimeError("agent_provider.local.json must contain a JSON object.")
    return _validate(raw, "agent_provider.local.json")
