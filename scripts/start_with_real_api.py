#!/usr/bin/env python3
"""Start the backend server with real API credentials from ~/.claude/settings.json"""

import json
import os
import subprocess
import sys

# Load credentials from Claude settings
settings_path = os.path.expanduser("~/.claude/settings.json")
with open(settings_path) as f:
    settings = json.load(f)

env_vars = settings.get("env", {})

# Set required env vars
os.environ["ANTHROPIC_API_KEY"] = env_vars.get("ANTHROPIC_AUTH_TOKEN", "")
os.environ["ANTHROPIC_BASE_URL"] = env_vars.get("ANTHROPIC_BASE_URL", "")

if not os.environ["ANTHROPIC_API_KEY"]:
    print("ERROR: No API key found in ~/.claude/settings.json")
    sys.exit(1)

print(f"API Key loaded: {os.environ['ANTHROPIC_API_KEY'][:20]}...")
print(f"Base URL: {os.environ['ANTHROPIC_BASE_URL']}")

# Start uvicorn
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(project_root)

sys.path.insert(0, project_root)

from backend.main import create_app
import uvicorn

app = create_app()

uvicorn.run(
    app,
    host="0.0.0.0",
    port=8765,
    reload=False,
)
