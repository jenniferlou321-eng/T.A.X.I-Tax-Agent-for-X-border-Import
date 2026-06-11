"""Agent chat MCP tool 测试 (v0 暂用 mock mode)"""
import json
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


# ═══════════════════════════════════════════════════════════
# MCP 工具签名一致性回归 (2026-06 修复)
# 防止再次出现 validate_return / submit_return 这种
# "LLM 拿平面字段调 → wrapper ** 展开 → TypeError" 的回归。
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_validate_vat_return_accepts_return_data_dict():
    """回归 (2026-06): validate_return 走 takes_dict 路径, 不再 TypeError"""
    from backend.jurisdictions.uk.vat.agent_tools import UKVATAgentToolSet
    tools = UKVATAgentToolSet()
    result = await tools.validate_return(return_data={
        "vat_due_sales": "2500.00",
        "vat_due_acquisitions": "0.00",
        "vat_reclaimed_purchases": "1200.00",
        "total_sales_ex_vat": "12500",
        "total_purchases_ex_vat": "6000",
        "total_goods_supplied_eu": "0",
        "total_goods_acquired_eu": "0",
    })
    assert "content" in result
    text = result["content"][0]["text"]
    parsed = json.loads(text)
    assert parsed["success"] is True


@pytest.mark.asyncio
async def test_submit_vat_return_accepts_return_data_dict():
    """回归 (2026-06): submit_return 走 takes_dict 路径, 3-arg + return_data dict 不再 TypeError"""
    from unittest.mock import patch, AsyncMock
    from backend.jurisdictions.uk.vat.agent_tools import UKVATAgentToolSet
    tools = UKVATAgentToolSet()
    with patch("backend.jurisdictions.uk.vat.agent_tools._build_hmrc_service") as ms:
        ms.return_value.submit_return = AsyncMock(return_value={
            "processingDate": "2026-04-07",
            "formBundleNumber": "FB-001",
            "paymentIndicator": "BANK",
        })
        result = await tools.submit_return(
            taxpayer_id="GB123456789",
            period_key="26A1",
            return_data={
                "vat_due_sales": "100.00",
                "vat_due_acquisitions": "0.00",
                "total_vat_due": "100.00",
                "vat_reclaimed_purchases": "0.00",
                "net_vat_due": "100.00",
                "total_sales_ex_vat": "500",
                "total_purchases_ex_vat": "0",
                "total_goods_supplied_eu": "0",
                "total_goods_acquired_eu": "0",
            },
        )
    parsed = json.loads(result["content"][0]["text"])
    assert parsed["success"] is True


def test_get_tool_metadata_all_8_have_json_schema():
    """回归 (2026-06): 8 个工具的 input_schema 必须是 JSON Schema dict, 全部带 properties"""
    from backend.jurisdictions.uk.vat.agent_tools import UKVATAgentToolSet
    tools = UKVATAgentToolSet()
    meta = {m["name"]: m for m in tools.get_tool_metadata()}
    assert len(meta) == 8
    for name, m in meta.items():
        schema = m["input_schema"]
        assert isinstance(schema, dict), f"{name} input_schema must be dict"
        assert "properties" in schema, f"{name} input_schema missing 'properties'"
        # 工具必须有 description 字段 (不能空)
        assert m.get("description"), f"{name} missing description"


def test_get_tool_metadata_validate_submit_have_return_data():
    """回归 (2026-06): validate / submit 的 9-Box 字段必须包成 return_data 子对象"""
    from backend.jurisdictions.uk.vat.agent_tools import UKVATAgentToolSet
    meta = {m["name"]: m for m in UKVATAgentToolSet().get_tool_metadata()}
    for name in ("validate_vat_return", "submit_vat_return"):
        schema = meta[name]["input_schema"]
        assert "return_data" in schema["properties"], f"{name} missing return_data"
        rd = schema["properties"]["return_data"]
        assert "properties" in rd, f"{name}.return_data must have nested properties"
        assert "vat_due_sales" in rd["properties"], f"{name}.return_data missing vat_due_sales"


@pytest.mark.asyncio
async def test_analyze_business_data_returns_nine_box_in_hmrc_format():
    """回归 (2026-06): analyze_business_data 的 nine_box 必须用 HMRC 字段名"""
    from backend.jurisdictions.uk.vat.agent_tools import UKVATAgentToolSet
    import json as _json
    tools = UKVATAgentToolSet()
    ir = _json.loads(_json.dumps({
        "company": {"name": "Test Co", "vrn": "GB123"},
        "sales_invoices": [],
        "purchase_invoices": [],
    }))
    raw = await tools.analyze_business_data(_json.dumps(ir))
    result = _json.loads(raw["content"][0]["text"])
    nine_box = result["nine_box"]
    # 必须是 HMRC 风格 (无 box 前缀)
    assert "vat_due_sales" in nine_box
    assert "total_sales_ex_vat" in nine_box
    # 旧 alias 仍要保留
    assert "box1_vat_due_sales" in result["nine_box_legacy"]
    # 字段命名信息要带
    assert result["nine_box_field_naming"]["current"] == "hmrc"
