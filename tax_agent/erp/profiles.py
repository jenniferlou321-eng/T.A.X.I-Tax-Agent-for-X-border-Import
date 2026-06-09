"""CSV Profile — 单一 Profile (Generic) for v0

v1 再加 Sage / Xero / QBO Profile。
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Tuple
from datetime import date

from ..models.erp_models import SalesTransaction, PurchaseTransaction


REQUIRED_COLUMNS = [
    "txn_date", "txn_type", "counterparty",
    "net", "vat", "gross", "vat_rate", "tax_code",
]


class GenericProfile:
    """v0 唯一 Profile：8 列必填，txn_type 区分 sale/purchase"""

    name = "generic"

    def detect(self, headers: List[str]) -> float:
        """返回 0.0-1.0 匹配分数。>=0.7 视为命中。"""
        headers_lower = [h.strip().lower() for h in headers]
        matched = sum(1 for c in REQUIRED_COLUMNS if c in headers_lower)
        return matched / len(REQUIRED_COLUMNS)

    def transform_row(
        self, row: Dict[str, str], row_index: int,
    ) -> Tuple[SalesTransaction | PurchaseTransaction | None, str | None]:
        """把一行 dict 转换为 SalesTransaction / PurchaseTransaction。
        返回 (txn, None) 或 (None, error_message)。"""
        try:
            common = {
                "id": f"{'SALE' if row['txn_type'].lower() == 'sale' else 'PIN'}-{row_index:05d}",
                "txn_date": date.fromisoformat(row["txn_date"].strip()),
                "counterparty": row["counterparty"].strip(),
                "net_amount": Decimal(str(row["net"]).strip()),
                "vat_amount": Decimal(str(row["vat"]).strip()),
                "gross_amount": Decimal(str(row["gross"]).strip()),
                "vat_rate": Decimal(str(row["vat_rate"]).strip()),
                "tax_code": row["tax_code"].strip(),
            }
            if row["txn_type"].strip().lower() == "sale":
                return SalesTransaction(**common), None
            elif row["txn_type"].strip().lower() == "purchase":
                return PurchaseTransaction(**common), None
            else:
                return None, f"unknown txn_type: {row['txn_type']!r}"
        except (ValueError, KeyError) as e:
            return None, f"parse error: {e}"
