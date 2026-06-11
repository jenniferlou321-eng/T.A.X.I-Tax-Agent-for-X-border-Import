"""Tests for the tax knowledge MCP server."""
import json

import pytest

from backend.agent.tax_knowledge_store import TaxKnowledgeStore, KnowledgeSection
from backend.agent.tax_knowledge_prompts import TAX_KB_SUBAGENT_PROMPT
from backend.agent.tax_knowledge_tools import TaxKnowledgeAgentToolSet
from backend.agent.tools import create_mcp_servers
from backend.agent.engine import TaxAgentEngine
from backend.registry import JurisdictionRegistry
from backend.agent.prompts import get_system_prompt


def test_subagent_prompt_exists():
    assert "tax_kb_researcher" in TAX_KB_SUBAGENT_PROMPT
    assert "search_tax_knowledge" in TAX_KB_SUBAGENT_PROMPT


class TestTaxKnowledgeStore:
    def test_empty_store_lists_nothing(self):
        store = TaxKnowledgeStore(base_path="/nonexistent")
        assert store.list_supported() == []

    def test_parses_markdown_sections(self, tmp_path):
        uk_vat = tmp_path / "uk"
        uk_vat.mkdir(parents=True)
        (uk_vat / "vat.md").write_text(
            "# UK VAT Rules\n\n"
            "## Standard Rate\n\nStandard rate is 20%.\n\n"
            "## EU B2B Sales\n\nEU B2B sales are zero-rated.\n",
            encoding="utf-8",
        )
        store = TaxKnowledgeStore(base_path=str(tmp_path))
        supported = store.list_supported()
        assert ("uk", "vat") in supported
        results = store.search("uk", "vat", "EU B2B", top_k=5)
        assert len(results) == 1
        assert results[0].title == "EU B2B Sales"
        assert "zero-rated" in results[0].content
        assert results[0].source_path.endswith("uk/vat.md")

    def test_search_returns_empty_when_no_match(self, tmp_path):
        uk_vat = tmp_path / "uk"
        uk_vat.mkdir(parents=True)
        (uk_vat / "vat.md").write_text("## Standard Rate\n20%\n", encoding="utf-8")
        store = TaxKnowledgeStore(base_path=str(tmp_path))
        assert store.search("uk", "vat", "nonexistent topic") == []

    def test_top_k_truncates_results(self, tmp_path):
        uk_vat = tmp_path / "uk"
        uk_vat.mkdir(parents=True)
        (uk_vat / "vat.md").write_text(
            "## A\nVAT\n\n## B\nVAT\n\n## C\nVAT\n",
            encoding="utf-8",
        )
        store = TaxKnowledgeStore(base_path=str(tmp_path))
        results = store.search("uk", "vat", "VAT", top_k=2)
        assert len(results) == 2

    def test_h3_not_treated_as_h2(self, tmp_path):
        uk_vat = tmp_path / "uk"
        uk_vat.mkdir(parents=True)
        (uk_vat / "vat.md").write_text(
            "## Standard Rate\n20%\n\n### Detail\nMore info.\n",
            encoding="utf-8",
        )
        store = TaxKnowledgeStore(base_path=str(tmp_path))
        sections = store.search("uk", "vat", "Standard")
        assert len(sections) == 1
        assert "### Detail" in sections[0].content

    def test_multi_word_ranking(self, tmp_path):
        uk_vat = tmp_path / "uk"
        uk_vat.mkdir(parents=True)
        (uk_vat / "vat.md").write_text(
            "## EU B2B Sales\nZero-rated.\n\n## Domestic Sales\nStandard rate.\n",
            encoding="utf-8",
        )
        store = TaxKnowledgeStore(base_path=str(tmp_path))
        results = store.search("uk", "vat", "EU B2B")
        assert results[0].title == "EU B2B Sales"

    def test_list_supported_is_sorted(self, tmp_path):
        (tmp_path / "uk").mkdir()
        (tmp_path / "de").mkdir()
        (tmp_path / "uk" / "vat.md").write_text("## A\n", encoding="utf-8")
        (tmp_path / "de" / "vat.md").write_text("## A\n", encoding="utf-8")
        store = TaxKnowledgeStore(base_path=str(tmp_path))
        assert store.list_supported() == [("de", "vat"), ("uk", "vat")]


class TestTaxKnowledgeTools:
    @pytest.mark.asyncio
    async def test_list_supported_jurisdictions(self, tmp_path):
        uk_dir = tmp_path / "uk"
        uk_dir.mkdir()
        (uk_dir / "vat.md").write_text("## Standard Rate\n20%\n", encoding="utf-8")
        tools = TaxKnowledgeAgentToolSet(store_base_path=str(tmp_path))
        result = await tools.list_supported_jurisdictions()
        text = result["content"][0]["text"]
        assert "uk" in text
        assert "vat" in text

    @pytest.mark.asyncio
    async def test_get_tax_rates_uk_vat(self):
        tools = TaxKnowledgeAgentToolSet()
        result = await tools.get_tax_rates(jurisdiction="uk", tax_type="vat", year="2026")
        parsed = json.loads(result["content"][0]["text"])
        assert parsed["success"] is True
        assert parsed["jurisdiction"] == "uk"
        assert parsed["tax_type"] == "vat"
        assert "standard" in parsed["rates"]

    @pytest.mark.asyncio
    async def test_search_tax_knowledge(self, tmp_path):
        uk_dir = tmp_path / "uk"
        uk_dir.mkdir()
        (uk_dir / "vat.md").write_text(
            "## EU B2B Sales\nZero-rated when customer has valid EU VAT number.\n",
            encoding="utf-8",
        )
        tools = TaxKnowledgeAgentToolSet(store_base_path=str(tmp_path))
        result = await tools.search_tax_knowledge(jurisdiction="uk", tax_type="vat", query="EU B2B")
        parsed = json.loads(result["content"][0]["text"])
        assert parsed["success"] is True
        assert len(parsed["results"]) == 1
        assert "Zero-rated" in parsed["results"][0]["content"]


def test_engine_has_global_kb_server():
    registry = JurisdictionRegistry()
    engine = TaxAgentEngine(registry=registry, api_key="dummy")
    assert engine._mcp_servers is not None
    assert ("global", "tax_kb") in engine._mcp_servers


def test_prompt_mentions_tax_kb_subagent():
    prompt = get_system_prompt("uk", "vat")
    assert "tax_kb_researcher" in prompt
    assert "get_tax_rates" in prompt
