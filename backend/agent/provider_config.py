"""Agent provider config — SDK/API credentials deliberately isolated from env.

The TaxAgent backend must not read API key / base URL / model from parent-shell
`ANTHROPIC_*` variables. Claude Code `/model` and shell exports can otherwise
leak into the uvicorn process and make the SDK CLI spawn with the wrong model.

Local config lives at repo root `agent_provider.local.json` (gitignored):

{
  "api_key": "...",
  "base_url": "https://api.deepseek.com/anthropic",
  "model": "deepseek-v4-flash"
}
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class AgentProviderConfig:
    api_key: str
    base_url: str
    model: str


@lru_cache(maxsize=1)
def get_agent_provider_config() -> AgentProviderConfig:
    """Load the fixed SDK provider config from a local gitignored JSON file.

    Intentionally does *not* fall back to os.environ. If the file is missing or
    malformed, fail loudly so the frontend ErrorCard shows the real setup issue.
    """
    path = Path(__file__).resolve().parents[2] / "agent_provider.local.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise RuntimeError(
            "Missing agent_provider.local.json. Create it with api_key, base_url, and model."
        ) from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON in agent_provider.local.json: {e}") from e

    api_key = str(raw.get("api_key") or "").strip()
    base_url = str(raw.get("base_url") or "").strip().rstrip("/")
    model = str(raw.get("model") or "").strip()
    missing = [
        name for name, value in (
            ("api_key", api_key),
            ("base_url", base_url),
            ("model", model),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "agent_provider.local.json missing required field(s): " + ", ".join(missing)
        )

    return AgentProviderConfig(api_key=api_key, base_url=base_url, model=model)
