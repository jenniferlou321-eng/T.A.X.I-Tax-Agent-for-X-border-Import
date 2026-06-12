"""Tests for POST /api/erp/erpnext/pull endpoint.

Wires together: ErpNextPullError / pull_invoices (Task 3) +
ImportHubStore (Task 2) + HubInvoice (Task 1) via the FastAPI router.
"""
import pytest
from datetime import date
from decimal import Decimal
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.imported_data_buffer import ImportHubStore


client = TestClient(app)


def test_pull_endpoint_writes_to_hub_store(httpx_mock, monkeypatch):
    """POST /api/erp/erpnext/pull → 拉发票 → 写 ImportHubStore(period)。"""
    from backend.erp import erpnext_pull

    async def fake_pull(*args, **kwargs):
        from backend.models.erp_models import HubInvoice
        return [HubInvoice(
            id="SINV-001", txn_date=date(2026, 3, 15),
            counterparty="ACME", net_amount=Decimal("1000"),
            vat_amount=Decimal("200"), gross_amount=Decimal("1200"),
            vat_rate=Decimal("0.20"), tax_code="T1", source="erpnext_pull",
        )]

    monkeypatch.setattr(erpnext_pull, "pull_invoices", fake_pull)

    try:
        resp = client.post("/api/erp/erpnext/pull", json={
            "url": "http://erp.test:8000",
            "api_key": "k", "api_secret": "s",
            "period": "Q1_2026",
            "period_start": "2026-01-01", "period_end": "2026-03-31",
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "ok"
        assert body["sales"] == 1
        assert body["purchases"] == 0
        assert body["count"]["total"] == 1

        # 验证 store
        listed = ImportHubStore.list("Q1_2026")
        assert len(listed) == 1
        assert listed[0].id == "SINV-001"
    finally:
        ImportHubStore.clear("Q1_2026")


def test_pull_endpoint_401_returns_500_with_status(httpx_mock, monkeypatch):
    """ERPNext 401 → 500 + status_code 在 detail 中。"""
    from backend.erp import erpnext_pull

    async def fake_pull_401(*args, **kwargs):
        raise erpnext_pull.ErpNextPullError("401 unauthorized", status_code=401)

    monkeypatch.setattr(erpnext_pull, "pull_invoices", fake_pull_401)

    try:
        resp = client.post("/api/erp/erpnext/pull", json={
            "url": "http://erp.test:8000",
            "api_key": "bad", "api_secret": "bad",
            "period": "Q1_2026",
            "period_start": "2026-01-01", "period_end": "2026-03-31",
        })
        assert resp.status_code == 500  # 或自定义,见实现
        body = resp.json()
        assert body["detail"]["status_code"] == 401
    finally:
        ImportHubStore.clear("Q1_2026")


def test_pull_endpoint_merges_both_doctypes(httpx_mock, monkeypatch):
    """Fake pull_invoices returns 1 sale from Sales Invoice call, 1 purchase from Purchase Invoice call.
    Endpoint should write both to the store."""
    from backend.erp import erpnext_pull
    from backend.models.erp_models import HubInvoice

    async def fake_pull_dispatch(base_url, api_key, api_secret, period_start, period_end, doctype, since=None):
        if doctype == "Sales Invoice":
            return [HubInvoice(
                id="S-001", txn_date=date(2026, 3, 15), counterparty="A",
                net_amount=Decimal("1000"), vat_amount=Decimal("200"),
                gross_amount=Decimal("1200"), vat_rate=Decimal("0.20"), tax_code="T1",
            )]
        elif doctype == "Purchase Invoice":
            return [HubInvoice(
                id="P-001", txn_date=date(2026, 3, 16), counterparty="B",
                net_amount=Decimal("500"), vat_amount=Decimal("100"),
                gross_amount=Decimal("600"), vat_rate=Decimal("0.20"), tax_code="T2",
            )]
        return []

    monkeypatch.setattr(erpnext_pull, "pull_invoices", fake_pull_dispatch)

    resp = client.post("/api/erp/erpnext/pull", json={
        "url": "http://erp.test:8000",
        "api_key": "k", "api_secret": "s",
        "period": "Q1_2026",
        "period_start": "2026-01-01", "period_end": "2026-03-31",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["sales"] == 1
    assert body["purchases"] == 1
    listed = ImportHubStore.list("Q1_2026")
    assert len(listed) == 2
    assert {x.id for x in listed} == {"S-001", "P-001"}
    ImportHubStore.clear("Q1_2026")
