"""One-shot SDK smoke test: drive the real ClaudeSDKClient against MiniMax.

Loads .env, spawns the bundled claude CLI via the SDK, asks a trivial question,
prints the reply (or the captured CLI stderr on hang/timeout).
"""
import asyncio
import os
import pathlib
import sys

ENV_EXTRA = {}
for _line in pathlib.Path(__file__).resolve().parent.parent.joinpath(".env").read_text().splitlines():
    _line = _line.strip()
    if _line and not _line.startswith("#") and "=" in _line:
        _k, _v = _line.split("=", 1)
        os.environ[_k] = _v
        ENV_EXTRA[_k] = _v

sys.path.insert(0, "/root/TAXI")

# Claude Code refuses --dangerously-skip-permissions as root unless sandboxed.
ENV_EXTRA["IS_SANDBOX"] = "1"
os.environ["IS_SANDBOX"] = "1"

_ERRS = []


def _on_err(s: str) -> None:
    _ERRS.append(s)
    sys.stderr.write("[CLI-STDERR] " + s.rstrip() + "\n")


async def _main() -> None:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ClaudeSDKClient,
        ResultMessage,
        TextBlock,
    )

    opts = ClaudeAgentOptions(
        system_prompt="You are terse. Answer in one short sentence.",
        cli_path="/usr/local/bin/claude",
        permission_mode="bypassPermissions",
        setting_sources=[],
        env=ENV_EXTRA,
        max_turns=1,
        stderr=_on_err,
    )
    out = []
    async with ClaudeSDKClient(options=opts) as client:
        await client.query("What is 7 times 6? Reply with just the number.")
        async for msg in client.receive_response():
            if isinstance(msg, AssistantMessage):
                for b in msg.content:
                    if isinstance(b, TextBlock):
                        out.append(b.text)
            if isinstance(msg, ResultMessage):
                break
    print("SDK_REPLY:", "".join(out).strip()[:200])


if __name__ == "__main__":
    try:
        asyncio.run(asyncio.wait_for(_main(), timeout=60))
    except asyncio.TimeoutError:
        print(f"TIMEOUT after 60s; captured {len(_ERRS)} stderr line(s)")
