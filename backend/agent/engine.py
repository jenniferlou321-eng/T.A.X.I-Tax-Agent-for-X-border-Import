"""TaxAgent Engine — Claude Agent SDK 核心引擎（多管辖地版）

基于 ClaudeSDKClient 的智能报税 Agent。
支持多管辖地/税种并行：一个 session 挂载所有 MCP server,LLM 用 namespace 自路由。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Optional

import httpx  # 用于 SDK 不可用时直连 MiniMax /v1/messages

from .prompts import get_system_prompt, get_multi_jurisdiction_prompt
from backend.models.jurisdictions import is_valid_jurisdiction
from .tools import (
    create_mcp_servers,
    get_allowlist_for,
    SDK_AVAILABLE,
    set_registry,
)
from .workspace_store import ensure_case, mount_cases, AGENT_WORKSPACE_ROOT
from .session_store import cleanup_old_sessions
from .provider_config import get_agent_provider_config
from backend.services.audit_log import AuditLog
from backend.agent.tax_knowledge_store import TaxKnowledgeStore

# SDK 会话自动清理阈值 — 保留最近 N 个会话的 JSONL,避免磁盘无限累积。
# ~/.claude/projects/ 单项目可达数百 MB;每轮 chat 完成后异步清理。
_SESSION_KEEP_LIMIT = 10


def _cleanup_sessions_async() -> int:
    """在后台线程中清理旧 SDK 会话,删除多余的 JSONL 文件。

    在 chat() 末尾通过 loop.create_task(asyncio.to_thread(...)) 调度,
    不会阻塞流式响应。
    """
    try:
        return cleanup_old_sessions(keep=_SESSION_KEEP_LIMIT)
    except Exception as e:  # 静默失败 — 清理失败不影响 chat 主体
        import logging
        logging.getLogger(__name__).debug("session cleanup failed: %s", e)
        return 0

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
# Workspace 注入: 单一事实源 (M2/M3)
# 事实要点在 _WORKSPACE_FACTS 一处定义,三条 system_prompt 出口
# (SDK / httpx / httpx-fallback) + 用户消息尾的即时提醒都从它派生,
# 杜绝"多处手写 → 改一处漏一处"的措辞漂移。
# ═══════════════════════════════════════════════════════════

_WORKSPACE_FACTS = (
    "manifest.json holds the company name, VRN, and period; other files: "
    "sales.json, purchases.json, nine_box.json, warnings.json, source_meta.json, "
    "and source_docs/*.json. "
    "Never ask the user for VRN / company name / period — they are in the workspace. "
    "Do NOT enumerate or describe ~/.taxi/workspace/<case_id>/ legacy directories "
    "or any unselected case data. "
    "If related_cases/ exists, read it only for the currently selected cross-border case."
)


def _build_multi_workspace_reminder(slots: list[JurisdictionSlot]) -> str:
    """即时提醒(进用户消息尾): 抗注意力衰减的第二次 workspace 提示。

    事实要点统一取自 _WORKSPACE_FACTS(单一事实源),这里只加"本轮 active
    workspace 已就绪"的即时语气外壳。
    """
    active = [s for s in slots if s.workspace_path]
    if not active:
        return ""
    root = str(AGENT_WORKSPACE_ROOT)
    return (
        f"\n\n[Active Workspace: {root}]\n"
        "The case you selected has been copied into this active workspace. "
        "Read manifest.json FIRST, then the other files as needed. "
        + _WORKSPACE_FACTS
    )


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


# 追加到 system_prompt 末尾的 workspace 说明,两个语气变体(都派生自 _WORKSPACE_FACTS):
#   _WORKSPACE_INSTRUCTION          — 有 Read 工具(SDK 路径): 指示先读 manifest.json
#   _WORKSPACE_INSTRUCTION_NO_READ  — 无 Read 工具(httpx 路径): 数据已由后端加载,别反问
_WORKSPACE_INSTRUCTION = (
    "\n\n[Workspace]\n"
    f"Case data, when selected, is copied into a single active directory: "
    f"{AGENT_WORKSPACE_ROOT}/ (empty by default). "
    "**CRITICAL: when the active workspace is available, you MUST read "
    "manifest.json FIRST before responding.** "
    + _WORKSPACE_FACTS
)

_WORKSPACE_INSTRUCTION_NO_READ = (
    "\n\n[Workspace]\n"
    "Case data, when selected, has already been loaded from disk by the backend "
    "and included in the message — you do not have a file-reading tool here. "
    + _WORKSPACE_FACTS
)


# ═══════════════════════════════════════════════════════════
# Session State
# ═══════════════════════════════════════════════════════════

# Skill 插件根:一个国家一个 local plugin(backend/agent/skill_plugins/<cc>/)。
_SKILL_PLUGIN_ROOT = Path(__file__).resolve().parent / "skill_plugins"


def _derive_skill_plugins(mcp_server_keys) -> list[dict]:
    """从已挂载 MCP server 的 (cc, tt) keys 推出 local plugin 列表。

    一个国家一个插件;仅当 skill_plugins/<cc>/skills/ 实际存在时纳入
    (de/cn/fr 无 agent tools → 无 server key → 自动跳过)。
    """
    ccs = {cc for (cc, tt) in mcp_server_keys if cc != "global"}
    plugins: list[dict] = []
    for cc in sorted(ccs):
        if (_SKILL_PLUGIN_ROOT / cc / "skills").is_dir():
            plugins.append({"type": "local", "path": str(_SKILL_PLUGIN_ROOT / cc)})
    return plugins


def _expected_skill_names(mcp_server_keys) -> set[str]:
    """本进程应当加载的 skill 命名空间集(用于 init 自检)。

    仅计入磁盘上确实 ship 了 SKILL.md 的 (cc, tt);tax_type 下划线→连字符。
    """
    names: set[str] = set()
    for (cc, tt) in mcp_server_keys:
        if cc == "global":
            continue
        tt_hyphen = tt.replace("_", "-")
        if (_SKILL_PLUGIN_ROOT / cc / "skills" / tt_hyphen).is_dir():
            names.add(f"{cc}:{tt_hyphen}")
    return names


def _all_mounted_slots(
    active_slots, mcp_server_keys
) -> list[tuple[str, str, str]]:
    """mount-all:返回全部已挂载 (cc, tt) 段(给 system prompt 用)。

    active_slots 在前并保留其 workspace_path;其余已挂载税种补空 workspace。

    只纳入 prompt 层能渲染的 (cc, tt)——即 is_valid_jurisdiction 为真者。
    某些 adapter(如 CN)用带前缀的 tax_type(cn_cit / cn_vat),不在
    TAX_TYPES 白名单、也没有 prompts/<cc>/<tt>.py 段;直接喂给
    get_multi_jurisdiction_prompt 会抛 KeyError 崩掉整个会话。这里跳过并
    告警,而不是让 mount-all 把不支持的税种卷进 system prompt。
    """
    out: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    skipped: list[tuple[str, str]] = []
    for s in active_slots:
        key = (s.jurisdiction, s.tax_type)
        if key in seen:
            continue
        seen.add(key)
        if not is_valid_jurisdiction(s.jurisdiction, s.tax_type):
            skipped.append(key)
            continue
        out.append((s.jurisdiction, s.tax_type, s.workspace_path))
    for (cc, tt) in sorted(k for k in mcp_server_keys if k[0] != "global"):
        if (cc, tt) in seen:
            continue
        seen.add((cc, tt))
        if not is_valid_jurisdiction(cc, tt):
            skipped.append((cc, tt))
            continue
        out.append((cc, tt, ""))
    if skipped:
        logging.getLogger(__name__).warning(
            "mount-all 跳过无 prompt 段的已注册税种(MCP 工具仍挂载,但不进 "
            "system prompt / namespace map):%s。如需启用,请在 TAX_TYPES 加入该 "
            "tax_type 并新增 prompts/<cc>/<tt>.py。", sorted(set(skipped)),
        )
    return out


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
    _init_skills_checked: bool = False  # init 自检只跑一次(init 每会话只发一次)

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
        kb_store: Optional['TaxKnowledgeStore'] = None,
    ):
        # Hosted deployments can configure TAXI_ANTHROPIC_* explicitly. A missing
        # provider is valid and selects the mock path for the public demo.
        self._provider = get_agent_provider_config()
        self.api_key = api_key or self._provider.api_key
        self._strict_live = os.environ.get("TAXI_REQUIRE_LIVE_AGENT", "0") == "1"
        if self._strict_live and not self.api_key:
            raise RuntimeError("Live Agent requires TAXI_ANTHROPIC_API_KEY on the server")
        if self._strict_live and not SDK_AVAILABLE:
            raise RuntimeError("claude-agent-sdk is unavailable: full MCP Agent cannot start")
        self.cwd = cwd or os.getcwd()
        self.permission_mode = permission_mode
        self.sessions: dict[str, AgentSession] = {}

        # Claude Code CLI 以 root 运行时拒绝 --dangerously-skip-permissions，
        # 除非显式声明处于沙箱环境。本部署在容器内以 root 运行，故置位。
        os.environ.setdefault("IS_SANDBOX", "1")

        # Registry & MCP Servers
        self._registry = registry
        self._mcp_servers: dict[tuple[str, str], dict] = {}

        # 缓存外部注入的 KB store,以便 corpus sync router 复用同一实例。
        self._kb_store = kb_store

        # H3: AuditLog 实例,供 _sdk_chat 记录 tool_invoked / tool_completed / agent_completed 事件
        self._audit: AuditLog = AuditLog()

        if registry:
            set_registry(registry)
            if SDK_AVAILABLE:
                self._mcp_servers = create_mcp_servers(registry, kb_store=kb_store)

        # Make the selected mode visible in service logs without leaking credentials.
        if not SDK_AVAILABLE:
            print("[WARN] claude-agent-sdk not installed. Engine runs in MOCK mode.")
            print("       Install: pip install claude-agent-sdk")
        elif not self.api_key:
            print("[INFO] No Agent provider configured. Engine runs in MOCK demo mode.")

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
            try:
                # 每次选择/分析 case 都先清空固定 active workspace,再把当前 case 投影进去。
                # 第一个 case 写根目录;其余相关实体写 related_cases/<case_id>/。
                mounted = mount_cases(
                    effective_case_ids,
                    raw_business_data if raw_business_data else None,
                )
                for i, (ws_path, manifest) in enumerate(mounted):
                    slot = session.jurisdictions[i] if i < len(session.jurisdictions) else None
                    if not slot:
                        continue
                    slot.workspace_path = ws_path
                    # 从 manifest 提取 VRN / period
                    if manifest.get("vrn") and not slot.taxpayer_id:
                        slot.taxpayer_id = manifest["vrn"]
                    if not slot.period_key:
                        if manifest.get("period_key"):
                            slot.period_key = manifest["period_key"]
                        elif manifest.get("period"):
                            p = manifest["period"]
                            slot.period_key = p if isinstance(p, str) else str(p)
                yield f"📂 active workspace 已就绪: {AGENT_WORKSPACE_ROOT}\n"
            except Exception as e:
                yield f"⚠️ workspace 落盘失败: {e}\n"
        elif raw_business_data and session.jurisdictions and not session.jurisdictions[0].workspace_path:
            # 兼容: raw_business_data 有但无 case_id → 落盘到固定 active workspace
            try:
                ws_path, manifest = ensure_case("default", raw_business_data)
                session.jurisdictions[0].workspace_path = ws_path
                yield f"📂 active workspace 已就绪: {AGENT_WORKSPACE_ROOT}\n"
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
        # SDK 模式有 3 分钟硬超时 — 超时后降级到 mock,避免长挂 SSE 流。
        # (历史上 Minimax 代理曾卡住几分钟,导致前端 SSE 流死锁,SimpleHTTP
        # server 线程耗尽,新资源请求 502。复杂多工具调用场景需要 2-3 分钟。)
        if SDK_AVAILABLE and self.api_key:
            import asyncio
            yielded_anything = False
            try:
                async with asyncio.timeout(180):
                    async for chunk in self._sdk_chat(session, enriched_message):
                        yielded_anything = True
                        yield chunk
            except (asyncio.TimeoutError, TimeoutError):
                if self._strict_live:
                    yield {"__agui__": "step_end", "step_name": ""}
                    yield "\n❌ 实时 Agent 请求超时，请稍后重试。本次没有执行模拟对话。\n"
                    return
                if not yielded_anything:
                    yield {"__agui__": "step_end", "step_name": ""}
                    yield ("\n⚠️ SDK 3 分钟未响应(可能是 Minimax 代理无响应),"
                           "已自动降级到 mock 模式...\n")
                    async for chunk in self._mock_chat(session, enriched_message):
                        yield chunk
                    return
        elif self.api_key:
            if self._strict_live:
                raise RuntimeError("Live Agent requires Claude Agent SDK and MCP tools")
            # SDK 缺失但 provider config 可用 — 直接 httpx 调
            slots_as_tuples = [
                (s.jurisdiction, s.tax_type, s.workspace_path)
                for s in session.jurisdictions
            ] or [("uk", "vat", "")]
            try:
                system_prompt = get_multi_jurisdiction_prompt(slots_as_tuples)
            except Exception:
                system_prompt = "You are T.A.X.I., a helpful tax filing assistant."
            # httpx 模式没有 Read 工具,但仍告知 workspace 存在(无 Read 变体)
            if any(s.workspace_path for s in session.jurisdictions):
                system_prompt += _WORKSPACE_INSTRUCTION_NO_READ
            async for chunk in self._httpx_chat(
                session=session, user_message=enriched_message, system_prompt=system_prompt,
            ):
                yield chunk
        else:
            if self._strict_live:
                raise RuntimeError("Live Agent configuration is missing")
            async for chunk in self._mock_chat(session, enriched_message):
                yield chunk

        # 保存对话历史
        session.messages.append({"role": "user", "content": user_message})

        # 自动清理: 只保留最近 10 个 SDK 会话,避免 `~/.claude/projects/`
        # 持续累积 JSONL(单项目可达数百 MB)。用异步调度避免阻塞流式响应。
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(asyncio.to_thread(_cleanup_sessions_async))
        except RuntimeError:
            # 没有 running loop (e.g. 直接调用 chat 而非通过 FastAPI)
            _cleanup_sessions_async()

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

    async def _evict_other_clients(self, keep_session_id: str) -> None:
        """断开除 keep_session_id 外所有 session 的 SDK client。

        策略 (单 client): 进程内同一时刻最多存活一个 claude.exe 子进程。
        每个 ClaudeSDKClient 是一个常驻 CLI 子进程 (空闲 ~300-500MB,
        多工具调用时飙到 ~2.9GB)。前端每次刷新都新建 session_id,若不回收
        旧子进程,会累积到撞 OOM,内核杀 claude.exe → :9000 反代返回 502。

        在激活某 session 的 client 前调用,保证"最新对话独占子进程"。
        单个 disconnect 失败不影响其余回收。
        """
        for sid, sess in list(self.sessions.items()):
            if sid == keep_session_id:
                continue
            client = sess._client
            if client is None:
                continue
            try:
                await client.disconnect()
            except Exception:
                pass
            sess._client = None
            sess._mounted_jurisdictions_hash = ""

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
            # 单 client 策略: 激活本 session 前,断开其余所有 session 的子进程,
            # 保证进程内最多一个 claude.exe (防 OOM → 502, 见 _evict_other_clients)。
            await self._evict_other_clients(keep_session_id=session.session_id)

            if session._client:
                try:
                    await session._client.disconnect()
                except Exception:
                    pass

            # 组合多国 prompt + workspace 说明。
            # mount-all:system prompt 覆盖全部已挂载 (cc,tt) 的薄段(指针+门禁),
            # 让 agent 任意会话都能顺手载入某税种 skill 办理;active slot 保留
            # workspace_path,其余补空。知识在各税种 skill 里按需加载。
            slots_as_tuples = _all_mounted_slots(slots, self._mcp_servers.keys())
            system_prompt = get_multi_jurisdiction_prompt(slots_as_tuples)
            system_prompt += _WORKSPACE_INSTRUCTION

            # allowlist: 覆盖全部已挂载 MCP server 的 namespace（通配符）。
            # 原来用 get_multi_jurisdiction_allowlist(slots_as_tuples) 只覆盖活跃
            # slots，导致其他税种的 namespace 被 SDK 拦截。现改为从 self._mcp_servers
            # 直接生成，保证所有挂载 server 均可调用。
            # （slots_as_tuples 仍用于 system_prompt，不受影响。）
            allowlist = [
                f"mcp__{info['name']}__*"
                for info in self._mcp_servers.values()
            ]
            allowlist += ["Read", "Glob", "Grep"]

            # 挂载所有已注册的 MCP server（不限于 active slots）。
            # self._mcp_servers 在 __init__ 时已枚举全部 jurisdiction/tax_type，
            # 将它们全部挂载，LLM 通过 namespace 自路由，避免"只暴露当前 slot
            # 对应税种"的问题（CT/PAYE/SA/SDLT 工具在 VAT-only slot 下也可用）。
            mcp_servers = {}
            for key, mcp_info in self._mcp_servers.items():
                if key == ("global", "tax_kb"):
                    continue  # KB 单独处理，避免重复
                mcp_servers[mcp_info["name"]] = mcp_info["instance"]
            kb_info = self._mcp_servers.get(("global", "tax_kb"))
            if kb_info:
                mcp_servers[kb_info["name"]] = kb_info["instance"]

            options_kwargs = {
                "system_prompt": system_prompt,
                "allowed_tools": allowlist,
                # 禁用内置 AskUserQuestion 工具:T.A.X.I. 设计上希望 Agent 直接调用 MCP
                # 工具读取 workspace(manifest.json 含 VRN/期间等),不要向用户反问选择题。
                # deny 比 allow 严格,即使 bypassPermissions 也生效。
                # SDK 字段定义: claude_agent_sdk/types.py:1666
                "disallowed_tools": ["AskUserQuestion"],
                "mcp_servers": mcp_servers,
                "permission_mode": self.permission_mode,
                "cwd": self.cwd,
                "add_dirs": [str(AGENT_WORKSPACE_ROOT)],
                "setting_sources": [],
                "strict_mcp_config": True,
                "include_partial_messages": True,
                "thinking": {"type": "adaptive", "display": "summarized"},
                "env": {
                    k: v
                    for k, v in {
                        # Provider config is fixed from agent_provider.local.json.
                        # Do NOT read parent-shell ANTHROPIC_* here.
                        "ANTHROPIC_BASE_URL": self._provider.base_url,
                        "ANTHROPIC_AUTH_TOKEN": self.api_key,
                        "ANTHROPIC_API_KEY": self.api_key,
                        "ANTHROPIC_MODEL": self._provider.model,
                        "ANTHROPIC_DEFAULT_SONNET_MODEL": self._provider.model,
                        "ANTHROPIC_DEFAULT_HAIKU_MODEL": self._provider.model,
                        "ANTHROPIC_DEFAULT_OPUS_MODEL": self._provider.model,
                        "CLAUDE_CODE_ENABLE_TELEMETRY": os.environ.get("CLAUDE_CODE_ENABLE_TELEMETRY"),
                        "OTEL_TRACES_EXPORTER": os.environ.get("OTEL_TRACES_EXPORTER"),
                        "OTEL_METRICS_EXPORTER": os.environ.get("OTEL_METRICS_EXPORTER"),
                        "OTEL_LOGS_EXPORTER": os.environ.get("OTEL_LOGS_EXPORTER"),
                        "OTEL_EXPORTER_OTLP_ENDPOINT": os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"),
                        "IS_SANDBOX": "1",
                        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                        # 屏蔽 CLI 自带的 bundled/builtin skills(deep-research、loop、
                        # simplify、verify、code-review 等)。这些 skill 烧录在 CLI
                        # 二进制里(getSkills 的 builtinPluginSkills 类别),不走
                        # setting_sources / CLAUDE_CONFIG_DIR / --plugin-dir,所以
                        # setting_sources=[] 拦不住它们,只能用这个 env 开关。
                        # 设为 "1" 后 init 的 skills 列表只剩我们的 uk:* 插件 skill。
                        "CLAUDE_CODE_DISABLE_BUNDLED_SKILLS": "1",
                    }.items()
                    if v
                },
            }
            options_kwargs["model"] = self._provider.model

            # Skill 插件:一个国家一个 local plugin。setting_sources=[] 屏蔽
            # ~/.claude 与 project 的 .claude/skills + 已启用插件(host superpowers
            # 等)发现;plugins(--plugin-dir)独立于 setting_sources 加载我们的
            # uk 插件;skills="all" 启用所有"被发现"的 skill。但 CLI 自带的
            # bundled/builtin skill 不在以上任何一类里(烧录在二进制),需上面
            # env 里的 CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1 才能彻底剔除,否则
            # skills="all" 会把它们一并启用进 init 列表。
            # skills="all" 还会自动把裸 `Skill` 工具追加进 allowed_tools。
            # 知识(税率/表结构/workflow)放在 skill body,渐进披露按需加载。
            _skill_plugins = _derive_skill_plugins(self._mcp_servers.keys())
            if _skill_plugins:
                options_kwargs["plugins"] = _skill_plugins
                options_kwargs["skills"] = "all"

            # 注册税法调研 sub-agent
            from backend.agent.tax_knowledge_prompts import TAX_KB_SUBAGENT_PROMPT
            from claude_agent_sdk.types import AgentDefinition
            options_kwargs["agents"] = {
                "tax_kb_researcher": AgentDefinition(
                    description="Tax law research sub-agent",
                    prompt=TAX_KB_SUBAGENT_PROMPT,
                    tools=[
                        "mcp__tax_agent_global_tax_kb__search_tax_knowledge",
                        "mcp__tax_agent_global_tax_kb__list_supported_jurisdictions",
                        "mcp__tax_agent_global_tax_kb__get_tax_rates",
                    ],
                    maxTurns=10,
                )
            }

            # CLI 子进程 stderr 透传 —— 带时间戳落盘 + 同步透传到 stderr 便于 live tail
            # 这是 Python SDK 0.2.95 唯一支持的"看 CLI 在干嘛"的方式:
            # debug_stderr 已被 deprecated,TypeScript 的 debugFile 选项没暴露给 Python。
            # 看 logs/sdk-debug.log 即可逐行追踪 CLI 子进程。
            import sys as _sys
            from pathlib import Path as _Path
            _log_dir = _Path(__file__).resolve().parents[2] / "logs"
            _log_dir.mkdir(parents=True, exist_ok=True)
            _cli_log = logging.getLogger("backend.agent.claude_cli")
            if not _cli_log.handlers:
                _fh = logging.FileHandler(_log_dir / "sdk-debug.log", encoding="utf-8")
                _fh.setFormatter(logging.Formatter(
                    "%(asctime)s.%(msecs)03d %(levelname)s [claude-cli] %(message)s",
                    datefmt="%Y-%m-%dT%H:%M:%S",
                ))
                _sh = logging.StreamHandler(_sys.stderr)
                _sh.setFormatter(logging.Formatter("[claude-cli] %(message)s"))
                _cli_log.addHandler(_fh)
                _cli_log.addHandler(_sh)
                _cli_log.setLevel(logging.INFO)
                _cli_log.propagate = False
            options_kwargs["stderr"] = lambda line: _cli_log.info(str(line).rstrip())

            options = ClaudeAgentOptions(**options_kwargs)
            session._client = ClaudeSDKClient(options=options)
            await session._client.__aenter__()
            session._mounted_jurisdictions_hash = jhash
            session._init_skills_checked = False  # 新连接 → 重新做一次 init 自检

        session.status = "chatting"
        client = session._client

        try:
            await client.query(user_message, session_id=session.session_id)

            # 立即通知前端 agent 已进入思考阶段（填补 query→首事件的空窗期）
            yield {"__agui__": "step_start", "step_name": "thinking"}

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
                            # 通知前端：从"思考"切换到"调工具"
                            yield {"__agui__": "step_start", "step_name": f"tool:{block.name}"}
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
                    # 工具执行完毕 → 回到"思考"阶段
                    yield {"__agui__": "step_start", "step_name": "thinking"}

                elif isinstance(msg, SystemMessage):
                    if msg.subtype == "notification":
                        data = msg.data or {}
                        yield f"\n📢 {data.get('message', '')}\n"
                    elif msg.subtype == "init" and not session._init_skills_checked:
                        # init 每会话只发一次 → 自检 skill 插件是否按预期加载。
                        # SystemMessage 无 typed 属性,从 .data 读 skills/plugins。
                        session._init_skills_checked = True
                        loaded = set((msg.data or {}).get("skills") or [])
                        expected = _expected_skill_names(self._mcp_servers.keys())
                        missing = expected - loaded
                        if missing:
                            logging.getLogger(__name__).warning(
                                "Skill plugins not fully loaded: missing=%s loaded=%s "
                                "(plugins=%s)",
                                sorted(missing), sorted(loaded),
                                (msg.data or {}).get("plugins"),
                            )

                elif isinstance(msg, ResultMessage):
                    # 关闭残留 step（如有）
                    yield {"__agui__": "step_end", "step_name": ""}
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
            if self._strict_live:
                yield {"__agui__": "step_end", "step_name": ""}
                logging.getLogger(__name__).exception("Live Agent MCP/SDK failure")
                yield {"__agui__": "tool_unavailable", "reason": f"sdk_error: {type(e).__name__}"}
                yield "\n❌ 实时 Agent 或工具调用失败，请稍后重试；没有生成模拟结果。\n"
                try:
                    await client.disconnect()
                except Exception:
                    pass
                session._client = None
                return
            yield {"__agui__": "step_end", "step_name": ""}
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
            # 即便降级到此路径,workspace 数据(若有)仍已落盘 — 告知 agent 别反问
            if any(s.workspace_path for s in session.jurisdictions):
                system_prompt += _WORKSPACE_INSTRUCTION_NO_READ
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
        base_url = self._provider.base_url.rstrip("/")
        url = f"{base_url}/v1/messages"
        model_name = self._provider.model

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
        yield {"__agui__": "step_start", "step_name": "thinking"}
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
            yield f"注意：当前招聘演示版的对话助手仅提供 UK VAT 脚本化示例；其他管辖地可体验页面内已实现的计算与模拟申报流程。\n"
            yield f"如需真实模型推理，需由项目维护者配置受控的模型 API。\n\n"
            yield f"我可以帮您:\n"
            yield f"1. 查询待申报义务\n"
            yield f"2. 自动计算申报表\n"
            yield f"3. 验证数据合规性\n"
            yield f"4. 体验模拟申报流程（不会向税务机关提交）\n"
            yield {"__agui__": "step_end", "step_name": ""}
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
            yield "📋 VAT 9-BOX 演示结果（固定样例数值；不代表对任意上传文件完成动态计算）\n"
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

            yield "💰 演示样例净应缴: £5,037.00\n\n"
            yield "✅ 演示分析完成。\n\n"
            yield "   注意：以上为固定演示样例结果，并非根据本次上传数据重新核算；确认后也只会执行模拟流程，不会向 HMRC 提交。"
            session.status = "confirming"
            yield {"__agui__": "step_end", "step_name": ""}
            return

        if "报税" in user_message or "filing" in msg_lower:
            if ws_prefix:
                yield f"我来帮您完成英国 VAT 季度申报。\n\n{ws_prefix}\n"
                yield "当前为公开演示模式，不会调用 HMRC API。您可以在申报页面体验本地计算、校验和模拟提交流程。"
            else:
                yield "我来帮您完成英国 VAT 季度申报。"
                await asyncio.sleep(0.3)
                yield "\n\n您可以从页面中的 UK VAT 示例案例开始，查看本地计算、校验和模拟申报流程。"
                yield "当前网站为演示环境，不会向 HMRC 提交真实申报。"

        elif "义务" in user_message or "obligations" in msg_lower:
            yield "📋 查询演示申报义务...\n"
            await asyncio.sleep(0.5)
            yield "\n以下为固定演示期间，并非实时 HMRC 查询结果：\n"
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
                yield "\n演示样例净应缴: £1,300.00（固定样例结果，非实时核算）"

        elif "提交" in user_message or "submit" in msg_lower:
            session.status = "confirming"
            yield "⚠️ 提交申报前，请确认：\n\n"
            yield "1. 数据准确无误\n"
            yield "2. 计算结果正确\n"
            yield "3. 您有权限代表该企业申报\n\n"
            yield "确认后将执行模拟申报流程；不会向 HMRC 发送任何真实申报。\n"
            yield "[✅ 确认提交]"

        elif "确认" in user_message or "confirm" in msg_lower:
            session.status = "submitting"
            yield "🚀 正在运行模拟申报流程...\n\n"
            await asyncio.sleep(1)
            yield "✅ 演示申报完成（Mock 模式；未向 HMRC 提交）\n\n"
            yield "模拟回执：\n"
            yield "- Demo Receipt ID: DEMO-321591334754\n"
            yield "- 示例处理时间: 2026-06-02T12:00:00Z\n"
            yield "- 说明: 该回执仅用于展示交互流程，不代表税务机关受理。\n\n"
            session.status = "done"

        else:
            yield "我是 TaxAgent 智能报税助手。\n\n"
            if ws_prefix:
                yield ws_prefix + "\n"
            yield "我可以帮您体验：\n"
            yield "1. 浏览企业发票数据分析示例\n"
            yield "2. 查看演示申报义务\n"
            yield "3. 体验申报数据校验与本地计算\n"
            yield "4. 体验模拟申报流程（不会向税务机关提交）\n\n"
            yield "当前为公开招聘演示模式；无模型密钥时，对话采用脚本化示例响应。申报回执为模拟数据，不代表税务机关受理。"
        yield {"__agui__": "step_end", "step_name": ""}

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
