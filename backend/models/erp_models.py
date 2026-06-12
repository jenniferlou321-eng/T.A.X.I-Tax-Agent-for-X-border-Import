"""ERP 数据模型 — 通用交易 + 9-Box 容器

供 ImportResult / reconcile / orchestrator 共享。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class SalesTransaction(BaseModel):
    """一张销售发票"""
    id: str
    txn_date: date
    counterparty: str
    net_amount: Decimal
    vat_amount: Decimal
    gross_amount: Decimal
    vat_rate: Decimal
    tax_code: str
    is_eu: bool = False
    is_reverse_charge: bool = False


class PurchaseTransaction(BaseModel):
    """一张采购发票"""
    id: str
    txn_date: date
    counterparty: str
    net_amount: Decimal
    vat_amount: Decimal
    gross_amount: Decimal
    vat_rate: Decimal
    tax_code: str
    is_recoverable: bool = True
    is_eu_acquisition: bool = False


class ERPNineBox(BaseModel):
    """ERP（demo case / CSV / 真连）自报的 9-Box 值"""
    box1_vat_due_sales: Decimal = Decimal("0")
    box2_vat_due_acquisitions: Decimal = Decimal("0")
    box3_total_vat_due: Decimal = Decimal("0")
    box4_vat_reclaimed: Decimal = Decimal("0")
    box5_net_vat_due: Decimal = Decimal("0")
    box6_total_sales_ex_vat: int = 0
    box7_total_purchases_ex_vat: int = 0
    box8_total_goods_supplied_eu: int = 0
    box9_total_goods_acquired_eu: int = 0
    scheme_flags: List[str] = Field(default_factory=list)


class ImportResult(BaseModel):
    """一次导入的完整结果"""
    sales: List[SalesTransaction]
    purchases: List[PurchaseTransaction]
    erp_provided_boxes: ERPNineBox
    source_profile: str
    source_filename: str
    source_hash: str
    warnings: List[str] = Field(default_factory=list)
    rejected_rows: List[Dict[str, Any]] = Field(default_factory=list)
    # 原始 case metadata（company / period / intra_group_transactions /
    # source_documents 等）。保存下来供后续分析工具（如
    # business_analyzer.analyze_business_data 需要 top-level `company`）
    # 使用。Optional 是为了不破坏没有 metadata 字段的旧 case（CSV 解析
    # 路径不会塞 metadata）。
    metadata: Optional[Dict[str, Any]] = None


class HubInvoice(BaseModel):
    """一张在 Import Hub 中存储的发票。

    统一三种来源(ERPNext pull / CSV / push)的最小表示。
    同一 period 内按 id 去重。
    """
    id: str
    txn_date: date
    counterparty: str
    net_amount: Decimal
    vat_amount: Decimal
    gross_amount: Decimal
    vat_rate: Decimal
    tax_code: str
    cancelled: bool = False       # ERPNext docstatus=2
    is_amend: bool = False        # ERPNext Credit/Debit Note
    parent: Optional[str] = None  # 原发票 id(若 is_amend)
    source: str = "erpnext_pull"  # erpnext_pull | csv | erpnext_push
    pulled_at: Optional[str] = None  # ISO8601 string