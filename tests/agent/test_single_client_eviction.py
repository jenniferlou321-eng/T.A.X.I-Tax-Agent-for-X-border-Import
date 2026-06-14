"""测试: SDK 模式下进程内最多只存活一个 ClaudeSDKClient 子进程。

根因 (2026-06-14 OOM 事故): 每个 AgentSession 持有一个常驻 claude.exe 子进程,
前端每次刷新都新建 session_id,旧子进程从不回收 → 累积到撞 OOM,内核杀进程 →
:9000 反代返回 502。

策略 (用户拍板): SDK 只允许运行一个 client,新对话激活时立即停掉旧的。
"engine._evict_other_clients(keep_session_id)" 必须断开除 keep 之外所有 session 的 client。
"""
from __future__ import annotations

import asyncio

from backend.agent.engine import AgentSession, TaxAgentEngine


class _StubClient:
    """记录 disconnect 是否被调用的假 client。"""
    def __init__(self):
        self.connected = True

    async def disconnect(self):
        self.connected = False


def test_evict_other_clients_disconnects_all_but_keep():
    """激活某 session 时,其余 session 的 client 必须被断开并清空。"""
    engine = TaxAgentEngine()  # 无 registry 也能构造

    # 三个 session,各自挂一个活跃 client
    for sid in ("a", "b", "c"):
        s = AgentSession(session_id=sid)
        s._client = _StubClient()
        s._mounted_jurisdictions_hash = "uk:vat"
        engine.sessions[sid] = s

    clients = {sid: engine.sessions[sid]._client for sid in ("a", "b", "c")}

    # 激活 "b" → "a" 和 "c" 的 client 必须被断开
    asyncio.run(engine._evict_other_clients(keep_session_id="b"))

    assert clients["a"].connected is False, "session a 的子进程未被回收"
    assert clients["c"].connected is False, "session c 的子进程未被回收"
    assert clients["b"].connected is True, "不应断开当前激活的 session b"

    # 被淘汰的 session 其 _client 必须置空,杜绝重复 disconnect / 悬挂引用
    assert engine.sessions["a"]._client is None
    assert engine.sessions["c"]._client is None
    assert engine.sessions["b"]._client is clients["b"]


def test_evict_is_safe_when_no_other_clients():
    """只有一个 session 时,evict 不应抛异常。"""
    engine = TaxAgentEngine()
    s = AgentSession(session_id="solo")
    s._client = _StubClient()
    engine.sessions["solo"] = s

    asyncio.run(engine._evict_other_clients(keep_session_id="solo"))
    assert engine.sessions["solo"]._client is not None


def test_evict_tolerates_disconnect_failure():
    """某个 client.disconnect() 抛错时,不影响其余回收,也不冒泡。"""
    class _BadClient(_StubClient):
        async def disconnect(self):
            raise RuntimeError("boom")

    engine = TaxAgentEngine()
    bad = AgentSession(session_id="bad")
    bad._client = _BadClient()
    good = AgentSession(session_id="good")
    good._client = _StubClient()
    keep = AgentSession(session_id="keep")
    keep._client = _StubClient()
    engine.sessions.update({"bad": bad, "good": good, "keep": keep})

    good_client = good._client
    # 不应抛
    asyncio.run(engine._evict_other_clients(keep_session_id="keep"))

    assert good_client.connected is False
    assert engine.sessions["bad"]._client is None
    assert engine.sessions["good"]._client is None
