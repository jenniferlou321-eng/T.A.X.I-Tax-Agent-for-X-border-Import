"""CSV Profile — Profile registry for various ERP export formats.

Currently registered profiles:
- generic: 8-column v0 layout (txn_date/txn_type/counterparty/net/vat/...)
- erpnext_export: ERPNext UI Report → Sales/Purchase Invoice export

Adding a new profile:
1. Implement a class with `name`, `detect(headers) -> float`, and
   `transform_row(row, row_index) -> (txn | None, err | None)`.
2. Add an instance to `_PROFILES` at the bottom of this file.
3. Add tests under `tests/erp/test_<name>_profile.py`.
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
    required_columns = REQUIRED_COLUMNS

    def detect(self, headers: List[str]) -> float:
        """返回 0.0-1.0 匹配分数。>=0.7 视为命中。"""
        headers_lower = [h.strip().lower() for h in headers]
        required = self.required_columns
        matched = sum(1 for c in required if c in headers_lower)
        return matched / len(required)

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


class ERPNextExportProfile:
    """ERPNext 导出 CSV (Report → Sales/Purchase Invoice) 的 Profile。

    通过 ERPNext UI 导出报表时,默认 header 为:
        Name, Posting Date, Customer/Supplier, Net Total, Total Taxes,
        Grand Total, Docstatus

    通过 ID 前缀 (SINV-/PINV-) 区分销售/采购。

    ERPNext 的销售/采购报表是分开导出的, 所以一个 CSV 里只会出现
    Customer 或 Supplier 其中一列。`required_columns` 只列硬必需的列;
    `optional_column_groups` 列出"至少要有一个"的可选列组。
    """

    name = "erpnext_export"
    required_columns = [
        "name", "posting date",
        "net total", "total taxes", "grand total", "docstatus",
    ]
    optional_column_groups = [
        ["customer", "supplier"],
    ]

    # Back-compat — 旧检测逻辑 / 外部代码可能引用 ERPNEXT_HEADERS
    ERPNEXT_HEADERS = required_columns + [c for g in optional_column_groups for c in g]

    def detect(self, headers: List[str]) -> float:
        """返回 0.0-1.0 匹配分数。>=0.7 视为命中。"""
        headers_lower = [h.strip().lower() for h in headers]
        required = self.required_columns
        matched = sum(1 for h in required if h in headers_lower)
        return matched / len(required)

    def transform_row(
        self, row: Dict[str, str], row_index: int,
    ) -> Tuple[SalesTransaction | PurchaseTransaction | None, str | None]:
        """把一行 dict 转换为 SalesTransaction / PurchaseTransaction。
        返回 (txn, None) 或 (None, error_message)。"""
        try:
            name = row["Name"].strip()
            net = Decimal(str(row["Net Total"]).strip())
            vat = Decimal(str(row["Total Taxes"]).strip())
            gross = Decimal(str(row["Grand Total"]).strip())
            vat_rate = (vat / net).quantize(Decimal("0.0001")) if net != 0 else Decimal("0")
            common = {
                "id": name,
                "txn_date": date.fromisoformat(row["Posting Date"].strip()),
                "counterparty": (row.get("Customer") or row.get("Supplier") or "").strip(),
                "net_amount": net,
                "vat_amount": vat,
                "gross_amount": gross,
                "vat_rate": vat_rate,
                "tax_code": "T1",
            }
            if name.startswith("S"):
                return SalesTransaction(**common), None
            elif name.startswith("P"):
                return PurchaseTransaction(**common), None
            return None, f"unknown prefix: {name!r}"
        except (ValueError, KeyError) as e:
            return None, f"parse error: {e}"


# Profile registry — single source of truth for `parse_csv` auto-detection.
_PROFILES = {
    "generic": GenericProfile(),
    "erpnext_export": ERPNextExportProfile(),
}
