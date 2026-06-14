"""TaxAgentEngine → AG-UI 事件适配层。

把 `engine.chat(...)` 内部 yield 的标准化 payload 转成
[AG-UI](https://github.com/ag-ui-protocol/ag-ui) 协议事件，再用
`ag_ui.encoder.EventEncoder` 编码为 SSE 字节流输出到前端。

内部 payload 约定（由 engine.py 的 _sdk_chat / _httpx_chat / _mock_chat 产出）：
    - str        — 文本片段（直接显示给用户）
    - dict{"__agui__": "tool_*"|"step_*", ...} — 结构化 AG-UI 信号

所有 SDK 客户端 / MCP 状态仍归 `engine._sdk_chat`；本模块只做转换。
"""
from __future__ import annotations

import uuid
from typing import Any, AsyncIterator, List, Optional

from ag_ui.core import (
    EventType,
    ReasoningEndEvent,
    ReasoningMessageContentEvent,
    ReasoningMessageEndEvent,
    ReasoningMessageStartEvent,
    ReasoningStartEvent,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)
from ag_ui.encoder import EventEncoder


def _classify_error(e: BaseException) -> tuple[str, str]:
    """把异常分类成 (kind, hint),给前端 ErrorCard 用。

    kind 取值固定集合:network / auth / timeout / validation / rate_limit / internal。
    hint 是一行"人话"指引,例如"检查 agent_provider.local.json 的 api_key 是否设置"。

    顺序很关键 — Python 3.11 里 TimeoutError / PermissionError 都是 OSError 子类,
    所以先按 string match 分类,最后才用 isinstance。
    """
    etype = type(e).__name__
    msg = str(e)
    low = msg.lower()

    # 限流(消息里有 "rate" + "limit" 或状态码 429)
    if ("rate" in low and "limit" in low) or "429" in msg:
        return ("rate_limit", "触发 LLM 限流。稍候重试,或升级 API 套餐。")
    # 超时
    if "timeout" in low or "timed out" in low or etype == "TimeoutError":
        return ("timeout", "上游 LLM 响应超时。可重试,或在 .env 调高 SDK_TIMEOUT。")
    # 鉴权
    if (
        "api key" in low
        or "unauthorized" in low
        or "authentication" in low
        or "401" in msg
        or "403" in msg
        or etype in ("AuthenticationError", "PermissionDeniedError")
    ):
        return (
            "auth",
            "API key 无效或缺失。检查 agent_provider.local.json 的 api_key 是否正确、是否过期。",
        )
    # 网络层(SDK/CLI 子进程 / httpx 连不上)— 必须放鉴权/超时之后,
    # 否则 ConnectionRefusedError / TimeoutError / PermissionError 这些 OSError 子类
    # 会被一刀切。
    if (
        isinstance(e, (ConnectionError,))
        or etype in ("ConnectionRefusedError", "ConnectionResetError", "EOFError")
        or "connection" in low
        or "eof" in low
    ):
        return (
            "network",
            "后端连不上上游 LLM 服务。检查 agent_provider.local.json 的 base_url / 网络是否能访问。",
        )
    # 校验
    if etype in ("ValueError", "TypeError", "KeyError", "ValidationError"):
        return (
            "validation",
            "输入数据或工具参数校验失败。检查 case_id / line_items 是否与模板一致。",
        )
    # 兜底
    return (
        "internal",
        f"未分类错误({etype})。复制右侧 Details 贴给开发,或查 logs/sdk-debug.log。",
    )


class _AguiStreamState:
    """Per-run mutable state for AG-UI event sequencing.

    Holds the current `text_msg_id` (for accumulating `TEXT_MESSAGE_CONTENT`
    deltas), the `tool_parent_msg_id` (set when a `TOOL_CALL_START` opens a
    block — used as the `messageId` on the subsequent `TOOL_CALL_RESULT`),
    and the open/close flags so the start/end events are emitted exactly
    once per logical handle.
    """

    def __init__(self) -> None:
        self.text_msg_id: str = str(uuid.uuid4())
        self.text_open: bool = False
        self.tool_parent_msg_id: Optional[str] = None
        self.tool_open: bool = False
        self.step_open: bool = False
        self.current_step_name: str = ""
        # 扩展思考（extended thinking）：与 text / tool 并行的独立句柄。
        # 模型可同时开着 text + reasoning（先思考再开口）；
        # 我们的协议允许多个 content handle 共存。
        self.reasoning_msg_id: str = str(uuid.uuid4())
        self.reasoning_open: bool = False
        # 请求级 trace id:由 router 在调 stream_agui_events 之前 set,
        # 透传到 RUN_ERROR 事件,前端可贴进工单 / 拿来和 logs/sdk-debug.log 对照。
        self.request_id: str = ""


async def stream_agui_events(
    *,
    thread_id: str,
    run_id: Optional[str],
    engine: Any,
    session: Any,
    user_message: str,
    raw_business_data: Optional[dict] = None,
    uploaded_data: Optional[list] = None,
    case_id: Optional[str] = None,
    case_ids: Optional[list[str]] = None,
    request_id: Optional[str] = None,
) -> AsyncIterator[str]:
    """运行 engine.chat 并把内部 yield 转成 SSE 字符串（AG-UI 格式）。

    request_id: 透传到 RUN_ERROR 事件,便于和 logs/sdk-debug.log 对照。允许外部
    传入(由 router 生成);不传则自动生成一个。
    """
    enc = EventEncoder()
    rid = run_id or str(uuid.uuid4())
    st = _AguiStreamState()
    st.request_id = request_id or str(uuid.uuid4())

    # ── 1) lifecycle: RUN_STARTED ──
    yield enc.encode(
        RunStartedEvent(
            type=EventType.RUN_STARTED,
            thread_id=thread_id,
            run_id=rid,
        )
    )

    async def _open_text() -> List[str]:
        if not st.text_open:
            st.text_open = True
            return [
                enc.encode(
                    TextMessageStartEvent(
                        type=EventType.TEXT_MESSAGE_START,
                        message_id=st.text_msg_id,
                        role="assistant",
                    )
                )
            ]
        return []

    async def _close_text() -> List[str]:
        if st.text_open:
            st.text_open = False
            closed_id = st.text_msg_id
            st.text_msg_id = str(uuid.uuid4())
            return [
                enc.encode(
                    TextMessageEndEvent(
                        type=EventType.TEXT_MESSAGE_END,
                        message_id=closed_id,
                    )
                )
            ]
        return []

    async def _open_reasoning() -> List[str]:
        # 思考句柄与 text 并行：可同时为"open"。idempotent — 重复 open
        # 不产生新事件。首段 REASONING_* 事件由 reasoning_content 路径
        # 触发（self-healing），所以 reasoning_start 单独触发时不强制 open。
        if not st.reasoning_open:
            st.reasoning_open = True
            return [
                enc.encode(
                    ReasoningStartEvent(
                        type=EventType.REASONING_START,
                        message_id=st.reasoning_msg_id,
                    )
                ),
                enc.encode(
                    ReasoningMessageStartEvent(
                        type=EventType.REASONING_MESSAGE_START,
                        message_id=st.reasoning_msg_id,
                        role="reasoning",
                    )
                ),
            ]
        return []

    async def _close_reasoning() -> List[str]:
        if st.reasoning_open:
            st.reasoning_open = False
            closed_id = st.reasoning_msg_id
            st.reasoning_msg_id = str(uuid.uuid4())
            return [
                enc.encode(
                    ReasoningMessageEndEvent(
                        type=EventType.REASONING_MESSAGE_END,
                        message_id=closed_id,
                    )
                ),
                enc.encode(
                    ReasoningEndEvent(
                        type=EventType.REASONING_END,
                        message_id=closed_id,
                    )
                ),
            ]
        return []

    try:
        async for chunk in engine.chat(
            session.session_id,
            user_message,
            uploaded_data=uploaded_data,
            raw_business_data=raw_business_data,
            case_id=case_id,
            case_ids=case_ids,
        ):
            # ── 文本片段 ──
            if isinstance(chunk, str):
                for sse in await _open_text():
                    yield sse
                yield enc.encode(
                    TextMessageContentEvent(
                        type=EventType.TEXT_MESSAGE_CONTENT,
                        message_id=st.text_msg_id,
                        delta=chunk,
                    )
                )
                continue

            # ── 结构化 AG-UI 信号 ──
            if isinstance(chunk, dict):
                kind = chunk.get("__agui__")

                if kind == "reasoning_start":
                    # 思考段：与 text 互不干扰 — 我们不主动 close text，
                    # 允许两个句柄同时 open（Anthropic 也是这么发的）。
                    for sse in await _open_reasoning():
                        yield sse

                elif kind == "reasoning_content":
                    # self-healing：即使 engine 没显式 yield reasoning_start，
                    # 收到第一条 delta 时也补发 START。
                    for sse in await _open_reasoning():
                        yield sse
                    yield enc.encode(
                        ReasoningMessageContentEvent(
                            type=EventType.REASONING_MESSAGE_CONTENT,
                            message_id=st.reasoning_msg_id,
                            delta=chunk["delta"],
                        )
                    )

                elif kind == "reasoning_end":
                    for sse in await _close_reasoning():
                        yield sse

                elif kind == "tool_start":
                    # 工具调用前关闭 text 流（如果还开着）
                    for sse in await _close_text():
                        yield sse
                    tc_id = chunk["tool_call_id"]
                    if not st.tool_open:
                        parent = (
                            chunk.get("parent_message_id")
                            or st.tool_parent_msg_id
                            or st.text_msg_id
                        )
                        yield enc.encode(
                            ToolCallStartEvent(
                                type=EventType.TOOL_CALL_START,
                                tool_call_id=tc_id,
                                tool_call_name=chunk["tool_name"],
                                parent_message_id=parent,
                            )
                        )
                        st.tool_open = True
                        st.tool_parent_msg_id = tc_id

                elif kind == "tool_args":
                    yield enc.encode(
                        ToolCallArgsEvent(
                            type=EventType.TOOL_CALL_ARGS,
                            tool_call_id=chunk["tool_call_id"],
                            delta=chunk["delta"],
                        )
                    )

                elif kind == "tool_end":
                    yield enc.encode(
                        ToolCallEndEvent(
                            type=EventType.TOOL_CALL_END,
                            tool_call_id=chunk["tool_call_id"],
                        )
                    )
                    st.tool_open = False

                elif kind == "tool_result":
                    yield enc.encode(
                        ToolCallResultEvent(
                            type=EventType.TOOL_CALL_RESULT,
                            message_id=st.tool_parent_msg_id or st.text_msg_id,
                            tool_call_id=chunk["tool_call_id"],
                            content=chunk["content"],
                        )
                    )

                elif kind == "step_start":
                    # 自动关闭前一个 step（如有），再开新 step
                    if st.step_open:
                        yield enc.encode(
                            StepFinishedEvent(
                                type=EventType.STEP_FINISHED,
                                step_name=st.current_step_name,
                            )
                        )
                    yield enc.encode(
                        StepStartedEvent(
                            type=EventType.STEP_STARTED,
                            step_name=chunk["step_name"],
                        )
                    )
                    st.step_open = True
                    st.current_step_name = chunk["step_name"]

                elif kind == "step_end":
                    if st.step_open:
                        yield enc.encode(
                            StepFinishedEvent(
                                type=EventType.STEP_FINISHED,
                                step_name=st.current_step_name,
                            )
                        )
                        st.step_open = False
                        st.current_step_name = ""

                # 未知 kind 静默忽略
                continue

            # 其它类型 chunk（None 等）— 忽略

        # ── 收尾：关闭任何还开着的 handle ──
        for sse in await _close_text():
            yield sse
        for sse in await _close_reasoning():
            yield sse
        if st.tool_open:
            yield enc.encode(
                ToolCallEndEvent(
                    type=EventType.TOOL_CALL_END,
                    tool_call_id=st.tool_parent_msg_id or "(unknown)",
                )
            )
        if st.step_open:
            yield enc.encode(
                StepFinishedEvent(
                    type=EventType.STEP_FINISHED,
                    step_name=st.current_step_name or "(inferred)",
                )
            )
            st.step_open = False
            st.current_step_name = ""

        # ── lifecycle: RUN_FINISHED ──
        yield enc.encode(
            RunFinishedEvent(
                type=EventType.RUN_FINISHED,
                thread_id=thread_id,
                run_id=rid,
            )
        )

    except Exception as e:  # noqa: BLE001 — 顶层兜底，任何异常转 RUN_ERROR
        # 先关掉残留 handle，再发 RUN_ERROR
        if st.text_open:
            try:
                yield enc.encode(
                    TextMessageEndEvent(
                        type=EventType.TEXT_MESSAGE_END,
                        message_id=st.text_msg_id,
                    )
                )
            except Exception:
                pass
            st.text_open = False
        if st.reasoning_open:
            try:
                for sse in await _close_reasoning():
                    yield sse
            except Exception:
                pass
            st.reasoning_open = False
        if st.tool_open:
            try:
                yield enc.encode(
                    ToolCallEndEvent(
                        type=EventType.TOOL_CALL_END,
                        tool_call_id=st.tool_parent_msg_id or "(unknown)",
                    )
                )
            except Exception:
                pass
            st.tool_open = False
        if st.step_open:
            try:
                yield enc.encode(
                    StepFinishedEvent(
                        type=EventType.STEP_FINISHED,
                        step_name=st.current_step_name or "(error)",
                    )
                )
            except Exception:
                pass
            st.step_open = False
            st.current_step_name = ""
        # ── 增强的 RUN_ERROR payload（前端 ErrorCard 直接消费）
        # ConfiguredBaseModel 开了 extra="allow" (ag_ui/core/types.py:12-19)，
        # 所以下面这些字段会随 SSE 一起序列化到前端。
        kind, hint = _classify_error(e)
        yield enc.encode(
            RunErrorEvent(
                type=EventType.RUN_ERROR,
                message=f"{type(e).__name__}: {e}",
                code=kind,
                # 额外字段(extra="allow"):
                errorKind=kind,
                errorHint=hint,
                errorStage=st.current_step_name or None,
                requestId=st.request_id,
            )
        )
