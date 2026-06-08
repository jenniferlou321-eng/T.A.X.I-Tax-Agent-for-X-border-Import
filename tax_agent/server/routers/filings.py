"""申报路由 — preview / submit / status / history / obligations"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Query
from pydantic import BaseModel

from tax_agent.models.tax_data import (
    TaxType, PeriodType, FiscalPeriod, TaxpayerInfo, TaxData, LineItem,
)
from tax_agent.models.results import FilingStatus

router = APIRouter(prefix="/filings", tags=["filings"])


# ── Request Schemas ──

class PeriodInput(BaseModel):
    year: int
    period_type: str
    period_key: str
    start_date: str
    end_date: str


class TaxpayerInput(BaseModel):
    name: str
    tax_id: str
    tax_id_type: str


class LineItemInput(BaseModel):
    category: str
    amount: float
    sub_category: str = ""
    currency: str = ""


class FilingRequest(BaseModel):
    jurisdiction: str          # "uk"
    tax_type: str              # "vat"
    period: PeriodInput
    taxpayer: TaxpayerInput
    data: list[LineItemInput]


# ── Helpers ──

in_memory_filings: dict[str, dict] = {}


def _build_tax_data(req: FilingRequest) -> TaxData:
    return TaxData(
        tax_type=TaxType(req.tax_type),
        period=FiscalPeriod(
            year=req.period.year,
            period_type=PeriodType(req.period.period_type.lower()),
            period_key=req.period.period_key,
            start_date=date.fromisoformat(req.period.start_date),
            end_date=date.fromisoformat(req.period.end_date),
        ),
        taxpayer=TaxpayerInfo(
            name=req.taxpayer.name,
            tax_id=req.taxpayer.tax_id,
            tax_id_type=req.taxpayer.tax_id_type,
        ),
        line_items=[
            LineItem(
                category=li.category,
                amount=Decimal(str(li.amount)),
                sub_category=li.sub_category,
                currency=li.currency,
            )
            for li in req.data
        ],
    )


# ── Endpoints ──

@router.post("/preview")
async def preview_filing(req: FilingRequest, request: Request):
    """预览计算（不提交）"""
    registry = request.app.state.registry
    adapter = registry.get(req.jurisdiction)
    tax_type = TaxType(req.tax_type)
    data = _build_tax_data(req)

    calc = adapter.calculate(tax_type, data)
    report = adapter.validate(tax_type, data)

    return {
        "calculation": {
            "total_tax_due": str(calc.total_tax_due),
            "breakdown": [
                {"category": b.category, "amount": str(b.amount)}
                for b in calc.breakdown
            ],
            "warnings": calc.warnings,
        },
        "validation": {
            "is_valid": report.is_valid,
            "errors": [
                {"field": e.field, "message": e.message}
                for e in report.errors
            ],
            "warnings": [
                {"field": w.field, "message": w.message}
                for w in report.warnings
            ],
        },
        "can_submit": report.is_valid,
    }


@router.post("/submit")
async def submit_filing(req: FilingRequest, request: Request):
    """提交申报"""
    registry = request.app.state.registry
    orchestrator = request.app.state.orchestrator
    adapter = registry.get(req.jurisdiction)
    tax_type = TaxType(req.tax_type)
    data = _build_tax_data(req)

    result = await orchestrator.run(adapter, tax_type, data)

    # 持久化到内存存储（Demo）
    filing_record = {
        "filing_id": result.filing_id,
        "status": result.status.value,
        "receipt": {
            "receipt_id": result.receipt.receipt_id,
            "submitted_at": result.receipt.submitted_at.isoformat(),
            "raw_response": result.receipt.raw_response,
        } if result.receipt else None,
        "errors": [
            {"code": e.code, "message": e.message, "stage": e.stage}
            for e in result.errors
        ],
        "stage_results": {
            k: {
                "stage": v.stage,
                "status": v.status,
                "message": v.message,
                "detail": v.detail,
                "started_at": v.started_at.isoformat() if v.started_at else None,
                "completed_at": v.completed_at.isoformat() if v.completed_at else None,
            }
            for k, v in result.stage_results.items()
        },
        "jurisdiction": req.jurisdiction,
        "tax_type": req.tax_type,
        "period": req.period.model_dump(),
        "taxpayer": req.taxpayer.model_dump(),
    }
    in_memory_filings[result.filing_id] = filing_record

    return filing_record


@router.get("/{filing_id}")
async def get_filing(filing_id: str, request: Request):
    """查询申报详情"""
    if filing_id in in_memory_filings:
        return in_memory_filings[filing_id]

    return {
        "filing_id": filing_id,
        "status": "submitted",
        "message": "Detail retrieval not yet persisted; use /status for live checks.",
    }


@router.get("/{filing_id}/status")
async def get_filing_status(filing_id: str, request: Request):
    """查询申报状态"""
    if filing_id in in_memory_filings:
        return {
            "filing_id": filing_id,
            "status": in_memory_filings[filing_id]["status"],
        }

    return {
        "filing_id": filing_id,
        "status": "submitted",
    }


@router.get("/")
async def list_filings(
    jurisdiction: Optional[str] = None,
    status: Optional[str] = None,
    request: Request = None,
):
    """历史申报列表"""
    filings = list(in_memory_filings.values())
    if jurisdiction:
        filings = [f for f in filings if f.get("jurisdiction") == jurisdiction]
    if status:
        filings = [f for f in filings if f.get("status") == status]

    return {"filings": filings, "total": len(filings)}


# ── Tax Filing Obligations (Multi-jurisdiction) ──

@router.get("/obligations/{country}/{tax_type}")
async def get_obligations(
    country: str,
    tax_type: str,
    request: Request,
    # 主要字段：通用 taxpayer_id（UK VAT/SA/CT/PAYE/SDLT 等）
    taxpayer_id: Optional[str] = Query(None, description="Taxpayer ID (统一字段，UK 体系: VRN/NINO/CTREF/EMPREF)"),
    # 向后兼容的别名：允许直接 API 用户用 vrn/nino/ctref/empref/utr 调用
    vrn: Optional[str] = Query(None, description="[兼容] UK VAT 注册号，等同于 taxpayer_id"),
    nino: Optional[str] = Query(None, description="[兼容] UK Self Assessment NINO"),
    ctref: Optional[str] = Query(None, description="[兼容] UK Corporation Tax CTREF"),
    empref: Optional[str] = Query(None, description="[兼容] UK PAYE EMPREF"),
    utr: Optional[str] = Query(None, description="[兼容] UK UTR (Unique Taxpayer Reference)"),
    from_date: Optional[str] = Query(None, description="查询起始日期 (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="查询结束日期 (YYYY-MM-DD)"),
    status_filter: Optional[str] = Query(None, alias="status", description="O=Open, F=Fulfilled"),
):
    """获取指定管辖地的待申报义务列表

    通过 JurisdictionAdapter 抽象层路由到各国具体实现。
    必须先完成对应国家的 OAuth 授权。

    `taxpayer_id` 是规范字段名；同时接受 vrn/nino/ctref/empref/utr 作为兼容别名
    （按优先级 taxpayer_id > vrn > nino > ctref > empref > utr）。
    """
    # 统一所有命名的 ID 字段为 taxpayer_id
    if not taxpayer_id:
        for alt in (vrn, nino, ctref, empref, utr):
            if alt:
                taxpayer_id = alt
                break

    if not taxpayer_id:
        raise HTTPException(
            status_code=422,
            detail="query.taxpayer_id: Field required (or one of: vrn/nino/ctref/empref/utr)",
        )
    from tax_agent.models.tax_data import TaxType as TaxTypeEnum

    registry = request.app.state.registry
    adapter = registry.get(country)

    try:
        tt = TaxTypeEnum(tax_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown tax type: {tax_type}")

    if tt not in adapter.tax_types:
        raise HTTPException(
            status_code=400,
            detail=f"Tax type {tax_type} not supported for {adapter.country_name}"
        )

    try:
        obligations = await adapter.get_obligations(
            tax_type=tt,
            taxpayer_id=taxpayer_id,
            status_filter=status_filter or "",
        )
    except NotImplementedError:
        raise HTTPException(
            status_code=501,
            detail=f"Obligations query not yet implemented for {adapter.country_name}"
        )
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"obligations": obligations}
