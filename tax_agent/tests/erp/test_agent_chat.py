"""Agent chat MCP tool 测试 (v0 暂用 mock mode)"""
import pytest
from tax_agent.jurisdictions.uk.vat.agent_tools import UKVATAgentToolSet


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
