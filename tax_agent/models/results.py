"""管线结果类型 — 贯穿申报全流程的数据结构"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional


class FilingStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ERROR = "error"


# ── 渠道层 ──

@dataclass
class AuthResult:
    success: bool
    token: Optional[str] = None
    expires_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class Receipt:
    """税局回执"""
    receipt_id: str                     # HMRC receipt / correlation ID
    submitted_at: datetime
    raw_response: dict = field(default_factory=dict)


@dataclass
class SubmitResult:
    success: bool
    receipt: Optional[Receipt] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: dict = field(default_factory=dict)


@dataclass
class StatusResult:
    status: FilingStatus
    detail: str = ""
    updated_at: datetime = field(default_factory=datetime.utcnow)


# ── 管线层 ──

@dataclass
class BreakdownItem:
    category: str
    amount: Decimal
    rate: Optional[Decimal] = None


@dataclass
class DeductionItem:
    category: str
    amount: Decimal
    rule_ref: str = ""


@dataclass
class CalculationResult:
    """计算结果"""
    total_tax_due: Decimal
    breakdown: list[BreakdownItem] = field(default_factory=list)
    deductions: list[DeductionItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ValidationError:
    field: str
    message: str
    severity: str = "error"             # "error" | "warning"


@dataclass
class ValidationReport:
    """校验报告"""
    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)


@dataclass
class StageResult:
    """单个管道阶段结果 — 支持 Pipeline 可视化"""
    stage: str                          # "PRECHECK" | "PREPARE" | "CALCULATE" | "VALIDATE" | "SUBMIT" | "TRACK"
    status: str                         # "pending" | "running" | "success" | "warning" | "error"
    message: str = ""
    detail: dict = field(default_factory=dict)   # 阶段特有详情，供前端展示
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    # 保留向后兼容
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FilingError:
    """申报错误"""
    code: str
    message: str
    stage: str
    recoverable: bool
    retry_count: int = 0


@dataclass
class AuditEntry:
    """审计日志条目"""
    filing_id: str
    stage: str
    action: str                         # "data_validated", "tax_calculated", "submitted", ...
    detail: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class FilingPayload:
    """提交到税局的数据载体"""
    tax_type: 'TaxType'                 # type: ignore
    period: 'FiscalPeriod'             # type: ignore
    taxpayer: 'TaxpayerInfo'           # type: ignore
    body: dict                          # JSON (API) or key-value map (Browser)
    headers: dict = field(default_factory=dict)
    idempotency_key: str = ""


@dataclass
class FilingResult:
    """申报结果 — 贯穿全流程"""
    filing_id: str
    status: FilingStatus
    stage_results: dict[str, StageResult] = field(default_factory=dict)
    receipt: Optional[Receipt] = None
    audit_trail: list[AuditEntry] = field(default_factory=list)
    errors: list[FilingError] = field(default_factory=list)