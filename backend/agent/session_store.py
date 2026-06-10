"""Session Store — 读取 ~/.claude/projects 下的 SDK 会话历史

claude-agent-sdk 自动将会话保存为 .jsonl 文件:
    ~/.claude/projects/<project-dir>/<session_id>.jsonl

每条记录是一个 JSON 对象，包含 type, message, attachment 等字段。
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional


def _get_project_dir() -> str:
    """找到当前项目对应的 .claude/projects 目录。

    路径格式: ~/.claude/projects/-Users-gtc-Learning------finalreport-tax-agent
    """
    base = os.path.expanduser("~/.claude/projects")
    cwd = os.getcwd()
    # 将路径中的 / 替换为 -，去掉开头的 -
    sanitized = cwd.replace("/", "-").lstrip("-")

    # 尝试精确匹配
    for name in os.listdir(base):
        if sanitized in name:
            return os.path.join(base, name)

    # 回退：找包含 finalreport-tax-agent 的目录（排除 scripts 子目录）
    for name in os.listdir(base):
        if "finalreport-tax-agent" in name and "scripts" not in name:
            return os.path.join(base, name)

    return ""


def list_sessions() -> list[dict]:
    """列出所有历史会话摘要。

    Returns:
        按时间倒序排列的会话列表，每个会话包含:
            session_id, created_at, updated_at, message_count, preview
    """
    project_dir = _get_project_dir()
    if not project_dir or not os.path.isdir(project_dir):
        return []

    sessions = []
    for fname in os.listdir(project_dir):
        if not fname.endswith(".jsonl"):
            continue

        session_id = fname[:-6]  # strip .jsonl
        path = os.path.join(project_dir, fname)

        try:
            with open(path) as f:
                lines = f.readlines()

            if not lines:
                continue

            created_at = None
            updated_at = None
            preview = ""
            msg_count = 0

            for line in lines:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts = record.get("timestamp")
                if ts:
                    if created_at is None:
                        created_at = ts
                    updated_at = ts

                rtype = record.get("type")
                if rtype == "user":
                    raw_content = record.get("message", {}).get("content", "")
                    if isinstance(raw_content, str) and raw_content:
                        preview = raw_content[:80]
                        msg_count += 1
                    elif isinstance(raw_content, list) and raw_content:
                        # content is array (tool_result, etc.)
                        first = raw_content[0]
                        if isinstance(first, dict) and first.get("type") == "tool_result":
                            preview = "[工具结果]"
                        else:
                            preview = str(first)[:80]
                        msg_count += 1
                elif rtype == "queue-operation" and record.get("operation") == "enqueue":
                    content = record.get("content", "")
                    if content and isinstance(content, str) and not preview:
                        preview = content[:80]
                elif rtype == "assistant" and record.get("content"):
                    # assistant messages may be embedded differently
                    pass

            sessions.append({
                "session_id": session_id,
                "created_at": created_at,
                "updated_at": updated_at,
                "message_count": msg_count,
                "preview": preview or "(空会话)",
            })
        except Exception:
            continue

    # 按 updated_at 倒序
    sessions.sort(key=lambda s: s.get("updated_at") or "", reverse=True)
    return sessions


def get_session_messages(session_id: str) -> list[dict]:
    """获取指定会话的完整对话记录。

    Args:
        session_id: 会话 UUID（即 .jsonl 文件名）

    Returns:
        消息列表，每条消息包含 role, content, timestamp
    """
    project_dir = _get_project_dir()
    if not project_dir:
        return []

    path = os.path.join(project_dir, f"{session_id}.jsonl")
    if not os.path.exists(path):
        return []

    messages = []
    with open(path) as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            rtype = record.get("type")
            ts = record.get("timestamp", "")

            # 用户消息
            if rtype == "user":
                msg = record.get("message", {})
                if msg.get("content"):
                    messages.append({
                        "role": "user",
                        "content": msg["content"],
                        "timestamp": ts,
                    })

            # 助手消息（可能有多种格式）
            elif rtype == "assistant":
                content_parts = []
                for block in record.get("content", []):
                    if isinstance(block, dict):
                        if block.get("type") == "text" and block.get("text"):
                            content_parts.append(block["text"])
                        elif block.get("type") == "thinking" and block.get("thinking"):
                            content_parts.append(f"[思考: {block['thinking']}]")
                if content_parts:
                    messages.append({
                        "role": "assistant",
                        "content": "\n".join(content_parts),
                        "timestamp": ts,
                    })

            # 工具调用结果
            elif rtype == "tool_result":
                content = record.get("content", "")
                if content:
                    messages.append({
                        "role": "tool",
                        "content": str(content),
                        "timestamp": ts,
                    })

            # queue-operation 中的用户消息（如果还没被 user 类型覆盖）
            elif rtype == "queue-operation":
                op = record.get("operation")
                content = record.get("content", "")
                if op == "enqueue" and content:
                    # 检查是否已作为 user 消息存在
                    if not messages or messages[-1].get("content") != content:
                        messages.append({
                            "role": "user",
                            "content": content,
                            "timestamp": ts,
                        })

    return messages


def delete_session(session_id: str) -> bool:
    """删除指定会话文件。

    Args:
        session_id: 会话 UUID

    Returns:
        是否成功删除
    """
    project_dir = _get_project_dir()
    if not project_dir:
        return False

    path = os.path.join(project_dir, f"{session_id}.jsonl")
    try:
        if os.path.exists(path):
            os.remove(path)
            return True
    except Exception:
        pass
    return False
