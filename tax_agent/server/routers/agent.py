"""Agent 聊天路由 — WebSocket + HTTP SSE 双模式

提供与 TaxAgent Engine 的实时对话接口。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException
from fastapi.responses import StreamingResponse

from tax_agent.agent import TaxAgentEngine
from tax_agent.agent.session_store import list_sessions, get_session_messages, delete_session

router = APIRouter(prefix="/agent", tags=["agent"])

# 全局引擎实例（由 lifespan 注入）
_engine: Optional[TaxAgentEngine] = None


def set_engine(engine: TaxAgentEngine) -> None:
    """在应用启动时设置全局引擎实例"""
    global _engine
    _engine = engine


def get_engine() -> TaxAgentEngine:
    """获取全局引擎实例"""
    if _engine is None:
        raise RuntimeError("Agent engine not initialized")
    return _engine


# ── HTTP SSE 聊天接口 ──

@router.post("/chat")
async def agent_chat(
    session_id: Optional[str] = Query(None),
    message: str = Query(...),
    raw_data: Optional[str] = Query(None),
):
    """HTTP SSE 流式聊天接口

    适合前端使用 EventSource 接收流式响应。
    支持通过 raw_data 参数传递原始企业 JSON 数据。
    """
    engine = get_engine()
    sid = session_id or str(uuid.uuid4())

    # 解析原始业务数据
    raw_business_data = None
    if raw_data:
        try:
            raw_business_data = json.loads(raw_data)
        except json.JSONDecodeError:
            pass

    async def event_stream():
        async for chunk in engine.chat(sid, message, raw_business_data=raw_business_data):
            # SSE 格式: data: {...}\n\n
            payload = json.dumps({"chunk": chunk, "session_id": sid})
            yield f"data: {payload}\n\n"
        yield f"data: {json.dumps({'done': True, 'session_id': sid})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
    )


# ── WebSocket 实时聊天接口 ──

@router.websocket("/ws/chat")
async def agent_websocket(websocket: WebSocket):
    """WebSocket 实时聊天接口

    前端连接后发送 JSON: {"session_id": "...", "message": "..."}
    服务端流式返回文本片段。
    """
    await websocket.accept()
    engine = get_engine()

    try:
        while True:
            # 接收用户消息
            data = await websocket.receive_json()
            session_id = data.get("session_id") or str(uuid.uuid4())
            message = data.get("message", "")
            uploaded = data.get("data")

            # 发送会话 ID（首次）
            await websocket.send_json({
                "type": "session",
                "session_id": session_id,
            })

            # 解析原始业务数据
            raw_business_data = None
            if uploaded and isinstance(uploaded, dict) and "company" in uploaded:
                raw_business_data = uploaded
                uploaded = None  # 原始数据不走 line_items 路径

            # 流式发送 Agent 响应
            async for chunk in engine.chat(
                session_id, message,
                uploaded_data=uploaded,
                raw_business_data=raw_business_data,
            ):
                await websocket.send_json({
                    "type": "chunk",
                    "content": chunk,
                })

            # 发送结束标记
            await websocket.send_json({
                "type": "done",
                "session_id": session_id,
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "error": str(e),
        })


# ── 会话状态查询 ──

@router.get("/status/{session_id}")
async def get_session_status(session_id: str):
    """查询 Agent 会话状态"""
    engine = get_engine()
    return await engine.get_status(session_id)


@router.get("/health")
async def agent_health():
    """Agent 服务健康检查"""
    engine = get_engine()
    return {
        "status": "ok",
        "sdk_available": engine._mcp_servers is not None,
        "jurisdictions_loaded": list(engine._mcp_servers.keys()) if engine._mcp_servers else [],
    }


# ── 示例数据接口 ──

@router.get("/sample-data")
async def get_sample_data():
    """获取 TechFlow Distribution Ltd 示例企业数据"""
    import os
    from pathlib import Path

    # 尝试多个可能的路径
    paths = [
        Path(__file__).parent.parent.parent / "data" / "realCaseData.json",
        Path(__file__).parent.parent.parent.parent / "frontend" / "src" / "data" / "realCaseData.json",
    ]

    for p in paths:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)

    raise HTTPException(status_code=404, detail="Sample data not found")


# ── 历史会话接口（读取 ~/.claude/projects 下的 SDK 会话文件） ──

@router.get("/sessions")
async def get_sessions():
    """获取历史会话列表

    从 ~/.claude/projects/ 下读取 claude-agent-sdk 自动保存的 .jsonl 会话文件。
    按时间倒序排列。
    """
    return {"sessions": list_sessions()}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages_api(session_id: str):
    """获取指定会话的完整对话记录"""
    messages = get_session_messages(session_id)
    return {
        "session_id": session_id,
        "messages": messages,
        "count": len(messages),
    }


@router.delete("/sessions/{session_id}")
async def delete_session_api(session_id: str):
    """删除指定会话"""
    success = delete_session(session_id)
    return {"success": success, "session_id": session_id}
