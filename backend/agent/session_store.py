"""Session Store — 读取 SDK 会话历史 (Public API 包装)

依赖 claude-agent-sdk 0.2.95+ 公开 API:
    - list_sessions(directory=None, limit=None, offset=0, include_worktrees=True)
    - get_session_messages(session_id, directory=None, limit=None, offset=0)
    - delete_session(session_id, directory=None)
    - project_key_for_directory 间接使用 — 通过 directory=cwd 传参

底层 SDK 把会话存 ~/.claude/projects/<project_key>/<session_id>.jsonl,
我们不直接拼 project_key,避开路径清洗/列表扫描。
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import claude_agent_sdk  # noqa: F401  (用于 raise 异常捕获)
from claude_agent_sdk import (
    delete_session as _sdk_delete_session,
    get_session_messages as _sdk_get_session_messages,
    list_sessions as _sdk_list_sessions,
)

# cwd 在进程生命周期内不变,缓存避免每次调用 os.getcwd()
_CWD = os.getcwd()


# ── helpers ──

def _ms_to_iso(ms: int | None) -> str:
    """SDK 传回毫秒时间戳 (last_modified / created_at),前端期望 ISO 字符串。"""
    if not ms:
        return ""
    try:
        return datetime.utcfromtimestamp(ms / 1000).isoformat() + "Z"
    except (ValueError, TypeError, OSError):
        return ""


def _flatten_user_content(raw_content: Any) -> list[dict]:
    """把 SessionMessage.message['content'] 拍平成 UI 消息列表。

    入参: str 或 list[content block] (Anthropic API 格式)
    出参: 0~2 个 {role, content, timestamp} 元素
        - user/assistant: 直接一条
        - tool_result: 合成一条 role="tool"
    """
    if isinstance(raw_content, str):
        return [{"role": "user", "content": raw_content}]

    if not isinstance(raw_content, list):
        return []

    out: list[dict] = []
    text_parts: list[str] = []
    for block in raw_content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            t = block.get("text")
            if t:
                text_parts.append(t)
        elif btype == "tool_result":
            out.append({"role": "tool", "content": str(block)})
        # thinking / tool_use 在 history view 不展示 (AG-UI 流式已展示)
    if text_parts:
        out.insert(0, {"role": "user", "content": "\n".join(text_parts)})
    return out


# ── public API (与旧版同名 / 同返回形状, router 零修改) ──

def list_sessions() -> list[dict]:
    """列出历史会话摘要。

    Returns:
        按 last_modified 倒序, 每个会话:
            {session_id, created_at, updated_at, summary}
        注: `message_count` 字段已被移除 (SDK 不计算, 估算不可靠)。
            `preview` 字段被 SDK 的 `summary` 替代 (预计算标题)。
    """
    try:
        sessions = _sdk_list_sessions(directory=_CWD, include_worktrees=False)
    except Exception:
        return []

    out: list[dict] = []
    for s in sessions:
        out.append({
            "session_id": s.session_id,
            "created_at": _ms_to_iso(s.created_at),
            "updated_at": _ms_to_iso(s.last_modified),
            "summary": s.summary or s.first_prompt or "(空会话)",
        })

    out.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return out


def get_session_messages(session_id: str) -> list[dict]:
    """获取会话完整对话记录。

    Args:
        session_id: 会话 UUID (SDK SessionInfo.session_id)

    Returns:
        消息列表,每条 {role, content, timestamp}。
        role ∈ {"user", "assistant", "tool"} — 维持旧版契约,
        让 frontend AgentChatPage.tsx (role: 'tool' 已支持) 零修改。
    """
    try:
        records = _sdk_get_session_messages(
            session_id, directory=_CWD, limit=1000, offset=0
        )
    except (ValueError, FileNotFoundError):
        return []

    messages: list[dict] = []
    for rec in records:
        rtype = getattr(rec, "type", None)
        message = getattr(rec, "message", None) or {}
        raw_content = message.get("content") if isinstance(message, dict) else None
        ts = getattr(rec, "uuid", "")  # UUID 作为稳定标识,前端 fallback 到 Date.now()

        if rtype == "user":
            for m in _flatten_user_content(raw_content):
                m["timestamp"] = ts
                messages.append(m)

        elif rtype == "assistant":
            text_parts: list[str] = []
            if isinstance(raw_content, list):
                for block in raw_content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        t = block.get("text")
                        if t:
                            text_parts.append(t)
            if text_parts:
                messages.append({
                    "role": "assistant",
                    "content": "\n".join(text_parts),
                    "timestamp": ts,
                })
            # thinking / tool_use 不进 history (AG-UI 流式已展示)

    return messages


def delete_session(session_id: str) -> bool:
    """删除会话。True 成功, False 任何异常。"""
    try:
        _sdk_delete_session(session_id, directory=_CWD)
        return True
    except (ValueError, FileNotFoundError, OSError):
        return False


# ── 自动清理 ──

def cleanup_old_sessions(keep: int = 10) -> int:
    """保留最近 N 个会话,删除其余的(按 last_modified 倒序)。

    适用场景:SDK 会话 JSONL 持续累积在 `~/.claude/projects/<proj>/`,
    单项目可达数百 MB。每轮 chat 后/启动时调用,把磁盘占用控制在 keep 份。

    Args:
        keep: 保留的最近会话数。默认 10。

    Returns:
        删除的会话数。
    """
    if keep < 0:
        keep = 0
    try:
        sessions = _sdk_list_sessions(directory=_CWD, include_worktrees=False)
    except Exception:
        return 0

    if len(sessions) <= keep:
        return 0

    # SDK 返回顺序: 已按 last_modified 倒序;显式再排一次以防万一
    sessions_sorted = sorted(
        sessions,
        key=lambda s: getattr(s, "last_modified", 0) or 0,
        reverse=True,
    )
    to_delete = sessions_sorted[keep:]
    deleted = 0
    for s in to_delete:
        try:
            _sdk_delete_session(s.session_id, directory=_CWD)
            deleted += 1
        except (ValueError, FileNotFoundError, OSError):
            # 单个失败不影响其他删除
            continue
    return deleted
