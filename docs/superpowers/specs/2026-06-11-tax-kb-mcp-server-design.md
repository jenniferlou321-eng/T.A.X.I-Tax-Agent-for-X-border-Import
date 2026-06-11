# Tax Knowledge MCP Server — Design Spec

**Date:** 2026-06-11  
**Topic:** A global, extensible MCP server that lets the T.A.X.I. agent query tax laws across jurisdictions.  
**Status:** Design approved; ready for implementation plan.

---

## Context

T.A.X.I. currently embeds tax-law knowledge in two places:

1. `backend/agent/prompts.py` — hard-coded Python strings for UK VAT/SA/CT/PAYE/SDLT; DE/FR/CN fall back to a 4-line stub.
2. `docs/jurisdictions/{cc}/` — markdown documents (e.g. `uk/vat-rules.md`, `cn/README.md`).

There is **no structured, queryable tax-law API** and **no MCP tool** that the agent can call to look up rules on demand. The LLM must rely on whatever fit in its context window or hope its pre-training is correct. For a tax-filing product, that is a compliance risk.

This spec designs a new MCP server (`tax_agent_global_tax_kb`) plus a dedicated sub-agent for multi-turn retrieval.

---

## Goals

1. **Agent can query tax laws on demand** via MCP tools.
2. **Coverage starts with existing jurisdictions** (UK, DE, FR, CN, testland) and is **extensible without code changes**.
3. **Multi-turn retrieval** is handled by a dedicated sub-agent, not by ad-hoc tool chaining.
4. **Vector/embedding support is reserved** for a future phase; the first phase uses keyword search over markdown sections.
5. **No changes to existing filing tools, adapters, registry, or orchestrator.**

---

## Non-Goals

- Real-time web scraping of tax authorities' websites.
- A vector database in phase 1.
- Replacing the jurisdiction-specific system prompts in `prompts.py`.
- Multi-language answers (English only for phase 1).

---

## Architecture

```text
┌────────────────────────────────────────────────────────────────────┐
│ Main Agent (ClaudeSDKClient)                                       │
│                                                                    │
│  System prompt section:                                            │
│  "For complex tax-law questions, call the tax_kb_researcher        │
│   sub-agent. For simple rates/concepts, call get_tax_rates or      │
│   explain_tax_concept directly."                                   │
│                                                                    │
│  ├─ SDK sub-agent: tax_kb_researcher                               │
│  │     system_prompt = TAX_KB_SUBAGENT_PROMPT                      │
│  │     allowed_tools = [mcp__tax_agent_global_tax_kb__search_tax_knowledge]
│  │     max_rounds = 3                                              │
│  │                                                                  │
│  │   multi-turn search → filter → synthesize → return answer       │
│  │                                                                  │
│  └─ Direct MCP tool calls: get_tax_rates / explain_tax_concept     │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
                                │
                                │ MCP + sub-agent channels
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│ MCP Server: tax_agent_global_tax_kb                                │
│                                                                    │
│  TaxKnowledgeAgentToolSet                                          │
│  ├── search_tax_knowledge(jurisdiction, tax_type, query)           │
│  │     → used by the sub-agent                                     │
│  ├── get_tax_rates(jurisdiction, tax_type, year)                   │
│  ├── explain_tax_concept(jurisdiction, tax_type, concept)          │
│  └── list_supported_jurisdictions()                                │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│ TaxKnowledgeStore                                                  │
│  ├── load_markdown(jurisdiction, tax_type)                         │
│  ├── search(jurisdiction, tax_type, query, top_k=5)                │
│  │     Phase 1: keyword search over H2 sections                   │
│  │     Phase 2: vector similarity (reserved interface)            │
│  └── list_supported()                                              │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    data/tax_knowledge/{cc}/{tax_type}.md
```

---

## Components

### 1. Knowledge Files (`data/tax_knowledge/`)

**Convention**

```text
data/tax_knowledge/
├── README.md                    # Authoring guide
├── uk/
│   ├── vat.md
│   ├── self_assessment.md
│   ├── corporation_tax.md
│   ├── paye.md
│   └── stamp_duty.md
├── de/
│   └── vat.md
├── fr/
│   └── vat.md
├── cn/
│   └── vat.md
└── testland/
    └── vat.md
```

**Markdown format**

- Each H2 (`## Topic Name`) is one searchable section.
- Each section should fit in ~300 tokens so the sub-agent can ingest multiple sections.
- Citations are embedded as `<!-- source: https://... -->` HTML comments or footnotes.

**Adding a new jurisdiction**

1. Create `data/tax_knowledge/{cc}/`.
2. Add `{tax_type}.md`.
3. Restart backend. No code changes.

### 2. `TaxKnowledgeStore` (`backend/agent/tax_knowledge_store.py`)

Responsibilities:

- Load markdown files at startup and on file-change events (or simple TTL cache).
- Index by `(jurisdiction, tax_type)`.
- Split markdown into H2 sections.
- Provide `search(jurisdiction, tax_type, query, top_k=5) -> list[KnowledgeSection]`.
- Provide `list_supported() -> list[tuple[str, str]]`.

Phase-1 search algorithm:

1. Exact H2 title match (case-insensitive substring).
2. Keyword match in section body (TF-style scoring).
3. Return top-K sections sorted by score.

Reserved Phase-2 interface:

```python
async def search(
    self,
    jurisdiction: str,
    tax_type: str,
    query: str,
    top_k: int = 5,
    mode: Literal["keyword", "vector"] = "keyword",
) -> list[KnowledgeSection]:
    ...
```

### 3. `TaxKnowledgeAgentToolSet` (`backend/agent/tax_knowledge_tools.py`)

Extends `AgentToolSet` (same pattern as `UKVATAgentToolSet`).

| Tool | Input | Output | Caller |
|---|---|---|---|
| `search_tax_knowledge` | `jurisdiction`, `tax_type`, `query` | `list[dict]` with `title`, `content`, `source_path` | Sub-agent only |
| `get_tax_rates` | `jurisdiction`, `tax_type`, `year?` | JSON rate table | Main agent |
| `explain_tax_concept` | `jurisdiction`, `tax_type`, `concept` | Short definition + source | Main agent |
| `list_supported_jurisdictions` | none | List of `(jurisdiction, tax_type)` | Main agent |

All tools return `_tool_ok(...)` / `_tool_error(...)` format consistent with existing tools.

### 4. Sub-Agent Configuration

The sub-agent is **not** an MCP tool. It is registered in `ClaudeAgentOptions` when the main `ClaudeSDKClient` is created.

```python
# backend/agent/engine.py — inside _sdk_chat()
options_kwargs["subagents"] = {
    "tax_kb_researcher": {
        "system_prompt": TAX_KB_SUBAGENT_PROMPT,
        "allowed_tools": [
            "mcp__tax_agent_global_tax_kb__search_tax_knowledge",
        ],
        "max_rounds": 3,
        "permission_mode": "auto",  # sub-agent may call its tool without user confirmation
    }
}
```

`TAX_KB_SUBAGENT_PROMPT` (in `backend/agent/tax_knowledge_prompts.py`):

```text
You are a tax-research sub-agent. Your only job is to retrieve accurate,
jurisdiction-specific tax rules from the TaxKnowledgeStore.

You have access to one tool:
  search_tax_knowledge(jurisdiction: str, tax_type: str, query: str)

Instructions:
1. Analyze the user's topic.
2. Call search_tax_knowledge up to 3 times with refined queries.
3. Filter out irrelevant snippets.
4. Synthesize a concise answer with citations (file path + H2 heading).
5. If no relevant rules are found, say so explicitly.
```

### 5. Main Agent Prompt Update

Append a section to `backend/agent/prompts.py::_GENERIC_PROMPT_HEADER` (or to `_UK_VAT_PROMPT` as a pilot):

```text
## Tax Law Research
For complex tax-law questions, call the `tax_kb_researcher` sub-agent.
It will search the knowledge base and return a concise answer with citations.
For simple rate/concept lookups, call `get_tax_rates` or `explain_tax_concept`
directly.
```

### 6. MCP Registration

`backend/agent/tools.py::create_mcp_servers()` currently iterates over `registry._adapters`. A new global server must be registered outside that loop:

```python
def create_mcp_servers(registry: JurisdictionRegistry | None = None) -> dict:
    servers = {}
    # 1. Jurisdiction-specific servers (existing)
    for adapter in registry._adapters.values():
        ...

    # 2. Global tax-knowledge server (new)
    kb_tool_set = TaxKnowledgeAgentToolSet()
    kb_server = create_sdk_mcp_server(
        name=kb_tool_set.server_name,
        version="1.0.0",
        tools=[_make_tool_wrapper(kb_tool_set, meta) for meta in kb_tool_set.get_tool_metadata()],
    )
    servers[("global", "tax_kb")] = {
        "name": kb_tool_set.server_name,
        "instance": kb_server,
    }
    return servers
```

Engine change:

```python
# backend/agent/engine.py:: _sdk_chat()
mcp_info = self._mcp_servers.get((jurisdiction, tax_type))
if mcp_info:
    options_kwargs["mcp_servers"] = {mcp_info["name"]: mcp_info["instance"]}

# Always attach the global tax-knowledge server
kb_info = self._mcp_servers.get(("global", "tax_kb"))
if kb_info:
    options_kwargs.setdefault("mcp_servers", {})[kb_info["name"]] = kb_info["instance"]
```

---

## Data Flow

### Flow A: Sub-Agent Research (complex query)

1. User asks: "Under UK VAT, when can I zero-rate an EU B2B sale?"
2. Main agent decides to call `tax_kb_researcher` sub-agent.
3. Sub-agent analyzes topic and calls `search_tax_knowledge("uk", "vat", "EU B2B zero rating")`.
4. Store returns H2 sections matching the query.
5. Sub-agent calls `search_tax_knowledge("uk", "vat", "valid EU VAT number")` to refine.
6. Sub-agent filters, synthesizes, returns answer with citations.
7. Main agent presents answer to user.

### Flow B: Direct Tool Call (simple query)

1. User asks: "What's the UK VAT standard rate for 2026?"
2. Main agent calls `get_tax_rates("uk", "vat", "2026")`.
3. Tool returns `{"standard": 0.20, ...}`.
4. Main agent answers immediately.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Knowledge file missing | `search_tax_knowledge` returns empty list; sub-agent reports "No relevant rules found." |
| Invalid jurisdiction/tax_type | Tool returns `_tool_error` with list of supported options. |
| Sub-agent exceeds max rounds | Force stop after 3 rounds; synthesize from retrieved snippets. |
| Sub-agent returns malformed content | Tool handler catches and returns `_tool_error` with raw output. |
| Store search returns low-confidence results | Still return them; sub-agent decides relevance. |
| Embedding mode requested but not available | Fallback to keyword search with a warning. |

---

## Testing Strategy

1. **Store unit tests**
   - `TaxKnowledgeStore.search("uk", "vat", "EU B2B")` returns the `## EU B2B Sales` section.
   - Adding `data/tax_knowledge/de/vat.md` makes `("de", "vat")` appear in `list_supported()`.

2. **MCP tool unit tests**
   - `get_tax_rates("uk", "vat", "2026")` returns expected rate object.
   - `explain_tax_concept("uk", "vat", "reverse charge")` returns a definition.
   - `list_supported_jurisdictions()` returns non-empty list.

3. **Sub-agent integration tests (mocked)**
   - Mock `search_tax_knowledge` to return snippets.
   - Verify sub-agent can be invoked and synthesizes an answer.

4. **End-to-end test**
   - Start backend.
   - Call `/api/agent/chat` with "Explain UK VAT reverse charge".
   - Verify response mentions reverse charge rules and cites `uk/vat.md`.

---

## Future Work

1. **Vector search**
   - Pre-compute embeddings for each H2 section.
   - Store in `data/tax_knowledge/{cc}/{tax_type}.md.embeddings.json` or a vector DB.
   - Swap `TaxKnowledgeStore.search()` implementation; tool interfaces stay the same.

2. **Web-source freshness**
   - Add a script that fetches official HMRC/BZSt/DGFiP pages and regenerates markdown.

3. **Multi-language support**
   - Add `lang` parameter to tools.

4. **Fine-grained citations**
   - Return line ranges or paragraph IDs, not just H2 headings.

---

## Files to Create / Modify

### Create
- `backend/agent/tax_knowledge_store.py`
- `backend/agent/tax_knowledge_tools.py`
- `backend/agent/tax_knowledge_prompts.py`
- `data/tax_knowledge/README.md`
- `data/tax_knowledge/uk/vat.md`
- `data/tax_knowledge/uk/self_assessment.md`
- `data/tax_knowledge/uk/corporation_tax.md`
- `data/tax_knowledge/uk/paye.md`
- `data/tax_knowledge/uk/stamp_duty.md`
- `data/tax_knowledge/de/vat.md` (stub)
- `data/tax_knowledge/fr/vat.md` (stub)
- `data/tax_knowledge/cn/vat.md` (stub)
- `tests/agent/test_tax_knowledge.py`

### Modify
- `backend/agent/tools.py` — register global server
- `backend/agent/engine.py` — attach global server + sub-agent config
- `backend/agent/prompts.py` — add tax-law research section
- `backend/models/agent_tools.py` — optional: add `server_name` class attr convention

---

## Open Questions

None. Design approved by user on 2026-06-11.

---

## Spec Self-Review

- **Placeholder scan:** No TBD/TODO.
- **Internal consistency:** Sub-agent uses MCP tool; main agent uses SDK sub-agent mechanism; interfaces align.
- **Scope check:** Phase 1 is keyword search + markdown files; vector search is reserved.
- **Ambiguity check:** "Extensible without code changes" means adding markdown files only.
