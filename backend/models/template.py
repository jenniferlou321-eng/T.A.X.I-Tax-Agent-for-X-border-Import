"""数据模板系统 — 前端据此动态渲染表单"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from .tax_data import TaxType


class FieldType(Enum):
    NUMBER = "number"
    TEXT = "text"
    SELECT = "select"
    DATE = "date"
    FILE = "file"


@dataclass
class FieldValidation:
    """字段校验规则"""
    min: Optional[Decimal] = None
    max: Optional[Decimal] = None
    decimal_places: int = 2
    pattern: Optional[str] = None           # regex
    options: list[str] = field(default_factory=list)  # SELECT 选项


@dataclass
class TemplateField:
    """模板字段 — 映射到 LineItem.category"""
    key: str                                # → LineItem.category
    label: str                              # 前端显示
    field_type: FieldType
    required: bool = True
    validation: FieldValidation = field(default_factory=FieldValidation)
    hint: str = ""
    example: str = ""
    auto_calculated: bool = False           # 自动计算字段 (如 Box3=Box1+Box2)
    allow_manual_override: bool = True      # 是否允许手动覆盖自动计算结果


@dataclass
class TemplateSection:
    """模板分区"""
    title: str
    description: str = ""
    fields: list[TemplateField] = field(default_factory=list)
    is_optional: bool = False


@dataclass
class DataTemplate:
    """完整数据模板"""
    tax_type: TaxType
    jurisdiction: str
    version: str                            # 模板版本（应对税法变更）
    sections: list[TemplateSection]
    valid_from: date
    valid_until: Optional[date] = None