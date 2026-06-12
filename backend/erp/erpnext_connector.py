"""ERPNext → T.A.X.I. push receiver.

Validates HMAC signature, converts ERPNext invoice payload to
ImportResult-compatible structure, and stores it in the
in-memory buffer for the agent / API to consume.
"""
from __future__ import annotations

import hmac
import hashlib
from decimal import Decimal
from datetime import date
from typing import Any, Dict, List

from ..models.erp_models import (
    ImportResult, SalesTransaction, PurchaseTransaction, ERPNineBox,
)
from .reconcile import compute_taxi_nine_box


def validate_signature(body: bytes, signature: str, secret: str) -> bool:
    """Constant-time HMAC-SHA256 signature check."""
    if not signature or not secret:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def payload_to_import_result(payload: Dict[str, Any]) -> ImportResult:
    """Convert an ERPNext push payload (single invoice) to ImportResult.

    Payload shape (from tax_integration/events/invoice_pushed.py):
        {
          "source": "erpnext",
          "txn_type": "sale" | "purchase",
          "docname": "ACC-SINV-2026-00001",
          "posting_date": "2026-03-15",
          "counterparty": "...",
          "net_amount": 1000.0,
          "vat_amount": 200.0,
          "gross_amount": 1200.0,
          "tax_code": "T1",
          "company": "...",
          "currency": "GBP",
          "pushed_at": "2026-..."
        }
    """
    txn_type = payload.get("txn_type")
    common = {
        "id": payload.get("docname", ""),
        "txn_date": _parse_date(payload.get("posting_date")),
        "counterparty": payload.get("counterparty") or "",
        "net_amount": Decimal(str(payload.get("net_amount", 0))),
        "vat_amount": Decimal(str(payload.get("vat_amount", 0))),
        "gross_amount": Decimal(str(payload.get("gross_amount", 0))),
        "vat_rate": _infer_vat_rate(payload),
        "tax_code": payload.get("tax_code") or "T1",
    }
    sales: List[SalesTransaction] = []
    purchases: List[PurchaseTransaction] = []
    if txn_type == "sale":
        sales.append(SalesTransaction(**common))
    elif txn_type == "purchase":
        purchases.append(PurchaseTransaction(**common))
    else:
        raise ValueError(f"unknown txn_type: {txn_type!r}")

    nine_box = compute_taxi_nine_box(sales, purchases)
    return ImportResult(
        sales=sales,
        purchases=purchases,
        erp_provided_boxes=nine_box,
        source_profile="erpnext:v1",
        source_filename="erpnext-push",
        source_hash="",
        warnings=[],
        rejected_rows=[],
        metadata={
            "company": payload.get("company"),
            "currency": payload.get("currency"),
            "pushed_at": payload.get("pushed_at"),
            "source": "erpnext",
        },
    )


def _parse_date(s) -> date:
    if isinstance(s, date):
        return s
    return date.fromisoformat(str(s))


def _infer_vat_rate(payload: Dict[str, Any]) -> Decimal:
    net = Decimal(str(payload.get("net_amount", 0)))
    vat = Decimal(str(payload.get("vat_amount", 0)))
    if net > 0:
        return (vat / net).quantize(Decimal("0.0001"))
    return Decimal("0")
