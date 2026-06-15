"""UK VAT Validator — 提交前合规性校验"""

from decimal import Decimal
from backend.models.tax_data import TaxData
from backend.models.results import ValidationReport, ValidationError


def validate_uk_vat(data: TaxData) -> ValidationReport:
    """校验 UK VAT Return 数据合规性"""
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    line_map = {li.category: li.amount for li in data.line_items}

    # 必填字段检查
    required_fields = {
        "vat_reclaimed_purchases": "Box 4 — VAT reclaimed",
        "total_sales_ex_vat": "Box 6 — Total sales",
        "total_purchases_ex_vat": "Box 7 — Total purchases",
    }
    for key, label in required_fields.items():
        if key not in line_map:
            errors.append(ValidationError(
                field=key,
                message=f"Required field missing: {label}",
                severity="error",
            ))

    # 金额非负检查
    for key, amount in line_map.items():
        if amount < 0:
            errors.append(ValidationError(
                field=key,
                message=f"Negative amount not allowed: {key} = {amount}",
                severity="error",
            ))

    # 小数精度检查 — HMRC 要求 Box 1-5 最多 2 位小数，Box 6-9 必须为整数
    for key, amount in line_map.items():
        if amount.as_tuple().exponent < -2:
            # Box 6-9 必须整磅（无小数位）
            if key in ("total_sales_ex_vat", "total_purchases_ex_vat",
                       "total_goods_supplied_eu", "total_goods_acquired_eu"):
                errors.append(ValidationError(
                    field=key,
                    message=f"Box 6-9 must be whole pounds (no decimals): {key} = {amount}",
                    severity="error",
                ))
            else:
                # Box 1-5 最多 2 位小数
                errors.append(ValidationError(
                    field=key,
                    message=f"Box 1-5 must have at most 2 decimal places: {key} = {amount}",
                    severity="error",
                ))

    # ── 一致性检查 ──
    box1 = line_map.get("vat_due_sales", Decimal("0"))
    box2 = line_map.get("vat_due_acquisitions", Decimal("0"))
    box3 = line_map.get("total_vat_due", Decimal("0"))
    box4 = line_map.get("vat_reclaimed_purchases", Decimal("0"))
    box5 = line_map.get("net_vat_due", Decimal("0"))
    box6 = line_map.get("total_sales_ex_vat", Decimal("0"))
    box7 = line_map.get("total_purchases_ex_vat", Decimal("0"))
    box9 = line_map.get("total_goods_acquired_eu", Decimal("0"))

    # 1. 销售-销项一致性
    if box1 > 0 and box6 == 0:
        warnings.append(ValidationError(
            field="total_sales_ex_vat",
            message="VAT due on sales is positive but Box 6 (total sales) is zero",
            severity="warning",
        ))

    # 2. EU 取得对称性(Box 2 ↔ Box 9) — 反向征收 / EU acquisition 的核心不变量
    if box9 > 0 and box2 == 0:
        warnings.append(ValidationError(
            field="vat_due_acquisitions",
            message=(
                "Box 9 reports EU acquisitions but Box 2 is zero — "
                "reverse charge / EU acquisition VAT may be missing from Box 2. "
                "If you have EU purchases (e.g. German or French suppliers), "
                "the corresponding VAT due must be reported in Box 2, even though "
                "it is reclaimable in Box 4."
            ),
            severity="warning",
        ))
    if box2 > 0 and box9 == 0:
        warnings.append(ValidationError(
            field="total_goods_acquired_eu",
            message=(
                "Box 2 reports VAT due on EU acquisitions but Box 9 is zero — "
                "the underlying goods value must be reported in Box 9."
            ),
            severity="warning",
        ))

    # 3. 进项 VAT 与采购额一致性(Box 4 ↔ Box 7)
    if box4 > 0 and box7 == 0:
        warnings.append(ValidationError(
            field="total_purchases_ex_vat",
            message=(
                "Box 4 claims input VAT but Box 7 (total purchases) is zero — "
                "this is only valid if ALL input VAT comes from PVA (postponed VAT accounting) "
                "or reverse charge with no net purchase value. Verify Box 7 includes the "
                "underlying purchase values (e.g. CIF £157,500 for C1-103 PVA import)."
            ),
            severity="warning",
        ))

    # 4. Box 3 = Box 1 + Box 2 核算
    expected_box3 = box1 + box2
    if box3 != expected_box3:
        warnings.append(ValidationError(
            field="total_vat_due",
            message=(
                f"Box 3 (£{box3}) does NOT equal Box 1 + Box 2 (£{expected_box3}). "
                "Box 3 must be exactly Box 1 + Box 2 per HMRC rules. "
                "Recalculate before submission."
            ),
            severity="warning",
        ))

    # 5. Box 5 = |Box 3 − Box 4| 核算 (HMRC: netVatDue must be ≥ 0)
    expected_box5 = abs(box3 - box4)
    if box5 != expected_box5:
        warnings.append(ValidationError(
            field="net_vat_due",
            message=(
                f"Box 5 (£{box5}) does NOT equal |Box 3 − Box 4| = £{expected_box5}. "
                "Per HMRC, Box 5 must be the absolute difference. Recalculate."
            ),
            severity="warning",
        ))

    # 6. 粗略异常:Box 4 远超 Box 1(可能触发 HMRC 人工审)
    if box4 > box1 * 3 and box1 > 0:
        warnings.append(ValidationError(
            field="vat_reclaimed_purchases",
            message=(
                "VAT reclaimed (Box 4) significantly exceeds VAT due (Box 1) — "
                "this may trigger HMRC review. If caused by PVA or reverse charge, "
                "ensure both sides are declared correctly."
            ),
            severity="warning",
        ))

    return ValidationReport(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )