"""Tax knowledge store — loads markdown files + JSONL corpus, serves BM25 search."""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class KnowledgeSection:
    """One searchable section of a tax knowledge file."""
    title: str
    content: str
    source_path: str
    order: int = 0
    # 新增：来自 JSONL 语料的元数据
    url: str = ""
    source_authority: str = ""
    tax_tags: list[str] = field(default_factory=list)
    status: str = "current"


class TaxKnowledgeStore:
    """Loads `data/tax_knowledge/{jurisdiction}/{tax_type}.md` and `data/tax_corpus/chunks_with_tags.jsonl`.

    Search: BM25 over cleaned text for JSONL chunks; keyword matching for markdown.
    """

    # BM25 parameters
    K1 = 1.5
    B = 0.75

    def __init__(self, base_path: str | None = None):
        self.base_path = Path(base_path) if base_path else Path(__file__).resolve().parent.parent.parent / "data" / "tax_knowledge"
        self._corpus_path = self.base_path.parent / "tax_corpus" / "chunks_with_tags.jsonl"
        self._cache: dict[Tuple[str, str], List[KnowledgeSection]] = {}
        self._corpus_sections: dict[Tuple[str, str], List[KnowledgeSection]] = {}
        self._load_all()

    # ── loading ──────────────────────────────────────────────

    def _load_all(self) -> None:
        self._load_markdown()
        self._load_jsonl_corpus()

    def _load_markdown(self) -> None:
        """加载现有的 Markdown stub 文件。"""
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
            sections.append(KnowledgeSection(
                title=title, content=content, source_path=str(path), order=order,
            ))
            order += 1
        return sections

    def _load_jsonl_corpus(self) -> None:
        """加载清洗后的 JSONL 语料，按 (jurisdiction, tax_type) 分组。

        每个 chunk 的 tax_tags 是数组（如 ["vat", "hmrc_penalties_and_interest"]）。
        一个 chunk 会出现在多个 (cc, tax_tag) 缓存条目中。
        """
        if not self._corpus_path.exists():
            return

        with open(self._corpus_path, "r", encoding="utf-8") as f:
            chunks = [json.loads(line) for line in f]

        order_counter: dict[Tuple[str, str], int] = Counter()

        for c in chunks:
            tax_tags = c.get("tax_tags", [])
            if not tax_tags:
                tax_tags = ["unknown"]

            for tag in tax_tags:
                key = ("uk", tag)  # 当前仅 UK 语料
                section = KnowledgeSection(
                    title=c.get("title", ""),
                    content=c.get("text", ""),   # 原始正文（BM25 用）
                    source_path=c.get("url", ""),
                    order=order_counter[key],
                    url=c.get("url", ""),
                    source_authority=c.get("source_authority", ""),
                    tax_tags=tax_tags,
                    status=c.get("status", "current"),
                )
                self._corpus_sections.setdefault(key, []).append(section)
                order_counter[key] += 1

    # ── listing ─────────────────────────────────────────────

    def reload(self) -> None:
        """Reload all data from disk.

        Call this after the corpus JSONL file has been replaced (e.g. by the
        corpus sync service). Subsequent search() calls will reflect the new
        content. Re-runs the same _load_all() flow used at __init__.
        """
        self._cache.clear()
        self._corpus_sections.clear()
        self._load_all()

    def list_supported(self) -> List[Tuple[str, str]]:
        """返回所有支持的 (jurisdiction, tax_type) 对（含 MD + corpus）。"""
        keys = set(self._cache.keys()) | set(self._corpus_sections.keys())
        return sorted(keys)

    def get_section(
        self, jurisdiction: str, tax_type: str, title: str,
    ) -> Optional[KnowledgeSection]:
        """按 H2 标题取 1 个 section（仅 Markdown 源）。"""
        sections = self._cache.get((jurisdiction, tax_type), [])
        for section in sections:
            if section.title == title:
                return section
        return None

    # ── search ───────────────────────────────────────────────

    # 英文停用词（BM25 分词用）
    _STOP_WORDS = frozenset(
        "a an the and or of to in for on at by is are was were be been being "
        "as it its their there this that these those".split()
    )

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        tokens = []
        for part in re.split(r"[\s,;.!?:()\"'`]+", text.lower()):
            if not part:
                continue
            for word in re.findall(r"[a-z][a-z0-9_\-]{1,}", part):
                if word not in TaxKnowledgeStore._STOP_WORDS and len(word) > 1:
                    tokens.append(word)
        return tokens

    def _bm25_search(
        self, sections: List[KnowledgeSection], query: str, top_k: int,
    ) -> List[KnowledgeSection]:
        """对 JSONL 语料执行 BM25 搜索。"""
        if not sections or not query:
            return []

        # 构建 BM25 索引（按需，每个 (cc, tax_type) 首次搜索时构建）
        N = len(sections)
        doc_tokens = []
        doc_lens = []
        df = Counter()
        tf_list = []
        for s in sections:
            tokens = self._tokenize(s.content)
            doc_tokens.append(tokens)
            doc_lens.append(len(tokens))
            tf = Counter(tokens)
            tf_list.append(tf)
            for term in tf:
                df[term] += 1
        avgdl = sum(doc_lens) / max(N, 1)

        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []

        scores = []
        for i, tokens in enumerate(doc_tokens):
            dl = doc_lens[i]
            tf = tf_list[i]
            s = 0.0
            for q in q_tokens:
                if q not in tf:
                    continue
                f = tf[q]
                n_q = df.get(q, 0)
                idf = math.log(1 + (N - n_q + 0.5) / (n_q + 0.5))
                s += idf * (f * (self.K1 + 1)) / (f + self.K1 * (1 - self.B + self.B * dl / avgdl))
            if s > 0:
                scores.append((s, i))

        scores.sort(key=lambda x: -x[0])
        return [sections[i] for _, i in scores[:top_k]]

    def _keyword_search(
        self, sections: List[KnowledgeSection], query: str, top_k: int,
    ) -> List[KnowledgeSection]:
        """对 Markdown sections 执行关键词匹配（保持向后兼容）。"""
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

    def search(
        self, jurisdiction: str, tax_type: str, query: str, top_k: int = 5,
    ) -> List[KnowledgeSection]:
        """搜索知识库（优先 JSONL 语料 BM25，回退 Markdown 关键词）。

        搜索策略：
        - 若 JSONL 语料有该 (jurisdiction, tax_type) 的数据 → BM25 搜索
        - 否则 → 现有 Markdown 关键词搜索（向后兼容）
        - 若两者都有 → 合并结果（JSONL 结果在前）
        """
        corpus_key = (jurisdiction, tax_type)
        md_key = (jurisdiction, tax_type)

        corpus_results = []
        md_results = []

        if corpus_key in self._corpus_sections:
            corpus_results = self._bm25_search(
                self._corpus_sections[corpus_key], query, top_k,
            )
        if md_key in self._cache:
            md_results = self._keyword_search(
                self._cache[md_key], query, max(1, top_k - len(corpus_results)),
            )

        # JSONL 优先，MD 补位
        seen_titles = {s.title for s in corpus_results}
        combined = list(corpus_results)
        for s in md_results:
            if s.title not in seen_titles:
                combined.append(s)
                seen_titles.add(s.title)
        return combined[:top_k]
