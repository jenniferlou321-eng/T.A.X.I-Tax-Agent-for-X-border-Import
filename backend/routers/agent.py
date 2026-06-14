"""Agent 聊天路由 — WebSocket + HTTP SSE 双模式

提供与 TaxAgent Engine 的实时对话接口。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, Response
from fastapi.responses import StreamingResponse, JSONResponse

from backend.agent import TaxAgentEngine
from backend.agent.agui_adapter import stream_agui_events
from backend.agent.session_store import list_sessions, get_session_messages, delete_session
from backend.agent.workspace_store import AGENT_WORKSPACE_ROOT, clear_agent_workspace, mount_cases

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
    response: Response,
    session_id: Optional[str] = Query(None),
    message: str = Query(...),
    raw_data: Optional[str] = Query(None),
    case_id: Optional[str] = Query(None),
    case_ids: Optional[str] = Query(None),  # 多管辖地:逗号分隔
    thread_id: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
):
    """HTTP SSE 流式聊天接口 (AG-UI 兼容)

    case_ids 优先(多管辖地):逗号分隔的 case_id 列表,后端为每个创建 JurisdictionSlot。
    case_id 单个(向后兼容)。
    raw_data 保留兼容老客户端。

    错误处理:任何在第一个 SSE 事件之前的失败(例如 engine 未初始化),会返回
    JSON 错误体 `{detail, kind, hint, request_id}` + 4xx/5xx 状态码 + X-Request-Id
    头,供前端 ErrorCard 直接消费。
    """
    # 给这次 run 一个稳定 id,响应头带回,失败时也回在 JSON body 里。
    request_id = str(uuid.uuid4())
    response.headers["X-Request-Id"] = request_id

    try:
        engine = get_engine()
    except Exception as e:
        from backend.agent.agui_adapter import _classify_error
        kind, hint = _classify_error(e)
        return JSONResponse(
            status_code=503,
            content={
                "detail": f"{type(e).__name__}: {e}",
                "kind": kind,
                "hint": hint,
                "request_id": request_id,
            },
            headers={"X-Request-Id": request_id},
        )

    sid = session_id or str(uuid.uuid4())
    tid = thread_id or sid
    rid = run_id or str(uuid.uuid4())

    raw_business_data = None
    if raw_data:
        try:
            raw_business_data = json.loads(raw_data)
        except json.JSONDecodeError:
            pass

    parsed_case_ids = case_ids.split(",") if case_ids else None

    async def event_stream():
        async for sse in stream_agui_events(
            thread_id=tid,
            run_id=rid,
            engine=engine,
            session=engine._get_or_create_session(sid),
            user_message=message,
            raw_business_data=raw_business_data,
            case_id=case_id,
            case_ids=parsed_case_ids,
            request_id=request_id,
        ):
            yield sse

    # 流式响应:包一层,确保启动期(还没 yield 第一个 event 就死)也能给前端
    # 看到结构化错误,而不是一段莫名其妙的 500 + 空 body。
    async def safe_event_stream():
        try:
            async for sse in event_stream():
                yield sse
        except Exception as e:
            # 走到这里说明在 RUN_STARTED 之后、stream 中途崩了 — 走 RUN_ERROR 路径
            # 已经发不出来,只能直接发一个 RUN_ERROR SSE 事件。借助 agui_adapter
            # 的分类器保持一致的 kind/hint。
            from ag_ui.core import EventType, RunErrorEvent
            from ag_ui.encoder import EventEncoder
            from backend.agent.agui_adapter import _classify_error
            kind, hint = _classify_error(e)
            enc = EventEncoder()
            yield enc.encode(
                RunErrorEvent(
                    type=EventType.RUN_ERROR,
                    message=f"{type(e).__name__}: {e}",
                    code=kind,
                    errorKind=kind,
                    errorHint=hint,
                    requestId=request_id,
                )
            )

    return StreamingResponse(
        safe_event_stream(),
        media_type="text/event-stream",
        headers={"X-Request-Id": request_id},
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

    # AG-UI 标准 body 没有 case_id 字段;从 forwardedProps / state 提取
    case_id = None
    case_ids = None
    if getattr(input_data, "forwarded_props", None):
        case_id = input_data.forwarded_props.get("case_id")
        case_ids_str = input_data.forwarded_props.get("case_ids")
        if case_ids_str:
            case_ids = case_ids_str.split(",")
    if not case_id and getattr(input_data, "state", None):
        case_id = input_data.state.get("case_id") if isinstance(input_data.state, dict) else None

    async def event_stream():
        async for sse in stream_agui_events(
            thread_id=input_data.thread_id,
            run_id=input_data.run_id,
            engine=engine,
            session=engine._get_or_create_session(sid),
            user_message=user_message,
            case_id=case_id,
            case_ids=case_ids,
            request_id=str(uuid.uuid4()),
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
            case_id = data.get("case_id")
            # 多管辖地:case_ids 为逗号分隔字符串
            case_ids_str = data.get("case_ids")
            case_ids = case_ids_str.split(",") if case_ids_str else None

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
                case_id=case_id,
                case_ids=case_ids,
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


# ── Agent active workspace 接口 ──

@router.post("/workspace/cases/{case_id}")
async def mount_agent_workspace_case(case_id: str):
    """把前端当前选择的 case 复制到固定 Agent 工作目录。

    目录固定为 ~/.taxi/agent_workspace/。每次 mount 都先清空旧内容,避免
    Agent 看到上一次选择的 case。
    """
    mounted = mount_cases([case_id])
    _, manifest = mounted[0]
    return {
        "workspace_path": str(AGENT_WORKSPACE_ROOT),
        "manifest": manifest,
    }


@router.delete("/workspace")
async def clear_agent_workspace_api():
    """清空固定 Agent 工作目录。前端"清空数据"按钮会调用它。"""
    return {"workspace_path": clear_agent_workspace(), "cleared": True}


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
