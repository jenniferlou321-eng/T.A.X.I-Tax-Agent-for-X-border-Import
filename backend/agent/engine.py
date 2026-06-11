"""TaxAgent Engine — Claude Agent SDK 核心引擎（多管辖地版）

基于 ClaudeSDKClient 的智能报税 Agent。
支持多管辖地/税种的动态 MCP Server 切换。
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

import httpx  # 用于 SDK 不可用时直连 MiniMax /v1/messages

from .prompts import get_system_prompt
from .tools import (
    create_mcp_servers,
    get_allowlist_for,
    SDK_AVAILABLE,
    set_registry,
)

# ── SDK 导入（带优雅降级） ──
if SDK_AVAILABLE:
    from claude_agent_sdk import (
        ClaudeSDKClient,
        ClaudeAgentOptions,
        AssistantMessage,
        TextBlock,
        ThinkingBlock,
        ToolUseBlock,
        ToolResultBlock,
        ResultMessage,
        StreamEvent,
        SystemMessage,
    )
else:
    class _MsgBase:
        pass

    AssistantMessage = _MsgBase
    TextBlock = _MsgBase
    ThinkingBlock = _MsgBase
    ToolUseBlock = _MsgBase
    ToolResultBlock = _MsgBase
    ResultMessage = _MsgBase
    StreamEvent = _MsgBase
    SystemMessage = _MsgBase

    class _ClientBase:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def query(self, prompt: str, session_id: str = "default"):
            pass
        async def receive_response(self):
            return []
        async def set_permission_mode(self, mode: str):
            pass
        async def disconnect(self):
            pass

    ClaudeSDKClient = _ClientBase  # type: ignore

    class _OptsBase:
        def __init__(self, **kwargs):
            pass
    ClaudeAgentOptions = _OptsBase  # type: ignore


# ═══════════════════════════════════════════════════════════
# Session State
# ═══════════════════════════════════════════════════════════

@dataclass
class AgentSession:
    """Agent 会话状态（补充 SDK 原生会话的元数据）"""
    session_id: str
    user_id: str = "anonymous"
    jurisdiction: str = ""           # 空字符串 = 未确定，由首次交互推断
    tax_type: str = "vat"
    taxpayer_id: str = ""            # 通用纳税人识别号（VRN, Steuernummer, USCC 等）
    period_key: str = ""
    status: str = "idle"             # idle | chatting | calculating | confirming | submitting | done
    line_items: list[dict] = field(default_factory=list)
    raw_business_data: Optional[dict] = None
    messages: list[dict] = field(default_factory=list)
    # SDK client cache (按 jurisdiction 缓存，切换 jurisdiction 时重建)
    _clients: dict[str, ClaudeSDKClient] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════
# TaxAgent Engine
# ═══════════════════════════════════════════════════════════

class TaxAgentEngine:
    """TaxAgent 智能报税引擎（多管辖地）

    支持:
        - 动态 MCP Server: 每个管辖地/税种独立 server
        - 动态工具白名单: 按 session.jurisdiction 过滤
        - 动态系统提示: 按 session.jurisdiction 加载对应法规知识

    用法:
        from backend import JurisdictionRegistry
        registry = JurisdictionRegistry()
        registry.register(UKJurisdictionAdapter())

        engine = TaxAgentEngine(registry=registry)
        async for chunk in engine.chat("session-1", "帮我报税"):
            print(chunk, end="")
    """

    def __init__(
        self,
        registry: Optional['JurisdictionRegistry'] = None,
        api_key: Optional[str] = None,
        cwd: Optional[str] = None,
        permission_mode: str = "bypassPermissions",
    ):
        # 支持两种 token env var 命名: ANTHROPIC_API_KEY (官方) / ANTHROPIC_AUTH_TOKEN (代理服务常用)
        self.api_key = (
            api_key
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or ""
        )
        self.cwd = cwd or os.getcwd()
        self.permission_mode = permission_mode
        self.sessions: dict[str, AgentSession] = {}

        # Claude Code CLI 以 root 运行时拒绝 --dangerously-skip-permissions，
        # 除非显式声明处于沙箱环境。本部署在容器内以 root 运行，故置位。
        os.environ.setdefault("IS_SANDBOX", "1")

        # Registry & MCP Servers
        self._registry = registry
        self._mcp_servers: dict[tuple[str, str], dict] = {}

        if registry:
            set_registry(registry)
            if SDK_AVAILABLE:
                self._mcp_servers = create_mcp_servers(registry)

        # SDK 不可用时给出清晰提示
        if not SDK_AVAILABLE:
            print("[WARN] claude-agent-sdk not installed. Engine runs in MOCK mode.")
            print("       Install: pip install claude-agent-sdk")

    # ── Public API ──

    async def chat(
        self,
        session_id: str,
        user_message: str,
        uploaded_data: Optional[list[dict]] = None,
        raw_business_data: Optional[dict] = None,
        jurisdiction: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """与 Agent 对话，流式返回响应文本。

        Args:
            session_id: 会话唯一标识
            user_message: 用户输入
            uploaded_data: 用户上传的 line items（可选）
            raw_business_data: 用户上传的原始企业数据（可选）
            jurisdiction: 强制指定管辖地（可选，否则从会话状态推断）

        Yields:
            流式文本片段
        """
        session = self._get_or_create_session(session_id)

        # 处理管辖地切换
        if jurisdiction:
            session.jurisdiction = jurisdiction
        # 如果 raw_business_data 中有公司信息，自动推断管辖地
        elif raw_business_data and not session.jurisdiction:
            # TODO: 根据 VAT scheme / 公司注册地推断
            session.jurisdiction = "uk"

        # 处理上传数据
        if uploaded_data:
            session.line_items = uploaded_data
            yield "📎 已接收上传数据，共 {} 条记录\n".format(len(uploaded_data))

        # 处理原始业务数据
        if raw_business_data:
            session.raw_business_data = raw_business_data
            company = raw_business_data.get("company", {})
            company_name = company.get("name", "Unknown")
            sales_count = len(raw_business_data.get("sales_invoices", []))
            purchase_count = len(raw_business_data.get("purchase_invoices", []))
            yield f"📎 已接收企业原始数据: {company_name}\n"
            yield f"   销售发票 {sales_count} 张, 采购发票 {purchase_count} 张\n"

        # 构建增强消息
        enriched_message = user_message
        if getattr(session, "raw_business_data", None):
            company = session.raw_business_data.get("company", {})
            tax_id = company.get("vrn", "")
            period_key = company.get("period", {}).get("period_key", "")
            data_summary = (
                f"\n\n[系统: 用户已上传完整企业原始数据]\n"
                f"公司名称: {company.get('name', '')}\n"
                f"纳税人识别号: {tax_id}\n"
                f"申报期间: {company.get('period', {}).get('label', '')} ({company.get('period', {}).get('start', '')} ~ {company.get('period', {}).get('end', '')})\n"
                f"数据包含: {len(session.raw_business_data.get('sales_invoices', []))} 张销售发票, "
                f"{len(session.raw_business_data.get('purchase_invoices', []))} 张采购发票, "
                f"{len(session.raw_business_data.get('expense_claims', []))} 条费用报销, "
                f"{len(session.raw_business_data.get('reverse_charge_transactions', []))} 条反向征收, "
                f"{len(session.raw_business_data.get('vat_adjustments', []))} 条 VAT 调整\n"
                f"\n你可以使用 analyze_business_data 工具分析这些数据，参数 company_data_json 为原始数据的 JSON 字符串。"
            )
            enriched_message += data_summary
            if tax_id:
                session.taxpayer_id = tax_id
            if period_key:
                session.period_key = period_key
        elif session.line_items and "数据" not in user_message and "data" not in user_message.lower():
            enriched_message += f"\n\n[系统: 用户已上传 {len(session.line_items)} 条 line items]"

        # 选择模式：
        #   - SDK 装了 + api_key → SDK 真模式
        #   - SDK 没装 + api_key + BASE_URL → httpx 直连 (MiniMax 等代理服务)
        #   - 都没 → mock 降级
        if SDK_AVAILABLE and self.api_key:
            async for chunk in self._sdk_chat(session, enriched_message):
                yield chunk
        elif self.api_key and os.environ.get("ANTHROPIC_BASE_URL"):
            # SDK 缺失但有 key + 自定义 endpoint — 直接 httpx 调
            jurisdiction = session.jurisdiction or "uk"
            tax_type = session.tax_type or "vat"
            try:
                system_prompt = get_system_prompt(jurisdiction, tax_type)
            except Exception:
                system_prompt = "You are T.A.X.I., a helpful tax filing assistant."
            async for chunk in self._httpx_chat(
                session=session, user_message=enriched_message, system_prompt=system_prompt,
            ):
                yield chunk
        else:
            async for chunk in self._mock_chat(session, enriched_message):
                yield chunk

        # 保存对话历史
        session.messages.append({"role": "user", "content": user_message})

    async def get_status(self, session_id: str) -> dict:
        """获取会话当前状态"""
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        return {
            "session_id": session.session_id,
            "status": session.status,
            "jurisdiction": session.jurisdiction,
            "tax_type": session.tax_type,
            "taxpayer_id": session.taxpayer_id,
            "period_key": session.period_key,
            "line_items_count": len(session.line_items),
            "message_count": len(session.messages),
            "sdk_available": SDK_AVAILABLE,
        }

    async def reset_session(self, session_id: str) -> None:
        """重置会话状态并清理所有 SDK clients"""
        session = self.sessions.get(session_id)
        if session:
            for client in session._clients.values():
                try:
                    await client.disconnect()
                except Exception:
                    pass
            session._clients.clear()
        if session_id in self.sessions:
            del self.sessions[session_id]

    async def set_jurisdiction(self, session_id: str, jurisdiction: str, tax_type: str = "vat") -> None:
        """切换会话的管辖地和税种（会触发 client 重建）"""
        session = self.sessions.get(session_id)
        if not session:
            return
        if session.jurisdiction != jurisdiction or session.tax_type != tax_type:
            # 断开旧 jurisdiction 的 client
            old_key = f"{session.jurisdiction}:{session.tax_type}"
            old_client = session._clients.pop(old_key, None)
            if old_client:
                try:
                    await old_client.disconnect()
                except Exception:
                    pass
            session.jurisdiction = jurisdiction
            session.tax_type = tax_type

    # ── SDK Real Mode ──

    async def _sdk_chat(
        self,
        session: AgentSession,
        user_message: str,
    ) -> AsyncIterator[str]:
        """使用 ClaudeSDKClient 进行真实对话。
        若 SDK 不可用或初始化失败，自动回退到 httpx 直连 MiniMax /v1/messages。
        """
        # 确定管辖地（默认 uk）
        jurisdiction = session.jurisdiction or "uk"
        tax_type = session.tax_type or "vat"
        client_key = f"{jurisdiction}:{tax_type}"

        # 获取或创建对应管辖地的 SDK client
        client = session._clients.get(client_key)
        if client is None:
            system_prompt = get_system_prompt(jurisdiction, tax_type)
            allowlist = get_allowlist_for(jurisdiction, tax_type)

            options_kwargs = {
                "system_prompt": system_prompt,
                "allowed_tools": allowlist,
                "permission_mode": self.permission_mode,
                "cwd": self.cwd,
                # 不加载 user/project settings，避免首次运行 onboarding/trust 阻塞
                "setting_sources": [],
                # AG-UI 协议需要 token-level streaming：开启后 CLI 在
                # 每个 content_block_delta 上 emit StreamEvent 帧，
                # 我们在 receive_response() 里识别它们并 yield 纯文本。
                # 注意：启用后 SDK 仍会再 emit 一次完整的 AssistantMessage，
                # 下面的循环用 `stream_active` 标志跳过那段以避免重复。
                "include_partial_messages": True,
                # 启用 extended thinking：display="summarized" 让 CLI 子进程
                # 流式输出 thinking 文本（而非仅 emit 签名），前端可在折叠面板
                # 中展示模型的推理过程。"adaptive" 允许模型自行决定深度；
                # 不思考的模型把它当 no-op，所以无条件启用。
                "thinking": {"type": "adaptive", "display": "summarized"},
                # 显式转发路由 + 沙箱标志给 CLI 子进程
                "env": {
                    k: v
                    for k, v in {
                        "ANTHROPIC_BASE_URL": os.environ.get("ANTHROPIC_BASE_URL"),
                        "ANTHROPIC_AUTH_TOKEN": self.api_key,
                        "ANTHROPIC_API_KEY": self.api_key,
                        "ANTHROPIC_DEFAULT_SONNET_MODEL": os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL"),
                        "ANTHROPIC_DEFAULT_HAIKU_MODEL": os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL"),
                        "ANTHROPIC_DEFAULT_OPUS_MODEL": os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL"),
                        "IS_SANDBOX": "1",
                        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                    }.items()
                    if v
                },
            }
            # model 名称: 优先 ANTHROPIC_DEFAULT_SONNET_MODEL (代理服务的 model 名)
            model_name = (
                os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
                or os.environ.get("ANTHROPIC_MODEL")
            )
            if model_name:
                options_kwargs["model"] = model_name

            # 附加对应管辖地的 MCP Server
            mcp_info = self._mcp_servers.get((jurisdiction, tax_type))
            if mcp_info:
                options_kwargs["mcp_servers"] = {mcp_info["name"]: mcp_info["instance"]}

            # 把 CLI 子进程的 stderr 透到后端日志，便于诊断挂起/认证问题
            import sys as _sys
            options_kwargs["stderr"] = lambda line: _sys.stderr.write(
                "[claude-cli] " + str(line).rstrip() + "\n"
            )

            options = ClaudeAgentOptions(**options_kwargs)
            client = ClaudeSDKClient(options=options)
            await client.__aenter__()
            session._clients[client_key] = client

        session.status = "chatting"

        try:
            await client.query(user_message, session_id=session.session_id)

            # AG-UI 协议关键：include_partial_messages=True 时，CLI 在每个
            # content_block_delta 上 emit StreamEvent(delta)；之后还会 emit
            # 一次完整的 AssistantMessage(TextBlock)。我们用 `stream_active`
            # 标记本轮是否已经从 delta 路径 yield 过 — 若是，整段 TextBlock
            # 跳过（避免用户先逐字看到再整段重发一遍）。
            stream_active = False

            async for msg in client.receive_response():
                if isinstance(msg, StreamEvent):
                    event = msg.event or {}
                    etype = event.get("type")
                    if etype == "content_block_start":
                        data = event.get("data") or {}
                        # Anthropic text / thinking block 开始 → 后续会走 delta 路径
                        if isinstance(data, dict) and data.get("type") in ("text", "thinking"):
                            stream_active = True
                    elif etype == "content_block_delta":
                        delta = event.get("delta") or {}
                        if delta.get("type") == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                stream_active = True
                                yield text
                        elif delta.get("type") == "thinking_delta":
                            # 扩展思考：把每个 token 累加成 reasoning_content 流式信号，
                            # 由 AG-UI 适配器编码为 REASONING_MESSAGE_CONTENT 事件。
                            # signature_delta（thinking 收尾时附带）忽略。
                            text = delta.get("thinking", "")
                            if text:
                                stream_active = True
                                yield {"__agui__": "reasoning_content", "delta": text}
                    # 其它 StreamEvent 形态（ping / content_block_stop 等）忽略

                elif isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            if stream_active:
                                # 这一轮已经从 delta 流出过，跳过整段
                                continue
                            yield block.text
                        elif isinstance(block, ThinkingBlock):
                            # 非流式 replay / 旧 CLI 不发 thinking_delta 的回退路径。
                            # stream_active=True 时整段跳过，避免与上面的 delta 流重复；
                            # 没有 thinking 文本的 block 也直接跳过。
                            if stream_active or not getattr(block, "thinking", None):
                                continue
                            yield {"__agui__": "reasoning_start"}
                            yield {"__agui__": "reasoning_content", "delta": block.thinking}
                            yield {"__agui__": "reasoning_end"}
                        elif isinstance(block, ToolUseBlock):
                            # 工具调用 → 发结构化信号给 AG-UI 适配器
                            tool_id = (
                                getattr(block, "id", None)
                                or f"tool_{uuid.uuid4().hex[:8]}"
                            )
                            yield {
                                "__agui__": "tool_start",
                                "tool_call_id": tool_id,
                                "tool_name": block.name,
                                "parent_message_id": None,
                            }
                            if hasattr(block, "input") and block.input is not None:
                                try:
                                    args_str = json.dumps(
                                        block.input, ensure_ascii=False
                                    )
                                except (TypeError, ValueError):
                                    args_str = str(block.input)
                                if args_str and args_str != "null":
                                    yield {
                                        "__agui__": "tool_args",
                                        "tool_call_id": tool_id,
                                        "delta": args_str,
                                    }
                            yield {
                                "__agui__": "tool_end",
                                "tool_call_id": tool_id,
                            }
                    stream_active = False  # 消息边界，重置

                elif isinstance(msg, ToolResultBlock):
                    tool_id = getattr(msg, "tool_use_id", None) or ""
                    try:
                        tool_result = self._parse_tool_result(msg)
                        content_str = json.dumps(tool_result, ensure_ascii=False)
                    except Exception:
                        content_str = "(unparseable tool result)"
                    yield {
                        "__agui__": "tool_result",
                        "tool_call_id": tool_id,
                        "content": content_str,
                    }

                elif isinstance(msg, SystemMessage):
                    if msg.subtype == "notification":
                        data = msg.data or {}
                        yield f"\n📢 {data.get('message', '')}\n"

                elif isinstance(msg, ResultMessage):
                    if msg.is_error:
                        yield f"\n❌ Agent 错误: {msg.result or 'Unknown error'}\n"
                    else:
                        if msg.total_cost_usd:
                            yield f"\n💰 本次对话消耗: ${msg.total_cost_usd:.4f}\n"
                        yield "\n---\n"

        except Exception as e:
            yield f"\n⚠️ SDK 不可用 ({type(e).__name__}: {str(e)[:80]}), 回退到 httpx 直连 MiniMax...\n"
            try:
                await client.disconnect()
            except Exception:
                pass
            session._clients.pop(client_key, None)
            # 回退: 用 httpx 直接调 MiniMax /v1/messages
            jurisdiction = session.jurisdiction or "uk"
            tax_type = session.tax_type or "vat"
            try:
                system_prompt = get_system_prompt(jurisdiction, tax_type)
            except Exception:
                system_prompt = "You are T.A.X.I., a helpful tax filing assistant."
            async for chunk in self._httpx_chat(
                session=session,
                user_message=user_message,
                system_prompt=system_prompt,
            ):
                yield chunk
            return

    async def _httpx_chat(
        self,
        session: AgentSession,
        user_message: str,
        system_prompt: str,
    ) -> AsyncIterator[str]:
        """直连 MiniMax /v1/messages 端点（不依赖 claude-agent-sdk）。

        用于 musl 等无 SDK wheel 的环境，或 SDK 失败后的 fallback。MiniMax
        是 Anthropic 兼容 API，支持 `stream: true` → SSE 事件流。
        本实现走真流式（httpx_sse.aconnect_sse），逐 token yield —
        不再像之前那样先 await 整个响应再一次性 parse。
        """
        base_url = (
            os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")
        )
        url = f"{base_url}/v1/messages"
        # model: MiniMax 真实模型名是 "MiniMax-M3"（不带方括号），需从 env 清洗
        raw_model = (
            os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
            or os.environ.get("ANTHROPIC_MODEL")
            or "MiniMax-M3"
        )
        # 清洗 [1m] 等后缀
        import re
        model_name = re.sub(r"\[.*?\]", "", raw_model).strip() or "MiniMax-M3"

        req_body = {
            "model": model_name,
            "max_tokens": 4096,
            "stream": True,   # ← 关键：开启 Anthropic 风格 SSE 流
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_message},
            ],
        }

        # 延迟 import：httpx_sse 是 SDK 的传递依赖，不在 requirements.txt 强约束
        from httpx_sse import aconnect_sse

        stream_active = False  # 标记本轮 text 是否已开始（用于过滤空 content_block_start）

        async with httpx.AsyncClient(timeout=60) as client:
            try:
                async with aconnect_sse(
                    client,
                    "POST",
                    url,
                    headers={
                        "content-type": "application/json",
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "accept": "text/event-stream",
                    },
                    json=req_body,
                ) as event_source:
                    async for sse in event_source.aiter_sse():
                        ev_type = sse.event
                        if ev_type == "content_block_start":
                            try:
                                data = sse.json()
                            except Exception:
                                data = {}
                            if isinstance(data, dict) and (data.get("data") or {}).get("type") == "text":
                                stream_active = True
                        elif ev_type == "content_block_delta":
                            try:
                                data = sse.json()
                            except Exception:
                                continue
                            delta = data.get("delta") or {}
                            if delta.get("type") == "text_delta":
                                text = delta.get("text", "")
                                if text:
                                    stream_active = True
                                    yield text
                        elif ev_type == "content_block_stop":
                            # block 关闭，stream_active 不重置（多 block 也行）
                            pass
                        elif ev_type == "message_stop":
                            break
                        elif ev_type == "error":
                            try:
                                err = sse.json()
                            except Exception:
                                err = {"error": {"message": sse.data}}
                            yield f"\n❌ API 错误: {err}\n"
                            return
                        # 其它事件（message_start / ping 等）忽略
            except Exception as e:
                yield f"\n❌ HTTP 错误: {type(e).__name__}: {e}\n"
                return

        session.status = "idle"

    # ── Mock Fallback Mode ──

    async def _mock_chat(
        self,
        session: AgentSession,
        user_message: str,
    ) -> AsyncIterator[str]:
        """SDK 未安装时的降级响应（演示用）"""
        import asyncio

        msg_lower = user_message.lower()
        jurisdiction = session.jurisdiction or "uk"

        # 演示用的推理片段：让前端折叠面板在没有 API key 时也能展示
        # 完整生命周期（auto-open → collapse）。生产环境不会跑这条路径。
        yield {"__agui__": "reasoning_start"}
        for piece in (
            "用户提问: " + user_message[:40] + "\n",
            "判断 jurisdiction: " + jurisdiction + "\n",
            "按意图路由到对应 handler\n",
        ):
            yield {"__agui__": "reasoning_content", "delta": piece}
        yield {"__agui__": "reasoning_end"}
        await asyncio.sleep(0.2)

        if jurisdiction != "uk":
            yield f"我是 TaxAgent 智能报税助手。\n\n"
            yield f"当前管辖地: {jurisdiction.upper()}\n"
            yield f"注意: Mock 模式仅支持 UK 演示。要体验 {jurisdiction.upper()} 的报税功能，\n"
            yield f"请安装 claude-agent-sdk 并配置对应国家的 API 凭证。\n\n"
            yield f"我可以帮您:\n"
            yield f"1. 查询待申报义务\n"
            yield f"2. 自动计算申报表\n"
            yield f"3. 验证数据合规性\n"
            yield f"4. 提交申报\n"
            return

        # UK Mock Mode (保持不变)
        if getattr(session, "raw_business_data", None) and ("分析" in user_message or "analyze" in msg_lower or "计算" in msg_lower or "报税" in msg_lower):
            data = session.raw_business_data
            company = data.get("company", {})
            sales = data.get("sales_invoices", [])
            purchases = data.get("purchase_invoices", [])

            yield f"🔍 正在分析 {company.get('name', '企业')} 的原始业务数据...\n\n"
            await asyncio.sleep(0.3)

            domestic_sales = [s for s in sales if s.get("type") in ("domestic_b2b", "domestic_b2c")]
            eu_sales = [s for s in sales if s.get("type") == "eu_b2b"]
            zero_sales = [s for s in sales if s.get("type") == "zero_rated"]
            export_sales = [s for s in sales if s.get("type") == "export"]
            yield "📊 销售分析\n"
            yield "-" * 30 + "\n"
            yield f"  标准税率销售: {len(domestic_sales)} 笔 → Box 1 + Box 6\n"
            yield f"  EU B2B 销售: {len(eu_sales)} 笔 → Box 8 (零税率)\n"
            yield f"  零税率销售: {len(zero_sales)} 笔 → Box 6\n"
            yield f"  出口销售: {len(export_sales)} 笔 → Box 6 (免税)\n\n"

            dom_purchases = [p for p in purchases if p.get("type") == "domestic"]
            imports = [p for p in purchases if p.get("type") == "import"]
            eu_acq = [p for p in purchases if p.get("type") == "eu_acquisition"]
            exempt = [p for p in purchases if p.get("type") == "exempt"]
            yield "📦 采购分析\n"
            yield "-" * 30 + "\n"
            yield f"  国内采购: {len(dom_purchases)} 笔 → Box 4 + Box 7\n"
            yield f"  进口采购: {len(imports)} 笔 → Box 4 (C79) + Box 7\n"
            yield f"  EU 采购: {len(eu_acq)} 笔 → Box 2 + Box 4 + Box 7 + Box 9\n"
            yield f"  免税采购: {len(exempt)} 笔 → 不计入\n\n"

            await asyncio.sleep(0.3)
            yield "📋 HMRC 9-BOX VAT RETURN (基于 TechFlow Distribution Ltd Q1 数据)\n"
            yield "=" * 40 + "\n"
            yield "  Box 1  VAT due on sales:        £42,520.00\n"
            yield "  Box 2  VAT due on acquisitions: £13,700.00\n"
            yield "  Box 3  Total VAT due:           £56,220.00\n"
            yield "  Box 4  VAT reclaimed:           £51,183.00\n"
            yield "  Box 5  Net VAT due:             £ 5,037.00\n"
            yield "  ─────────────────────────────────────\n"
            yield "  Box 6  Total sales ex VAT:      £245,300\n"
            yield "  Box 7  Total purchases ex VAT:  £240,465\n"
            yield "  Box 8  Goods supplied to EU:    £ 42,450\n"
            yield "  Box 9  Goods acquired from EU:  £ 68,500\n"
            yield "=" * 40 + "\n\n"

            yield "💰 结果: 应付 HMRC £5,037.00\n\n"
            yield "✅ 分析完成。\n\n"
            yield "   要继续报税，请确认以上数据，我将为您提交至 HMRC。"
            session.status = "confirming"
            return

        if "报税" in user_message or "filing" in msg_lower:
            yield "我来帮您完成英国 VAT 季度申报。"
            await asyncio.sleep(0.3)
            yield "\n\n首先，请告诉我您的 VRN（VAT Registration Number），"
            yield "或者上传您的销售/采购数据文件，"
            yield "我将自动计算并提交申报。"

        elif "义务" in user_message or "obligations" in msg_lower:
            yield "📋 查询 HMRC 申报义务...\n"
            await asyncio.sleep(0.5)
            yield "\n找到以下待申报期间：\n"
            yield "- Period Key: 24A1 (2026-01-01 ~ 2026-03-31)\n"
            yield "- Period Key: 24A2 (2026-04-01 ~ 2026-06-30)\n"
            yield "\n请选择要申报的期间。"

        elif "计算" in user_message or "calculate" in msg_lower:
            if not session.line_items:
                yield "请先上传数据或提供 line items。"
            else:
                yield "🧮 正在计算 VAT...\n\n"
                await asyncio.sleep(0.5)
                yield "Box 1 (VAT due on sales): £2,500.00\n"
                yield "Box 2 (VAT due on acquisitions): £0.00\n"
                yield "Box 3 (Total VAT due): £2,500.00 ✅\n"
                yield "Box 4 (VAT reclaimed): £1,200.00\n"
                yield "Box 5 (Net VAT due): £1,300.00 ✅\n"
                yield "\n应付 HMRC: £1,300.00"

        elif "提交" in user_message or "submit" in msg_lower:
            session.status = "confirming"
            yield "⚠️ 提交申报前，请确认：\n\n"
            yield "1. 数据准确无误\n"
            yield "2. 计算结果正确\n"
            yield "3. 您有权限代表该企业申报\n\n"
            yield "确认后，我将提交至 HMRC。\n"
            yield "[✅ 确认提交]"

        elif "确认" in user_message or "confirm" in msg_lower:
            session.status = "submitting"
            yield "🚀 正在提交至 HMRC...\n\n"
            await asyncio.sleep(1)
            yield "✅ 申报成功！\n\n"
            yield "HMRC 回执：\n"
            yield "- Form Bundle Number: 321591334754\n"
            yield "- Processing Date: 2026-06-02T12:00:00Z\n"
            yield "- Payment Indicator: DD\n\n"
            session.status = "done"

        else:
            yield "我是 TaxAgent 智能报税助手。\n\n"
            yield "我可以帮您：\n"
            yield "1. 分析原始企业发票数据并自动计算 VAT Return\n"
            yield "2. 查询 HMRC 待申报义务\n"
            yield "3. 验证申报数据合规性\n"
            yield "4. 提交 VAT Return 至 HMRC\n"
            yield "5. 查询已提交的申报\n\n"
            yield "请告诉我您需要什么帮助？"

    # ── Helpers ──

    def _get_or_create_session(self, session_id: str) -> AgentSession:
        if session_id not in self.sessions:
            self.sessions[session_id] = AgentSession(
                session_id=session_id,
                user_id="anonymous",
            )
        return self.sessions[session_id]

    def _parse_tool_result(self, msg: ToolResultBlock) -> dict:
        """解析 ToolResultBlock 中的 JSON 结果。"""
        try:
            if hasattr(msg, "content") and msg.content:
                for block in msg.content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "")
                        return json.loads(text)
            return {"success": True}
        except (json.JSONDecodeError, AttributeError):
            return {"success": True}
