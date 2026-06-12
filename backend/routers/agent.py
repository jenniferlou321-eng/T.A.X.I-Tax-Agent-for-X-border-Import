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

from backend.agent import TaxAgentEngine
from backend.agent.agui_adapter import stream_agui_events
from backend.agent.session_store import list_sessions, get_session_messages, delete_session

# AG-UI 协议标准请求体类型（threadId/runId/messages/state/...）。
# 当 `ag-ui-protocol` 不可用时降级为 Any — 这样 dev 环境也能 import。
try:
    from ag_ui.core import RunAgentInput
except Exception:  # pragma: no cover — 极少见，依赖未装
    RunAgentInput = None  # type: ignore[assignment]

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


# ── HTTP SSE 聊天接口 (AG-UI 兼容) ──

@router.post("/chat")
async def agent_chat(
    session_id: Optional[str] = Query(None),
    message: str = Query(...),
    raw_data: Optional[str] = Query(None),
    thread_id: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
):
    """HTTP SSE 流式聊天接口 (AG-UI 兼容)

    保留 query string 入口（dashboard / loadSampleData 路径）以避免破坏
    前端现有调用。**输出**遵循 AG-UI 事件协议：data: {type:..., ...}\\n\\n
    事件序列 (RUN_STARTED → TEXT_MESSAGE_* → RUN_FINISHED 等)，不再
    是旧的 {chunk, session_id, done} 格式。

    如需走标准 AG-UI 请求体，使用 POST /api/agent/agui 端点。
    """
    engine = get_engine()
    sid = session_id or str(uuid.uuid4())
    tid = thread_id or sid   # AG-UI thread_id 与 session_id 双向映射
    rid = run_id or str(uuid.uuid4())

    # 解析原始业务数据
    raw_business_data = None
    if raw_data:
        try:
            raw_business_data = json.loads(raw_data)
        except json.JSONDecodeError:
            pass

    async def event_stream():
        async for sse in stream_agui_events(
            thread_id=tid,
            run_id=rid,
            engine=engine,
            session=engine._get_or_create_session(sid),
            user_message=message,
            raw_business_data=raw_business_data,
        ):
            yield sse

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
    )


# ── 标准 AG-UI 协议端点 ──

@router.post("/agui")
async def agent_agui(input_data: "RunAgentInput"):
    """标准 AG-UI 协议端点 — body 为 RunAgentInput
    (threadId/runId/messages/state/tools/context/forwardedProps)。

    客户端应:
      POST /api/agent/agui
      Content-Type: application/json
      Accept: text/event-stream
      Body: {"threadId":"...","runId":"...","messages":[{...}]}

    响应: text/event-stream + AG-UI 事件序列 (RUN_STARTED → ... → RUN_FINISHED)。
    """
    if RunAgentInput is None:
        raise HTTPException(
            status_code=503,
            detail="ag-ui-protocol package not installed. pip install ag-ui-protocol",
        )
    engine = get_engine()
    sid = input_data.thread_id

    # 把 AG-UI 的 messages 列表拍平成一条 user_message
    # （T.A.X.I. engine.chat 当前只接单条 user 消息；多轮历史由
    # session 内部维护，无需前端重复传）
    user_message = ""
    for m in reversed(input_data.messages or []):
        if m.role == "user" and m.content:
            user_message = m.content
            break

    async def event_stream():
        async for sse in stream_agui_events(
            thread_id=input_data.thread_id,
            run_id=input_data.run_id,
            engine=engine,
            session=engine._get_or_create_session(sid),
            user_message=user_message,
        ):
            yield sse

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
    """获取 TechFlow 跨境集团示例企业数据（CN 母公司 + UK 子公司）"""
    from pathlib import Path

    # 单一来源：frontend 资产, 后端为前端兜底也读它（不要在 repo-root data/ 另放副本）
    _root = Path(__file__).resolve().parent.parent.parent
    sample = _root / "frontend" / "src" / "data" / "realCaseData.json"
    if not sample.is_file():
        raise HTTPException(status_code=404, detail="Sample data not found")
    with open(sample, "r", encoding="utf-8") as f:
        return json.load(f)


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
