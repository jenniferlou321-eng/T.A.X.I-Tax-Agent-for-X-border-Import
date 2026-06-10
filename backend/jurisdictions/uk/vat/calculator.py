"""UK VAT Calculator — 9-box VAT 计算逻辑

HMRC MTD for VAT API 规范:
- Box 3 = Box 1 + Box 2
- Box 5 = |Box 3 − Box 4| (必须为非负值)
- Box 6-9 为整磅数（无小数位）

v0 修订：加 `mode` 形参。
- mode="recompute" (默认，向后兼容): 旧行为，breakdown 来自 data.line_items
- mode="reconcile": breakdown 来自 data.metadata["erp_provided_boxes"]，
  同时调 reconcile 生成 discrepancy_report
"""
from decimal import Decimal
from typing import Optional

from backend.models.tax_data import TaxData
from backend.models.results import CalculationResult, BreakdownItem
from backend.erp.reconcile import compute_taxi_nine_box, reconcile, ReconciliationDelta
from backend.models.erp_models import ERPNineBox


def calculate_uk_vat(data: TaxData, mode: str = "recompute") -> CalculationResult:
    """计算 UK VAT Return 9-box 值

    Box 3 = Box 1 + Box 2
    Box 5 = |Box 3 − Box 4|  (HMRC 要求 netVatDue 必须 ≥ 0)

    mode='reconcile' 时，breakdown 取自 data.metadata['erp_provided_boxes']，
    discrepancy_report 用 T.A.X.I. 算的 9-Box 与 ERP 报的对比。
    """
    # ── reconcile mode ──
    if mode == "reconcile":
        erp_boxes_dict = data.metadata.get("erp_provided_boxes")
        if not erp_boxes_dict:
            # 没传 ERP 9-Box → 退回 recompute
            mode = "recompute"
        else:
            erp_boxes = ERPNineBox.model_validate(erp_boxes_dict)
            sales = data.metadata.get("sales_transactions", [])
            purchases = data.metadata.get("purchase_transactions", [])
            taxi_boxes = compute_taxi_nine_box(sales, purchases)
            delta = reconcile(erp_boxes, taxi_boxes, erp_source=data.metadata.get("source", "unknown"))

            breakdown = [
                BreakdownItem(category="vat_due_sales", amount=erp_boxes.box1_vat_due_sales),
                BreakdownItem(category="vat_due_acquisitions", amount=erp_boxes.box2_vat_due_acquisitions),
                BreakdownItem(category="total_vat_due", amount=erp_boxes.box3_total_vat_due),
                BreakdownItem(category="vat_reclaimed_purchases", amount=erp_boxes.box4_vat_reclaimed),
                BreakdownItem(category="net_vat_due", amount=erp_boxes.box5_net_vat_due),
            ]
            warnings: list[str] = list(delta.notes)
            if (erp_boxes.box3_total_vat_due - erp_boxes.box4_vat_reclaimed) < 0:
                warnings.append("Net VAT due is negative (repayment due from HMRC) — Box 5 shown as positive per HMRC requirements")
            return CalculationResult(
                total_tax_due=erp_boxes.box5_net_vat_due,
                breakdown=breakdown,
                warnings=warnings,
                discrepancy_report=delta,
                compute_mode="reconcile",
            )

    # ── recompute mode (default) ──
    line_map = {li.category: li.amount for li in data.line_items}

    box1 = line_map.get("vat_due_sales", Decimal("0"))
    box2 = line_map.get("vat_due_acquisitions", Decimal("0"))
    box3 = box1 + box2
    box4 = line_map.get("vat_reclaimed_purchases", Decimal("0"))
    box5 = abs(box3 - box4)  # HMRC: netVatDue must be positive

    return CalculationResult(
        total_tax_due=box5,
        breakdown=[
            BreakdownItem(category="vat_due_sales", amount=box1),
            BreakdownItem(category="vat_due_acquisitions", amount=box2),
            BreakdownItem(category="total_vat_due", amount=box3),
            BreakdownItem(category="vat_reclaimed_purchases", amount=box4),
            BreakdownItem(category="net_vat_due", amount=box5),
        ],
        warnings=(
            ["Net VAT due is negative (repayment due from HMRC) — Box 5 shown as positive per HMRC requirements"]
            if (box3 - box4) < 0
            else []
        ),
        discrepancy_report=None,
        compute_mode="recompute",
    )
