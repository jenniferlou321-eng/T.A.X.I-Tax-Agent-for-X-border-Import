"""Agent chat MCP tool 测试 (v0 暂用 mock mode)"""
import pytest
from backend.jurisdictions.uk.vat.agent_tools import UKVATAgentToolSet

from backend.agent.agui_adapter import stream_agui_events


@pytest.mark.asyncio
async def test_ingest_erp_data_demo_case():
    tools = UKVATAgentToolSet()
    result = await tools.ingest_erp_data(source="demo", case_id="techflow_q1_2026")
    assert "content" in result
    text = result["content"][0]["text"]
    assert "techflow" in text or "import_result" in text


@pytest.mark.asyncio
async def test_ingest_erp_data_missing_case_id():
    tools = UKVATAgentToolSet()
    result = await tools.ingest_erp_data(source="demo")
    assert result.get("is_error") is True
    text = result["content"][0]["text"]
    assert "case_id" in text


@pytest.mark.asyncio
async def test_ingest_erp_data_case_not_found():
    tools = UKVATAgentToolSet()
    result = await tools.ingest_erp_data(source="demo", case_id="nonexistent")
    assert result.get("is_error") is True


@pytest.mark.asyncio
async def test_ingest_erp_data_csv_base64():
    import base64
    csv = (
        b"txn_date,txn_type,counterparty,net,vat,gross,vat_rate,tax_code\n"
        b"2026-01-15,sale,ACME,1000,200,1200,0.20,T1\n"
    )
    tools = UKVATAgentToolSet()
    result = await tools.ingest_erp_data(
        source="csv", csv_base64=base64.b64encode(csv).decode(),
    )
    assert "content" in result


# ── AG-UI Reasoning (extended thinking) 端到端 round-trip ──


class _StubSession:
    """stream_agui_events 只用到 .session_id 一个属性。"""
    session_id = "stub-session"


class _StubEngine:
    """模拟 engine.chat：先输出思考段，再输出文本。"""

    async def chat(self, *args, **kwargs):
        yield {"__agui__": "reasoning_start"}
        yield {"__agui__": "reasoning_content", "delta": "用户问的是 "}
        yield {"__agui__": "reasoning_content", "delta": "VAT 申报。"}
        yield {"__agui__": "reasoning_end"}
        yield "Box 1 应付 £42,520。\n"


@pytest.mark.asyncio
async def test_reasoning_round_trip_emits_agui_events():
    """stream_agui_events 应把 engine 的 reasoning_* 信号正确编码为
    REASONING_* AG-UI 事件，并保持 REASONING_* 在 TEXT_MESSAGE_* 之前。"""
    out: list[str] = []
    async for sse in stream_agui_events(
        thread_id="t",
        run_id="r",
        engine=_StubEngine(),
        session=_StubSession(),
        user_message="hi",
    ):
        out.append(sse)
    joined = "".join(out)

    # 事件类型都出现过
    assert "REASONING_START" in joined
    assert "REASONING_MESSAGE_START" in joined
    assert "REASONING_MESSAGE_CONTENT" in joined
    assert "REASONING_MESSAGE_END" in joined
    assert "REASONING_END" in joined
    assert "TEXT_MESSAGE_START" in joined
    assert "TEXT_MESSAGE_CONTENT" in joined
    assert "RUN_FINISHED" in joined

    # delta 内容被传过去（JSON 会把每个 delta 单独 encode，所以分开断言）
    assert "用户问的是 " in joined
    assert "VAT 申报。" in joined
    assert "Box 1 应付" in joined

    # 顺序约束：REASONING_START 早于 TEXT_MESSAGE_START；REASONING_END
    # 在 RUN_FINISHED 之前；每个 REASONING_* 事件对都有配对的 start/end。
    assert joined.index("REASONING_START") < joined.index("TEXT_MESSAGE_START")
    assert joined.index("REASONING_END") < joined.index("RUN_FINISHED")


@pytest.mark.asyncio
async def test_reasoning_content_self_heals_without_explicit_start():
    """如果 engine 只 yield reasoning_content（漏掉 reasoning_start），
    适配器应自动补发 REASONING_START / REASONING_MESSAGE_START。"""

    class _NoStartEngine:
        async def chat(self, *args, **kwargs):
            yield {"__agui__": "reasoning_content", "delta": "x"}
            yield {"__agui__": "reasoning_end"}
            yield "answer"

    out: list[str] = []
    async for sse in stream_agui_events(
        thread_id="t", run_id="r",
        engine=_NoStartEngine(), session=_StubSession(), user_message="hi",
    ):
        out.append(sse)
    joined = "".join(out)
    assert "REASONING_START" in joined
    assert "REASONING_MESSAGE_CONTENT" in joined
    assert "x" in joined
    assert "REASONING_END" in joined
    assert joined.index("REASONING_START") < joined.index("REASONING_MESSAGE_CONTENT")
