"""数据模型包"""

from .tax_data import (
    TaxType, PeriodType, ChannelType,
    Address, Contact, FiscalPeriod,
    TaxpayerInfo, LineItem, Attachment, TaxData,
)
from .template import (
    FieldType, FieldValidation, TemplateField,
    TemplateSection, DataTemplate,
)
from .results import (
    FilingStatus,
    AuthResult, Receipt, SubmitResult, StatusResult,
    BreakdownItem, DeductionItem, CalculationResult,
    ValidationError, ValidationReport,
    StageResult, FilingError, AuditEntry,
    FilingPayload, FilingResult,
)

__all__ = [
    "TaxType", "PeriodType", "ChannelType",
    "Address", "Contact", "FiscalPeriod",
    "TaxpayerInfo", "LineItem", "Attachment", "TaxData",
    "FieldType", "FieldValidation", "TemplateField",
    "TemplateSection", "DataTemplate",
    "FilingStatus",
    "AuthResult", "Receipt", "SubmitResult", "StatusResult",
    "BreakdownItem", "DeductionItem", "CalculationResult",
    "ValidationError", "ValidationReport",
    "StageResult", "FilingError", "AuditEntry",
    "FilingPayload", "FilingResult",
]