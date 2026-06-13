"""TaxAgent Engine — Claude Agent SDK 核心引擎（多管辖地版）

基于 ClaudeSDKClient 的智能报税 Agent。
支持多管辖地/税种并行：一个 session 挂载所有 MCP server,LLM 用 namespace 自路由。
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

import httpx  # 用于 SDK 不可用时直连 MiniMax /v1/messages

from .prompts import get_system_prompt, get_multi_jurisdiction_prompt
from .tools import (
    create_mcp_servers,
    get_allowlist_for,
    get_multi_jurisdiction_allowlist,
    SDK_AVAILABLE,
    set_registry,
)
from .workspace_store import ensure_case, WORKSPACE_ROOT
from backend.services.audit_log import AuditLog

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
# Workspace Reminder (SDK 模式 + mock 模式共用)
# ═══════════════════════════════════════════════════════════

def _build_multi_workspace_reminder(slots: list[JurisdictionSlot]) -> str:
    """构造多管辖地 workspace reminder — 列出所有 workspace 路径。"""
    active = [s for s in slots if s.workspace_path]
    if not active:
        return ""
    if len(active) == 1:
        s = active[0]
        return (
            f"\n\n[Workspace: {s.workspace_path}]\n"
            f"**先读 manifest.json 获取公司名/VRN/期间,再按需读 sales.json / purchases.json 等。**"
            f"**该路径在整轮会话持续有效,不要让用户重发数据,不要向用户索要 VRN/期间等已存在于 manifest 的信息。**"
        )
    lines = ["\n\n[Workspaces]"]
    for s in active:
        cc_label = s.jurisdiction.upper()
        tt_label = s.tax_type.replace("_", " ").title()
        lines.append(f"- {cc_label} {tt_label}: {s.workspace_path}")
    lines.append(
        "**先读各目录下的 manifest.json 获取公司名/纳税人ID/期间,再按需读其他文件。**"
        "**这些路径在整轮会话持续有效,不要让用户重发数据。**"
    )
    return "\n".join(lines)


def _infer_jurisdiction_from_case_id(case_id: str) -> tuple[str, str]:
    """从 case_id 提取 (jurisdiction, tax_type)。"""
    cid = case_id.lower()
    cc = "uk"
    for c in ("uk", "cn", "de", "fr", "testland"):
        if f"-{c}-" in cid or cid.startswith(c):
            cc = c
            break
    tt = "vat"
    if "corporation_tax" in cid or "-ct-" in cid:
        tt = "corporation_tax"
    elif "self_assessment" in cid or "-sa-" in cid:
        tt = "self_assessment"
    elif "paye" in cid:
        tt = "paye"
    elif "stamp_duty" in cid or "-sdlt-" in cid:
        tt = "stamp_duty"
    return cc, tt


# 通用 workspace 目录布局说明(追加到 system_prompt 末尾)
_WORKSPACE_INSTRUCTION = (
    "\n\n[Workspace]\n"
    "Case data is on disk at ~/.taxi/workspace/<case_id>/. "
    "Files: manifest.json (company name, VRN, period), sales.json, purchases.json, "
    "nine_box.json, warnings.json, source_meta.json, and source_docs/*.json. "
    "**CRITICAL: When a workspace path is provided in the user message, you MUST read "
    "manifest.json FIRST before responding.** It contains VRN, company name, and period — "
    "never ask the user for this information. After reading manifest, use the Read tool "
    "to load any other files you need (sales.json, purchases.json, etc.). "
    "Do NOT ask the user to resend data. The workspace path remains valid for the entire session."
)


# ═══════════════════════════════════════════════════════════
# Session State
# ═══════════════════════════════════════════════════════════

@dataclass
class JurisdictionSlot:
    """一个活跃的 (jurisdiction, tax_type) 绑定。"""
    jurisdiction: str
    tax_type: str = "vat"
    workspace_path: str = ""
    taxpayer_id: str = ""
    period_key: str = ""


@dataclass
class AgentSession:
    """Agent 会话状态（补充 SDK 原生会话的元数据）

    多管辖地支持: jurisdictions 列表替代原来的单一 jurisdiction 字段。
    向后兼容: 通过 @property 访问旧字段名,零修改调用方。
    """
    session_id: str
    user_id: str = "anonymous"
    jurisdictions: list[JurisdictionSlot] = field(default_factory=list)
    status: str = "idle"             # idle | chatting | calculating | confirming | submitting | done
    line_items: list[dict] = field(default_factory=list)
    raw_business_data: Optional[dict] = None  # deprecated: 保留字段避免破坏 session store
    _case_id: str = ""  # 内部:首次拿到 case_id 后缓存,后续轮次复用
    messages: list[dict] = field(default_factory=list)
    # 单一 SDK client(挂载所有 MCP server),jurisdictions 变化时重建
    _client: Optional[ClaudeSDKClient] = None
    _mounted_jurisdictions_hash: str = ""  # 追踪当前 client 挂载了哪些 jurisdiction

    # ── 向后兼容 property ──

    @property
    def jurisdiction(self) -> str:
        return self.jurisdictions[0].jurisdiction if self.jurisdictions else ""

    @jurisdiction.setter
    def jurisdiction(self, v: str) -> None:
        if v and (not self.jurisdictions or self.jurisdictions[0].jurisdiction != v):
            if self.jurisdictions:
                self.jurisdictions[0].jurisdiction = v
            else:
                self.jurisdictions.append(JurisdictionSlot(jurisdiction=v))

    @property
    def tax_type(self) -> str:
        return self.jurisdictions[0].tax_type if self.jurisdictions else "vat"

    @tax_type.setter
    def tax_type(self, v: str) -> None:
        if self.jurisdictions:
            self.jurisdictions[0].tax_type = v
        else:
            self.jurisdictions.append(JurisdictionSlot(jurisdiction="uk", tax_type=v))

    @property
    def taxpayer_id(self) -> str:
        return self.jurisdictions[0].taxpayer_id if self.jurisdictions else ""

    @taxpayer_id.setter
    def taxpayer_id(self, v: str) -> None:
        if self.jurisdictions:
            self.jurisdictions[0].taxpayer_id = v

    @property
    def period_key(self) -> str:
        return self.jurisdictions[0].period_key if self.jurisdictions else ""

    @period_key.setter
    def period_key(self, v: str) -> None:
        if self.jurisdictions:
            self.jurisdictions[0].period_key = v

    @property
    def workspace_path(self) -> str:
        return self.jurisdictions[0].workspace_path if self.jurisdictions else ""

    @workspace_path.setter
    def workspace_path(self, v: str) -> None:
        if self.jurisdictions:
            self.jurisdictions[0].workspace_path = v


# ═══════════════════════════════════════════════════════════
# TaxAgent Engine
# ═══════════════════════════════════════════════════════════

class TaxAgentEngine:
    """TaxAgent 智能报税引擎（多管辖地）

    支持:
        - 多管辖地并行: 一个 session 挂载所有 MCP server
        - Namespace 路由: LLM 通过 mcp__tax_agent_{cc}_{tt}__ 自路由
        - 动态系统提示: 按活跃 jurisdictions 组合对应法规知识

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

        # H3: AuditLog 实例,供 _sdk_chat 记录 tool_invoked / tool_completed / agent_completed 事件
        self._audit: AuditLog = AuditLog()

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
        case_id: Optional[str] = None,
        case_ids: Optional[list[str]] = None,
    ) -> AsyncIterator[str]:
        """与 Agent 对话，流式返回响应文本。

        Args:
            session_id: 会话唯一标识
            user_message: 用户输入
            uploaded_data: 用户上传的 line items（可选）
            raw_business_data: 用户上传的原始企业数据（可选）
            jurisdiction: 强制指定管辖地（可选，否则从 case_id 推断）
            case_id: 单个案例标识(向后兼容)
            case_ids: 多个案例标识(多管辖地),优先于 case_id

        Yields:
            流式文本片段
        """
        session = self._get_or_create_session(session_id)

        # ── 处理 case_ids / case_id → JurisdictionSlot ──
        effective_case_ids = case_ids or ([case_id] if case_id else [])
        for cid in effective_case_ids:
            cc, tt = _infer_jurisdiction_from_case_id(cid)
            # 缓存首个 case_id(向后兼容 _case_id 属性)
            if not session._case_id:
                session._case_id = cid
            # 避免重复追加同 (cc, tt)
            if not any(s.jurisdiction == cc and s.tax_type == tt for s in session.jurisdictions):
                slot = JurisdictionSlot(jurisdiction=cc, tax_type=tt)
                session.jurisdictions.append(slot)

        # 强制指定管辖地(覆盖推断)
        if jurisdiction and not session.jurisdictions:
            session.jurisdictions.append(JurisdictionSlot(jurisdiction=jurisdiction))
        elif jurisdiction:
            session.jurisdictions[0].jurisdiction = jurisdiction

        # 如果 raw_business_data 中有公司信息且无任何 jurisdiction → 默认 uk
        if raw_business_data and not session.jurisdictions:
            session.jurisdictions.append(JurisdictionSlot(jurisdiction="uk"))

        # ── 处理上传数据 ──
        if uploaded_data:
            session.line_items = uploaded_data
            yield "📎 已接收上传数据，共 {} 条记录\n".format(len(uploaded_data))

        # ── Workspace 落盘 ──
        if effective_case_ids:
            for i, cid in enumerate(effective_case_ids):
                slot = session.jurisdictions[i] if i < len(session.jurisdictions) else None
                if slot and not slot.workspace_path:
                    try:
                        # 首个 case_id 带 raw_business_data(如有),其余从 fixture 加载
                        ws_raw = raw_business_data if (i == 0 and raw_business_data) else None
                        ws_path, manifest = ensure_case(cid, ws_raw)
                        slot.workspace_path = ws_path
                        yield f"📂 workspace 已就绪: {ws_path}\n"
                        # 从 manifest 提取 VRN / period
                        if manifest.get("vrn") and not slot.taxpayer_id:
                            slot.taxpayer_id = manifest["vrn"]
                        if not slot.period_key:
                            if manifest.get("period_key"):
                                slot.period_key = manifest["period_key"]
                            elif manifest.get("period"):
                                p = manifest["period"]
                                slot.period_key = p if isinstance(p, str) else str(p)
                    except Exception as e:
                        yield f"⚠️ workspace 落盘失败: {e}\n"
        elif raw_business_data and session.jurisdictions and not session.jurisdictions[0].workspace_path:
            # 兼容: raw_business_data 有但无 case_id → 落盘到 default
            try:
                ws_path, manifest = ensure_case("default", raw_business_data)
                session.jurisdictions[0].workspace_path = ws_path
                yield f"📂 workspace 已就绪: {ws_path}\n"
                if manifest.get("vrn") and not session.jurisdictions[0].taxpayer_id:
                    session.jurisdictions[0].taxpayer_id = manifest["vrn"]
            except Exception:
                pass
            session.raw_business_data = raw_business_data  # 保留字段(向后兼容)

        # ── 构建增强消息 ──
        enriched_message = user_message
        enriched_message += _build_multi_workspace_reminder(session.jurisdictions)
        if (not any(s.workspace_path for s in session.jurisdictions)
                and session.line_items
                and "数据" not in user_message and "data" not in user_message.lower()):
            enriched_message += f"\n\n[系统: 用户已上传 {len(session.line_items)} 条 line items]"

        # ── 选择模式 ──
        if SDK_AVAILABLE and self.api_key:
            async for chunk in self._sdk_chat(session, enriched_message):
                yield chunk
        elif self.api_key and os.environ.get("ANTHROPIC_BASE_URL"):
            # SDK 缺失但有 key + 自定义 endpoint — 直接 httpx 调
            slots_as_tuples = [
                (s.jurisdiction, s.tax_type, s.workspace_path)
                for s in session.jurisdictions
            ] or [("uk", "vat", "")]
            try:
                system_prompt = get_multi_jurisdiction_prompt(slots_as_tuples)
            except Exception:
                system_prompt = "You are T.A.X.I., a helpful tax filing assistant."
            # httpx 模式没有 Read 工具,但仍告知 workspace 存在
            if any(s.workspace_path for s in session.jurisdictions):
                system_prompt += (
                    "\n\n[Workspace] Case data has been loaded from disk. "
                    "VRN and period are already available — do NOT ask the user for them. "
                    "Respond based on the workspace information provided in the message."
                )
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
            "jurisdictions": [
                {"cc": s.jurisdiction, "tt": s.tax_type, "workspace": s.workspace_path}
                for s in session.jurisdictions
            ],
            # 向后兼容
            "jurisdiction": session.jurisdiction,
            "tax_type": session.tax_type,
            "taxpayer_id": session.taxpayer_id,
            "period_key": session.period_key,
            "line_items_count": len(session.line_items),
            "message_count": len(session.messages),
            "sdk_available": SDK_AVAILABLE,
        }

    async def reset_session(self, session_id: str) -> None:
        """重置会话状态并清理 SDK client"""
        session = self.sessions.get(session_id)
        if session and session._client:
            try:
                await session._client.disconnect()
            except Exception:
                pass
        if session_id in self.sessions:
            del self.sessions[session_id]

    async def set_jurisdiction(self, session_id: str, jurisdiction: str, tax_type: str = "vat") -> None:
        """切换会话的管辖地和税种(会触发 client 重建)。

        保留向后兼容:调用方仍可通过此方法切 jurisdiction。
        实际上 jurisdictions 变化会在下次 _sdk_chat 时自动重建 client。
        """
        session = self.sessions.get(session_id)
        if not session:
            return
        if not session.jurisdictions:
            session.jurisdictions.append(JurisdictionSlot(jurisdiction=jurisdiction, tax_type=tax_type))
        else:
            if session.jurisdictions[0].jurisdiction != jurisdiction or session.jurisdictions[0].tax_type != tax_type:
                session.jurisdictions[0].jurisdiction = jurisdiction
                session.jurisdictions[0].tax_type = tax_type

    # ── SDK Real Mode ──

    async def _sdk_chat(
        self,
        session: AgentSession,
        user_message: str,
    ) -> AsyncIterator[str]:
        """使用 ClaudeSDKClient 进行真实对话(多管辖地统一挂载)。

        一个 client 挂载所有活跃 jurisdiction 的 MCP server + 全局 KB。
        LLM 通过 mcp__tax_agent_{cc}_{tt}__ namespace 自路由。
        jurisdictions 变化时重建 client。
        """
        # 确定活跃 jurisdictions（空则默认 uk:vat）
        slots = session.jurisdictions or [JurisdictionSlot(jurisdiction="uk", tax_type="vat")]
        jhash = "|".join(f"{s.jurisdiction}:{s.tax_type}" for s in slots)

        # 仅当 jurisdictions 变化或 client 不存在时重建
        if session._client is None or session._mounted_jurisdictions_hash != jhash:
            if session._client:
                try:
                    await session._client.disconnect()
                except Exception:
                    pass

            # 组合多国 prompt + workspace 说明
            slots_as_tuples = [
                (s.jurisdiction, s.tax_type, s.workspace_path) for s in slots
            ]
            system_prompt = get_multi_jurisdiction_prompt(slots_as_tuples)
            system_prompt += _WORKSPACE_INSTRUCTION

            # 多国 allowlist(通配符)
            allowlist = get_multi_jurisdiction_allowlist(slots_as_tuples)

            # 挂载所有 jurisdiction 的 MCP server + 全局 KB
            mcp_servers = {}
            for slot in slots:
                key = (slot.jurisdiction, slot.tax_type)
                mcp_info = self._mcp_servers.get(key)
                if mcp_info:
                    mcp_servers[mcp_info["name"]] = mcp_info["instance"]
            kb_info = self._mcp_servers.get(("global", "tax_kb"))
            if kb_info:
                mcp_servers[kb_info["name"]] = kb_info["instance"]

            options_kwargs = {
                "system_prompt": system_prompt,
                "allowed_tools": allowlist,
                "mcp_servers": mcp_servers,
                "permission_mode": self.permission_mode,
                "cwd": self.cwd,
                "add_dirs": [str(WORKSPACE_ROOT)],
                "setting_sources": [],
                "strict_mcp_config": True,
                "include_partial_messages": True,
                "thinking": {"type": "adaptive", "display": "summarized"},
                "env": {
                    k: v
                    for k, v in {
                        "ANTHROPIC_BASE_URL": os.environ.get("ANTHROPIC_BASE_URL"),
                        "ANTHROPIC_AUTH_TOKEN": self.api_key,
                        "ANTHROPIC_API_KEY": self.api_key,
                        "ANTHROPIC_DEFAULT_SONNET_MODEL": os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL"),
                        "ANTHROPIC_DEFAULT_HAIKU_MODEL": os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL"),
                        "ANTHROPIC_DEFAULT_OPUS_MODEL": os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL"),
                        "CLAUDE_CODE_ENABLE_TELEMETRY": os.environ.get("CLAUDE_CODE_ENABLE_TELEMETRY"),
                        "OTEL_TRACES_EXPORTER": os.environ.get("OTEL_TRACES_EXPORTER"),
                        "OTEL_METRICS_EXPORTER": os.environ.get("OTEL_METRICS_EXPORTER"),
                        "OTEL_LOGS_EXPORTER": os.environ.get("OTEL_LOGS_EXPORTER"),
                        "OTEL_EXPORTER_OTLP_ENDPOINT": os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
                        "IS_SANDBOX": "1",
                        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                    }.items()
                    if v
                },
            }
            model_name = (
                os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
                or os.environ.get("ANTHROPIC_MODEL")
            )
            if model_name:
                options_kwargs["model"] = model_name

            # 注册税法调研 sub-agent
            from backend.agent.tax_knowledge_prompts import TAX_KB_SUBAGENT_PROMPT
            from claude_agent_sdk.types import AgentDefinition
            options_kwargs["agents"] = {
                "tax_kb_researcher": AgentDefinition(
                    description="Tax law research sub-agent",
                    prompt=TAX_KB_SUBAGENT_PROMPT,
                    tools=["mcp__tax_agent_global_tax_kb__search_tax_knowledge"],
                    maxTurns=3,
                )
            }

            # CLI 子进程 stderr 透传
            import sys as _sys
            options_kwargs["stderr"] = lambda line: _sys.stderr.write(
                "[claude-cli] " + str(line).rstrip() + "\n"
            )

            options = ClaudeAgentOptions(**options_kwargs)
            session._client = ClaudeSDKClient(options=options)
            await session._client.__aenter__()
            session._mounted_jurisdictions_hash = jhash

        session.status = "chatting"
        client = session._client

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
                            # H3: 记录工具调用 (tool_invoked)
                            self._audit.record(
                                session.session_id, "SDK_CHAT", "tool_invoked",
                                {"tool": block.name, "tool_id": tool_id},
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
                    # H3: 记录工具完成 (tool_completed; tool 名称不在 scope)
                    self._audit.record(
                        session.session_id, "SDK_CHAT", "tool_completed",
                        {"tool_id": tool_id, "content_len": len(content_str)},
                    )

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
                    # H3: 记录 agent_completed (成功 / 错误 / 成本)
                    self._audit.record(
                        session.session_id, "SDK_CHAT", "agent_completed",
                        {"is_error": msg.is_error, "total_cost_usd": msg.total_cost_usd},
                    )

        except Exception as e:
            yield f"\n⚠️ SDK 不可用 ({type(e).__name__}: {str(e)[:80]}), 回退到 httpx 直连 MiniMax (无 MCP 工具)...\n"
            yield {"__agui__": "tool_unavailable", "reason": f"sdk_fallback: {type(e).__name__}: {str(e)[:120]}"}
            try:
                await client.disconnect()
            except Exception:
                pass
            session._client = None
            # 回退: 用 httpx 直接调
            slots_as_tuples = [
                (s.jurisdiction, s.tax_type, s.workspace_path)
                for s in (session.jurisdictions or [JurisdictionSlot(jurisdiction="uk")])
            ]
            try:
                system_prompt = get_multi_jurisdiction_prompt(slots_as_tuples)
            except Exception:
                system_prompt = "You are T.A.X.I., a helpful tax filing assistant."
            system_prompt += (
                "\n\n[Tool-Failure Notice] MCP tools are currently unavailable. "
                "Do NOT fabricate any numeric tax values. If the user asks for "
                "calculations, tell them the toolchain is offline and stop."
            )
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
        jurisdictions_desc = ", ".join(
            f"{s.jurisdiction.upper()}/{s.tax_type}" for s in session.jurisdictions
        ) or "UK/VAT"

        # 构造 workspace 前缀(多管辖地)
        ws_prefix = ""
        if any(s.workspace_path for s in session.jurisdictions):
            ws_prefix = "📂 Workspaces:\n"
            for s in session.jurisdictions:
                if s.workspace_path:
                    cc = s.jurisdiction.upper()
                    ws_prefix += f"  - {cc}: {s.workspace_path}\n"

        # 演示用的推理片段
        yield {"__agui__": "reasoning_start"}
        for piece in (
            "用户提问: " + user_message[:40] + "\n",
            "活跃管辖地: " + jurisdictions_desc + "\n",
            "按意图路由到对应 handler\n",
        ):
            yield {"__agui__": "reasoning_content", "delta": piece}
        yield {"__agui__": "reasoning_end"}
        await asyncio.sleep(0.2)

        # Mock 模式: 仅 UK VAT 有详细演示,其他管辖地给出提示
        has_non_uk = any(s.jurisdiction != "uk" for s in session.jurisdictions)
        if has_non_uk and not any(s.jurisdiction == "uk" for s in session.jurisdictions):
            yield f"我是 TaxAgent 智能报税助手。\n\n"
            yield f"活跃管辖地: {jurisdictions_desc}\n"
            yield f"注意: Mock 模式仅支持 UK VAT 演示。要体验其他管辖地的报税功能，\n"
            yield f"请安装 claude-agent-sdk 并配置对应国家的 API 凭证。\n\n"
            yield f"我可以帮您:\n"
            yield f"1. 查询待申报义务\n"
            yield f"2. 自动计算申报表\n"
            yield f"3. 验证数据合规性\n"
            yield f"4. 提交申报\n"
            return

        if getattr(session, "raw_business_data", None) and ("分析" in user_message or "analyze" in msg_lower or "计算" in msg_lower or "报税" in msg_lower):
            data = session.raw_business_data
            company = data.get("company", {})
            sales = data.get("sales_invoices", [])
            purchases = data.get("purchase_invoices", [])

            yield ws_prefix
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
            if ws_prefix:
                yield f"我来帮您完成英国 VAT 季度申报。\n\n{ws_prefix}\n"
                yield "Mock 模式无法调用 HMRC API — 请切换到 SDK 模式执行真实申报。"
            else:
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
            if ws_prefix:
                yield ws_prefix + "\n"
            yield "我可以帮您：\n"
            yield "1. 分析原始企业发票数据并自动计算 VAT Return\n"
            yield "2. 查询 HMRC 待申报义务\n"
            yield "3. 验证申报数据合规性\n"
            yield "4. 提交 VAT Return 至 HMRC\n\n"
            if ws_prefix:
                yield "Mock 模式功能有限 — 请安装 SDK 并配置 API key 获得完整体验。"
            else:
                yield "5. 查询已提交的申报\n\n请告诉我您需要什么帮助？"

    # ── Helpers ──

    def _get_or_create_session(self, session_id: str) -> AgentSession:
        if session_id not in self.sessions:
            self.sessions[session_id] = AgentSession(
                session_id=session_id,
                user_id="anonymous",
            )
        return self.sessions[session_id]

    def _parse_tool_result(self, msg: ToolResultBlock) -> dict:
        """把 ToolResultBlock 转成 dict, 失败时返回明确的 error (不再静默吞错)。

        修 Bug (2026-06): 原版在 content 为空 / 不可解析时一律返回
        {"success": True}, 让 LLM 误以为工具成功, 同时也掩盖了协议层错误
        (例如 wrapper 抛 TypeError 被 SDK 吞掉)。新版返回
        {"success": False, "error": "..."} 并透传 is_error 标志。
        """
        is_error = bool(getattr(msg, "is_error", None))
        tool_use_id = getattr(msg, "tool_use_id", "unknown")

        content = getattr(msg, "content", None)
        # 路径 1: content 是 list[dict] (MCP 规范)
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text", "")
                    try:
                        parsed = json.loads(text)
                    except (json.JSONDecodeError, TypeError):
                        parsed = {"raw": text}
                    if isinstance(parsed, dict):
                        if is_error:
                            parsed["success"] = False
                            parsed.setdefault("is_error", True)
                        return parsed
                    return {"success": not is_error, "raw": parsed}
        # 路径 2: content 是 str
        elif isinstance(content, str) and content:
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                parsed = {"raw": content}
            if isinstance(parsed, dict):
                if is_error:
                    parsed["success"] = False
                return parsed
            return {"success": not is_error, "raw": parsed}

        # content 为空 / 缺失 → 明确报错, 不再静默
        return {
            "success": False,
            "error": f"tool result for {tool_use_id} has no content",
            "is_error": is_error,
        }
