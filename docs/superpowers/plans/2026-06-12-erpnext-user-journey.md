# T.A.X.I. ERPNext User Journey v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an accountant user manually Pull ERPNext invoice data (or upload CSV) into T.A.X.I., preview it, then go down the Agent-chat or manual 9-Box path to file UK VAT — with period-isolated store, Cancel + Credit-Note amend handling, and ERPNext-side Web Form link.

**Architecture:** Add a unified `ImportHubStore` (in-memory, period-keyed) on the backend; add a REST `POST /api/erp/erpnext/pull` endpoint that calls ERPNext REST API; add an ERPNext `cancel`/`is_return` field pathway; cancel-filter in `compute_taxi_nine_box`; new front-end `ImportHubPage` + `ImportPreviewPage` with a Period selector; ERPNext Web Form for back-link; existing push path stays in code but is feature-flagged off.

**Tech Stack:** Python 3.11 + FastAPI + Pydantic + httpx + pytest-httpx / React 19 + TypeScript + Vite + Zustand / Frappe v15 + REST API

**Spec:** `/root/TAXI/docs/superpowers/specs/2026-06-12-erpnext-user-journey-design.md`

---

## File Structure

### New Python files
| File | Responsibility |
|---|---|
| `backend/erp/erpnext_pull.py` | `pull_invoices(url, key, secret, period_start, period_end, since=None)` → list[HubInvoice] |
| `backend/services/imported_data_buffer.py` | `ImportHubStore` (period-keyed in-memory store with dedup_by(docname)) |
| `tests/erp/test_erpnext_pull.py` | 6 tests: pull sale, pull purchase, cancel, amend, period filter, 401 |
| `tests/erp/test_imported_data_buffer.py` | 5 tests: add, dedup, cancel-update, period-clear, count |

### Modified Python files
| File | Change |
|---|---|
| `backend/models/erp_models.py` | + `HubInvoice` Pydantic model + `cancelled` / `is_amend` / `parent` / `source` / `pulled_at` fields |
| `backend/erp/reconcile.py` | `compute_taxi_nine_box` 加 `filter_cancelled=True` 参数 |
| `backend/erp/profiles.py` | + `ERPNextExportProfile` detect & transform |
| `backend/erp_router.py` | + `POST /erpnext/pull` + `GET /erpnext/credentials` (check, no secrets) |

### New Frontend files
| File | Responsibility |
|---|---|
| `frontend/src/pages/ImportHubPage.tsx` | `/import` route: Period selector + 2 cards |
| `frontend/src/pages/ImportPreviewPage.tsx` | `/import/preview` route: read-only table + 2 CTAs |
| `frontend/src/components/ImportHubCardErpNext.tsx` | Card A: ERPNext Pull with credentials modal |
| `frontend/src/components/ImportHubCardCsv.tsx` | Card B: CSV upload (re-uses CsvImportWizard) |
| `frontend/src/components/ImportPreviewTable.tsx` | Read-only table with cancelled / amend styling |
| `frontend/src/components/ErpCredentialsModal.tsx` | Modal for URL / API Key / API Secret input |

### Modified Frontend files
| File | Change |
|---|---|
| `frontend/src/App.tsx` | + `/import` + `/import/preview` routes |
| `frontend/src/api/client.ts` | + `api.erp.erpnextPull()` + `api.erp.erpnextStatus()` (refactor) |
| `frontend/src/stores/demoStore.ts` | + `erpnextCredentials` (url/key/secret) + `hubDataByPeriod: Record<period, {sales, purchases, lastPulledAt}>` |
| `frontend/src/pages/DashboardPage.tsx` | + `[⬇ 导入外部数据]` button (top of case grid) |

### Frappe-side changes
| File | Change |
|---|---|
| `frappe-bench/apps/tax_integration/tax_integration/hooks.py` | Comment-out `doc_events` for on_submit push (feature-flag default off) |
| `frappe-bench/apps/tax_integration/tax_integration/integration/web_form/taxi_link/taxi_link.json` | New Web Form: single `url` field linking to `http://localhost:9000/import` |

---

## Task 1: Add `HubInvoice` model with cancel/amend fields

**Files:**
- Modify: `backend/models/erp_models.py:55-70` (after `ImportResult`)
- Test: `tests/erp/test_hub_invoice_model.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/erp/test_hub_invoice_model.py
from datetime import date
from decimal import Decimal
from backend.models.erp_models import HubInvoice


def test_hub_invoice_required_fields():
    """HubInvoice needs id/date/amounts/vat_rate, optional cancel/amend."""
    inv = HubInvoice(
        id="SINV-2026-0142",
        txn_date=date(2026, 3, 15),
        counterparty="ACME Ltd",
        net_amount=Decimal("1000"),
        vat_amount=Decimal("200"),
        gross_amount=Decimal("1200"),
        vat_rate=Decimal("0.20"),
        tax_code="T1",
    )
    assert inv.cancelled is False
    assert inv.is_amend is False
    assert inv.parent is None
    assert inv.source == "erpnext_pull"  # default


def test_hub_invoice_cancel_and_amend():
    inv = HubInvoice(
        id="CN-2026-0001",
        txn_date=date(2026, 3, 20),
        counterparty="ACME Ltd",
        net_amount=Decimal("-1000"),
        vat_amount=Decimal("-200"),
        gross_amount=Decimal("-1200"),
        vat_rate=Decimal("0.20"),
        tax_code="T1",
        cancelled=False,
        is_amend=True,
        parent="SINV-2026-0142",
        source="erpnext_pull",
    )
    assert inv.is_amend is True
    assert inv.parent == "SINV-2026-0142"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/erp/test_hub_invoice_model.py -v`
Expected: FAIL with `ImportError: cannot import name 'HubInvoice'`

- [ ] **Step 3: Add `HubInvoice` model to `backend/models/erp_models.py`**

Append after the `ImportResult` class (around line 70):

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/erp/test_hub_invoice_model.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/models/erp_models.py tests/erp/test_hub_invoice_model.py
git commit -m "feat(model): HubInvoice with cancel/amend/parent fields"
```

---

## Task 2: Add `ImportHubStore` in-memory store

**Files:**
- Create: `backend/services/imported_data_buffer.py`
- Test: `tests/erp/test_imported_data_buffer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/erp/test_imported_data_buffer.py
from datetime import date
from decimal import Decimal
from backend.models.erp_models import HubInvoice
from backend.services.imported_data_buffer import ImportHubStore


def _make_invoice(docname: str, **overrides) -> HubInvoice:
    base = dict(
        id=docname,
        txn_date=date(2026, 3, 15),
        counterparty="ACME",
        net_amount=Decimal("1000"),
        vat_amount=Decimal("200"),
        gross_amount=Decimal("1200"),
        vat_rate=Decimal("0.20"),
        tax_code="T1",
    )
    base.update(overrides)
    return HubInvoice(**base)


def test_store_add_and_dedup():
    """同一 (period, id) 后写覆盖前(cancelled 字段可改)。"""
    ImportHubStore.clear("Q1_2026")
    ImportHubStore.add("Q1_2026", [_make_invoice("SINV-001")])
    ImportHubStore.add("Q1_2026", [_make_invoice("SINV-001", counterparty="NEW NAME")])
    listed = ImportHubStore.list("Q1_2026")
    assert len(listed) == 1
    assert listed[0].counterparty == "NEW NAME"


def test_store_cancel_update_via_re_add():
    """Cancel 事件:同 id 再 add,只改 cancelled 字段。"""
    ImportHubStore.clear("Q1_2026")
    ImportHubStore.add("Q1_2026", [_make_invoice("SINV-001")])
    ImportHubStore.add("Q1_2026", [_make_invoice("SINV-001", cancelled=True)])
    assert ImportHubStore.list("Q1_2026")[0].cancelled is True


def test_store_period_isolation():
    """不同 period 完全隔离。"""
    ImportHubStore.clear()
    ImportHubStore.add("Q1_2026", [_make_invoice("A")])
    ImportHubStore.add("Q2_2026", [_make_invoice("A")])
    assert len(ImportHubStore.list("Q1_2026")) == 1
    assert len(ImportHubStore.list("Q2_2026")) == 1
    ImportHubStore.clear()


def test_store_count_summary():
    """count 返 sales/purchases/cancelled/amends 字典。"""
    ImportHubStore.clear("Q1_2026")
    ImportHubStore.add("Q1_2026", [
        _make_invoice("S1"),
        _make_invoice("P1", id="P1", tax_code="T2"),
        _make_invoice("S2", cancelled=True),
        _make_invoice("CN1", is_amend=True, parent="S1"),
    ])
    summary = ImportHubStore.count("Q1_2026")
    assert summary["sales"] == 1       # 只算 S1,S2 已 cancel
    assert summary["purchases"] == 1   # P1
    assert summary["cancelled"] == 1   # S2
    assert summary["amends"] == 1      # CN1
    assert summary["total"] == 4
    ImportHubStore.clear()


def test_store_clear_specific_period():
    """clear(period) 只清一个;clear() 清全部。"""
    ImportHubStore.clear()
    ImportHubStore.add("Q1_2026", [_make_invoice("A")])
    ImportHubStore.add("Q2_2026", [_make_invoice("B")])
    ImportHubStore.clear("Q1_2026")
    assert ImportHubStore.list("Q1_2026") == []
    assert len(ImportHubStore.list("Q2_2026")) == 1
    ImportHubStore.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/erp/test_imported_data_buffer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services.imported_data_buffer'`

- [ ] **Step 3: Create `backend/services/imported_data_buffer.py`**

```python
"""ImportHubStore — 按 period 隔离的 in-memory store。

去重规则:同一 (period, id) 后写覆盖前;Cancel 事件 = 同 id 再 add 并标 cancelled。
"""
from __future__ import annotations

from typing import Dict, List, Optional

from ..models.erp_models import HubInvoice


class _Store:
    """Module-level singleton (process-local)."""

    _data: Dict[str, Dict[str, HubInvoice]] = {}

    @classmethod
    def add(cls, period: str, invoices: List[HubInvoice]) -> None:
        bucket = cls._data.setdefault(period, {})
        for inv in invoices:
            bucket[inv.id] = inv  # dedup by (period, id) — 后写覆盖

    @classmethod
    def list(cls, period: str) -> List[HubInvoice]:
        return list(cls._data.get(period, {}).values())

    @classmethod
    def count(cls, period: str) -> dict:
        items = cls.list(period)
        return {
            "sales": sum(1 for x in items if x.id.startswith("S") and not x.cancelled and not x.is_amend),
            "purchases": sum(1 for x in items if x.id.startswith("P") and not x.cancelled and not x.is_amend),
            "cancelled": sum(1 for x in items if x.cancelled),
            "amends": sum(1 for x in items if x.is_amend),
            "total": len(items),
        }

    @classmethod
    def clear(cls, period: Optional[str] = None) -> None:
        if period is None:
            cls._data.clear()
        else:
            cls._data.pop(period, None)


# Public API (module-level convenience)
ImportHubStore = _Store  # 暴露类, 调用方写 ImportHubStore.add(...) 即可
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/erp/test_imported_data_buffer.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/services/imported_data_buffer.py tests/erp/test_imported_data_buffer.py
git commit -m "feat(store): ImportHubStore period-keyed dedup-by-docname"
```

---

## Task 3: Add `pull_invoices` ERPNext REST client

**Files:**
- Create: `backend/erp/erpnext_pull.py`
- Test: `tests/erp/test_erpnext_pull.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/erp/test_erpnext_pull.py
import pytest
from datetime import date
from decimal import Decimal

pytestmark = pytest.mark.asyncio


async def test_pull_single_sales_invoice(httpx_mock):
    """Mock ERPNext GET /api/resource/Sales%20Invoice → 1 张发票 → 1 个 HubInvoice(sale)。"""
    from backend.erp.erpnext_pull import pull_invoices

    httpx_mock.add_response(
        method="GET",
        url="http://erp.test:8000/api/resource/Sales%20Invoice",
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
        url="http://erp.test:8000/api/resource/Purchase%20Invoice",
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
        url="http://erp.test:8000/api/resource/Sales%20Invoice",
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
        url="http://erp.test:8000/api/resource/Sales%20Invoice",
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

    # 不管 ERPNext 返什么,我们只验证发出去的 URL 包含 period 范围
    httpx_mock.add_response(
        method="GET",
        url="http://erp.test:8000/api/resource/Sales%20Invoice",
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
        url="http://erp.test:8000/api/resource/Sales%20Invoice",
        status_code=401, json={"error": "unauthorized"},
    )
    with pytest.raises(ErpNextPullError) as exc_info:
        await pull_invoices(
            base_url="http://erp.test:8000",
            api_key="bad", api_secret="bad",
            period_start=date(2026, 1, 1), period_end=date(2026, 3, 31),
        )
    assert exc_info.value.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/erp/test_erpnext_pull.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create `backend/erp/erpnext_pull.py`**

```python
"""ERPNext REST API 客户端 — 手动 Pull 拉本期内已 Submit 的发票。

调用方:backend/erp_router.py::POST /erpnext/pull
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List, Optional

import httpx

from ..models.erp_models import HubInvoice


class ErpNextPullError(Exception):
    """ERPNext Pull 失败(网络/凭证/解析)。"""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


async def pull_invoices(
    base_url: str, api_key: str, api_secret: str,
    period_start: date, period_end: date,
    doctype: str = "Sales Invoice",
    since: Optional[date] = None,
) -> List[HubInvoice]:
    """拉 ERPNext 列表 + 转换 → list[HubInvoice]。

    Args:
        base_url: e.g. "http://my.local:8000"
        api_key/api_secret: ERPNext API 凭证
        period_start/period_end: posting_date 范围
        doctype: "Sales Invoice" 或 "Purchase Invoice"
        since: modified >= since(增量);None = 全量
    """
    headers = {
        "Authorization": f"token {api_key}:{api_secret}",
    }
    # ERPNext filter syntax: [["posting_date", "Between", [start, end]]]
    filters = [["posting_date", "Between", [period_start.isoformat(), period_end.isoformat()]]]
    if since is not None:
        filters.append(["modified", ">=", since.isoformat()])
    # docstatus ∈ {1, 2} = submitted + cancelled
    filters.append(["docstatus", "in", [1, 2]])

    params = {
        "filters": str(filters).replace("'", '"'),  # ERPNext 期望 JSON 字符串
        "limit_page_length": 500,
        "fields": json_fields(doctype),
    }

    url = f"{base_url.rstrip('/')}/api/resource/{doctype.replace(' ', '%20')}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.get(url, headers=headers, params=params)
        except httpx.RequestError as e:
            raise ErpNextPullError(f"network error: {e}") from e

    if resp.status_code in (401, 403):
        raise ErpNextPullError(
            f"ERPNext returned {resp.status_code}",
            status_code=resp.status_code,
        )
    if resp.status_code != 200:
        raise ErpNextPullError(
            f"ERPNext returned {resp.status_code}: {resp.text[:200]}",
            status_code=resp.status_code,
        )

    payload = resp.json()
    docs = payload.get("data", [])
    return [_to_hub_invoice(d, doctype) for d in docs]


def _to_hub_invoice(doc: dict, doctype: str) -> HubInvoice:
    counterparty = doc.get("customer_name") or doc.get("supplier_name") or ""
    net = Decimal(str(doc.get("net_total", 0)))
    vat = Decimal(str(doc.get("total_taxes_and_charges", 0)))
    vat_rate = (vat / net).quantize(Decimal("0.0001")) if net != 0 else Decimal("0")
    is_amend = bool(doc.get("is_return", 0))
    parent = doc.get("return_against") if is_amend else None
    return HubInvoice(
        id=doc.get("name", ""),
        txn_date=date.fromisoformat(doc["posting_date"]),
        counterparty=counterparty,
        net_amount=net,
        vat_amount=vat,
        gross_amount=Decimal(str(doc.get("grand_total", 0))),
        vat_rate=vat_rate,
        tax_code="T1",
        cancelled=(doc.get("docstatus") == 2),
        is_amend=is_amend,
        parent=parent,
        source="erpnext_pull",
    )


def json_fields(doctype: str) -> str:
    common = '["name", "posting_date", "net_total", "total_taxes_and_charges", "grand_total", "docstatus", "is_return", "return_against"]'
    if doctype == "Sales Invoice":
        return common.replace("]", ', "customer_name"]')
    return common.replace("]", ', "supplier_name"]')
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/erp/test_erpnext_pull.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/erp/erpnext_pull.py tests/erp/test_erpnext_pull.py
git commit -m "feat(erp): ERPNext REST pull client with cancel/amend detection"
```

---

## Task 4: Add `POST /api/erp/erpnext/pull` endpoint

**Files:**
- Modify: `backend/erp_router.py` (append after `erpnext_status`)
- Test: `tests/erp/test_pull_endpoint.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/erp/test_pull_endpoint.py
import pytest
from datetime import date
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.imported_data_buffer import ImportHubStore


client = TestClient(app)


def test_pull_endpoint_writes_to_hub_store(httpx_mock, monkeypatch):
    """POST /api/erp/erpnext/pull → 拉发票 → 写 ImportHubStore(period)。"""
    from backend.erp import erpnext_pull

    async def fake_pull(*args, **kwargs):
        from backend.models.erp_models import HubInvoice
        from decimal import Decimal
        return [HubInvoice(
            id="SINV-001", txn_date=date(2026, 3, 15),
            counterparty="ACME", net_amount=Decimal("1000"),
            vat_amount=Decimal("200"), gross_amount=Decimal("1200"),
            vat_rate=Decimal("0.20"), tax_code="T1", source="erpnext_pull",
        )]

    monkeypatch.setattr(erpnext_pull, "pull_invoices", fake_pull)

    resp = client.post("/api/erp/erpnext/pull", json={
        "url": "http://erp.test:8000",
        "api_key": "k", "api_secret": "s",
        "period": "Q1_2026",
        "period_start": "2026-01-01", "period_end": "2026-03-31",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["sales"] == 1
    assert body["purchases"] == 0
    assert body["count"]["total"] == 1

    # 验证 store
    listed = ImportHubStore.list("Q1_2026")
    assert len(listed) == 1
    assert listed[0].id == "SINV-001"
    ImportHubStore.clear("Q1_2026")


def test_pull_endpoint_401_returns_500_with_status(httpx_mock, monkeypatch):
    """ERPNext 401 → 500 + status_code 在 detail 中。"""
    from backend.erp import erpnext_pull

    async def fake_pull_401(*args, **kwargs):
        raise erpnext_pull.ErpNextPullError("401 unauthorized", status_code=401)

    monkeypatch.setattr(erpnext_pull, "pull_invoices", fake_pull_401)

    resp = client.post("/api/erp/erpnext/pull", json={
        "url": "http://erp.test:8000",
        "api_key": "bad", "api_secret": "bad",
        "period": "Q1_2026",
        "period_start": "2026-01-01", "period_end": "2026-03-31",
    })
    assert resp.status_code == 500  # 或自定义,见实现
    body = resp.json()
    assert body["detail"]["status_code"] == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/erp/test_pull_endpoint.py -v`
Expected: FAIL with `404 Not Found` (endpoint doesn't exist)

- [ ] **Step 3: Add endpoint to `backend/erp_router.py`**

Append after the `erpnext_status` function (line ~153):

```python
from .erp.erpnext_pull import ErpNextPullError, pull_invoices
from .services.imported_data_buffer import ImportHubStore


@router.post("/erpnext/pull")
async def erpnext_pull(payload: dict):
    """手动 Pull:从 T.A.X.I. 主动拉 ERPNext 数据。

    Body: {
      "url": "http://my.local:8000",
      "api_key": "...", "api_secret": "...",
      "period": "Q1_2026",
      "period_start": "2026-01-01", "period_end": "2026-03-31",
      "since": "2026-04-01" (optional, 增量)
    }

    拉 Sales Invoice + Purchase Invoice 两个 doctype,合并写 store。
    """
    from datetime import date
    period = payload.get("period", "")
    if not period:
        raise HTTPException(status_code=422, detail="period required")
    period_start = date.fromisoformat(payload["period_start"])
    period_end = date.fromisoformat(payload["period_end"])
    since = date.fromisoformat(payload["since"]) if payload.get("since") else None

    base_url = payload.get("url", "").rstrip("/")
    api_key = payload.get("api_key", "")
    api_secret = payload.get("api_secret", "")

    all_invoices = []
    for doctype in ("Sales Invoice", "Purchase Invoice"):
        try:
            invs = await pull_invoices(
                base_url=base_url, api_key=api_key, api_secret=api_secret,
                period_start=period_start, period_end=period_end,
                doctype=doctype, since=since,
            )
            all_invoices.extend(invs)
        except ErpNextPullError as e:
            raise HTTPException(
                status_code=500,
                detail={"message": str(e), "status_code": e.status_code, "doctype": doctype},
            ) from e

    ImportHubStore.add(period, all_invoices)
    summary = ImportHubStore.count(period)
    return {
        "status": "ok",
        "period": period,
        "sales": summary["sales"],
        "purchases": summary["purchases"],
        "cancelled": summary["cancelled"],
        "amends": summary["amends"],
        "count": summary,
        "doctype_breakdown": {
            "Sales Invoice": sum(1 for i in all_invoices if i.id.startswith("S")),
            "Purchase Invoice": sum(1 for i in all_invoices if i.id.startswith("P")),
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/erp/test_pull_endpoint.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/erp_router.py tests/erp/test_pull_endpoint.py
git commit -m "feat(router): POST /api/erp/erpnext/pull writes to ImportHubStore"
```

---

## Task 5: Filter cancelled in `compute_taxi_nine_box`

**Files:**
- Modify: `backend/erp/reconcile.py:32-37`
- Test: `tests/erp/test_reconcile.py` (add 1 new test)

- [ ] **Step 1: Write the failing test**

```python
# tests/erp/test_reconcile.py — append this test
from decimal import Decimal
from backend.erp.reconcile import compute_taxi_nine_box
from backend.models.erp_models import SalesTransaction, PurchaseTransaction


def test_nine_box_excludes_cancelled():
    """cancelled=True 的发票不进 9-Box 计算。"""
    s1 = SalesTransaction(
        id="S1", txn_date=__import__("datetime").date(2026, 3, 15),
        counterparty="A", net_amount=Decimal("1000"), vat_amount=Decimal("200"),
        gross_amount=Decimal("1200"), vat_rate=Decimal("0.20"), tax_code="T1",
    )
    s2 = SalesTransaction(
        id="S2", txn_date=__import__("datetime").date(2026, 3, 16),
        counterparty="B", net_amount=Decimal("500"), vat_amount=Decimal("100"),
        gross_amount=Decimal("600"), vat_rate=Decimal("0.20"), tax_code="T1",
    )
    s2.cancelled = True  # 模拟 Cancel 后的发票

    box = compute_taxi_nine_box(sales=[s1, s2], purchases=[])
    # 只 S1 进 9-Box,S2 cancel 不算
    assert box.box1_vat_due_sales == Decimal("200")
    assert box.box6_total_sales_ex_vat == 1000
```

Wait — `SalesTransaction` is the Pydantic model and doesn't have `cancelled` field. We need to filter at the `HubInvoice` level, not at the `compute_taxi_nine_box` level. Let me rethink.

Actually, the cleaner design is: `compute_taxi_nine_box` keeps its current signature (works on `SalesTransaction` / `PurchaseTransaction`), and the **caller** (the orchestrator / preview / agent) is responsible for filtering cancelled HubInvoices BEFORE converting them to Sales/PurchaseTransaction.

So this task should be: add a helper `hub_invoices_to_sales_purchases(hub_invoices, *, filter_cancelled=True) -> (sales, purchases)` that does the filtering and conversion.

**Replace Step 1-3 with:**

- [ ] **Step 1: Write the failing test**

```python
# tests/erp/test_hub_invoice_to_txn.py
from datetime import date
from decimal import Decimal
from backend.models.erp_models import HubInvoice
from backend.erp.erpnext_pull import hub_invoices_to_txn  # 或放 reconcile.py


def test_hub_to_txn_filters_cancelled():
    invs = [
        HubInvoice(id="S1", txn_date=date(2026, 3, 15), counterparty="A",
                   net_amount=Decimal("1000"), vat_amount=Decimal("200"),
                   gross_amount=Decimal("1200"), vat_rate=Decimal("0.20"), tax_code="T1"),
        HubInvoice(id="S2", txn_date=date(2026, 3, 16), counterparty="B",
                   net_amount=Decimal("500"), vat_amount=Decimal("100"),
                   gross_amount=Decimal("600"), vat_rate=Decimal("0.20"), tax_code="T1",
                   cancelled=True),  # 应被过滤
    ]
    sales, purchases = hub_invoices_to_txn(invs, filter_cancelled=True)
    assert len(sales) == 1
    assert sales[0].id == "S1"


def test_hub_to_txn_split_sale_vs_purchase():
    invs = [
        HubInvoice(id="S1", txn_date=date(2026, 3, 15), counterparty="A",
                   net_amount=Decimal("1000"), vat_amount=Decimal("200"),
                   gross_amount=Decimal("1200"), vat_rate=Decimal("0.20"), tax_code="T1"),
        HubInvoice(id="P1", txn_date=date(2026, 3, 16), counterparty="B",
                   net_amount=Decimal("500"), vat_amount=Decimal("100"),
                   gross_amount=Decimal("600"), vat_rate=Decimal("0.20"), tax_code="T2"),
    ]
    sales, purchases = hub_invoices_to_txn(invs)
    assert len(sales) == 1 and sales[0].id == "S1"
    assert len(purchases) == 1 and purchases[0].id == "P1"


def test_hub_to_txn_keeps_amend_negative_amounts():
    """Credit Note (is_amend, net<0) 应该保留,9-Box 自然抵减。"""
    invs = [
        HubInvoice(id="S1", txn_date=date(2026, 3, 15), counterparty="A",
                   net_amount=Decimal("1000"), vat_amount=Decimal("200"),
                   gross_amount=Decimal("1200"), vat_rate=Decimal("0.20"), tax_code="T1"),
        HubInvoice(id="CN1", txn_date=date(2026, 3, 20), counterparty="A",
                   net_amount=Decimal("-1000"), vat_amount=Decimal("-200"),
                   gross_amount=Decimal("-1200"), vat_rate=Decimal("0.20"), tax_code="T1",
                   is_amend=True, parent="S1"),
    ]
    sales, _ = hub_invoices_to_txn(invs)
    # CN1 应该被识别为 sales(因为 id 以 S 开头,doctype=Sales Invoice)
    assert len(sales) == 2
    assert sum(s.net_amount for s in sales) == Decimal("0")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/erp/test_hub_invoice_to_txn.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Add `hub_invoices_to_txn` to `backend/erp/erpnext_pull.py` (or a new helper file)**

Add at the end of `backend/erp/erpnext_pull.py`:

```python
from ..models.erp_models import SalesTransaction, PurchaseTransaction


def hub_invoices_to_txn(
    invoices: List[HubInvoice], *, filter_cancelled: bool = True,
) -> tuple[List[SalesTransaction], List[PurchaseTransaction]]:
    """HubInvoice list → (sales, purchases)。

    Cancelled 的发票默认过滤掉。Amend 保留(同 id 前缀归类,负数自然抵减 9-Box)。
    """
    sales: List[SalesTransaction] = []
    purchases: List[PurchaseTransaction] = []
    for inv in invoices:
        if filter_cancelled and inv.cancelled:
            continue
        common = dict(
            id=inv.id, txn_date=inv.txn_date, counterparty=inv.counterparty,
            net_amount=inv.net_amount, vat_amount=inv.vat_amount,
            gross_amount=inv.gross_amount, vat_rate=inv.vat_rate, tax_code=inv.tax_code,
        )
        # 简化:id 以 S 开头 → sales,以 P 开头 → purchases(其他 fallback)
        if inv.id.startswith("S"):
            sales.append(SalesTransaction(**common))
        elif inv.id.startswith("P"):
            purchases.append(PurchaseTransaction(**common))
        else:
            # 兜底:看不出就放 sales
            sales.append(SalesTransaction(**common))
    return sales, purchases
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/erp/test_hub_invoice_to_txn.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/erp/erpnext_pull.py tests/erp/test_hub_invoice_to_txn.py
git commit -m "feat(erp): hub_invoices_to_txn with cancelled filter + amend keep"
```

---

## Task 6: Add `ERPNextExportProfile` for CSV uploads

**Files:**
- Modify: `backend/erp/profiles.py` (append at end)
- Test: `tests/erp/test_erpnext_export_profile.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/erp/test_erpnext_export_profile.py
from decimal import Decimal
from backend.erp.profiles import ERPNextExportProfile


def test_detect_erpnext_headers():
    """ERPNext 导出 header 含 'Posting Date' / 'Customer' / 'Net Total' → 命中。"""
    p = ERPNextExportProfile()
    headers = ["Name", "Posting Date", "Customer", "Net Total", "Total Taxes", "Grand Total", "Docstatus"]
    score = p.detect(headers)
    assert score >= 0.7


def test_transform_sales_row():
    """ERPNext 行 → SalesTransaction(net=1000, vat=200)。"""
    p = ERPNextExportProfile()
    txn, err = p.transform_row({
        "Name": "SINV-2026-0142",
        "Posting Date": "2026-03-15",
        "Customer": "ACME Ltd",
        "Net Total": "1000",
        "Total Taxes": "200",
        "Grand Total": "1200",
        "Docstatus": "1",
    }, row_index=1)
    assert err is None
    assert txn.id == "SINV-2026-0142"
    assert txn.net_amount == Decimal("1000")
    assert txn.vat_amount == Decimal("200")
    # 应该是 SalesTransaction
    from backend.models.erp_models import SalesTransaction
    assert isinstance(txn, SalesTransaction)


def test_transform_purchase_row():
    p = ERPNextExportProfile()
    txn, err = p.transform_row({
        "Name": "PINV-2026-0089",
        "Posting Date": "2026-03-20",
        "Supplier": "Office Co",
        "Net Total": "450",
        "Total Taxes": "90",
        "Grand Total": "540",
        "Docstatus": "1",
    }, row_index=2)
    assert err is None
    from backend.models.erp_models import PurchaseTransaction
    assert isinstance(txn, PurchaseTransaction)
    assert txn.counterparty == "Office Co"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/erp/test_erpnext_export_profile.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Add `ERPNextExportProfile` to `backend/erp/profiles.py`**

```python
class ERPNextExportProfile:
    """ERPNext 导出 CSV(Report → Sales/Purchase Invoice)的 Profile。"""

    name = "erpnext_export"

    ERPNEXT_HEADERS = [
        "name", "posting date", "customer", "supplier",
        "net total", "total taxes", "grand total", "docstatus",
    ]

    def detect(self, headers: List[str]) -> float:
        headers_lower = [h.strip().lower() for h in headers]
        matched = sum(1 for h in self.ERPNEXT_HEADERS if h in headers_lower)
        return matched / len(self.ERPNEXT_HEADERS)

    def transform_row(
        self, row: Dict[str, str], row_index: int,
    ) -> Tuple[SalesTransaction | PurchaseTransaction | None, str | None]:
        try:
            name = row["Name"].strip()
            net = Decimal(str(row["Net Total"]).strip())
            vat = Decimal(str(row["Total Taxes"]).strip())
            gross = Decimal(str(row["Grand Total"]).strip())
            vat_rate = (vat / net).quantize(Decimal("0.0001")) if net != 0 else Decimal("0")
            common = {
                "id": name,
                "txn_date": date.fromisoformat(row["Posting Date"].strip()),
                "counterparty": (row.get("Customer") or row.get("Supplier") or "").strip(),
                "net_amount": net,
                "vat_amount": vat,
                "gross_amount": gross,
                "vat_rate": vat_rate,
                "tax_code": "T1",
            }
            if name.startswith("S"):
                return SalesTransaction(**common), None
            elif name.startswith("P"):
                return PurchaseTransaction(**common), None
            return None, f"unknown prefix: {name!r}"
        except (ValueError, KeyError) as e:
            return None, f"parse error: {e}"


# 注册到 _PROFILES(在文件顶部 _PROFILES dict 添加)
# _PROFILES["erpnext_export"] = ERPNextExportProfile
```

Then update the `_PROFILES` registration at the bottom of `profiles.py`:

```python
# 在 GenericProfile 后追加:
_ERPNEXT_PROFILE = ERPNextExportProfile()

# (现有的 _PROFILES = {"generic": GenericProfile()} 改为)
_PROFILES = {
    "generic": GenericProfile(),
    "erpnext_export": _ERPNEXT_PROFILE,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/erp/test_erpnext_export_profile.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/erp/profiles.py tests/erp/test_erpnext_export_profile.py
git commit -m "feat(erp): ERPNextExportProfile for CSV uploads from ERPNext UI"
```

---

## Task 7: Add `erpnextPull` to `api.erp` in `client.ts`

**Files:**
- Modify: `frontend/src/api/client.ts:140-150` (in `api.erp` block)

- [ ] **Step 1: Write the failing type check**

```bash
# 前端 type check
cd /root/TAXI/frontend && npx tsc --noEmit
# Expected: 无错误
```

(无单独前端单元测试;通过 typecheck + 后续组件测试覆盖)

- [ ] **Step 2: Add new method to `api.erp`**

In `frontend/src/api/client.ts`, replace the `erpnextStatus` entry (line ~140) with:

```typescript
erpnextStatus: () =>
      fetchApi<{
        connected: boolean;
        last_push_at: string | null;
        sales_count: number;
        purchases_count: number;
        docnames: string[];
        company?: string | null;
        source?: string | null;
      }>('/api/erp/erpnext/status'),
    erpnextPull: (body: {
      url: string;
      api_key: string;
      api_secret: string;
      period: string;
      period_start: string;
      period_end: string;
      since?: string;
    }) =>
      fetchApi<{
        status: 'ok';
        period: string;
        sales: number;
        purchases: number;
        cancelled: number;
        amends: number;
        count: { sales: number; purchases: number; cancelled: number; amends: number; total: number };
        doctype_breakdown: { 'Sales Invoice': number; 'Purchase Invoice': number };
      }>('/api/erp/erpnext/pull', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    erpnextHubSummary: (period: string) =>
      fetchApi<{
        period: string;
        sales: SalesTransaction[];
        purchases: PurchaseTransaction[];
        count: { sales: number; purchases: number; cancelled: number; amends: number; total: number };
      }>(`/api/erp/hub/summary?period=${encodeURIComponent(period)}`),
```

(Need to add `SalesTransaction` / `PurchaseTransaction` to the imports at the top of `client.ts`)

- [ ] **Step 3: Add `SalesTransaction` / `PurchaseTransaction` to imports**

At the top of `client.ts` (line ~1-8), add:

```typescript
import type {
  DataTemplate,
  FilingResult,
  CalculationResult,
  ValidationResult,
  VATObligation,
  ImportResult, ReconciliationDelta,
  SalesTransaction, PurchaseTransaction,  // ← 新增
} from '../types';
```

- [ ] **Step 4: Add `GET /api/erp/hub/summary` to backend `erp_router.py`**

Append after the pull endpoint:

```python
@router.get("/hub/summary")
def hub_summary(period: str):
    """取本 period 的 ImportHubStore 摘要(发票列表 + 计数)。"""
    from .models.erp_models import SalesTransaction, PurchaseTransaction
    items = ImportHubStore.list(period)
    sales = [
        SalesTransaction(
            id=i.id, txn_date=i.txn_date, counterparty=i.counterparty,
            net_amount=i.net_amount, vat_amount=i.vat_amount, gross_amount=i.gross_amount,
            vat_rate=i.vat_rate, tax_code=i.tax_code,
        )
        for i in items if not i.cancelled and i.id.startswith("S")
    ]
    purchases = [
        PurchaseTransaction(
            id=i.id, txn_date=i.txn_date, counterparty=i.counterparty,
            net_amount=i.net_amount, vat_amount=i.vat_amount, gross_amount=i.gross_amount,
            vat_rate=i.vat_rate, tax_code=i.tax_code,
        )
        for i in items if not i.cancelled and i.id.startswith("P")
    ]
    return {
        "period": period,
        "sales": [s.model_dump(mode="json") for s in sales],
        "purchases": [p.model_dump(mode="json") for p in purchases],
        "count": ImportHubStore.count(period),
        "raw": [i.model_dump(mode="json") for i in items],  # 含 cancelled / amend
    }
```

- [ ] **Step 5: Verify type check + restart backend + smoke test**

```bash
# typecheck
cd /root/TAXI/frontend && npx tsc --noEmit
# Expected: 无错误

# 重启 backend
pkill -f 'uvicorn backend.main' || true
sleep 1
cd /root/TAXI && nohup ./start_backend.sh > $HOME/logs/taxi.log 2>&1 &

# smoke test
sleep 5
curl http://localhost:8765/api/erp/hub/summary?period=Q1_2026
# Expected: {"period":"Q1_2026","sales":[],"purchases":[],"count":{...},"raw":[]}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.ts backend/erp_router.py
git commit -m "feat(api): erpnextPull + hubSummary endpoints; frontend client wrappers"
```

---

## Task 8: Extend `demoStore` with `erpnextCredentials` + `hubDataByPeriod`

**Files:**
- Modify: `frontend/src/stores/demoStore.ts` (interface + initial + partialize)

- [ ] **Step 1: Add type definitions and state fields**

In `demoStore.ts`, modify the `DemoState` interface (line ~42):

```typescript
interface DemoState {
  // ... existing fields ...
  erpConnectionOn: boolean;
  erpnextStatus: 'idle' | 'connected' | 'disconnected' | 'error';
  erpnextLastPushAt: string | null;
  erpnextSalesCount: number;
  erpnextPurchasesCount: number;
  erpnextDocnames: string[];

  // ── 新增:ERPNext 凭证(明文,本期 demo 限制)──
  erpnextCredentials: {
    url: string;
    apiKey: string;
    apiSecret: string;
  } | null;

  // ── 新增:按 period 隔离的 hub 数据摘要 ──
  hubDataByPeriod: Record<string, {
    salesCount: number;
    purchasesCount: number;
    cancelledCount: number;
    amendsCount: number;
    lastPulledAt: string | null;
  }>;

  // ... existing actions ...
  setErpnextCredentials: (creds: { url: string; apiKey: string; apiSecret: string } | null) => void;
  setHubDataForPeriod: (period: string, summary: {
    salesCount: number;
    purchasesCount: number;
    cancelledCount: number;
    amendsCount: number;
    lastPulledAt: string;
  }) => void;
}
```

- [ ] **Step 2: Add initial values + actions**

In the store implementation (around line ~100), add initial values:

```typescript
erpnextCredentials: null,
hubDataByPeriod: {},

setErpnextCredentials: (creds) => set({ erpnextCredentials: creds }),
setHubDataForPeriod: (period, summary) => set((state) => ({
  hubDataByPeriod: { ...state.hubDataByPeriod, [period]: summary },
})),
```

- [ ] **Step 3: Add to `partialize` for localStorage persistence**

In the `partialize` callback (line ~213), add:

```typescript
partialize: (state) => ({
  buffer: state.buffer,
  selectedPreset: state.selectedPreset,
  erpConnectionOn: state.erpConnectionOn,
  erpnextCredentials: state.erpnextCredentials,  // ← 新增
  hubDataByPeriod: state.hubDataByPeriod,        // ← 新增
}),
```

- [ ] **Step 4: Update `clearAll` to clear new fields**

Modify the `clearAll` action (line ~108) to also clear the new fields:

```typescript
clearAll: () => {
  set({
    selectedPreset: null,
    erpConnectionOn: false,
    buffer: null,
    erpnextStatus: 'idle',
    erpnextLastPushAt: null,
    erpnextSalesCount: 0,
    erpnextPurchasesCount: 0,
    erpnextDocnames: [],
    erpnextCredentials: null,  // ← 新增
    hubDataByPeriod: {},       // ← 新增
  });
  // ... localStorage cleanup unchanged ...
},
```

- [ ] **Step 5: Type check**

```bash
cd /root/TAXI/frontend && npx tsc --noEmit
# Expected: 无错误
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/stores/demoStore.ts
git commit -m "feat(store): erpnextCredentials + hubDataByPeriod for Import Hub"
```

---

## Task 9: Create `ImportHubCardErpNext` component

**Files:**
- Create: `frontend/src/components/ImportHubCardErpNext.tsx`
- Create: `frontend/src/components/ErpCredentialsModal.tsx`

- [ ] **Step 1: Create `ErpCredentialsModal.tsx`**

```typescript
// frontend/src/components/ErpCredentialsModal.tsx
import { useState } from 'react';

interface Props {
  initial?: { url: string; apiKey: string; apiSecret: string };
  onSave: (creds: { url: string; apiKey: string; apiSecret: string }) => void;
  onClose: () => void;
}

export default function ErpCredentialsModal({ initial, onSave, onClose }: Props) {
  const [url, setUrl] = useState(initial?.url ?? 'http://my.local:8000');
  const [apiKey, setApiKey] = useState(initial?.apiKey ?? '');
  const [apiSecret, setApiSecret] = useState(initial?.apiSecret ?? '');

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="card p-6 w-full max-w-md">
        <h2 className="text-lg font-semibold mb-4">ERPNext 凭证</h2>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-fg-dim">ERPNext URL</label>
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="w-full input"
              placeholder="http://my.local:8000"
            />
          </div>
          <div>
            <label className="text-xs text-fg-dim">API Key</label>
            <input
              type="text"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full input"
            />
          </div>
          <div>
            <label className="text-xs text-fg-dim">API Secret</label>
            <input
              type="password"
              value={apiSecret}
              onChange={(e) => setApiSecret(e.target.value)}
              className="w-full input"
            />
          </div>
          <p className="text-xs text-warning">
            ⚠️ 凭证不加密,仅存浏览器 localStorage(v0 demo 限制)。
          </p>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onClose} className="btn-secondary">取消</button>
          <button
            onClick={() => onSave({ url, apiKey, apiSecret })}
            disabled={!url || !apiKey || !apiSecret}
            className="btn-primary"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `ImportHubCardErpNext.tsx`**

```typescript
// frontend/src/components/ImportHubCardErpNext.tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDemoStore } from '../stores/demoStore';
import { api } from '../api/client';
import ErpCredentialsModal from './ErpCredentialsModal';

interface Props {
  period: string;
  periodStart: string;
  periodEnd: string;
}

export default function ImportHubCardErpNext({ period, periodStart, periodEnd }: Props) {
  const credentials = useDemoStore((s) => s.erpnextCredentials);
  const setCredentials = useDemoStore((s) => s.setErpnextCredentials);
  const setHubSummary = useDemoStore((s) => s.setHubDataForPeriod);
  const hubData = useDemoStore((s) => s.hubDataByPeriod[period]);

  const navigate = useNavigate();
  const [showCreds, setShowCreds] = useState(false);
  const [pulling, setPulling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePull = async () => {
    if (!credentials) {
      setShowCreds(true);
      return;
    }
    setPulling(true);
    setError(null);
    try {
      const result = await api.erp.erpnextPull({
        url: credentials.url,
        api_key: credentials.apiKey,
        api_secret: credentials.apiSecret,
        period,
        period_start: periodStart,
        period_end: periodEnd,
      });
      setHubSummary(period, {
        salesCount: result.sales,
        purchasesCount: result.purchases,
        cancelledCount: result.cancelled,
        amendsCount: result.amends,
        lastPulledAt: new Date().toISOString(),
      });
    } catch (e: any) {
      setError(e.message);
    } finally {
      setPulling(false);
    }
  };

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-medium">📥 从 ERPNext 导入</h3>
        <button onClick={() => setShowCreds(true)} className="text-xs text-fg-dim hover:text-fg">
          {credentials ? '✏️ 修改凭证' : '⚙️ 配置凭证'}
        </button>
      </div>

      <div className="text-sm space-y-2">
        <p className="text-fg-dim">
          凭证: {credentials ? '✓ 已配置' : '⚠️ 未配置'} ({credentials?.url ?? '—'})
        </p>
        {hubData && (
          <p className="text-fg-dim">
            上次拉取: {hubData.lastPulledAt ? new Date(hubData.lastPulledAt).toLocaleString() : '—'}
            {' · '}{hubData.salesCount} 销售 / {hubData.purchasesCount} 采购
            {hubData.cancelledCount > 0 && ` · ${hubData.cancelledCount} 已冲红`}
          </p>
        )}
      </div>

      <button
        onClick={handlePull}
        disabled={pulling}
        className="btn-primary mt-3 w-full"
      >
        {pulling ? '拉取中...' : '🔄 拉取本季度'}
      </button>

      {error && (
        <p className="text-xs text-error mt-2">❌ {error}</p>
      )}

      {showCreds && (
        <ErpCredentialsModal
          initial={credentials ?? undefined}
          onSave={(creds) => {
            setCredentials(creds);
            setShowCreds(false);
          }}
          onClose={() => setShowCreds(false)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 3: Type check**

```bash
cd /root/TAXI/frontend && npx tsc --noEmit
# Expected: 无错误
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ImportHubCardErpNext.tsx frontend/src/components/ErpCredentialsModal.tsx
git commit -m "feat(components): ImportHubCardErpNext + ErpCredentialsModal"
```

---

## Task 10: Create `ImportHubPage` with period selector + 2 cards

**Files:**
- Create: `frontend/src/pages/ImportHubPage.tsx`
- Create: `frontend/src/components/ImportHubCardCsv.tsx`
- Modify: `frontend/src/App.tsx` (add route)
- Modify: `frontend/src/pages/DashboardPage.tsx` (add entry button)

- [ ] **Step 1: Create `ImportHubCardCsv.tsx` (simple wrapper around existing CsvImportWizard)**

```typescript
// frontend/src/components/ImportHubCardCsv.tsx
import { useState } from 'react';
import { api } from '../api/client';
import { useDemoStore } from '../stores/demoStore';

interface Props { period: string; }

export default function ImportHubCardCsv({ period }: Props) {
  const setHubSummary = useDemoStore((s) => s.setHubDataForPeriod);
  const [uploading, setUploading] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const ir = await api.erp.importCsv(file, 'erpnext_export');
      setLastResult(`✓ ${file.name} · ${ir.sales.length} 销售 + ${ir.purchases.length} 采购`);
      setHubSummary(period, {
        salesCount: ir.sales.length,
        purchasesCount: ir.purchases.length,
        cancelledCount: 0,
        amendsCount: 0,
        lastPulledAt: new Date().toISOString(),
      });
    } catch (e: any) {
      setLastResult(`❌ ${e.message}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="card p-4">
      <h3 className="font-medium mb-3">📤 上传 CSV</h3>
      <input type="file" accept=".csv" onChange={handleFile} disabled={uploading} />
      {uploading && <p className="text-xs text-fg-dim mt-2">上传中...</p>}
      {lastResult && <p className="text-xs mt-2">{lastResult}</p>}
    </div>
  );
}
```

- [ ] **Step 2: Create `ImportHubPage.tsx`**

```typescript
// frontend/src/pages/ImportHubPage.tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ImportHubCardErpNext from '../components/ImportHubCardErpNext';
import ImportHubCardCsv from '../components/ImportHubCardCsv';

function currentPeriod(): { id: string; start: string; end: string } {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth(); // 0-11
  const q = Math.floor(month / 3) + 1;
  return {
    id: `Q${q}_${year}`,
    start: `${year}-${String((q - 1) * 3 + 1).padStart(2, '0')}-01`,
    end: `${year}-${String(q * 3).padStart(2, '0')}-${q === 1 || q === 4 ? '31' : '30'}`,
  };
}

export default function ImportHubPage() {
  const defaultPeriod = currentPeriod();
  const [period, setPeriod] = useState(defaultPeriod.id);
  const [start, setStart] = useState(defaultPeriod.start);
  const [end, setEnd] = useState(defaultPeriod.end);
  const navigate = useNavigate();

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-semibold mb-4">Import Hub</h1>

      <div className="card p-4 mb-6">
        <label className="text-sm text-fg-dim">本期</label>
        <select
          value={period}
          onChange={(e) => {
            setPeriod(e.target.value);
            // 简化: 实际可调一个 period→{start,end} 映射
          }}
          className="ml-2 input"
        >
          <option value="Q1_2026">Q1 2026</option>
          <option value="Q2_2026">Q2 2026</option>
          <option value="Q3_2026">Q3 2026</option>
          <option value="Q4_2026">Q4 2026</option>
        </select>
        <span className="ml-4 text-xs text-fg-dim">
          {start} ~ {end}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ImportHubCardErpNext period={period} periodStart={start} periodEnd={end} />
        <ImportHubCardCsv period={period} />
      </div>

      <div className="mt-6 text-right">
        <button
          onClick={() => navigate(`/import/preview?period=${period}`)}
          className="btn-primary"
        >
          ✓ 准备报税,继续到 Preview
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Add route to `App.tsx`**

```typescript
// frontend/src/App.tsx — modify the Routes block
import ImportHubPage from './pages/ImportHubPage'
import ImportPreviewPage from './pages/ImportPreviewPage'

// In the <Routes>:
<Route path="/import" element={<ImportHubPage />} />
<Route path="/import/preview" element={<ImportPreviewPage />} />
```

- [ ] **Step 4: Add entry button to `DashboardPage.tsx`**

Add to `DashboardPage.tsx` (top, before the case grid):

```typescript
import { useNavigate } from 'react-router-dom';

// Inside the component:
const navigate = useNavigate();
<button
  onClick={() => navigate('/import')}
  className="btn-primary"
>
  ⬇ 导入外部数据
</button>
```

- [ ] **Step 5: Type check + build**

```bash
cd /root/TAXI/frontend && npx tsc --noEmit
# Expected: 无错误
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/ImportHubPage.tsx frontend/src/components/ImportHubCardCsv.tsx frontend/src/App.tsx frontend/src/pages/DashboardPage.tsx
git commit -m "feat(pages): ImportHubPage + 2 cards + entry button on Dashboard"
```

---

## Task 11: Create `ImportPreviewPage` with 2 CTAs

**Files:**
- Create: `frontend/src/pages/ImportPreviewPage.tsx`
- Create: `frontend/src/components/ImportPreviewTable.tsx`

- [ ] **Step 1: Create `ImportPreviewTable.tsx`**

```typescript
// frontend/src/components/ImportPreviewTable.tsx
import type { SalesTransaction, PurchaseTransaction } from '../types';

interface Props {
  sales: SalesTransaction[];
  purchases: PurchaseTransaction[];
  raw?: Array<{ id: string; cancelled: boolean; is_amend: boolean; parent?: string }>;
}

export default function ImportPreviewTable({ sales, purchases, raw = [] }: Props) {
  const rows = [
    ...sales.map((s) => ({ ...s, kind: 'sale' as const })),
    ...purchases.map((p) => ({ ...p, kind: 'purchase' as const })),
  ];
  const rawMap = new Map(raw.map((r) => [r.id, r]));

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-fg-dim">
          <th>ID</th><th>日期</th><th>对手方</th>
          <th>净额</th><th>税额</th><th>含税</th><th>状态</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const rRaw = rawMap.get(r.id);
          const cancelled = rRaw?.cancelled ?? false;
          const isAmend = rRaw?.is_amend ?? false;
          return (
            <tr key={r.id} className={cancelled ? 'opacity-50 line-through' : ''}>
              <td>
                {r.id}
                {isAmend && rRaw?.parent && (
                  <span className="text-xs text-fg-dim ml-1">↳ {rRaw.parent}</span>
                )}
              </td>
              <td>{r.txn_date}</td>
              <td>{r.counterparty}</td>
              <td>£{r.net_amount}</td>
              <td>£{r.vat_amount}</td>
              <td>£{r.gross_amount}</td>
              <td>
                {cancelled && <span className="text-error text-xs">已冲红</span>}
                {isAmend && !cancelled && <span className="text-warning text-xs">冲红</span>}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 2: Create `ImportPreviewPage.tsx`**

```typescript
// frontend/src/pages/ImportPreviewPage.tsx
import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import ImportPreviewTable from '../components/ImportPreviewTable';
import type { SalesTransaction, PurchaseTransaction } from '../types';

export default function ImportPreviewPage() {
  const [params] = useSearchParams();
  const period = params.get('period') ?? 'Q1_2026';
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [sales, setSales] = useState<SalesTransaction[]>([]);
  const [purchases, setPurchases] = useState<PurchaseTransaction[]>([]);
  const [raw, setRaw] = useState<any[]>([]);
  const [count, setCount] = useState<{ sales: number; purchases: number; cancelled: number; amends: number; total: number } | null>(null);

  useEffect(() => {
    api.erp.erpnextHubSummary(period)
      .then((data) => {
        setSales(data.sales as any);
        setPurchases(data.purchases as any);
        setRaw(data.raw);
        setCount(data.count);
      })
      .catch((e) => console.error(e))
      .finally(() => setLoading(false));
  }, [period]);

  if (loading) return <div className="p-6">加载中...</div>;
  if (!count || count.total === 0) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <h1 className="text-2xl font-semibold mb-4">Preview · {period}</h1>
        <div className="card p-6 text-center">
          <p className="text-fg-dim">本期内还没有导入数据。</p>
          <button onClick={() => navigate('/import')} className="btn-secondary mt-4">
            ← 回 Import Hub
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-semibold mb-2">Preview · {period}</h1>
      <p className="text-sm text-fg-dim mb-4">
        销售 {count.sales} 笔 · 采购 {count.purchases} 笔 · {count.cancelled > 0 && `${count.cancelled} 已冲红 · `}{count.amends > 0 && `${count.amends} 冲红 Credit Note`}
      </p>

      <div className="card p-4 mb-6">
        <details>
          <summary className="cursor-pointer text-sm font-medium">▼ 明细表 ({count.total} 行)</summary>
          <div className="mt-3">
            <ImportPreviewTable sales={sales} purchases={purchases} raw={raw} />
          </div>
        </details>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <button onClick={() => navigate('/agent')} className="btn-primary py-4">
          🤖 与 Agent 对话
        </button>
        <button onClick={() => navigate('/filings/new')} className="btn-secondary py-4">
          📝 手动报税
        </button>
      </div>

      <div className="mt-4 text-center">
        <button onClick={() => navigate('/import')} className="text-xs text-fg-dim">
          ← 回 Import Hub 重拉数据
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Type check**

```bash
cd /root/TAXI/frontend && npx tsc --noEmit
# Expected: 无错误
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ImportPreviewPage.tsx frontend/src/components/ImportPreviewTable.tsx
git commit -m "feat(pages): ImportPreviewPage with 2 CTAs to agent/manual"
```

---

## Task 12: Disable ERPNext on_submit push + add Web Form

**Files:**
- Modify: `frappe-bench/apps/tax_integration/tax_integration/hooks.py`
- Create: `frappe-bench/apps/tax_integration/tax_integration/integration/web_form/taxi_link/taxi_link.json`

- [ ] **Step 1: Comment out `doc_events` in `hooks.py`**

Modify `frappe-bench/apps/tax_integration/tax_integration/hooks.py`:

```python
# v1 user journey: 自动 push 默认关闭 (用户手动从 T.A.X.I. Pull)
# 如需重新启用,取消下方注释:
# doc_events = {
#     "Sales Invoice": {
#         "on_submit": "tax_integration.events.invoice_pushed.push_sales_invoice"
#     },
#     "Purchase Invoice": {
#         "on_submit": "tax_integration.events.invoice_pushed.push_purchase_invoice"
#     }
# }
doc_events = {}
```

- [ ] **Step 2: Create the Web Form directory + JSON file**

```bash
mkdir -p ~/frappe-bench/apps/tax_integration/tax_integration/integration/web_form/taxi_link
```

Create `~/frappe-bench/apps/tax_integration/tax_integration/integration/web_form/taxi_link/taxi_link.json`:

```json
{
  "doctype": "Web Form",
  "name": "taxi-link",
  "module": "Integration",
  "title": "T.A.X.I. — UK VAT Filing",
  "route": "taxi-link",
  "doc_type": "TAXI Settings",
  "is_standard": 1,
  "published": 1,
  "login_required": 0,
  "max_attachment_size": 0,
  "allow_print": 0,
  "allow_delete": 0,
  "allow_edit": 0,
  "allow_submit": 0,
  "introduction": "点击下方按钮跳转到 T.A.X.I. Import Hub 拉取本期内已 Submit 的发票,继续 UK VAT 申报。",
  "web_form_fields": [
    {
      "doctype": "TAXI Settings",
      "fieldname": "taxi_api_url",
      "label": "T.A.X.I. URL"
    }
  ]
}
```

- [ ] **Step 3: Restart ERPNext bench to pick up new hooks**

```bash
cd ~/frappe-bench
bench --site my.local clear-cache
bench restart
```

- [ ] **Step 4: Verify doc_events is empty**

```bash
cd ~/frappe-bench && bench --site my.local console <<'PY'
import frappe
events = frappe.get_hooks("doc_events")
for doctype, hooks in events.items():
    if "Invoice" in doctype:
        print(f"{doctype}: {hooks}")
PY
# Expected: 空(无 Invoice hooks)
```

- [ ] **Step 5: Verify Web Form exists**

```bash
cd ~/frappe-bench && bench --site my.local console <<'PY'
import frappe
wf = frappe.get_doc("Web Form", "taxi-link")
print(f"Web Form: {wf.title}, route: {wf.route}")
PY
# Expected: Web Form: T.A.X.I. — UK VAT Filing, route: taxi-link
```

- [ ] **Step 6: Commit Frappe-side changes (in /root/frappe-bench)**

```bash
cd ~/frappe-bench
git add apps/tax_integration/
git commit -m "feat(tax_integration): disable auto-push; add Web Form back-link"
```

(本仓库/root/TAXI 不动,Frappe 是独立 git 仓库)

- [ ] **Step 7: Commit a note in the main repo**

In `/root/TAXI/docs/erp_integration.md`, append a section noting "v1 user journey: pull-only mode, see spec 2026-06-12". Then:

```bash
cd /root/TAXI
git add docs/erp_integration.md
git commit -m "docs: note v1 pull-only mode + spec link"
```

---

## Task 13: End-to-end smoke test + final commit

**Files:** none new

- [ ] **Step 1: Restart all services**

```bash
# T.A.X.I. backend
pkill -f 'uvicorn backend.main' || true
sleep 1
cd /root/TAXI && nohup ./start_backend.sh > $HOME/logs/taxi.log 2>&1 &

# T.A.X.I. frontend
pkill -f 'serve_frontend_9000' || true
sleep 1
cd /root/TAXI && nohup bash scripts/serve_frontend_9000.sh > $HOME/logs/frontend.log 2>&1 &
```

- [ ] **Step 2: Run all backend tests**

```bash
cd /root/TAXI && pytest tests/erp/ -v
# Expected: All tests pass
```

- [ ] **Step 3: Manual E2E: Pull from ERPNext (mock) → Preview → Manual filing**

```bash
# 配置 demoStore 凭证(用 curl 模拟前端的 pull 调用)
curl -X POST http://localhost:8765/api/erp/erpnext/pull \
  -H "Content-Type: application/json" \
  -d '{
    "url": "http://my.local:8000",
    "api_key": "fake-key", "api_secret": "fake-secret",
    "period": "Q1_2026",
    "period_start": "2026-01-01", "period_end": "2026-03-31"
  }'
# Expected: 500(因为 fake ERPNext 不可达),但 endpoint 存在

# 验证 hub summary endpoint
curl 'http://localhost:8765/api/erp/hub/summary?period=Q1_2026'
# Expected: {"period":"Q1_2026","sales":[],"purchases":[],"count":{...},"raw":[]}
```

- [ ] **Step 4: Open browser flow**

1. Visit `http://localhost:9000` → Dashboard
2. Click `[⬇ 导入外部数据]` button → lands on `/import`
3. Period selector shows "Q1 2026"
4. Click `[⚙️ 配置凭证]` → modal opens
5. Enter URL `http://my.local:8000` / API key / API secret → Save
6. Click `[🔄 拉取本季度]` → spinner, then error (because ERPNext not really configured) or success
7. (Optional) Click CSV upload with a sample file
8. Click `[✓ 准备报税]` → lands on `/import/preview?period=Q1_2026`
9. See "本期内还没有导入数据" empty state if no data
10. Click `[← 回 Import Hub]` → back to hub

- [ ] **Step 5: Final commit + tag**

```bash
cd /root/TAXI
git status --short
git add -A
git commit -m "feat(erp): v1 user journey — Import Hub + Preview + Pull API" --allow-empty
git tag v1-erpnext-user-journey
```

- [ ] **Step 6: Update CHANGELOG / README if needed**

```bash
# Append to README.md a "v1 ERPnext user journey" section
# (optional, for product-facing docs)
```

---

## Self-Review

**Spec coverage check** (skim each spec section → verify a task covers it):

| Spec § | Task |
|---|---|
| §1.1 总方案 A | Task 9-11 (front-end pages) |
| §1.2 三种数据流合并 | Task 2 (store) + Task 3 (pull) + Task 4 (endpoint) + Task 6 (CSV) |
| §1.3 模块位置 | All tasks |
| §2.1 Card A (Pull) | Task 9 (component) + Task 3 (backend pull) |
| §2.1 Card B (CSV) | Task 6 (profile) + Task 10 (component) |
| §2.2 Preview Page | Task 11 |
| §2.3 ImportHubStore | Task 2 |
| §2.4 9-Box 集成 | Task 5 |
| §3.1 完整旅程 | Task 9-11 |
| §3.2 ERPNext 侧引导 | Task 12 (Web Form) |
| §3.3 错账冲红 | Task 1 (model fields) + Task 3 (cancel/amend in pull) + Task 5 (filter) |
| §4.1 状态机 | Tasks 9-11 (UI states) + Task 4 (HTTP) |
| §4.2 不变量 1-10 | Task 2 (1-3,9) + Task 5 (5,6) + Task 8 (7,8) + Task 12 (4) |
| §5 错误处理 | Task 3 (401) + Task 4 (HTTP) + Task 9 (component) |
| §6 Out of scope | All tasks respect boundaries |
| §7 测试 | Tasks 1-6 include unit tests, Task 13 is E2E |
| §8 Risks | Task 8 (明文凭据) + Task 3 (大账套超时 60s) + Task 4 (401) |

**No placeholders / no "TBD"**: searched, none found.

**Type consistency**:
- `HubInvoice` defined in Task 1, used in Tasks 2/3/5 ✓
- `ImportHubStore.add/list/count/clear` defined in Task 2, used in Tasks 4/5/7 ✓
- `pull_invoices` defined in Task 3, used in Task 4 ✓
- `api.erp.erpnextPull/erpnextStatus/erpnextHubSummary` defined in Task 7, used in Tasks 9/10/11 ✓
- `setHubDataForPeriod(period, summary)` defined in Task 8, used in Task 9/10 ✓
- `erpnextCredentials` shape defined in Task 8, used in Task 9 ✓
- `hubDataByPeriod[period]` shape defined in Task 8, used in Task 11 ✓

**Plan issues found and fixed**:
- Task 5 originally wanted to add `filter_cancelled` to `compute_taxi_nine_box`, but realized that `SalesTransaction` doesn't have a `cancelled` field. **Pivoted to a `hub_invoices_to_txn()` helper** that does filtering BEFORE the conversion. This is a cleaner design — the `compute_taxi_nine_box` API stays simple and unchanged.
