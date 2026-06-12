"""In-memory buffer for ERPNext-pushed data.

v1 MVP: holds the most recent push. Phase 2 will replace with
persistent storage (Redis / DB) and support multi-document accumulation.
"""
from __future__ import annotations

from typing import Optional

from ..models.erp_models import ImportResult


_buffer: Optional[ImportResult] = None


def store_import_result(ir: ImportResult) -> None:
    global _buffer
    _buffer = ir


def get_import_result() -> Optional[ImportResult]:
    return _buffer


def clear_import_result() -> None:
    global _buffer
    _buffer = None
