"""Corpus sync service -- compare and merge tax corpus JSONL files.

The mirror JSONL simulates the "official source" (e.g. a fresh HMRC crawl).
The local JSONL is what TAXI's TaxKnowledgeStore currently serves.

Comparison is at source_id level (not chunk level): all chunks belonging to
the same source_id are concatenated and hashed, so chunk-boundary changes
inside an otherwise-unchanged document do NOT trigger false "modified" hits.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Data structures ────────────────────────────────────────────


@dataclass
class SourceInfo:
    """Metadata for one source in the diff report."""
    source_id: str
    title: str
    url: str
    source_authority: str
    tax_tags: list[str] = field(default_factory=list)
    chunk_count: int = 0
    status: str = "current"


@dataclass
class DiffSummary:
    new_count: int = 0
    modified_count: int = 0


@dataclass
class DiffReport:
    summary: DiffSummary
    new: list[SourceInfo] = field(default_factory=list)
    modified: list[SourceInfo] = field(default_factory=list)


@dataclass
class ApplyResult:
    success: bool
    new_count: int = 0
    modified_count: int = 0
    total_chunks_written: int = 0
    error: str = ""


# ── Internal helpers ────────────────────────────────────────────


def _load_jsonl(path: Path) -> dict[str, list[dict]]:
    """Load a JSONL file, group chunks by source_id, sort each group by chunk_index.

    Returns:
        {source_id: [chunk, ...]} in chunk_index order.
    """
    if not path.exists():
        return {}

    sources: dict[str, list[dict]] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chunk = json.loads(line)
            sid = chunk.get("source_id", "")
            if not sid:
                # Skip chunks without source_id -- they would break the diff
                # logic (can't be grouped, can't be re-inserted). They were
                # already rejected in L1 cleaning if url/source_id/local_file
                # are missing, so this is a defensive guard.
                continue
            sources.setdefault(sid, []).append(chunk)

    for sid in sources:
        sources[sid].sort(key=lambda c: c.get("chunk_index", 0))

    return sources


def _hash_source(chunks: list[dict]) -> str:
    """MD5 over the concatenated text of all chunks for one source.

    Concatenating (rather than hashing per-chunk) means chunk-boundary splits
    inside an unchanged document produce the same hash.
    """
    combined = "".join(c.get("text", "") for c in chunks)
    return hashlib.md5(combined.encode("utf-8")).hexdigest()


def _extract_source_info(chunks: list[dict]) -> SourceInfo:
    """Build SourceInfo from the first chunk of a source (they share metadata)."""
    first = chunks[0]
    return SourceInfo(
        source_id=first.get("source_id", ""),
        title=first.get("title", ""),
        url=first.get("url", ""),
        source_authority=first.get("source_authority", ""),
        tax_tags=list(first.get("tax_tags", []) or []),
        chunk_count=len(chunks),
        status=first.get("status", "current"),
    )


# ── Public API ─────────────────────────────────────────────────


def compare_corpus(
    local_path: Path, mirror_path: Path,
) -> DiffReport:
    """Compare mirror corpus against local corpus.

    Detection rules:
      - source_id in mirror, not in local         → NEW
      - source_id in both, but text hash differs   → MODIFIED
      - source_id in both, hash identical          → skip
      - source_id in local, not in mirror          → ignored (additive-only sync)

    Args:
        local_path: Path to local `chunks_with_tags.jsonl` (TAXI's active corpus).
        mirror_path: Path to mirror `chunks_with_tags.jsonl` (simulated remote).

    Returns:
        DiffReport with summary counts and per-source detail.
    """
    local_sources = _load_jsonl(local_path)
    mirror_sources = _load_jsonl(mirror_path)

    local_hashes: dict[str, str] = {
        sid: _hash_source(chunks) for sid, chunks in local_sources.items()
    }

    new_sources: list[SourceInfo] = []
    modified_sources: list[SourceInfo] = []

    for sid, chunks in mirror_sources.items():
        mirror_hash = _hash_source(chunks)
        local_hash = local_hashes.get(sid)
        if local_hash is None:
            new_sources.append(_extract_source_info(chunks))
        elif local_hash != mirror_hash:
            modified_sources.append(_extract_source_info(chunks))
        # else: hash identical → skip

    return DiffReport(
        summary=DiffSummary(
            new_count=len(new_sources),
            modified_count=len(modified_sources),
        ),
        new=new_sources,
        modified=modified_sources,
    )


def apply_corpus_updates(
    local_path: Path, mirror_path: Path,
) -> ApplyResult:
    """Merge mirror chunks into local JSONL atomically.

    Strategy:
      1. Load both files grouped by source_id.
      2. For each source_id in mirror:
         - not in local          → append all mirror chunks
         - in local, hash differs → replace local chunks with mirror chunks
         - in local, hash same    → skip
      3. Local-only sources are preserved unchanged.
      4. Reconstruct all chunks in source_id order, then chunk_index order.
      5. Write atomically: write to `.tmp`, then `replace()` over original.

    Note: this function does NOT reload the TaxKnowledgeStore. The caller
    (router) is responsible for calling `store.reload()` after a successful
    apply, so the in-memory search index reflects the new file.

    Args:
        local_path: Path to local `chunks_with_tags.jsonl` (will be overwritten).
        mirror_path: Path to mirror `chunks_with_tags.jsonl`.

    Returns:
        ApplyResult with counts and success flag.
    """
    if not mirror_path.exists():
        return ApplyResult(
            success=False, error=f"Mirror file not found: {mirror_path}",
        )

    local_sources = _load_jsonl(local_path)
    mirror_sources = _load_jsonl(mirror_path)

    local_hashes: dict[str, str] = {
        sid: _hash_source(chunks) for sid, chunks in local_sources.items()
    }

    new_count = 0
    modified_count = 0

    for sid, mirror_chunks in mirror_sources.items():
        mirror_hash = _hash_source(mirror_chunks)
        local_hash = local_hashes.get(sid)
        if local_hash is None:
            new_count += 1
        elif local_hash != mirror_hash:
            modified_count += 1
        else:
            # identical → keep local version (same content, no need to rewrite)
            continue
        # Either way, mirror wins (it's the new authoritative state)
        local_sources[sid] = mirror_chunks

    # Reconstruct all chunks: stable order = source_id, then chunk_index.
    all_chunks: list[dict] = []
    for sid in sorted(local_sources.keys()):
        all_chunks.extend(local_sources[sid])

    # Atomic write: write to a sibling .tmp, then rename over the target.
    # `.tmp` suffix avoids collision with the real `.jsonl`.
    tmp_path = local_path.with_suffix(local_path.suffix + ".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            for chunk in all_chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
        tmp_path.replace(local_path)
    except Exception as e:
        # Best-effort cleanup of leftover .tmp
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        return ApplyResult(success=False, error=f"Write failed: {e}")

    return ApplyResult(
        success=True,
        new_count=new_count,
        modified_count=modified_count,
        total_chunks_written=len(all_chunks),
    )
