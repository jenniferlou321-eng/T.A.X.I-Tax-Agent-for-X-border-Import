"""UK VAT Validator — 提交前合规性校验"""

from decimal import Decimal
from backend.models.tax_data import TaxType, TaxData
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

    # 一致性检查
    box1 = line_map.get("vat_due_sales", Decimal("0"))
    box4 = line_map.get("vat_reclaimed_purchases", Decimal("0"))
    box6 = line_map.get("total_sales_ex_vat", Decimal("0"))

    if box1 > 0 and box6 == 0:
        warnings.append(ValidationError(
            field="total_sales_ex_vat",
            message="VAT due on sales is positive but Box 6 (total sales) is zero",
            severity="warning",
        ))

    if box4 > box1 * 3:
        warnings.append(ValidationError(
            field="vat_reclaimed_purchases",
            message="VAT reclaimed significantly exceeds VAT due — may trigger HMRC review",
            severity="warning",
        ))

    return ValidationReport(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )