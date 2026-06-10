"""把 data/realCaseData.json 转成 data/erp_samples/techflow_q1_2026.json

Usage: python scripts/convert_realcase_to_erp_sample.py
"""
import json
from decimal import Decimal
from datetime import date
from pathlib import Path

from backend.models.erp_models import (
    SalesTransaction, PurchaseTransaction, ERPNineBox, ImportResult,
)


REALCASE = Path(__file__).parent.parent / "data" / "realCaseData.json"
OUTPUT = Path(__file__).parent.parent / "data" / "erp_samples" / "techflow_q1_2026.json"


def to_decimal(v) -> Decimal:
    return Decimal(str(v))


def _net(s: dict) -> Decimal:
    """realCaseData 用 `net` (GBP) 或 `net_gbp` (EU/import)。"""
    return to_decimal(s.get("net", s.get("net_gbp", "0")))


def convert_sale(s: dict) -> SalesTransaction:
    """Map realCaseData sales_invoices -> SalesTransaction.

    type 字段决定 VAT 处理：
    - domestic_b2b / domestic_b2c : standard 20% (T1)
    - zero_rated : 0% (T0)
    - eu_b2b     : 0% UK VAT，is_eu=True (reverse charge flow)
    - export     : 0% (outside scope)
    """
    t = s.get("type", "standard")
    net = _net(s)
    vat = to_decimal(s.get("vat", "0"))
    gross = to_decimal(s.get("gross", net + vat))
    if t in ("domestic_b2b", "domestic_b2c"):
        return SalesTransaction(
            id=s.get("id", "S-UNKNOWN"),
            txn_date=date.fromisoformat(s["date"]),
            counterparty=s.get("customer", "Unknown"),
            net_amount=net,
            vat_amount=vat,
            gross_amount=gross,
            vat_rate=Decimal("0.20"),
            tax_code="T1",
            is_eu=False,
            is_reverse_charge=False,
        )
    if t == "eu_b2b":
        return SalesTransaction(
            id=s.get("id", "S-UNKNOWN"),
            txn_date=date.fromisoformat(s["date"]),
            counterparty=s.get("customer", "Unknown"),
            net_amount=net,
            vat_amount=vat,
            gross_amount=gross,
            vat_rate=Decimal("0"),
            tax_code="T9",  # EC supply / cross-border
            is_eu=True,
            is_reverse_charge=True,
        )
    # zero_rated / export
    return SalesTransaction(
        id=s.get("id", "S-UNKNOWN"),
        txn_date=date.fromisoformat(s["date"]),
        counterparty=s.get("customer", "Unknown"),
        net_amount=net,
        vat_amount=vat,
        gross_amount=gross,
        vat_rate=Decimal("0"),
        tax_code="T0",
        is_eu=(t == "eu_b2b"),
        is_reverse_charge=(t == "eu_b2b"),
    )


def convert_purchase(p: dict) -> PurchaseTransaction:
    """Map realCaseData purchase_invoices -> PurchaseTransaction.

    type 字段：
    - domestic           : standard 20% input VAT (T1)
    - eu_acquisition     : 0% 输入（reverse charge）, is_eu_acquisition=True
    - import             : 0% 输入（C79 已缴 customs），recoverable=True
    - exempt             : 0% 输入, recoverable=False
    """
    t = p.get("type", "standard")
    net = _net(p)
    # EU acquisitions store VAT in `acquisition_vat`, imports/domestic use `vat`
    if t == "eu_acquisition":
        vat = to_decimal(p.get("acquisition_vat", "0"))
    else:
        vat = to_decimal(p.get("vat", "0"))
    gross = to_decimal(p.get("gross", net + vat))
    if t == "eu_acquisition":
        return PurchaseTransaction(
            id=p.get("id", "P-UNKNOWN"),
            txn_date=date.fromisoformat(p["date"]),
            counterparty=p.get("supplier", "Unknown"),
            net_amount=net,
            vat_amount=vat,
            gross_amount=gross,
            vat_rate=Decimal("0.20"),  # reverse charge reference rate
            tax_code="T2",  # EC acquisition
            is_recoverable=True,
            is_eu_acquisition=True,
        )
    if t == "import":
        return PurchaseTransaction(
            id=p.get("id", "P-UNKNOWN"),
            txn_date=date.fromisoformat(p["date"]),
            counterparty=p.get("supplier", "Unknown"),
            net_amount=net,
            vat_amount=vat,
            gross_amount=gross,
            vat_rate=Decimal("0.20"),
            tax_code="T8",  # import VAT
            is_recoverable=True,
            is_eu_acquisition=False,
        )
    if t == "exempt":
        return PurchaseTransaction(
            id=p.get("id", "P-UNKNOWN"),
            txn_date=date.fromisoformat(p["date"]),
            counterparty=p.get("supplier", "Unknown"),
            net_amount=net,
            vat_amount=vat,
            gross_amount=gross,
            vat_rate=Decimal("0"),
            tax_code="T0",
            is_recoverable=False,
            is_eu_acquisition=False,
        )
    # domestic (default)
    return PurchaseTransaction(
        id=p.get("id", "P-UNKNOWN"),
        txn_date=date.fromisoformat(p["date"]),
        counterparty=p.get("supplier", "Unknown"),
        net_amount=net,
        vat_amount=vat,
        gross_amount=gross,
        vat_rate=Decimal("0.20"),
        tax_code="T1",
        is_recoverable=bool(p.get("recoverable", True)),
        is_eu_acquisition=False,
    )


def main():
    raw = json.loads(REALCASE.read_text(encoding="utf-8"))
    sales = [convert_sale(s) for s in raw.get("sales_invoices", [])]
    purchases = [convert_purchase(p) for p in raw.get("purchase_invoices", [])]
    # 9-Box 用 v0 简化计算
    from backend.erp.reconcile import compute_taxi_nine_box
    nine_box = compute_taxi_nine_box(sales, purchases)
    # 故意埋 1 个小差异（demo wow 效果）：ERP 报的 box1 +3.50
    # pydantic v1/v2 compat: v1 用 copy(deep=True), v2 用 model_copy(deep=True)
    if hasattr(nine_box, "model_copy"):
        erp_box = nine_box.model_copy(deep=True)
    else:
        erp_box = nine_box.copy(deep=True)
    erp_box.box1_vat_due_sales = erp_box.box1_vat_due_sales + Decimal("3.50")
    ir = ImportResult(
        sales=sales, purchases=purchases,
        erp_provided_boxes=erp_box,
        source_profile="demo",
        source_filename="techflow_q1_2026.json",
        source_hash="techflow-2026-q1",
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # pydantic v1/v2 compat
    if hasattr(ir, "model_dump"):
        ir_json = ir.model_dump(mode="json")
    else:
        ir_json = ir.dict()
        import json as _json
        ir_json = _json.loads(_json.dumps(ir_json, default=str))
    OUTPUT.write_text(json.dumps(ir_json, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT} ({len(sales)} sales, {len(purchases)} purchases)")


if __name__ == "__main__":
    main()
