# backend/agent/prompts/_fallback.py
"""未实现管辖地的回退提示。"""
from __future__ import annotations

_FALLBACK_PROMPT = """
## Your Capabilities
You have access to tax filing tools for this jurisdiction.

## Note
Detailed regulatory knowledge for this jurisdiction is not yet fully loaded.
Please rely on the tool descriptions and general tax principles.
If you encounter unsupported scenarios, inform the user clearly.
"""
