"""Global tax knowledge MCP tool set."""
from __future__ import annotations

import json
from typing import Optional

from backend.models.agent_tools import AgentToolSet
from backend.agent.tax_knowledge_store import TaxKnowledgeStore
from backend.models.jurisdictions import is_valid_jurisdiction


def _tool_ok(data: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(data, indent=2, ensure_ascii=False)}]}


def _tool_error(msg: str, detail: str = "") -> dict:
    payload = {"success": False, "error": msg}
    if detail:
        payload["detail"] = detail
    return {"content": [{"type": "text", "text": json.dumps(payload)}], "is_error": True}


class TaxKnowledgeAgentToolSet(AgentToolSet):
    country_code = "global"
    tax_type = "tax_kb"

    def __init__(self, store_base_path: Optional[str] = None):
        self.store = TaxKnowledgeStore(base_path=store_base_path)

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

    async def search_tax_knowledge(self, jurisdiction: str, tax_type: str, query: str) -> dict:
        if not jurisdiction or not tax_type or not query:
            return _tool_error("jurisdiction, tax_type, and query are required")
        sections = self.store.search(jurisdiction, tax_type, query, top_k=5)
        results = [{"title": s.title, "content": s.content, "source_path": s.source_path} for s in sections]
        return _tool_ok({"success": True, "jurisdiction": jurisdiction, "tax_type": tax_type, "query": query, "results": results})

    async def get_tax_rates(self, jurisdiction: str, tax_type: str, year: Optional[str] = None) -> dict:
        """从 KB 读 ## Rates 段。

        数据驱动: 不再硬编码 if/elif。新国家在 data/tax_knowledge/{cc}/{tax}.md
        加 ## Rates 段后,本工具自动支持。
        """
        if not jurisdiction or not tax_type:
            return _tool_error("jurisdiction and tax_type are required")
        if not is_valid_jurisdiction(jurisdiction, tax_type):
            return _tool_error(
                f"Unknown jurisdiction={jurisdiction!r} or tax_type={tax_type!r}"
            )
        section = self.store.get_section(jurisdiction, tax_type, "Rates")
        if section is None:
            return _tool_ok({
                "success": True,
                "jurisdiction": jurisdiction,
                "tax_type": tax_type,
                "year": year,
                "rates": {"note": f"Rate table not yet available for {jurisdiction}/{tax_type}"},
            })
        # 解析 section.content 里的 ```json ... ``` 块
        import re
        m = re.search(r"```json\s*(\{.*?\})\s*```", section.content, re.DOTALL)
        if m is None:
            # 段存在但无 JSON 块(SA / PAYE 等按 band 征税)
            return _tool_ok({
                "success": True,
                "jurisdiction": jurisdiction,
                "tax_type": tax_type,
                "year": year,
                "rates": {"note": f"{tax_type} uses banded rates; see KB ## Bands section"},
            })
        rates = json.loads(m.group(1))
        return _tool_ok({
            "success": True,
            "jurisdiction": jurisdiction,
            "tax_type": tax_type,
            "year": year,
            "rates": rates,
        })

    async def list_supported_jurisdictions(self) -> dict:
        supported = self.store.list_supported()
        return _tool_ok({"success": True, "supported": [{"jurisdiction": j, "tax_type": t} for j, t in supported], "count": len(supported)})

    def get_tool_metadata(self) -> list[dict]:
        return [
            {
                "name": "search_tax_knowledge",
                "description": "Search the tax knowledge base for relevant sections. Intended for the tax_kb_researcher sub-agent.",
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
                "input_schema": {"type": "object", "properties": {}},
            },
        ]
