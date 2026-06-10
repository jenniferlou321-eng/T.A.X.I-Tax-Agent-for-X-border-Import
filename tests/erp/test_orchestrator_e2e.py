"""Orchestrator 端到端：demo case → import → submit pipeline"""
import pytest
import base64
from datetime import date
from decimal import Decimal

from backend.orchestrator import Orchestrator
from backend.jurisdictions.uk import UKJurisdictionAdapter
from backend.models.tax_data import (
    TaxData, TaxType, FiscalPeriod, PeriodType, TaxpayerInfo, LineItem,
)


@pytest.mark.asyncio
async def test_full_pipeline_with_demo_case_import():
    """Demo case import → 6 阶段跑通 → FilingResult.success"""
    orch = Orchestrator()
    adapter = UKJurisdictionAdapter()

    data = TaxData(
        tax_type=TaxType.VAT,
        period=FiscalPeriod(
            year=2026, period_type=PeriodType.QUARTERLY,
            period_key="26A1",
            start_date=date(2026, 1, 1), end_date=date(2026, 3, 31),
        ),
        taxpayer=TaxpayerInfo(
            name="TechFlow Distribution Ltd",
            tax_id="960606228", tax_id_type="vrn",
        ),
        line_items=[],
    )

    result = await orch.run(
        adapter, TaxType.VAT, data,
        import_payload={"source": "demo", "case_id": "techflow_q1_2026"},
    )

    assert result.filing_id is not None
    assert len(result.audit_trail) >= 4
    import_records = [e for e in result.audit_trail if e.stage == "IMPORT"]
    assert len(import_records) >= 2  # started + parsed
    assert data.metadata.get("source") == "demo"
    assert data.metadata.get("compute_mode") == "reconcile"


@pytest.mark.asyncio
async def test_import_failure_short_circuits_pipeline():
    """Import 失败时不应继续 PRECHECK+ 等阶段"""
    orch = Orchestrator()
    adapter = UKJurisdictionAdapter()

    data = TaxData(
        tax_type=TaxType.VAT,
        period=FiscalPeriod(
            year=2026, period_type=PeriodType.QUARTERLY,
            period_key="26A1",
            start_date=date(2026, 1, 1), end_date=date(2026, 3, 31),
        ),
        taxpayer=TaxpayerInfo(name="X", tax_id="X", tax_id_type="vrn"),
        line_items=[],
    )

    result = await orch.run(
        adapter, TaxType.VAT, data,
        import_payload={"source": "demo", "case_id": "nonexistent_case"},
    )

    assert result.status.value == "error"
    import_failed = [e for e in result.audit_trail if e.action == "erp.import.failed"]
    assert len(import_failed) == 1
