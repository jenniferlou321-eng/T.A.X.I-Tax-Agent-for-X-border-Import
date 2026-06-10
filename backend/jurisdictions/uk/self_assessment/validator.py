"""UK Self Assessment 数据校验器"""

from backend.models.tax_data import TaxData
from backend.models.results import ValidationReport, ValidationError


def validate_self_assessment(data: TaxData) -> ValidationReport:
    """校验 SA 申报数据

    规则：
    - 必填：nino, tax_year
    - tax_year 格式：YYYY-YY
    - 收入非负
    - 至少有一项收入来源
    - 日期格式
    """
    errors: list[ValidationError] = []
    warnings: list[ValidationError] = []

    line_map = {li.category: li.amount for li in data.line_items}

    # ── 必填字段 ──
    taxpayer_nino = data.taxpayer.tax_id or ""
    if not taxpayer_nino:
        errors.append(ValidationError(
            field="nino", message="NINO is required for Self Assessment",
        ))
    elif not _is_valid_nino_format(taxpayer_nino):
        errors.append(ValidationError(
            field="nino", message=f"Invalid NINO format: {taxpayer_nino}",
        ))

    # Tax year
    period_key = data.period.period_key or ""
    if not period_key:
        errors.append(ValidationError(
            field="tax_year", message="Tax year is required (e.g. 2023-24)",
        ))
    elif not _is_valid_tax_year(period_key):
        warnings.append(ValidationError(
            field="tax_year",
            message=f"Tax year format should be YYYY-YY (got '{period_key}')",
            severity="warning",
        ))

    # ── 数值校验 ──
    for category, amount in line_map.items():
        if amount < 0 and category not in ("loss_brought_forward", "total_losses", "balancing_payment"):
            errors.append(ValidationError(
                field=category,
                message=f"Amount must be non-negative: {amount}",
            ))

    # ── 业务规则：至少一项收入 ──
    income_categories = {
        "employment_income", "self_employment_net_profit",
        "property_net_income", "foreign_income", "savings_income",
        "dividend_income", "other_income",
    }
    has_income = any(cat in line_map and line_map[cat] > 0 for cat in income_categories)
    if not has_income:
        warnings.append(ValidationError(
            field="income",
            message="No income sources declared - is this a nil return?",
            severity="warning",
        ))

    # ── 业务规则：Pension relief 上限 ──
    pension = line_map.get("pension_contributions", 0)
    if pension > 60000:
        warnings.append(ValidationError(
            field="pension_contributions",
            message="Annual pension contributions > £60,000 - check lifetime allowance rules",
            severity="warning",
        ))

    # ── 业务规则：HMRC Online Filing Deadline ──
    period_year = data.period.year
    if period_year < 2014:
        warnings.append(ValidationError(
            field="period",
            message="Returns for tax years before 2014/15 may not be supported by MTD for ITSA",
            severity="warning",
        ))

    return ValidationReport(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def _is_valid_nino_format(nino: str) -> bool:
    """NINO 格式：2字母 + 6数字 + 1字母"""
    if len(nino) != 9:
        return False
    # 简化校验
    prefix = nino[:2]
    if prefix not in ("AB", "CD", "EF", "GH", "IJ", "KL", "MN", "OP", "QR", "ST", "UV", "WX", "YZ"):
        return False
    return nino[2:8].isdigit() and nino[8].isalpha()


def _is_valid_tax_year(tax_year: str) -> bool:
    """Tax year 格式：YYYY-YY"""
    if "-" not in tax_year:
        return False
    parts = tax_year.split("-")
    if len(parts) != 2:
        return False
    if len(parts[0]) != 4 or not parts[0].isdigit():
        return False
    if len(parts[1]) != 2 or not parts[1].isdigit():
        return False
    return True
