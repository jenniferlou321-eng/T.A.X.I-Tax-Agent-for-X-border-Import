"""Tests for backend/services/corpus_sync.py"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services.corpus_sync import (
    _load_jsonl,
    _hash_source,
    _extract_source_info,
    compare_corpus,
    apply_corpus_updates,
)


# ── helpers ─────────────────────────────────────────────────────


def _write_jsonl(path: Path, chunks: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")


def make_chunk(
    source_id: str,
    chunk_index: int,
    text: str,
    *,
    title: str | None = None,
    url: str | None = None,
    tax_tags: list[str] | None = None,
) -> dict:
    return {
        "chunk_id": f"{source_id}__chunk_{chunk_index:04d}",
        "source_id": source_id,
        "title": title or f"Title for {source_id}",
        "url": url or f"https://example.com/{source_id}",
        "source_authority": "HMRC",
        "tax_tags": tax_tags or ["vat"],
        "text": text,
        "status": "current",
        "chunk_index": chunk_index,
        "chunk_count": 1,
        "tax_type": "VAT",
        "text_length": len(text),
        "source_type": "guidance",
        "collection": "manuals",
        "local_file": f"/tmp/{source_id}.txt",
        "retrieved_at": "2026-06-12T00:00:00+00:00",
        "effective_from": None,
        "effective_to": None,
        "last_updated": None,
    }


# ── _load_jsonl ─────────────────────────────────────────────────


class TestLoadJsonl:
    def test_missing_file_returns_empty_dict(self, tmp_path):
        assert _load_jsonl(tmp_path / "nonexistent.jsonl") == {}

    def test_empty_file_returns_empty_dict(self, tmp_path):
        path = tmp_path / "empty.jsonl"
        path.write_text("")
        assert _load_jsonl(path) == {}

    def test_groups_by_source_id(self, tmp_path):
        path = tmp_path / "test.jsonl"
        _write_jsonl(path, [
            make_chunk("src_a", 1, "a1"),
            make_chunk("src_b", 1, "b1"),
            make_chunk("src_a", 2, "a2"),
        ])
        result = _load_jsonl(path)
        assert set(result.keys()) == {"src_a", "src_b"}
        assert len(result["src_a"]) == 2
        assert len(result["src_b"]) == 1

    def test_sorts_by_chunk_index(self, tmp_path):
        path = tmp_path / "test.jsonl"
        _write_jsonl(path, [
            make_chunk("src_a", 3, "third"),
            make_chunk("src_a", 1, "first"),
            make_chunk("src_a", 2, "second"),
        ])
        result = _load_jsonl(path)
        assert [c["chunk_index"] for c in result["src_a"]] == [1, 2, 3]

    def test_skips_chunks_without_source_id(self, tmp_path):
        path = tmp_path / "test.jsonl"
        _write_jsonl(path, [
            make_chunk("src_a", 1, "ok"),
            {"chunk_id": "no_sid", "text": "no sid here"},  # missing source_id
        ])
        result = _load_jsonl(path)
        assert list(result.keys()) == ["src_a"]


# ── _hash_source ────────────────────────────────────────────────


class TestHashSource:
    def test_same_text_same_hash(self):
        a = [make_chunk("x", 1, "hello"), make_chunk("x", 2, "world")]
        b = [make_chunk("x", 1, "hello"), make_chunk("x", 2, "world")]
        assert _hash_source(a) == _hash_source(b)

    def test_different_text_different_hash(self):
        a = [make_chunk("x", 1, "hello")]
        b = [make_chunk("x", 1, "hello modified")]
        assert _hash_source(a) != _hash_source(b)

    def test_chunk_boundary_change_same_hash(self):
        """Same total text, different chunk split → same hash.

        This is the core reason we hash at source level rather than per-chunk.
        """
        a = [make_chunk("x", 1, "hello world")]
        b = [make_chunk("x", 1, "hello "), make_chunk("x", 2, "world")]
        assert _hash_source(a) == _hash_source(b)

    def test_empty_text_still_hashes(self):
        assert _hash_source([]) == _hash_source([make_chunk("x", 1, "")])


# ── _extract_source_info ────────────────────────────────────────


class TestExtractSourceInfo:
    def test_reads_from_first_chunk(self):
        chunks = [
            make_chunk("src_a", 1, "first", title="My Title", url="https://u.rl"),
            make_chunk("src_a", 2, "second", title="OTHER", url="https://other"),
        ]
        info = _extract_source_info(chunks)
        assert info.source_id == "src_a"
        assert info.title == "My Title"  # first chunk wins
        assert info.url == "https://u.rl"
        assert info.chunk_count == 2
        assert info.tax_tags == ["vat"]


# ── compare_corpus ──────────────────────────────────────────────


class TestCompareCorpus:
    def test_all_new_when_local_empty(self, tmp_path):
        mirror = tmp_path / "mirror.jsonl"
        local = tmp_path / "local.jsonl"
        _write_jsonl(mirror, [make_chunk("src_a", 1, "hello")])
        local.write_text("")

        report = compare_corpus(local, mirror)
        assert report.summary.new_count == 1
        assert report.summary.modified_count == 0
        assert [s.source_id for s in report.new] == ["src_a"]

    def test_empty_diff_when_identical(self, tmp_path):
        mirror = tmp_path / "mirror.jsonl"
        local = tmp_path / "local.jsonl"
        chunks = [make_chunk("src_a", 1, "hello")]
        _write_jsonl(mirror, chunks)
        _write_jsonl(local, chunks)

        report = compare_corpus(local, mirror)
        assert report.summary.new_count == 0
        assert report.summary.modified_count == 0
        assert report.new == []
        assert report.modified == []

    def test_modified_detected_on_text_change(self, tmp_path):
        mirror = tmp_path / "mirror.jsonl"
        local = tmp_path / "local.jsonl"
        _write_jsonl(local, [make_chunk("src_a", 1, "old text")])
        _write_jsonl(mirror, [make_chunk("src_a", 1, "new text")])

        report = compare_corpus(local, mirror)
        assert report.summary.new_count == 0
        assert report.summary.modified_count == 1
        assert [s.source_id for s in report.modified] == ["src_a"]

    def test_mixed_new_and_modified(self, tmp_path):
        mirror = tmp_path / "mirror.jsonl"
        local = tmp_path / "local.jsonl"
        _write_jsonl(local, [
            make_chunk("src_a", 1, "old"),       # → modified
            make_chunk("src_b", 1, "unchanged"), # → unchanged
        ])
        _write_jsonl(mirror, [
            make_chunk("src_a", 1, "new"),       # → modified
            make_chunk("src_b", 1, "unchanged"), # → unchanged
            make_chunk("src_c", 1, "brand new"), # → new
        ])

        report = compare_corpus(local, mirror)
        assert report.summary.new_count == 1
        assert report.summary.modified_count == 1
        assert [s.source_id for s in report.new] == ["src_c"]
        assert [s.source_id for s in report.modified] == ["src_a"]

    def test_local_only_sources_ignored(self, tmp_path):
        """Sources in local but not in mirror must NOT show as deletions."""
        mirror = tmp_path / "mirror.jsonl"
        local = tmp_path / "local.jsonl"
        _write_jsonl(local, [
            make_chunk("src_a", 1, "x"),
            make_chunk("src_b", 1, "local-only orphan"),
        ])
        _write_jsonl(mirror, [make_chunk("src_a", 1, "x")])

        report = compare_corpus(local, mirror)
        assert report.summary.new_count == 0
        assert report.summary.modified_count == 0

    def test_empty_mirror_means_nothing_to_sync(self, tmp_path):
        mirror = tmp_path / "mirror.jsonl"
        local = tmp_path / "local.jsonl"
        mirror.write_text("")
        _write_jsonl(local, [make_chunk("src_a", 1, "x")])

        report = compare_corpus(local, mirror)
        assert report.summary.new_count == 0
        assert report.summary.modified_count == 0

    def test_chunk_split_only_does_not_trigger_modified(self, tmp_path):
        """If mirror re-splits the same text into different chunks, source-level
        hash stays the same, so it's NOT reported as modified.
        """
        mirror = tmp_path / "mirror.jsonl"
        local = tmp_path / "local.jsonl"
        _write_jsonl(local, [make_chunk("src_a", 1, "hello world")])
        _write_jsonl(mirror, [
            make_chunk("src_a", 1, "hello "),
            make_chunk("src_a", 2, "world"),
        ])

        report = compare_corpus(local, mirror)
        assert report.summary.new_count == 0
        assert report.summary.modified_count == 0


# ── apply_corpus_updates ────────────────────────────────────────


class TestApplyCorpusUpdates:
    def test_appends_new_sources(self, tmp_path):
        mirror = tmp_path / "mirror.jsonl"
        local = tmp_path / "local.jsonl"
        _write_jsonl(local, [make_chunk("src_a", 1, "existing")])
        _write_jsonl(mirror, [
            make_chunk("src_a", 1, "existing"),
            make_chunk("src_b", 1, "new content"),
        ])

        result = apply_corpus_updates(local, mirror)
        assert result.success
        assert result.new_count == 1
        assert result.modified_count == 0

        # local should now contain both sources
        local_sources = _load_jsonl(local)
        assert "src_a" in local_sources
        assert "src_b" in local_sources
        assert local_sources["src_b"][0]["text"] == "new content"

    def test_replaces_modified_sources(self, tmp_path):
        mirror = tmp_path / "mirror.jsonl"
        local = tmp_path / "local.jsonl"
        _write_jsonl(local, [make_chunk("src_a", 1, "old text")])
        _write_jsonl(mirror, [make_chunk("src_a", 1, "new text")])

        result = apply_corpus_updates(local, mirror)
        assert result.success
        assert result.new_count == 0
        assert result.modified_count == 1

        local_sources = _load_jsonl(local)
        assert local_sources["src_a"][0]["text"] == "new text"

    def test_preserves_local_only_sources(self, tmp_path):
        mirror = tmp_path / "mirror.jsonl"
        local = tmp_path / "local.jsonl"
        _write_jsonl(local, [
            make_chunk("src_a", 1, "exists in both"),
            make_chunk("src_b", 1, "local only"),
        ])
        _write_jsonl(mirror, [make_chunk("src_a", 1, "exists in both")])

        result = apply_corpus_updates(local, mirror)
        assert result.success
        local_sources = _load_jsonl(local)
        assert "src_b" in local_sources, "local-only source must be preserved"
        assert local_sources["src_b"][0]["text"] == "local only"

    def test_mirror_missing_returns_error(self, tmp_path):
        local = tmp_path / "local.jsonl"
        mirror = tmp_path / "nonexistent.jsonl"
        _write_jsonl(local, [make_chunk("src_a", 1, "x")])

        result = apply_corpus_updates(local, mirror)
        assert not result.success
        assert "not found" in result.error.lower()

    def test_atomic_write_leaves_no_tmp_file(self, tmp_path):
        mirror = tmp_path / "mirror.jsonl"
        local = tmp_path / "local.jsonl"
        _write_jsonl(local, [make_chunk("src_a", 1, "old")])
        _write_jsonl(mirror, [make_chunk("src_a", 1, "new")])

        apply_corpus_updates(local, mirror)

        # No .tmp should remain after a successful apply
        tmp_leftover = local.with_suffix(local.suffix + ".tmp")
        assert not tmp_leftover.exists()
        # And the real file should have new content
        assert _load_jsonl(local)["src_a"][0]["text"] == "new"

    def test_total_chunks_written_includes_all(self, tmp_path):
        mirror = tmp_path / "mirror.jsonl"
        local = tmp_path / "local.jsonl"
        _write_jsonl(local, [
            make_chunk("src_a", 1, "p1"),
            make_chunk("src_a", 2, "p2"),  # 2 chunks
        ])
        _write_jsonl(mirror, [
            make_chunk("src_a", 1, "p1"),
            make_chunk("src_a", 2, "p2"),
            make_chunk("src_b", 1, "p3"),  # +1 chunk
        ])

        result = apply_corpus_updates(local, mirror)
        assert result.success
        assert result.total_chunks_written == 3

    def test_apply_then_compare_is_clean(self, tmp_path):
        """End-to-end: apply, then compare again → no diff."""
        mirror = tmp_path / "mirror.jsonl"
        local = tmp_path / "local.jsonl"
        _write_jsonl(local, [make_chunk("src_a", 1, "old")])
        _write_jsonl(mirror, [make_chunk("src_a", 1, "new")])

        apply_corpus_updates(local, mirror)
        report = compare_corpus(local, mirror)
        assert report.summary.new_count == 0
        assert report.summary.modified_count == 0
