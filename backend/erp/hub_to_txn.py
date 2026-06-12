"""HubInvoice → 9-Box 交易记录的纯数据转换器。

被 3 个调用方共用:
- backend/erp/csv_parser.py(CSV 上传路径)
- backend/erp/erpnext_pull.py(ERPNext Pull 路径)
- backend/erp/erpnext_push.py(ERPNext Push 路径,future)

不依赖任何 HTTP/IO — 是纯粹的 in-memory transformer。
"""
from __future__ import annotations

from typing import List

from ..models.erp_models import HubInvoice, SalesTransaction, PurchaseTransaction


def hub_invoices_to_txn(
    invoices: List[HubInvoice], *, filter_cancelled: bool = True,
) -> tuple[List[SalesTransaction], List[PurchaseTransaction]]:
    """HubInvoice list → (sales, purchases)。

    Cancelled 的发票默认过滤掉。Amend 保留(同 id 前缀归类,负数自然抵减 9-Box)。
    未知 id 前缀会抛 ValueError — 强制调用方用规范的 id 命名(SINV-/ACC-SINV- 销售,
    PINV-/PCN-/PRN-/PRET- 采购等)。
    """
    sales: List[SalesTransaction] = []
    purchases: List[PurchaseTransaction] = []
    for inv in invoices:
        if filter_cancelled and inv.cancelled:
            continue
        common = dict(
            id=inv.id, txn_date=inv.txn_date, counterparty=inv.counterparty,
            net_amount=inv.net_amount, vat_amount=inv.vat_amount,
            gross_amount=inv.gross_amount, vat_rate=inv.vat_rate, tax_code=inv.tax_code,
        )
        if inv.id.startswith("S"):
            sales.append(SalesTransaction(**common))
        elif inv.id.startswith("P"):
            purchases.append(PurchaseTransaction(**common))
        else:
            raise ValueError(
                f"HubInvoice.id={inv.id!r} does not start with S or P; "
                "cannot classify as sale or purchase. Use a real ERPNext docname."
            )
    return sales, purchases
