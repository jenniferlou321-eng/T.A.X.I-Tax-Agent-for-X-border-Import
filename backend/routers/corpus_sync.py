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
async def check_updates() -> dict:
    """Compare the mirror corpus against the local corpus.

    Returns:
        {status: "no_mirror", message: "...", report: None}  if the mirror
            file is missing (admin hasn't dropped one in).
        {status: "ok", report: {...}}                          otherwise.
    """
    if not _MIRROR_CORPUS.exists():
        return {
            "status": "no_mirror",
            "message": (
                f"Mirror file not found. Drop chunks_with_tags.jsonl into "
                f"{_MIRROR_CORPUS.parent}/ and try again."
            ),
            "report": None,
        }

    try:
        report: DiffReport = compare_corpus(_LOCAL_CORPUS, _MIRROR_CORPUS)
    except Exception as e:
        logger.exception("compare_corpus failed")
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
