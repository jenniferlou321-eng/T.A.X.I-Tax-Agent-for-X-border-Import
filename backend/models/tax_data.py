"""数据模型 — 跨管辖地通用的税务数据抽象"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


class TaxType(Enum):
    VAT = "vat"
    SELF_ASSESSMENT = "self_assessment"
    CORPORATION_TAX = "corporation_tax"
    PAYE = "paye"
    STAMP_DUTY = "stamp_duty"
    CAPITAL_GAINS = "capital_gains"
    NATIONAL_INSURANCE = "national_insurance"
    IMPORT_DUTY = "import_duty"
    BUSINESS_RATES = "business_rates"
    WITHHOLDING_TAX = "withholding_tax"
    APPRENTICESHIP_LEVY = "apprenticeship_levy"
    # CN tax types
    CN_VAT = "cn_vat"
    CN_CIT = "cn_cit"
    CN_IIT = "cn_iit"                       # 个人所得税
    CN_SURCHARGES = "cn_surcharges"          # 城建税/教育费附加
    CN_STAMP_DUTY = "cn_stamp_duty"          # 印花税
    CN_PROPERTY_TAX = "cn_property_tax"      # 房产税
    CN_REAL_ESTATE_RENTAL_VAT = "cn_real_estate_rental_vat"  # 不动产租赁 VAT
    CN_PROPERTY_MGMT_VAT = "cn_property_mgmt_vat"  # 物业管理服务 VAT


class PeriodType(Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class ChannelType(Enum):
    API = "api"
    BROWSER = "browser"


@dataclass
class Address:
    line1: str
    line2: str = ""
    city: str = ""
    postcode: str = ""
    country: str = ""


@dataclass
class Contact:
    email: str = ""
    phone: str = ""


@dataclass
class FiscalPeriod:
    """税务期间 — 支持各国不同财年"""
    year: int
    period_type: PeriodType
    period_key: str                     # "2026-Q1", "2026-04", "25-26"
    start_date: date
    end_date: date


@dataclass
class TaxpayerInfo:
    """纳税人信息"""
    name: str
    tax_id: str                         # VRN / UTR / NINO / EIN
    tax_id_type: str                    # "vrn" | "utr" | "nino" | "ein"
    registration_number: Optional[str] = None
    address: Optional[Address] = None
    contact: Optional[Contact] = None


@dataclass
class LineItem:
    """税务明细行 — 最灵活的数据单元"""
    category: str                       # "vat_due_sales", "vat_reclaimed", ...
    amount: Decimal
    sub_category: str = ""
    currency: str = ""
    tax_amount: Optional[Decimal] = None
    description: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class Attachment:
    """附件（发票、凭证等）"""
    filename: str
    mime_type: str
    size_bytes: int
    content_path: str                   # 本地路径或 URL


@dataclass
class TaxData:
    """一次申报的完整数据"""
    tax_type: TaxType
    period: FiscalPeriod
    taxpayer: TaxpayerInfo
    line_items: list[LineItem]
    attachments: list[Attachment] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)