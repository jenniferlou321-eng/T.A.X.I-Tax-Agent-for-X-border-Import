import re

import pytest
from datetime import date
from decimal import Decimal

pytestmark = pytest.mark.asyncio

# pytest-httpx matches URL + query string by default, so we use regex
# patterns that match the path and ignore the ?filters=...&fields=... query.
SALES_URL = re.compile(r"^http://erp\.test:8000/api/resource/Sales%20Invoice(\?|$)")
PURCHASE_URL = re.compile(r"^http://erp\.test:8000/api/resource/Purchase%20Invoice(\?|$)")


async def test_pull_single_sales_invoice(httpx_mock):
    """Mock ERPNext GET /api/resource/Sales%20Invoice → 1 张发票 → 1 个 HubInvoice(sale)。"""
    from backend.erp.erpnext_pull import pull_invoices

    httpx_mock.add_response(
        method="GET",
        url=SALES_URL,
        json={"data": [{
            "name": "SINV-2026-0142",
            "posting_date": "2026-03-15",
            "customer_name": "ACME Ltd",
            "net_total": 1000.0,
            "total_taxes_and_charges": 200.0,
            "grand_total": 1200.0,
            "docstatus": 1,
        }]},
    )
    invs = await pull_invoices(
        base_url="http://erp.test:8000",
        api_key="k", api_secret="s",
        period_start=date(2026, 1, 1), period_end=date(2026, 3, 31),
    )
    assert len(invs) == 1
    assert invs[0].id == "SINV-2026-0142"
    assert invs[0].net_amount == Decimal("1000")
    assert invs[0].source == "erpnext_pull"
    assert invs[0].cancelled is False


async def test_pull_purchase_invoice(httpx_mock):
    """Mock GET Purchase Invoice → HubInvoice 不带 'S' 前缀。"""
    from backend.erp.erpnext_pull import pull_invoices

    httpx_mock.add_response(
        method="GET",
        url=PURCHASE_URL,
        json={"data": [{
            "name": "PINV-2026-0089",
            "posting_date": "2026-03-20",
            "supplier_name": "Office Co",
            "net_total": 450.0,
            "total_taxes_and_charges": 90.0,
            "grand_total": 540.0,
            "docstatus": 1,
        }]},
    )
    invs = await pull_invoices(
        base_url="http://erp.test:8000",
        api_key="k", api_secret="s",
        period_start=date(2026, 1, 1), period_end=date(2026, 3, 31),
        doctype="Purchase Invoice",
    )
    assert len(invs) == 1
    assert invs[0].id == "PINV-2026-0089"
    assert invs[0].counterparty == "Office Co"


async def test_pull_cancel_marks_cancelled(httpx_mock):
    """docstatus=2 → cancelled=True。"""
    from backend.erp.erpnext_pull import pull_invoices

    httpx_mock.add_response(
        method="GET",
        url=SALES_URL,
        json={"data": [{
            "name": "SINV-2026-0142",
            "posting_date": "2026-03-15",
            "customer_name": "ACME",
            "net_total": 1000.0,
            "total_taxes_and_charges": 200.0,
            "grand_total": 1200.0,
            "docstatus": 2,
        }]},
    )
    invs = await pull_invoices(
        base_url="http://erp.test:8000",
        api_key="k", api_secret="s",
        period_start=date(2026, 1, 1), period_end=date(2026, 3, 31),
    )
    assert invs[0].cancelled is True


async def test_pull_credit_note_marks_amend(httpx_mock):
    """is_return=1 + return_against → is_amend=True + parent 指向原发票。"""
    from backend.erp.erpnext_pull import pull_invoices

    httpx_mock.add_response(
        method="GET",
        url=SALES_URL,
        json={"data": [{
            "name": "CN-2026-0001",
            "posting_date": "2026-03-20",
            "customer_name": "ACME",
            "net_total": -1000.0,
            "total_taxes_and_charges": -200.0,
            "grand_total": -1200.0,
            "docstatus": 1,
            "is_return": 1,
            "return_against": "SINV-2026-0142",
        }]},
    )
    invs = await pull_invoices(
        base_url="http://erp.test:8000",
        api_key="k", api_secret="s",
        period_start=date(2026, 1, 1), period_end=date(2026, 3, 31),
    )
    assert invs[0].is_amend is True
    assert invs[0].parent == "SINV-2026-0142"
    assert invs[0].net_amount == Decimal("-1000")


async def test_pull_period_filter(httpx_mock):
    """ERPNext 自身按 posting_date 过滤;验证 filter payload 正确发出。"""
    from backend.erp.erpnext_pull import pull_invoices

    httpx_mock.add_response(
        method="GET",
        url=SALES_URL,
        json={"data": []},
    )
    await pull_invoices(
        base_url="http://erp.test:8000",
        api_key="k", api_secret="s",
        period_start=date(2026, 1, 1), period_end=date(2026, 3, 31),
    )
    request = httpx_mock.get_request()
    assert "2026-01-01" in str(request.url)
    assert "2026-03-31" in str(request.url)


async def test_pull_401_raises(httpx_mock):
    """ERPNext 401 → 抛 ErpNextPullError,调用方可捕获。"""
    from backend.erp.erpnext_pull import pull_invoices, ErpNextPullError

    httpx_mock.add_response(
        method="GET",
        url=SALES_URL,
        status_code=401, json={"error": "unauthorized"},
    )
    with pytest.raises(ErpNextPullError) as exc_info:
        await pull_invoices(
            base_url="http://erp.test:8000",
            api_key="bad", api_secret="bad",
            period_start=date(2026, 1, 1), period_end=date(2026, 3, 31),
        )
    assert exc_info.value.status_code == 401
