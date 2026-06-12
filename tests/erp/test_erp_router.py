"""erp router 测试 — FastAPI TestClient"""
import io
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.erp_router import router as erp_router
from backend.models.erp_models import ERPNineBox


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(erp_router, prefix="/api")
    return TestClient(app)


def test_list_demo_cases(client):
    resp = client.get("/api/erp/cases")
    assert resp.status_code == 200
    data = resp.json()
    assert "cases" in data
    assert isinstance(data["cases"], list)


def test_load_demo_case_uk_subsidiary(client):
    resp = client.get("/api/erp/cases/case-a-uk-subsidiary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_profile"] == "demo"
    assert len(data["sales"]) >= 1


def test_load_demo_case_not_found(client):
    resp = client.get("/api/erp/cases/nonexistent")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


def test_import_csv_multipart(client):
    csv_content = (
        b"txn_date,txn_type,counterparty,net,vat,gross,vat_rate,tax_code\n"
        b"2026-01-15,sale,ACME,1000,200,1200,0.20,T1\n"
    )
    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    resp = client.post("/api/erp/import", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["source_profile"] == "generic"
    assert len(data["sales"]) == 1
