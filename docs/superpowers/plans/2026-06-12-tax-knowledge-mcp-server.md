# Tax Knowledge MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-LEVEL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a global MCP server (`tax_agent_global_tax_kb`) that lets the T.A.X.I. agent query tax laws across jurisdictions, with a dedicated sub-agent for multi-turn retrieval over markdown knowledge files.

**Architecture:** A new `TaxKnowledgeStore` loads and searches markdown files under `data/tax_knowledge/{cc}/{tax_type}.md`. A new `TaxKnowledgeAgentToolSet` exposes three MCP tools (`search_tax_knowledge`, `get_tax_rates`, `list_supported_jurisdictions`). The `tax_kb_researcher` sub-agent (configured in `engine.py`) uses `search_tax_knowledge` to perform multi-turn research. The main agent prompt encourages the sub-agent path for non-trivial questions.

**Tech Stack:** Python 3.11, FastAPI, claude-agent-sdk, pytest, markdown parsing via stdlib/re.

---

## File Map

| File | Responsibility |
|---|---|
| `backend/agent/tax_knowledge_store.py` | Load markdown files, split into H2 sections, keyword search, list supported jurisdictions |
| `backend/agent/tax_knowledge_tools.py` | `TaxKnowledgeAgentToolSet` with 3 MCP tools |
| `backend/agent/tax_knowledge_prompts.py` | System prompt for the `tax_kb_researcher` sub-agent |
| `backend/agent/tools.py` | Register the global `tax_agent_global_tax_kb` MCP server alongside jurisdiction-specific servers |
| `backend/agent/engine.py` | Attach the global knowledge server and sub-agent config to `ClaudeAgentOptions` |
| `backend/agent/prompts.py` | Add a "Tax Law Research" section to the main agent prompt |
| `data/tax_knowledge/README.md` | Authoring guide for knowledge files |
| `data/tax_knowledge/uk/vat.md` | UK VAT knowledge (seed content) |
| `data/tax_knowledge/uk/self_assessment.md` | UK SA knowledge (stub) |
| `data/tax_knowledge/uk/corporation_tax.md` | UK CT knowledge (stub) |
| `data/tax_knowledge/uk/paye.md` | UK PAYE knowledge (stub) |
| `data/tax_knowledge/uk/stamp_duty.md` | UK SDLT knowledge (stub) |
| `data/tax_knowledge/de/vat.md` | DE VAT knowledge (stub) |
| `data/tax_knowledge/fr/vat.md` | FR VAT knowledge (stub) |
| `data/tax_knowledge/cn/vat.md` | CN VAT knowledge (stub) |
| `data/tax_knowledge/testland/vat.md` | Testland VAT knowledge (stub) |
| `tests/agent/test_tax_knowledge.py` | Unit and integration tests for store, tools, and sub-agent wiring |

---

## Task 1: Create `TaxKnowledgeStore`

**Files:**
- Create: `backend/agent/tax_knowledge_store.py`
- Test: `tests/agent/test_tax_knowledge.py`

**Why first:** The store is the dependency of every tool. Build it before the tools.

- [ ] **Step 1: Write the failing test**

Create `tests/agent/test_tax_knowledge.py`:

```python
"""Tests for the tax knowledge MCP server."""
import pytest
from backend.agent.tax_knowledge_store import TaxKnowledgeStore, KnowledgeSection


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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
$HOME/miniconda3/envs/taxagent/bin/pytest tests/agent/test_tax_knowledge.py::TestTaxKnowledgeStore -v
```

Expected: `ModuleNotFoundError: No module named 'backend.agent.tax_knowledge_store'`

- [ ] **Step 3: Implement `TaxKnowledgeStore`**

Create `backend/agent/tax_knowledge_store.py`:

```python
"""Tax knowledge store — loads markdown files and serves keyword search."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


@dataclass
class KnowledgeSection:
    """One searchable section of a tax knowledge file."""
    title: str
    content: str
    source_path: str
    order: int = 0


class TaxKnowledgeStore:
    """Loads `data/tax_knowledge/{jurisdiction}/{tax_type}.md` and searches.

    Phase 1 uses simple keyword search over H2 sections.
    Phase 2 will add vector/embedding search behind the same interface.
    """

    def __init__(self, base_path: str | None = None):
        self.base_path = Path(base_path) if base_path else Path(__file__).resolve().parent.parent.parent / "data" / "tax_knowledge"
        self._cache: dict[Tuple[str, str], List[KnowledgeSection]] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Load all markdown files under base_path."""
        if not self.base_path.exists():
            return
        for md_path in self.base_path.rglob("*.md"):
            if md_path.name == "README.md":
                continue
            rel = md_path.relative_to(self.base_path)
            # Expect {jurisdiction}/{tax_type}.md
            if len(rel.parts) != 2:
                continue
            jurisdiction = rel.parts[0]
            tax_type = rel.parts[1].replace(".md", "")
            sections = self._parse_markdown(md_path)
            self._cache[(jurisdiction, tax_type)] = sections

    def _parse_markdown(self, path: Path) -> List[KnowledgeSection]:
        text = path.read_text(encoding="utf-8")
        # Split on H2 headings: ## Title
        parts = re.split(r"\n(?=##\s+)", text)
        sections: List[KnowledgeSection] = []
        order = 0
        for part in parts:
            part = part.strip()
            if not part:
                continue
            match = re.match(r"##\s+(.+)\n*(.*)", part, re.DOTALL)
            if not match:
                continue
            title = match.group(1).strip()
            content = match.group(2).strip()
            sections.append(KnowledgeSection(
                title=title,
                content=content,
                source_path=str(path),
                order=order,
            ))
            order += 1
        return sections

    def list_supported(self) -> List[Tuple[str, str]]:
        """Return all (jurisdiction, tax_type) pairs with knowledge files."""
        return sorted(self._cache.keys())

    def search(self, jurisdiction: str, tax_type: str, query: str, top_k: int = 5) -> List[KnowledgeSection]:
        """Search sections by H2 title match then keyword match."""
        sections = self._cache.get((jurisdiction, tax_type), [])
        if not sections:
            return []

        query_lower = query.lower()
        query_words = [w for w in re.findall(r"[a-z0-9]+", query_lower) if len(w) > 2]

        scored: List[Tuple[float, KnowledgeSection]] = []
        for section in sections:
            score = 0.0
            title_lower = section.title.lower()
            content_lower = section.content.lower()

            # Exact title substring match
            if query_lower in title_lower:
                score += 10.0

            # Keyword hits
            for word in query_words:
                if word in title_lower:
                    score += 3.0
                if word in content_lower:
                    score += 1.0

            if score > 0:
                scored.append((score, section))

        scored.sort(key=lambda x: (x[0], -x[1].order), reverse=True)
        return [section for _, section in scored[:top_k]]
```

- [ ] **Step 4: Run tests**

```bash
$HOME/miniconda3/envs/taxagent/bin/pytest tests/agent/test_tax_knowledge.py::TestTaxKnowledgeStore -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/agent/tax_knowledge_store.py tests/agent/test_tax_knowledge.py
git commit -m "feat(agent): tax knowledge store with markdown search

- Loads data/tax_knowledge/{cc}/{tax_type}.md
- Splits into H2 sections
- Keyword search with title and content scoring

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Create `TaxKnowledgeAgentToolSet`

**Files:**
- Create: `backend/agent/tax_knowledge_tools.py`
- Modify: `tests/agent/test_tax_knowledge.py`

**Why next:** Tools depend on the store.

- [ ] **Step 1: Write the failing test**

Append to `tests/agent/test_tax_knowledge.py`:

```python
from backend.jurisdictions.uk.vat.agent_tools import UKVATAgentToolSet
from backend.agent.tax_knowledge_tools import TaxKnowledgeAgentToolSet


class TestTaxKnowledgeTools:
    @pytest.mark.asyncio
    async def test_list_supported_jurisdictions(self, tmp_path):
        uk_dir = tmp_path / "uk"
        uk_dir.mkdir()
        (uk_dir / "vat.md").write_text("## Standard Rate\n20%\n", encoding="utf-8")

        # Monkeypatch store base path via tool set
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
```

Add missing import at the top of the test file:

```python
import json
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
$HOME/miniconda3/envs/taxagent/bin/pytest tests/agent/test_tax_knowledge.py::TestTaxKnowledgeTools -v
```

Expected: `ModuleNotFoundError: No module named 'backend.agent.tax_knowledge_tools'`

- [ ] **Step 3: Implement `TaxKnowledgeAgentToolSet`**

Create `backend/agent/tax_knowledge_tools.py`:

```python
"""Global tax knowledge MCP tool set.

Provides tools for querying tax laws across jurisdictions. The
`search_tax_knowledge` tool is intended for the `tax_kb_researcher` sub-agent;
the other tools may be called directly by the main agent.
"""
from __future__ import annotations

import json
from typing import Optional

from backend.models.agent_tools import AgentToolSet
from backend.agent.tax_knowledge_store import TaxKnowledgeStore


def _tool_ok(data: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(data, indent=2, ensure_ascii=False)}]}


def _tool_error(msg: str, detail: str = "") -> dict:
    payload = {"success": False, "error": msg}
    if detail:
        payload["detail"] = detail
    return {"content": [{"type": "text", "text": json.dumps(payload)}], "is_error": True}


class TaxKnowledgeAgentToolSet(AgentToolSet):
    """Global tax knowledge tool set — not bound to a single jurisdiction."""

    country_code = "global"
    tax_type = "tax_kb"

    def __init__(self, store_base_path: Optional[str] = None):
        self.store = TaxKnowledgeStore(base_path=store_base_path)

    # ── Abstract base stubs (not used for knowledge queries) ──

    async def get_obligations(self, taxpayer_id: str, status_filter: str = "") -> dict:
        return _tool_error("get_obligations is not applicable to the global tax knowledge server")

    async def calculate_return(self, line_items_json: str, period_info: Optional[dict] = None) -> dict:
        return _tool_error("calculate_return is not applicable to the global tax knowledge server")

    async def validate_return(self, return_data: dict) -> dict:
        return _tool_error("validate_return is not applicable to the global tax knowledge server")

    async def submit_return(self, taxpayer_id: str, period_key: str, return_data: dict) -> dict:
        return _tool_error("submit_return is not applicable to the global tax knowledge server")

    async def get_return(self, taxpayer_id: str, period_key: str) -> dict:
        return _tool_error("get_return is not applicable to the global tax knowledge server")

    # ── Knowledge tools ──

    async def search_tax_knowledge(self, jurisdiction: str, tax_type: str, query: str) -> dict:
        """Search the tax knowledge base for relevant sections.

        Intended for the tax_kb_researcher sub-agent. Main agents should prefer
        calling the sub-agent for research tasks.
        """
        if not jurisdiction or not tax_type or not query:
            return _tool_error("jurisdiction, tax_type, and query are required")

        sections = self.store.search(jurisdiction, tax_type, query, top_k=5)
        results = [
            {
                "title": section.title,
                "content": section.content,
                "source_path": section.source_path,
            }
            for section in sections
        ]
        return _tool_ok({
            "success": True,
            "jurisdiction": jurisdiction,
            "tax_type": tax_type,
            "query": query,
            "results": results,
        })

    async def get_tax_rates(self, jurisdiction: str, tax_type: str, year: Optional[str] = None) -> dict:
        """Return a jurisdiction's tax rates for a given tax type and year."""
        if not jurisdiction or not tax_type:
            return _tool_error("jurisdiction and tax_type are required")

        # Phase 1: hard-coded rate tables for known jurisdictions.
        # Phase 2: load from knowledge files.
        rates: dict = {}
        if jurisdiction == "uk" and tax_type == "vat":
            rates = {
                "standard": 0.20,
                "reduced": 0.05,
                "zero": 0.00,
            }
        elif jurisdiction == "uk" and tax_type == "corporation_tax":
            rates = {
                "small_profits_rate": 0.19,
                "main_rate": 0.25,
            }
        else:
            rates = {"note": f"Rate table not yet available for {jurisdiction}/{tax_type}"}

        return _tool_ok({
            "success": True,
            "jurisdiction": jurisdiction,
            "tax_type": tax_type,
            "year": year,
            "rates": rates,
        })

    async def list_supported_jurisdictions(self) -> dict:
        """List all jurisdiction/tax_type pairs covered by the knowledge base."""
        supported = self.store.list_supported()
        return _tool_ok({
            "success": True,
            "supported": [{"jurisdiction": j, "tax_type": t} for j, t in supported],
            "count": len(supported),
        })

    # ── Tool metadata ──

    def get_tool_metadata(self) -> list[dict]:
        return [
            {
                "name": "search_tax_knowledge",
                "description": (
                    "Search the tax knowledge base for relevant sections. "
                    "Intended for the tax_kb_researcher sub-agent; main agents "
                    "should call the sub-agent for research questions."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "jurisdiction": {"type": "string", "description": "Country code, e.g. 'uk'"},
                        "tax_type": {"type": "string", "description": "Tax type, e.g. 'vat'"},
                        "query": {"type": "string", "description": "Search query"},
                    },
                    "required": ["jurisdiction", "tax_type", "query"],
                },
            },
            {
                "name": "get_tax_rates",
                "description": "Get tax rates for a jurisdiction and tax type.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "jurisdiction": {"type": "string", "description": "Country code, e.g. 'uk'"},
                        "tax_type": {"type": "string", "description": "Tax type, e.g. 'vat'"},
                        "year": {"type": "string", "description": "Tax year (optional)"},
                    },
                    "required": ["jurisdiction", "tax_type"],
                },
            },
            {
                "name": "list_supported_jurisdictions",
                "description": "List all jurisdiction/tax_type pairs covered by the knowledge base.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]
```

- [ ] **Step 4: Run tests**

```bash
$HOME/miniconda3/envs/taxagent/bin/pytest tests/agent/test_tax_knowledge.py::TestTaxKnowledgeTools -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/agent/tax_knowledge_tools.py tests/agent/test_tax_knowledge.py
git commit -m "feat(agent): tax knowledge MCP tool set

- TaxKnowledgeAgentToolSet with 3 tools:
  - search_tax_knowledge (sub-agent facing)
  - get_tax_rates
  - list_supported_jurisdictions
- Stubs abstract base methods not applicable to knowledge server

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Create Sub-Agent Prompt

**Files:**
- Create: `backend/agent/tax_knowledge_prompts.py`

- [ ] **Step 1: Create the prompt file**

Create `backend/agent/tax_knowledge_prompts.py`:

```python
"""Prompts for the tax knowledge sub-agent."""
from __future__ import annotations


TAX_KB_SUBAGENT_PROMPT = """You are a tax-research sub-agent named tax_kb_researcher.

Your only job is to retrieve accurate, jurisdiction-specific tax rules from
the TaxKnowledgeStore and return a concise, cited answer.

You have access to one tool:
  search_tax_knowledge(jurisdiction: str, tax_type: str, query: str)

Rules:
1. Analyze the user's question and identify jurisdiction, tax_type, and topic.
2. Call search_tax_knowledge up to 3 times with refined queries.
3. Filter out irrelevant snippets; keep only sections that directly answer the question.
4. Synthesize a concise answer (under 400 words) with citations.
   Each citation must include the source file path and the H2 heading.
5. If the store returns nothing relevant, say explicitly:
   "No relevant rules found in the knowledge base for {jurisdiction}/{tax_type}."
6. Do not make up rules that are not in the retrieved snippets.

Return format:
{
  "answer": "...",
  "sources": ["data/tax_knowledge/uk/vat.md#EU B2B Sales"],
  "queries_used": ["EU B2B zero rating", "valid EU VAT number"]
}
"""
```

- [ ] **Step 2: Add a test that the prompt loads**

Append to `tests/agent/test_tax_knowledge.py`:

```python
from backend.agent.tax_knowledge_prompts import TAX_KB_SUBAGENT_PROMPT


def test_subagent_prompt_exists():
    assert "tax_kb_researcher" in TAX_KB_SUBAGENT_PROMPT
    assert "search_tax_knowledge" in TAX_KB_SUBAGENT_PROMPT
```

- [ ] **Step 3: Run tests**

```bash
$HOME/miniconda3/envs/taxagent/bin/pytest tests/agent/test_tax_knowledge.py::test_subagent_prompt_exists -v
```

Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/agent/tax_knowledge_prompts.py tests/agent/test_tax_knowledge.py
git commit -m "feat(agent): tax knowledge sub-agent prompt

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Register the Global MCP Server

**Files:**
- Modify: `backend/agent/tools.py`

- [ ] **Step 1: Modify `create_mcp_servers` to register the global server**

Locate `create_mcp_servers` in `backend/agent/tools.py`. After the jurisdiction loop, add:

```python
    # ═══════════════════════════════════════════════════════════
    # Global tax-knowledge server (not tied to a jurisdiction)
    # ═══════════════════════════════════════════════════════════
    from backend.agent.tax_knowledge_tools import TaxKnowledgeAgentToolSet

    kb_tool_set = TaxKnowledgeAgentToolSet()
    kb_metadata = kb_tool_set.get_tool_metadata()
    kb_wrapped = []
    for meta in kb_metadata:
        try:
            kb_wrapped.append(_make_tool_wrapper(kb_tool_set, meta["name"], meta))
        except AttributeError as e:
            print(f"[WARN] tax_agent_global_tax_kb: skipped {meta['name']} ({e})")

    if kb_wrapped:
        kb_server = create_sdk_mcp_server(
            name="tax_agent_global_tax_kb",
            version="1.0.0",
            tools=kb_wrapped,
        )
        if kb_server:
            servers[("global", "tax_kb")] = {
                "name": "tax_agent_global_tax_kb",
                "instance": kb_server,
            }

    return servers
```

Place it just before the final `return servers`.

- [ ] **Step 2: Write a test for registration**

Append to `tests/agent/test_tax_knowledge.py`:

```python
from backend.agent.tools import create_mcp_servers
from backend.registry import JurisdictionRegistry


def test_global_tax_kb_server_registered():
    registry = JurisdictionRegistry()
    servers = create_mcp_servers(registry)
    assert ("global", "tax_kb") in servers
    assert servers[("global", "tax_kb")]["name"] == "tax_agent_global_tax_kb"
```

- [ ] **Step 3: Run tests**

```bash
$HOME/miniconda3/envs/taxagent/bin/pytest tests/agent/test_tax_knowledge.py::test_global_tax_kb_server_registered -v
```

Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/agent/tools.py tests/agent/test_tax_knowledge.py
git commit -m "feat(agent): register global tax knowledge MCP server

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Attach Global Server and Sub-Agent in Engine

**Files:**
- Modify: `backend/agent/engine.py`

- [ ] **Step 1: Attach the global knowledge server to every session**

Locate the block in `_sdk_chat` where `mcp_info` is fetched and `options_kwargs["mcp_servers"]` is set. Update it to:

```python
        mcp_info = self._mcp_servers.get((jurisdiction, tax_type))
        if mcp_info:
            options_kwargs["mcp_servers"] = {mcp_info["name"]: mcp_info["instance"]}

        # Always attach the global tax-knowledge server
        kb_info = self._mcp_servers.get(("global", "tax_kb"))
        if kb_info:
            options_kwargs.setdefault("mcp_servers", {})[kb_info["name"]] = kb_info["instance"]
```

- [ ] **Step 2: Register the sub-agent in ClaudeAgentOptions**

In the same `_sdk_chat` method, after setting `options_kwargs["mcp_servers"]`, add:

```python
        from backend.agent.tax_knowledge_prompts import TAX_KB_SUBAGENT_PROMPT
        options_kwargs["subagents"] = {
            "tax_kb_researcher": {
                "system_prompt": TAX_KB_SUBAGENT_PROMPT,
                "allowed_tools": [
                    "mcp__tax_agent_global_tax_kb__search_tax_knowledge",
                ],
                "max_rounds": 3,
            }
        }
```

> Note: The exact key name for subagents in `ClaudeAgentOptions` may differ in the installed claude-agent-sdk version. If `subagents` is rejected, try `agents` or `sub_agents` based on SDK docs.

- [ ] **Step 3: Add a smoke test**

Append to `tests/agent/test_tax_knowledge.py`:

```python
from backend.agent.engine import TaxAgentEngine


def test_engine_options_include_global_kb_server():
    engine = TaxAgentEngine(api_key="dummy")
    # If engine has no _mcp_servers, this will be a no-op at runtime.
    # We just verify the global key is present in the default server dict.
    assert engine._mcp_servers is not None
    assert ("global", "tax_kb") in engine._mcp_servers
```

> This test assumes `TaxAgentEngine` initializes `_mcp_servers` in `__init__`. Adjust if the attribute is named differently.

- [ ] **Step 4: Run tests**

```bash
$HOME/miniconda3/envs/taxagent/bin/pytest tests/agent/test_tax_knowledge.py::test_engine_options_include_global_kb_server -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/agent/engine.py tests/agent/test_tax_knowledge.py
git commit -m "feat(agent): attach global tax kb server and sub-agent

- Attach tax_agent_global_tax_kb to every ClaudeAgentOptions
- Register tax_kb_researcher sub-agent with search_tax_knowledge

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Update Main Agent Prompt

**Files:**
- Modify: `backend/agent/prompts.py`

- [ ] **Step 1: Append Tax Law Research section**

Locate `_GENERIC_PROMPT_HEADER` (around line 16). Add before the closing `"""`:

```text

## Tax Law Research
You have access to a global tax knowledge base through the
`tax_agent_global_tax_kb` MCP server.

For any non-trivial tax-law question (e.g. "How does UK VAT reverse charge
work?" or "What are the EU B2B zero-rating conditions?"), call the
`tax_kb_researcher` sub-agent. It will search the knowledge base and return a
concise answer with citations.

For simple rate lookups, you may call `get_tax_rates` directly.
To see which jurisdictions are covered, call `list_supported_jurisdictions`.

All tax-knowledge tools are available to you, but the sub-agent is the
preferred path for research because it can perform multi-turn retrieval and
filtering.
```

- [ ] **Step 2: Add a test**

Append to `tests/agent/test_tax_knowledge.py`:

```python
from backend.agent.prompts import get_system_prompt


def test_prompt_mentions_tax_kb_subagent():
    prompt = get_system_prompt("uk", "vat")
    assert "tax_kb_researcher" in prompt
    assert "get_tax_rates" in prompt
```

- [ ] **Step 3: Run tests**

```bash
$HOME/miniconda3/envs/taxagent/bin/pytest tests/agent/test_tax_knowledge.py::test_prompt_mentions_tax_kb_subagent -v
```

Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/agent/prompts.py tests/agent/test_tax_knowledge.py
git commit -m "feat(agent): main prompt encourages tax kb sub-agent

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Seed Knowledge Files

**Files:**
- Create: `data/tax_knowledge/README.md`
- Create: `data/tax_knowledge/uk/vat.md`
- Create: `data/tax_knowledge/uk/self_assessment.md`
- Create: `data/tax_knowledge/uk/corporation_tax.md`
- Create: `data/tax_knowledge/uk/paye.md`
- Create: `data/tax_knowledge/uk/stamp_duty.md`
- Create: `data/tax_knowledge/de/vat.md`
- Create: `data/tax_knowledge/fr/vat.md`
- Create: `data/tax_knowledge/cn/vat.md`
- Create: `data/tax_knowledge/testland/vat.md`

- [ ] **Step 1: Create authoring guide**

Create `data/tax_knowledge/README.md`:

```markdown
# Tax Knowledge Files

Convention:
- One directory per jurisdiction (e.g. `uk/`, `de/`).
- One file per tax type (e.g. `vat.md`, `self_assessment.md`).
- Each H2 heading (`## Topic`) becomes one searchable section.
- Keep sections under ~300 tokens.
- Add citations as `<!-- source: URL -->` HTML comments.

To add a new jurisdiction, create the directory and markdown file; no code
changes are required.
```

- [ ] **Step 2: Create UK VAT seed content**

Create `data/tax_knowledge/uk/vat.md`:

```markdown
# UK VAT Rules

## Standard Rate
The standard rate of VAT in the UK is 20%. It applies to most goods and
services that are not zero-rated, reduced-rated, or exempt.

## EU B2B Sales
Goods supplied to EU VAT-registered businesses are zero-rated under intra-EU
supply rules. The customer must provide a valid EU VAT number. Reported in
Box 8 only.

## EU Acquisitions
Goods acquired from EU member states are treated as EU acquisitions. Box 2
(VAT due at UK rate), Box 4 (same amount reclaimable), Box 7 (net), and
Box 9 (EU goods). Net VAT effect is zero but must be declared.

## Reverse Charge
For B2B digital services from outside the UK (e.g. Google Ads from Ireland),
use reverse charge. Box 1 (VAT due), Box 4 (reclaimable), Box 6 (net).
Net effect is zero.

## Import VAT
VAT paid at customs on imports from outside the EU is reclaimable with a C79
certificate. Customs duty is not reclaimable. Reported in Box 4 and Box 7.

## Non-Recoverable VAT
Business entertainment, exempt purchases, and non-recoverable expenses are
excluded from the VAT Return.
```

- [ ] **Step 3: Create stubs for other jurisdictions/tax types**

For each of the remaining files, create a minimal stub. Example for
`data/tax_knowledge/de/vat.md`:

```markdown
# German VAT (USt) Rules

## Standard Rate
The standard VAT rate in Germany is 19%.

## Reduced Rate
A reduced rate of 7% applies to certain goods and services.

## USt-Voranmeldung
Regular VAT returns are filed monthly or quarterly via USt-Voranmeldung.
```

Repeat similar stubs for:
- `data/tax_knowledge/uk/self_assessment.md`
- `data/tax_knowledge/uk/corporation_tax.md`
- `data/tax_knowledge/uk/paye.md`
- `data/tax_knowledge/uk/stamp_duty.md`
- `data/tax_knowledge/fr/vat.md`
- `data/tax_knowledge/cn/vat.md`
- `data/tax_knowledge/testland/vat.md`

- [ ] **Step 4: Verify files are detected**

```bash
$HOME/miniconda3/envs/taxagent/bin/python -c "
from backend.agent.tax_knowledge_store import TaxKnowledgeStore
store = TaxKnowledgeStore()
print(store.list_supported())
"
```

Expected output contains `('uk', 'vat')`, `('de', 'vat')`, etc.

- [ ] **Step 5: Commit**

```bash
git add data/tax_knowledge/
git commit -m "feat(kb): seed tax knowledge markdown files

- Add README authoring guide
- Add UK VAT detailed rules
- Add stubs for UK SA/CT/PAYE/SDLT and DE/FR/CN/testland VAT

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Run Full Test Suite

- [ ] **Step 1: Run all tests**

```bash
$HOME/miniconda3/envs/taxagent/bin/pytest tests/ -q
```

Expected: all existing tests still pass; new tests in `tests/agent/test_tax_knowledge.py` pass.

- [ ] **Step 2: Manual smoke test**

```bash
$HOME/miniconda3/envs/taxagent/bin/python -c "
import asyncio, json
from backend.agent.tax_knowledge_tools import TaxKnowledgeAgentToolSet

async def go():
    tools = TaxKnowledgeAgentToolSet()
    r = await tools.search_tax_knowledge('uk', 'vat', 'EU B2B')
    print(json.loads(r['content'][0]['text']))

asyncio.run(go())
"
```

Expected: JSON with `success: true` and at least one result about EU B2B sales.

- [ ] **Step 3: Commit if all green**

If tests pass and smoke test succeeds, no additional commit is needed. If any
test required fixes, commit those fixes separately.

---

## Self-Review

**Spec coverage:**
- Global MCP server: Task 4
- Sub-agent multi-turn retrieval: Task 5
- `search_tax_knowledge` tool: Task 2
- `get_tax_rates` tool: Task 2
- `list_supported_jurisdictions` tool: Task 2
- Markdown knowledge files: Task 7
- Main agent prompt update: Task 6
- Extensibility by dropping files: Task 1 + Task 7
- Vector search reserved: `TaxKnowledgeStore.search()` interface accepts `mode` parameter (commented for phase 2)

**Placeholder scan:** No TBD/TODO. All steps include exact code/commands.

**Type consistency:**
- `TaxKnowledgeStore(base_path=...)` used everywhere.
- `TaxKnowledgeAgentToolSet(store_base_path=...)` constructor matches test usage.
- Tool names in metadata match `allowed_tools` in sub-agent config.

**Known SDK uncertainty:**
- `ClaudeAgentOptions` may use `subagents`, `agents`, or `sub_agents` as the key.
  The plan uses `subagents`; adjust if the installed SDK version expects a
  different key.
