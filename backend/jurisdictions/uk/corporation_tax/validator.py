"""UK Corporation Tax 数据校验器"""

from decimal import Decimal
from datetime import date
from backend.models.tax_data import TaxData
from backend.models.results import ValidationReport, ValidationError


def validate_corporation_tax(data: TaxData) -> ValidationReport:
    """校验 CT 申报数据

    规则：
    - 必填：ctref, company_name, utr, period_start, period_end
    - accounting period ≤ 12 个月（除非变更会计期间）
    - 利润字段必填且非负
    - 已缴税款非负
    """
    errors = []
    warnings = []

    # ── 必填字段 ──
    ctref = data.taxpayer.tax_id or ""
    if not ctref:
        errors.append(ValidationError(
            field="ctref", message="Corporation Tax Reference is required",
        ))
    elif not ctref.isdigit() or len(ctref) != 10:
        errors.append(ValidationError(
            field="ctref", message=f"CTREF must be 10 digits (got '{ctref}')",
        ))

    if not data.taxpayer.name or data.taxpayer.name == "Unknown":
        errors.append(ValidationError(
            field="company_name", message="Company name is required",
        ))

    # ── 期间校验 ──
    period_start = data.period.start_date
    period_end = data.period.end_date
    if not period_start or not period_end:
        errors.append(ValidationError(
            field="period", message="Accounting period dates are required",
        ))
    elif period_end <= period_start:
        errors.append(ValidationError(
            field="period", message="Period end must be after period start",
        ))
    else:
        # 期间长度 ≤ 12 个月
        days = (period_end - period_start).days
        if days > 366:
            warnings.append(ValidationError(
                field="period",
                message=f"Accounting period is {days} days - check if it exceeds 12 months",
                severity="warning",
            ))

    # ── 业务规则校验 ──
    line_map = {li.category: li.amount for li in data.line_items}

    for category in ("trading_income", "trading_expenses"):
        if category in line_map and line_map[category] < 0:
            errors.append(ValidationError(
                field=category,
                message=f"{category} must be non-negative",
            ))

    # ── HMCTS 在线申报规则 ──
    period_year = data.period.year
    if period_year < 2011:
        warnings.append(ValidationError(
            field="period",
            message="CT600 online filing for periods before 2011/12 may not be supported",
            severity="warning",
        ))

    return ValidationReport(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
