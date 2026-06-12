"""Tax knowledge store — loads markdown files and serves keyword search."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class KnowledgeSection:
    """One searchable section of a tax knowledge file."""
    title: str
    content: str
    source_path: str
    order: int = 0


class TaxKnowledgeStore:
    """Loads `data/tax_knowledge/{jurisdiction}/{tax_type}.md` and searches."""

    def __init__(self, base_path: str | None = None):
        self.base_path = Path(base_path) if base_path else Path(__file__).resolve().parent.parent.parent / "data" / "tax_knowledge"
        self._cache: dict[Tuple[str, str], List[KnowledgeSection]] = {}
        self._load_all()

    def _load_all(self) -> None:
        if not self.base_path.exists():
            return
        for md_path in self.base_path.rglob("*.md"):
            if md_path.name == "README.md":
                continue
            rel = md_path.relative_to(self.base_path)
            if len(rel.parts) != 2:
                continue
            jurisdiction = rel.parts[0]
            tax_type = rel.parts[1].replace(".md", "")
            sections = self._parse_markdown(md_path)
            self._cache[(jurisdiction, tax_type)] = sections

    def _parse_markdown(self, path: Path) -> List[KnowledgeSection]:
        text = path.read_text(encoding="utf-8")
        parts = re.split(r"\n(?=##\s+[^#])", text)
        sections: List[KnowledgeSection] = []
        order = 0
        for part in parts:
            part = part.strip()
            if not part:
                continue
            match = re.match(r"##\s+([^#].*?)(?:\n+|$)(.*)", part, re.DOTALL)
            if not match:
                continue
            title = match.group(1).strip()
            content = match.group(2).strip()
            sections.append(KnowledgeSection(title=title, content=content, source_path=str(path), order=order))
            order += 1
        return sections

    def list_supported(self) -> List[Tuple[str, str]]:
        return sorted(self._cache.keys())

    def search(self, jurisdiction: str, tax_type: str, query: str, top_k: int = 5) -> List[KnowledgeSection]:
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
            if query_lower in title_lower:
                score += 10.0
            for word in query_words:
                if word in title_lower:
                    score += 3.0
                if word in content_lower:
                    score += 1.0
            if score > 0:
                scored.append((score, section))
        scored.sort(key=lambda x: (-x[0], x[1].order))
        return [section for _, section in scored[:top_k]]

    def get_section(
        self, jurisdiction: str, tax_type: str, title: str,
    ) -> Optional[KnowledgeSection]:
        """按 H2 标题取 1 个 section。

        Args:
            jurisdiction: cc
            tax_type: tax_type
            title: 严格匹配的 H2 标题(不含 `##` 前缀)

        Returns:
            第一个匹配 title 的 KnowledgeSection,或 None(未找到)
        """
        sections = self._cache.get((jurisdiction, tax_type), [])
        for section in sections:
            if section.title == title:
                return section
        return None
