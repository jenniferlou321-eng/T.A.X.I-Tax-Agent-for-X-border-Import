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
        # 扩展思考（extended thinking）：与 text / tool 并行的独立句柄。
        # 模型可同时开着 text + reasoning（先思考再开口）；
        # 我们的协议允许多个 content handle 共存。
        self.reasoning_msg_id: str = str(uuid.uuid4())
        self.reasoning_open: bool = False


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
) -> AsyncIterator[str]:
    """运行 engine.chat 并把内部 yield 转成 SSE 字符串（AG-UI 格式）。"""
    enc = EventEncoder()
    rid = run_id or str(uuid.uuid4())
    st = _AguiStreamState()

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
                    if not st.step_open:
                        yield enc.encode(
                            StepStartedEvent(
                                type=EventType.STEP_STARTED,
                                step_name=chunk["step_name"],
                            )
                        )
                        st.step_open = True

                elif kind == "step_end":
                    if st.step_open:
                        yield enc.encode(
                            StepFinishedEvent(
                                type=EventType.STEP_FINISHED,
                                step_name=chunk["step_name"],
                            )
                        )
                        st.step_open = False

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
                    step_name="(inferred)",
                )
            )

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
        yield enc.encode(
            RunErrorEvent(
                type=EventType.RUN_ERROR,
                message=f"{type(e).__name__}: {e}",
            )
        )
