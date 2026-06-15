"""reconcile — 对比 ERP 9-Box 与 T.A.X.I. 算的 9-Box，生成差异报告

v0 关键约束：
- T.A.X.I. 9-Box 永远从 sales/purchases 重新计算（不信任外部）
- 差异容差：£0.50（HMRC 官方 rounding 容差）
- 任意 box 差异 > tolerance → within_tolerance=False
"""
from __future__ import annotations

from decimal import Decimal
from typing import List, Tuple

from pydantic import BaseModel, Field

from ..models.erp_models import (
    ERPNineBox, SalesTransaction, PurchaseTransaction,
)


TOLERANCE_GBP = Decimal("0.50")


def _is_eu_acquisition(t: PurchaseTransaction) -> bool:
    """是否为 EU 取得(进 Box 2 VAT due + Box 9 EU goods)。

    两种数据约定都接受:
    - 显式 `is_eu_acquisition=True`(老式 CSV / 部分 case)
    - `is_reverse_charge=True` 且 `is_eu=True`(嘉汉 case 的 T2-UK-EU-RC 约定)

    EU 反向征收采购在 9-Box 上等同 EU acquisition:Box 2 申报 VAT due,
    同额进 Box 4 抵扣(由 is_recoverable 单独判定,不在此谓词内),
    Box 9 报货物净额。加 `is_eu` 限定是为了不误伤国内 CIS 建筑业反向征收
    (is_eu=False),那类不进 Box 2 / Box 9。
    """
    if getattr(t, "is_eu_acquisition", False):
        return True
    return bool(getattr(t, "is_reverse_charge", False) and getattr(t, "is_eu", False))


class ReconciliationDelta(BaseModel):
    """9-Box 差异报告"""
    box_diffs: dict[str, Decimal] = Field(default_factory=dict)
    total_abs_diff: Decimal = Decimal("0")
    within_tolerance: bool = True
    erp_source: str = ""
    notes: List[str] = Field(default_factory=list)


def compute_taxi_nine_box(
    sales: List[SalesTransaction], purchases: List[PurchaseTransaction],
) -> ERPNineBox:
    """从原始交易数据计算 T.A.X.I. 的 9-Box。"""
    box1 = sum(
        (t.vat_amount for t in sales if t.vat_rate > 0),
        Decimal("0"),
    )
    box2 = sum(
        (t.vat_amount for t in purchases if _is_eu_acquisition(t)),
        Decimal("0"),
    )
    box3 = box1 + box2
    box4 = sum(
        (t.vat_amount for t in purchases if t.is_recoverable),
        Decimal("0"),
    )
    box5 = abs(box3 - box4)
    # Box 6 = total sales excluding EU B2B (HMRC 9-Box: EU B2B 销售额
    # 单独在 Box 8 报告，不进 Box 6)。修复前 bug: Box 6 算所有 sales，
    # 与 Box 8 叠加后把 T9 销售算了两次。
    box6 = int(sum(
        (t.net_amount for t in sales if not t.is_eu), Decimal("0")
    ))
    box7 = int(sum((t.net_amount for t in purchases), Decimal("0")))
    box8 = int(sum((t.net_amount for t in sales if t.is_eu), Decimal("0")))
    box9 = int(sum(
        (t.net_amount for t in purchases if _is_eu_acquisition(t)),
        Decimal("0"),
    ))
    return ERPNineBox(
        box1_vat_due_sales=box1,
        box2_vat_due_acquisitions=box2,
        box3_total_vat_due=box3,
        box4_vat_reclaimed=box4,
        box5_net_vat_due=box5,
        box6_total_sales_ex_vat=box6,
        box7_total_purchases_ex_vat=box7,
        box8_total_goods_supplied_eu=box8,
        box9_total_goods_acquired_eu=box9,
    )


def reconcile(
    erp_boxes: ERPNineBox, taxi_boxes: ERPNineBox, erp_source: str,
    tolerance: Decimal = TOLERANCE_GBP,
) -> ReconciliationDelta:
    """对比两个 9-Box，生成差异报告。

    box_diffs 包含 9 个 box 的差值（taxi - erp）。
    notes 只列出超 tolerance 的 box。
    """
    diffs: dict[str, Decimal] = {}
    total_abs = Decimal("0")
    notes: List[str] = []

    pairs: List[Tuple[str, Decimal, Decimal]] = [
        ("box1", taxi_boxes.box1_vat_due_sales, erp_boxes.box1_vat_due_sales),
        ("box2", taxi_boxes.box2_vat_due_acquisitions, erp_boxes.box2_vat_due_acquisitions),
        ("box3", taxi_boxes.box3_total_vat_due, erp_boxes.box3_total_vat_due),
        ("box4", taxi_boxes.box4_vat_reclaimed, erp_boxes.box4_vat_reclaimed),
        ("box5", taxi_boxes.box5_net_vat_due, erp_boxes.box5_net_vat_due),
        ("box6", Decimal(taxi_boxes.box6_total_sales_ex_vat), Decimal(erp_boxes.box6_total_sales_ex_vat)),
        ("box7", Decimal(taxi_boxes.box7_total_purchases_ex_vat), Decimal(erp_boxes.box7_total_purchases_ex_vat)),
        ("box8", Decimal(taxi_boxes.box8_total_goods_supplied_eu), Decimal(erp_boxes.box8_total_goods_supplied_eu)),
        ("box9", Decimal(taxi_boxes.box9_total_goods_acquired_eu), Decimal(erp_boxes.box9_total_goods_acquired_eu)),
    ]
    for name, taxi_val, erp_val in pairs:
        d = taxi_val - erp_val
        diffs[name] = d
        total_abs += abs(d)
        if abs(d) > tolerance:
            notes.append(f"{name} 差异 {d} (TAXI={taxi_val}, ERP={erp_val}) > tolerance {tolerance}")

    return ReconciliationDelta(
        box_diffs=diffs,
        total_abs_diff=total_abs,
        within_tolerance=len(notes) == 0,
        erp_source=erp_source,
        notes=notes,
    )
