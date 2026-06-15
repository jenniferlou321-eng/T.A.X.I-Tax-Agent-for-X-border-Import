"""Corpus sync router — check and apply corpus updates from the mirror.

The "mirror" is a JSONL file placed by the admin in
`data/tax_corpus_mirror/chunks_with_tags.jsonl`. It simulates a fresh
authoritative state from the upstream (e.g. a new HMRC crawl). This router
compares the mirror against TAXI's active local corpus and (on admin
confirmation) merges the differences back into the local file.

After a successful apply, the router reloads the in-memory
TaxKnowledgeStore (stored on `app.state.knowledge_store`) so subsequent
search() calls reflect the new content.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

from backend.services.corpus_sync import (
    ApplyResult,
    DiffReport,
    SourceInfo,
    apply_corpus_updates,
    compare_corpus,
)

# Demo staging helper. check-updates auto-stages (holds back a curated set of
# REAL obscure-topic sources — inheritance tax / CGT / trusts — see the script)
# whenever the diff would otherwise be empty, so the "模拟收到上游更新" button
# always surfaces something without anyone running a command first. Production
# would replace this with a real upstream crawl writing the mirror.
from scripts.build_demo_mirror import stage_demo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/corpus", tags=["corpus"])

# Paths are resolved relative to the project root (the directory that contains
# `backend/` and `data/`). The same pattern is used elsewhere — e.g.
# tax_knowledge_store.py defaults to `data/tax_knowledge/` — so admins have a
# single predictable location.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_LOCAL_CORPUS = _PROJECT_ROOT / "data" / "tax_corpus" / "chunks_with_tags.jsonl"
_MIRROR_CORPUS = _PROJECT_ROOT / "data" / "tax_corpus_mirror" / "chunks_with_tags.jsonl"


def _source_info_to_dict(info: SourceInfo) -> dict[str, Any]:
    return {
        "source_id": info.source_id,
        "title": info.title,
        "url": info.url,
        "source_authority": info.source_authority,
        "tax_tags": list(info.tax_tags),
        "chunk_count": info.chunk_count,
        "status": info.status,
    }


def _report_to_dict(report: DiffReport) -> dict[str, Any]:
    return {
        "summary": {
            "new_count": report.summary.new_count,
            "modified_count": report.summary.modified_count,
        },
        "new": [_source_info_to_dict(s) for s in report.new],
        "modified": [_source_info_to_dict(s) for s in report.modified],
    }


@router.get("/check-updates")
async def check_updates(request: Request) -> dict:
    """Compare the mirror corpus against the local corpus.

    DEMO behaviour: if the mirror is missing, or the diff is empty (e.g. the
    previous batch was already applied), this auto-stages a fresh batch by
    holding back a curated set of REAL obscure-topic sources from the local
    corpus (see scripts/build_demo_mirror.py). That way every click of
    "模拟收到上游更新" surfaces an update without anyone running a command.

    Returns:
        {status: "ok", report: {...}} — always, in the demo, with new+modified > 0.
        {status: "error", ...}        — only on an unexpected failure.
    """

    def _diff() -> DiffReport | None:
        if not _MIRROR_CORPUS.exists():
            return None
        return compare_corpus(_LOCAL_CORPUS, _MIRROR_CORPUS)

    def _is_empty(r: DiffReport | None) -> bool:
        return r is None or (r.summary.new_count + r.summary.modified_count) == 0

    try:
        report = _diff()
        if _is_empty(report):
            # Re-stage from the clean baseline → hold back the curated set →
            # write the mirror, then reload the in-memory store so the held-back
            # content disappears from agent search until the user applies it.
            stage_demo(_LOCAL_CORPUS, _MIRROR_CORPUS)
            store = getattr(request.app.state, "knowledge_store", None)
            if store is not None and hasattr(store, "reload"):
                try:
                    store.reload()
                except Exception:
                    logger.exception("knowledge_store.reload() failed after staging")
            report = _diff()
    except Exception as e:
        logger.exception("check_updates failed")
        return {"status": "error", "message": f"Compare failed: {e}", "report": None}

    return {"status": "ok", "report": _report_to_dict(report)}


@router.post("/apply-updates")
async def apply_updates(request: Request) -> dict:
    """Merge mirror changes into the local corpus.

    On success, also reloads the in-memory TaxKnowledgeStore (when one is
    registered on `app.state.knowledge_store`) so the change is immediately
    visible to agents. If the reload fails after a successful merge, the
    endpoint returns `status: "partial"` — the file is updated on disk, but
    in-memory search results will be stale until the server restarts.
    """
    try:
        result: ApplyResult = apply_corpus_updates(_LOCAL_CORPUS, _MIRROR_CORPUS)
    except Exception as e:
        logger.exception("apply_corpus_updates failed")
        return {"status": "error", "message": f"Apply failed: {e}"}

    if not result.success:
        return {"status": "error", "message": result.error}

    body: dict[str, Any] = {
        "status": "ok",
        "result": {
            "new_count": result.new_count,
            "modified_count": result.modified_count,
            "total_chunks": result.total_chunks_written,
        },
    }

    # Reload the in-memory store so new chunks are immediately searchable.
    store = getattr(request.app.state, "knowledge_store", None)
    if store is not None and hasattr(store, "reload"):
        try:
            store.reload()
        except Exception as e:
            logger.exception("knowledge_store.reload() failed after apply")
            body["status"] = "partial"
            body["message"] = (
                f"Corpus file updated, but in-memory knowledge store reload "
                f"failed: {e}. Restart TAXI to pick up the new content."
            )

    return body
