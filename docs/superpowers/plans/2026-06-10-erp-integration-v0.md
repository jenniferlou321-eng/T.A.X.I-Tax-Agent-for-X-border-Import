# T.A.X.I. ERP Integration v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 ERP 数据接入 v0 demo，让用户能从 Dashboard 选 demo case、在 Agent chat 里完成 UK VAT 9-Box 复核、点 Submit 一键提交到 HMRC mock，全流程 Agent 主导、严格报错。

**Architecture:** 在 `Orchestrator` 6 阶段最前面新增 `_stage_import`；Agent 在 chat 里调 MCP 工具完成 CALCULATE/VALIDATE；用户点 Submit 时 Orchestrator 才一次性跑 PRECHECK+PREPARE+SUBMIT+TRACK 4 阶段。前端 Dashboard 加 3 控件 (ErpConnectionToggle/ClearDataButton/Case 切换高亮)；AgentChatPage 加 2 个一键按钮 + InvoiceMultiSelectPanel + 9-Box 差异表 + 错误表。所有数据流过 `tax_agent/erp/` 包的统一 `_stage_import` 路径。

**Tech Stack:** Python 3.11 + FastAPI + Pydantic + httpx + pytest-httpx / Frontend React 19 + TypeScript + Vite + Zustand / LLM Claude Agent SDK / 测试 pytest + pytest-asyncio + pytest-httpx

**Spec:** `/root/TAXI/tax_agent/docs/superpowers/specs/2026-06-10-erp-integration-v0-design.md`

---

## File Structure

### 新建 Python 包 (`tax_agent/erp/`)

| 文件 | 行数 | 职责 |
|---|---|---|
| `__init__.py` | 5 | 空包 |
| `csv_parser.py` | 80 | bytes → ImportResult（stdlib csv） |
| `profiles.py` | 120 | `CsvProfile` Protocol + `GenericProfile` |
| `reconcile.py` | 150 | `compute_taxi_nine_box` + `ReconciliationDelta` Pydantic |
| `audit_events.py` | 30 | 5 个 audit action 常量 |
| `erp_samples_loader.py` | 60 | `data/erp_samples/*.json` → `ImportResult` |

### 修改 Python 文件

| 文件 | 改动 |
|---|---|
| `tax_agent/orchestrator.py` | + `_stage_import` 方法 + 新 import |
| `tax_agent/jurisdictions/uk/vat/calculator.py` | + `mode` 形参 + reconcile 分支 |
| `tax_agent/jurisdictions/uk/vat/agent_tools.py` | + `ingest_erp_data` + `filter_invoices` MCP tools |
| `tax_agent/jurisdictions/__init__.py` | `JurisdictionAdapter.calculate` 形参加 `mode` |
| `tax_agent/server/routers/filings.py` | 响应补 `audit_trail` + `import_summary` |
| `tax_agent/server/main.py` | 注册 `erp` router |
| `pyproject.toml` | pytest 配置 |

### 新建 Python 测试

| 文件 | 测试数 |
|---|---|
| `tax_agent/tests/__init__.py` | — |
| `tax_agent/tests/erp/__init__.py` | — |
| `tax_agent/tests/conftest.py` | shared fixtures |
| `tax_agent/tests/erp/test_csv_parser.py` | 5 |
| `tax_agent/tests/erp/test_reconcile.py` | 4 |
| `tax_agent/tests/erp/test_erp_samples_loader.py` | 2 |
| `tax_agent/tests/erp/test_erp_router.py` | 3 |
| `tax_agent/tests/erp/test_orchestrator_e2e.py` | 2 |
| `tax_agent/tests/erp/test_agent_chat.py` | 2 |

### 新建 Frontend 文件

| 文件 | 行数 | 职责 |
|---|---|---|
| `ErpConnectionToggle.tsx` | 70 | Dashboard ERP on/off 切换 |
| `ClearDataButton.tsx` | 80 | Dashboard 一键清空数据 |
| `QuickActionButton.tsx` | 40 | 复用：两个一键按钮 |
| `CsvImportWizard.tsx` | 150 | drag-drop CSV |
| `InvoiceMultiSelectPanel.tsx` | 180 | 多选发票弹窗 |
| `ErrorTableCard.tsx` | 60 | chat 错误展示 |
| `NineBoxDiffTable.tsx` | 120 | 9-Box side-by-side |

### 修改 Frontend

| 文件 | 改动 |
|---|---|
| `frontend/src/api/client.ts` | + `erp` namespace |
| `frontend/src/types/index.ts` | + 新 types |
| `frontend/src/pages/DashboardPage.tsx` | + 3 控件 |
| `frontend/src/pages/AgentChatPage.tsx` | + QuickActionButton + Panel + Card |
| `frontend/src/components/CasePresetCard.tsx` | + 选中高亮状态 |
| `frontend/src/stores/demoStore.ts` | + `clearAll()` action |

### 新建数据文件

| 文件 | 大小 |
|---|---|
| `tax_agent/data/erp_samples/techflow_q1_2026.json` | ~13KB（从 realCaseData 转换） |
| `tax_agent/data/erp_samples/cross_border_eu_2026.json` | ~10KB |
| `tax_agent/data/erp_samples/generic_sales_template.csv` | ~3KB |

### 新建文档

| 文件 | 职责 |
|---|---|
| `tax_agent/docs/erp_integration.md` | 用户/开发者文档 |
| `tax_agent/scripts/convert_realcase_to_erp_sample.py` | realCaseData → JSON 转换 |

---

## Task Index

| # | 任务 | 文件数 | 估计 LOC |
|---|---|---|---|
| 1 | 数据模型：erp_models.py (ImportResult/SalesTransaction/...) | 1 | 90 |
| 2 | CSV 解析器：csv_parser.py + GenericProfile | 2 | 200 |
| 3 | reconcile 核心：reconcile.py (compute_taxi_nine_box + ReconciliationDelta) | 1 | 150 |
| 4 | audit_events.py + erp_samples_loader.py | 2 | 90 |
| 5 | /api/erp/* Router (server/erp.py) | 1 | 150 |
| 6 | UK calculator 加 mode 形参 + reconcile 分支 | 1 | 60 |
| 7 | Orchestrator 加 _stage_import | 1 | 50 |
| 8 | Filings router 响应补 audit_trail + import_summary | 1 | 30 |
| 9 | Agent MCP tools: ingest_erp_data + filter_invoices | 1 | 100 |
| 10 | Demo case JSON 数据文件 (3 个) | 3 | 50 |
| 11 | 前端：erp namespace in client.ts + 新 types | 2 | 80 |
| 12 | 前端：ErpConnectionToggle + ClearDataButton + demoStore 扩展 | 3 | 200 |
| 13 | 前端：DashboardPage 集成 3 控件 + CasePresetCard 选中高亮 | 2 | 100 |
| 14 | 前端：AgentChatPage 加 QuickActionButton + 两个一键按钮 | 2 | 80 |
| 15 | 前端：InvoiceMultiSelectPanel + ErrorTableCard + NineBoxDiffTable | 3 | 360 |
| 16 | 前端：AgentChatPage 集成 Panel/Card/Table | 1 | 80 |
| 17 | 前端：CsvImportWizard | 1 | 150 |
| 18 | 测试：conftest.py + test_csv_parser.py + test_reconcile.py | 4 | 200 |
| 19 | 测试：test_erp_samples_loader + test_erp_router | 2 | 120 |
| 20 | 测试：test_orchestrator_e2e + test_agent_chat | 2 | 200 |
| 21 | 文档：erp_integration.md + 转换脚本 | 2 | 250 |

**总计**: 21 个 task，约 30+ 个 git commit。

---

## Task 1: 数据模型 erp_models.py

**Files:**
- Create: `tax_agent/models/erp_models.py`

- [ ] **Step 1: Write the failing test**

创建 `tax_agent/tests/erp/test_erp_models.py`：

```python
"""erp_models 数据模型测试"""
from datetime import date
from decimal import Decimal
from tax_agent.models.erp_models import (
    SalesTransaction, PurchaseTransaction, ERPNineBox, ImportResult,
)


def test_sales_transaction_fields():
    t = SalesTransaction(
        id="INV-2026-001",
        txn_date=date(2026, 1, 15),
        counterparty="ACME Corp",
        net_amount=Decimal("1000.00"),
        vat_amount=Decimal("200.00"),
        gross_amount=Decimal("1200.00"),
        vat_rate=Decimal("0.20"),
        tax_code="T1",
    )
    assert t.id == "INV-2026-001"
    assert t.vat_rate == Decimal("0.20")
    assert t.is_eu is False  # default
    assert t.is_reverse_charge is False  # default


def test_purchase_transaction_fields():
    t = PurchaseTransaction(
        id="PIN-2026-001",
        txn_date=date(2026, 1, 20),
        counterparty="Office Supplies Ltd",
        net_amount=Decimal("500.00"),
        vat_amount=Decimal("100.00"),
        gross_amount=Decimal("600.00"),
        vat_rate=Decimal("0.20"),
        tax_code="T1",
    )
    assert t.is_recoverable is True  # default
    assert t.is_eu_acquisition is False  # default


def test_erp_nine_box_defaults():
    box = ERPNineBox()
    assert box.box1_vat_due_sales == Decimal("0")
    assert box.box6_total_sales_ex_vat == 0  # int
    assert box.scheme_flags == []  # list default


def test_import_result_required_fields():
    r = ImportResult(
        sales=[],
        purchases=[],
        erp_provided_boxes=ERPNineBox(),
        source_profile="generic",
        source_filename="test.csv",
        source_hash="abc123",
    )
    assert r.warnings == []  # default
    assert r.rejected_rows == []  # default
    assert r.erp_provided_boxes is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tax_agent && pytest tests/erp/test_erp_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tax_agent.models.erp_models'`

- [ ] **Step 3: Write minimal implementation**

创建 `tax_agent/models/erp_models.py`：

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tax_agent && pytest tests/erp/test_erp_models.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
cd /root/TAXI
git add tax_agent/models/erp_models.py tax_agent/tests/erp/test_erp_models.py
git commit -m "feat(erp): add Pydantic models for ERP import (SalesTransaction, ERPNineBox, ImportResult)"
```

---

## Task 2: CSV 解析器 + GenericProfile

**Files:**
- Create: `tax_agent/erp/profiles.py`
- Create: `tax_agent/erp/csv_parser.py`
- Create: `tax_agent/tests/erp/test_csv_parser.py`

- [ ] **Step 1: Write the failing test for GenericProfile**

创建 `tax_agent/tests/erp/test_csv_parser.py`：

```python
"""CSV 解析器 + Generic Profile 测试"""
import io
import pytest
from decimal import Decimal
from tax_agent.erp.csv_parser import (
    parse_csv, CsvParseError, detect_profile, REQUIRED_COLUMNS,
)
from tax_agent.erp.profiles import GenericProfile


def test_required_columns_constant():
    assert "txn_date" in REQUIRED_COLUMNS
    assert "txn_type" in REQUIRED_COLUMNS
    assert "counterparty" in REQUIRED_COLUMNS
    assert "net" in REQUIRED_COLUMNS
    assert "vat" in REQUIRED_COLUMNS
    assert "gross" in REQUIRED_COLUMNS
    assert "vat_rate" in REQUIRED_COLUMNS
    assert "tax_code" in REQUIRED_COLUMNS


def test_detect_profile_generic_exact_match():
    headers = REQUIRED_COLUMNS
    profile, confidence = detect_profile(headers)
    assert profile == "generic"
    assert confidence == 1.0


def test_detect_profile_generic_partial_match():
    headers = ["txn_date", "txn_type", "counterparty", "net", "vat", "gross", "vat_rate", "tax_code", "extra_col"]
    profile, confidence = detect_profile(headers)
    assert profile == "generic"
    assert confidence >= 0.7


def test_detect_profile_no_match_returns_generic_low_confidence():
    headers = ["random_col1", "random_col2"]
    profile, confidence = detect_profile(headers)
    assert profile == "generic"
    assert confidence < 0.7


def test_parse_csv_generic_valid():
    csv_bytes = (
        b"txn_date,txn_type,counterparty,net,vat,gross,vat_rate,tax_code\n"
        b"2026-01-15,sale,ACME Corp,1000.00,200.00,1200.00,0.20,T1\n"
        b"2026-01-20,purchase,Office Ltd,500.00,100.00,600.00,0.20,T1\n"
    )
    result = parse_csv(csv_bytes, profile="generic")
    assert result.source_profile == "generic"
    assert len(result.sales) == 1
    assert len(result.purchases) == 1
    assert result.sales[0].id.startswith("SALE-")
    assert result.sales[0].counterparty == "ACME Corp"
    assert result.sales[0].net_amount == Decimal("1000.00")
    assert result.purchases[0].counterparty == "Office Ltd"


def test_parse_csv_bom_strip():
    csv_bytes = b"\xef\xbb\xbf" + (
        b"txn_date,txn_type,counterparty,net,vat,gross,vat_rate,tax_code\n"
        b"2026-01-15,sale,ACME,100,20,120,0.20,T1\n"
    )
    result = parse_csv(csv_bytes, profile="generic")
    assert len(result.sales) == 1


def test_parse_csv_missing_required_column_raises():
    csv_bytes = b"txn_date,txn_type,counterparty,net\n2026-01-15,sale,ACME,100\n"
    with pytest.raises(CsvParseError, match="missing required column"):
        parse_csv(csv_bytes, profile="generic")


def test_parse_csv_rejected_rows_with_bad_data():
    csv_bytes = (
        b"txn_date,txn_type,counterparty,net,vat,gross,vat_rate,tax_code\n"
        b"2026-01-15,sale,ACME,1000.00,200.00,1200.00,0.20,T1\n"
        b"not-a-date,sale,Bad Inc,100,20,120,0.20,T1\n"
    )
    result = parse_csv(csv_bytes, profile="generic")
    assert len(result.sales) == 1
    assert len(result.rejected_rows) == 1
    assert result.rejected_rows[0]["row_index"] == 2


def test_parse_csv_header_corrupt_raises():
    csv_bytes = b"this is not,valid csv header at all\nrandom,data\n"
    with pytest.raises(CsvParseError, match="header"):
        parse_csv(csv_bytes, profile="generic")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tax_agent && pytest tests/erp/test_csv_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tax_agent.erp'`

- [ ] **Step 3: Create __init__.py**

创建 `tax_agent/erp/__init__.py`：

```python
"""ERP 数据接入包 — 解析 / reconcile / audit events / sample loader"""
```

- [ ] **Step 4: Write profiles.py**

创建 `tax_agent/erp/profiles.py`：

```python
"""CSV Profile — 单一 Profile (Generic) for v0

v1 再加 Sage / Xero / QBO Profile。
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Tuple
from datetime import date

from ..models.erp_models import SalesTransaction, PurchaseTransaction


REQUIRED_COLUMNS = [
    "txn_date", "txn_type", "counterparty",
    "net", "vat", "gross", "vat_rate", "tax_code",
]


class GenericProfile:
    """v0 唯一 Profile：8 列必填，txn_type 区分 sale/purchase"""

    name = "generic"

    def detect(self, headers: List[str]) -> float:
        """返回 0.0-1.0 匹配分数。>=0.7 视为命中。"""
        headers_lower = [h.strip().lower() for h in headers]
        matched = sum(1 for c in REQUIRED_COLUMNS if c in headers_lower)
        return matched / len(REQUIRED_COLUMNS)

    def transform_row(
        self, row: Dict[str, str], row_index: int,
    ) -> Tuple[SalesTransaction | PurchaseTransaction | None, str | None]:
        """把一行 dict 转换为 SalesTransaction / PurchaseTransaction。
        返回 (txn, None) 或 (None, error_message)。"""
        try:
            common = {
                "id": f"{'SALE' if row['txn_type'].lower() == 'sale' else 'PIN'}-{row_index:05d}",
                "txn_date": date.fromisoformat(row["txn_date"].strip()),
                "counterparty": row["counterparty"].strip(),
                "net_amount": Decimal(str(row["net"]).strip()),
                "vat_amount": Decimal(str(row["vat"]).strip()),
                "gross_amount": Decimal(str(row["gross"]).strip()),
                "vat_rate": Decimal(str(row["vat_rate"]).strip()),
                "tax_code": row["tax_code"].strip(),
            }
            if row["txn_type"].strip().lower() == "sale":
                return SalesTransaction(**common), None
            elif row["txn_type"].strip().lower() == "purchase":
                return PurchaseTransaction(**common), None
            else:
                return None, f"unknown txn_type: {row['txn_type']!r}"
        except (ValueError, KeyError) as e:
            return None, f"parse error: {e}"
```

- [ ] **Step 5: Write csv_parser.py**

创建 `tax_agent/erp/csv_parser.py`：

```python
"""CSV 解析器入口 — bytes → ImportResult"""
from __future__ import annotations

import csv
import hashlib
import io
from typing import List, Tuple

from ..models.erp_models import (
    ERPNineBox, ImportResult, SalesTransaction, PurchaseTransaction,
)
from .profiles import GenericProfile, REQUIRED_COLUMNS


class CsvParseError(ValueError):
    """Header-level CSV 错误（不是单行错误）"""


_PROFILES = {"generic": GenericProfile()}


def detect_profile(headers: List[str]) -> Tuple[str, float]:
    """根据 header 行检测最匹配的 profile。返回 (profile_name, confidence)。
    v0 只有一个 profile，固定返 generic。"""
    best_name, best_score = "generic", 0.0
    for name, p in _PROFILES.items():
        score = p.detect(headers)
        if score > best_score:
            best_name, best_score = name, score
    return best_name, best_score


def parse_csv(file_bytes: bytes, profile: str | None = None) -> ImportResult:
    """解析 CSV bytes → ImportResult。

    - profile=None: auto-detect
    - profile='generic': 强制走 GenericProfile
    - 行级错误写入 rejected_rows，不抛异常
    - header 缺失/污染 → 抛 CsvParseError
    """
    # 1. 解码 + 去 BOM
    try:
        text = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise CsvParseError(f"file not utf-8: {e}") from e

    # 2. 读 header
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    if not headers:
        raise CsvParseError("file has no header row")

    # 3. 选 profile
    if profile is None:
        profile, _ = detect_profile(headers)
    if profile not in _PROFILES:
        raise CsvParseError(f"unknown profile: {profile!r}")
    profile_obj = _PROFILES[profile]

    # 4. 检查必填列
    headers_lower = [h.strip().lower() for h in headers]
    missing = [c for c in REQUIRED_COLUMNS if c not in headers_lower]
    if missing:
        raise CsvParseError(f"missing required column(s): {missing}")

    # 5. 逐行解析
    sales: List[SalesTransaction] = []
    purchases: List[PurchaseTransaction] = []
    rejected: List[dict] = []
    warnings: List[str] = []

    for row_index, row in enumerate(reader, start=2):  # 1=header
        if not any(row.values()):  # 空行
            continue
        txn, err = profile_obj.transform_row(row, row_index)
        if err:
            rejected.append({"row_index": row_index, "reason": err, "raw": dict(row)})
            continue
        if isinstance(txn, SalesTransaction):
            sales.append(txn)
        elif isinstance(txn, PurchaseTransaction):
            purchases.append(txn)

    # 6. 算 9-Box（v0 简化：从交易数据汇总，不调 reconcile.py）
    nine_box = _compute_9box_from_transactions(sales, purchases)

    # 7. source hash
    source_hash = hashlib.sha256(file_bytes).hexdigest()[:16]

    return ImportResult(
        sales=sales,
        purchases=purchases,
        erp_provided_boxes=nine_box,
        source_profile=profile,
        source_filename="<from-bytes>",
        source_hash=source_hash,
        warnings=warnings,
        rejected_rows=rejected,
    )


def _compute_9box_from_transactions(
    sales: List[SalesTransaction], purchases: List[PurchaseTransaction],
) -> ERPNineBox:
    """v0 简化版 9-Box 计算（不调 reconcile.py，避免循环 import）。"""
    box1 = sum((t.vat_amount for t in sales if t.vat_rate > 0), Decimal("0"))
    box2 = sum((t.vat_amount for t in purchases if t.is_eu_acquisition), Decimal("0"))
    box3 = box1 + box2
    box4 = sum((t.vat_amount for t in purchases if t.is_recoverable), Decimal("0"))
    box5 = abs(box3 - box4)
    box6 = int(sum((t.net_amount for t in sales), Decimal("0")))
    box7 = int(sum((t.net_amount for t in purchases), Decimal("0")))
    box8 = int(sum((t.net_amount for t in sales if t.is_eu), Decimal("0")))
    box9 = int(sum((t.net_amount for t in purchases if t.is_eu_acquisition), Decimal("0")))
    return ERPNineBox(
        box1_vat_due_sales=box1,
        box2_vat_due_acquisitions=box2,
        box3_total_vat_due=box3,
        box4_vat_reclaimed=box4,
        box5_net_vat_due=box5,
        box6_total_sales_ex_vat=box6,
        box7_total_purchases_ex_vat=box7,
        box8_total_goods_supplied_eu=box8,
        box9_total_goods_acquired_eu=box9,
    )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd tax_agent && pytest tests/erp/test_csv_parser.py -v`
Expected: 9 passed

- [ ] **Step 7: Commit**

```bash
cd /root/TAXI
git add tax_agent/erp/__init__.py tax_agent/erp/csv_parser.py tax_agent/erp/profiles.py tax_agent/tests/erp/test_csv_parser.py
git commit -m "feat(erp): Generic CSV parser with auto-detection, row-level error tolerance"
```

---

## Task 3: reconcile.py — ReconciliationDelta + compute_taxi_nine_box

**Files:**
- Create: `tax_agent/erp/reconcile.py`
- Create: `tax_agent/tests/erp/test_reconcile.py`

- [ ] **Step 1: Write the failing test**

创建 `tax_agent/tests/erp/test_reconcile.py`：

```python
"""reconcile.py 测试"""
from decimal import Decimal
from tax_agent.erp.reconcile import (
    compute_taxi_nine_box, ReconciliationDelta, reconcile,
)
from tax_agent.models.erp_models import (
    ERPNineBox, SalesTransaction, PurchaseTransaction,
)
from datetime import date


def make_sale(net, vat, rate="0.20", code="T1"):
    return SalesTransaction(
        id="S-1", txn_date=date(2026, 1, 1), counterparty="X",
        net_amount=Decimal(net), vat_amount=Decimal(vat), gross_amount=Decimal(net) + Decimal(vat),
        vat_rate=Decimal(rate), tax_code=code,
    )


def make_purchase(net, vat, rate="0.20", code="T1", recoverable=True):
    return PurchaseTransaction(
        id="P-1", txn_date=date(2026, 1, 1), counterparty="Y",
        net_amount=Decimal(net), vat_amount=Decimal(vat), gross_amount=Decimal(net) + Decimal(vat),
        vat_rate=Decimal(rate), tax_code=code, is_recoverable=recoverable,
    )


def test_compute_taxi_nine_box_from_transactions():
    sales = [make_sale("1000", "200")]
    purchases = [make_purchase("500", "100")]
    box = compute_taxi_nine_box(sales, purchases)
    assert box.box1_vat_due_sales == Decimal("200")
    assert box.box4_vat_reclaimed == Decimal("100")
    assert box.box3_total_vat_due == Decimal("200")
    assert box.box5_net_vat_due == Decimal("100")
    assert box.box6_total_sales_ex_vat == 1000  # int
    assert box.box7_total_purchases_ex_vat == 500  # int


def test_compute_taxi_nine_box_excludes_zero_rated_from_box1():
    sales = [make_sale("1000", "200", "0.20"), make_sale("500", "0", "0.00", "T0")]
    box = compute_taxi_nine_box(sales, [])
    assert box.box1_vat_due_sales == Decimal("200")  # only standard
    assert box.box6_total_sales_ex_vat == 1500  # both included


def test_reconcile_identical_boxes_within_tolerance():
    a = ERPNineBox(box1_vat_due_sales=Decimal("100"))
    delta = reconcile(erp_boxes=a, taxi_boxes=a, erp_source="test")
    assert delta.total_abs_diff == Decimal("0")
    assert delta.within_tolerance is True


def test_reconcile_detects_box1_diff():
    erp = ERPNineBox(box1_vat_due_sales=Decimal("100.00"))
    taxi = ERPNineBox(box1_vat_due_sales=Decimal("103.50"))
    delta = reconcile(erp_boxes=erp, taxi_boxes=taxi, erp_source="test")
    assert delta.box_diffs["box1"] == Decimal("3.50")
    assert delta.within_tolerance is False
    assert delta.total_abs_diff == Decimal("3.50")
    assert any("box1" in n for n in delta.notes)


def test_reconcile_tolerance_boundary():
    """£0.50 内算 within_tolerance（HMRC 官方 rounding 容差）"""
    erp = ERPNineBox(box1_vat_due_sales=Decimal("100.00"))
    taxi = ERPNineBox(box1_vat_due_sales=Decimal("100.50"))
    delta = reconcile(erp_boxes=erp, taxi_boxes=taxi, erp_source="test")
    assert delta.box_diffs["box1"] == Decimal("0.50")
    assert delta.within_tolerance is True


def test_reconcile_aggregates_diffs_across_boxes():
    erp = ERPNineBox(
        box1_vat_due_sales=Decimal("100"),
        box4_vat_reclaimed=Decimal("50"),
    )
    taxi = ERPNineBox(
        box1_vat_due_sales=Decimal("102"),
        box4_vat_reclaimed=Decimal("50"),
    )
    delta = reconcile(erp_boxes=erp, taxi_boxes=taxi, erp_source="test")
    assert delta.total_abs_diff == Decimal("2.00")
    assert delta.within_tolerance is False
    assert len(delta.notes) == 1  # only box1 flagged
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tax_agent && pytest tests/erp/test_reconcile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tax_agent.erp.reconcile'`

- [ ] **Step 3: Write reconcile.py**

创建 `tax_agent/erp/reconcile.py`：

```python
"""reconcile — 对比 ERP 9-Box 与 T.A.X.I. 算的 9-Box，生成差异报告

v0 关键约束：
- T.A.X.I. 9-Box 永远从 sales/purchases 重新计算（不信任外部）
- 差异容差：£0.50（HMRC 官方 rounding 容差）
- 任意 box 差异 > tolerance → within_tolerance=False
"""
from __future__ import annotations

from decimal import Decimal
from typing import List, Tuple

from pydantic import BaseModel, Field

from ..models.erp_models import (
    ERPNineBox, SalesTransaction, PurchaseTransaction,
)


TOLERANCE_GBP = Decimal("0.50")


class ReconciliationDelta(BaseModel):
    """9-Box 差异报告"""
    box_diffs: dict[str, Decimal] = Field(default_factory=dict)
    total_abs_diff: Decimal = Decimal("0")
    within_tolerance: bool = True
    erp_source: str = ""
    notes: List[str] = Field(default_factory=list)


def compute_taxi_nine_box(
    sales: List[SalesTransaction], purchases: List[PurchaseTransaction],
) -> ERPNineBox:
    """从原始交易数据计算 T.A.X.I. 的 9-Box。"""
    box1 = sum(
        (t.vat_amount for t in sales if t.vat_rate > 0),
        Decimal("0"),
    )
    box2 = sum(
        (t.vat_amount for t in purchases if t.is_eu_acquisition),
        Decimal("0"),
    )
    box3 = box1 + box2
    box4 = sum(
        (t.vat_amount for t in purchases if t.is_recoverable),
        Decimal("0"),
    )
    box5 = abs(box3 - box4)
    box6 = int(sum((t.net_amount for t in sales), Decimal("0")))
    box7 = int(sum((t.net_amount for t in purchases), Decimal("0")))
    box8 = int(sum((t.net_amount for t in sales if t.is_eu), Decimal("0")))
    box9 = int(sum(
        (t.net_amount for t in purchases if t.is_eu_acquisition),
        Decimal("0"),
    ))
    return ERPNineBox(
        box1_vat_due_sales=box1,
        box2_vat_due_acquisitions=box2,
        box3_total_vat_due=box3,
        box4_vat_reclaimed=box4,
        box5_net_vat_due=box5,
        box6_total_sales_ex_vat=box6,
        box7_total_purchases_ex_vat=box7,
        box8_total_goods_supplied_eu=box8,
        box9_total_goods_acquired_eu=box9,
    )


def reconcile(
    erp_boxes: ERPNineBox, taxi_boxes: ERPNineBox, erp_source: str,
    tolerance: Decimal = TOLERANCE_GBP,
) -> ReconciliationDelta:
    """对比两个 9-Box，生成差异报告。

    box_diffs 包含 9 个 box 的差值（taxi - erp）。
    notes 只列出超 tolerance 的 box。
    """
    diffs: dict[str, Decimal] = {}
    total_abs = Decimal("0")
    notes: List[str] = []

    pairs: List[Tuple[str, Decimal, Decimal]] = [
        ("box1", taxi_boxes.box1_vat_due_sales, erp_boxes.box1_vat_due_sales),
        ("box2", taxi_boxes.box2_vat_due_acquisitions, erp_boxes.box2_vat_due_acquisitions),
        ("box3", taxi_boxes.box3_total_vat_due, erp_boxes.box3_total_vat_due),
        ("box4", taxi_boxes.box4_vat_reclaimed, erp_boxes.box4_vat_reclaimed),
        ("box5", taxi_boxes.box5_net_vat_due, erp_boxes.box5_net_vat_due),
        ("box6", Decimal(taxi_boxes.box6_total_sales_ex_vat), Decimal(erp_boxes.box6_total_sales_ex_vat)),
        ("box7", Decimal(taxi_boxes.box7_total_purchases_ex_vat), Decimal(erp_boxes.box7_total_purchases_ex_vat)),
        ("box8", Decimal(taxi_boxes.box8_total_goods_supplied_eu), Decimal(erp_boxes.box8_total_goods_supplied_eu)),
        ("box9", Decimal(taxi_boxes.box9_total_goods_acquired_eu), Decimal(erp_boxes.box9_total_goods_acquired_eu)),
    ]
    for name, taxi_val, erp_val in pairs:
        d = taxi_val - erp_val
        diffs[name] = d
        total_abs += abs(d)
        if abs(d) > tolerance:
            notes.append(f"{name} 差异 {d} (TAXI={taxi_val}, ERP={erp_val}) > tolerance {tolerance}")

    return ReconciliationDelta(
        box_diffs=diffs,
        total_abs_diff=total_abs,
        within_tolerance=len(notes) == 0,
        erp_source=erp_source,
        notes=notes,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tax_agent && pytest tests/erp/test_reconcile.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
cd /root/TAXI
git add tax_agent/erp/reconcile.py tax_agent/tests/erp/test_reconcile.py
git commit -m "feat(erp): reconcile 9-Box with £0.50 HMRC tolerance, per-box diffs"
```

---

## Task 4: audit_events.py + erp_samples_loader.py

**Files:**
- Create: `tax_agent/erp/audit_events.py`
- Create: `tax_agent/erp/erp_samples_loader.py`
- Create: `tax_agent/tests/erp/test_erp_samples_loader.py`

- [ ] **Step 1: Write the failing test for samples loader**

创建 `tax_agent/tests/erp/test_erp_samples_loader.py`：

```python
"""erp_samples_loader 测试"""
import pytest
from tax_agent.erp.erp_samples_loader import (
    load_demo_case, list_demo_cases, DemoCaseNotFoundError,
)


def test_list_demo_cases_returns_list():
    cases = list_demo_cases()
    assert isinstance(cases, list)
    assert "techflow_q1_2026" in cases or len(cases) >= 1  # 至少有 1 个


def test_load_demo_case_techflow_returns_import_result():
    result = load_demo_case("techflow_q1_2026")
    assert result.source_profile == "demo"
    assert len(result.sales) >= 1
    assert len(result.purchases) >= 1
    assert result.erp_provided_boxes.box1_vat_due_sales > 0


def test_load_demo_case_not_found_raises():
    with pytest.raises(DemoCaseNotFoundError, match="nonexistent_case"):
        load_demo_case("nonexistent_case")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tax_agent && pytest tests/erp/test_erp_samples_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tax_agent.erp.erp_samples_loader'`

- [ ] **Step 3: Write audit_events.py**

创建 `tax_agent/erp/audit_events.py`：

```python
"""Audit action constants for ERP import pipeline。

避免 audit_log 里的 action 字符串漂移。
"""

ERP_IMPORT_STARTED = "erp.import.started"
ERP_IMPORT_PARSED = "erp.import.parsed"
ERP_IMPORT_REJECTED_ROW = "erp.import.rejected_row"
ERP_IMPORT_FAILED = "erp.import.failed"
ERP_RECONCILE_COMPUTED = "erp.reconcile.computed"
ERP_COMPUTE_MODE_OVERRIDDEN = "erp.compute_mode.overridden"
```

- [ ] **Step 4: Write erp_samples_loader.py**

创建 `tax_agent/erp/erp_samples_loader.py`：

```python
"""Demo case JSON loader — 从 tax_agent/data/erp_samples/ 读预置案例"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

from ..models.erp_models import ImportResult


SAMPLES_DIR = Path(__file__).parent.parent / "data" / "erp_samples"


class DemoCaseNotFoundError(KeyError):
    """Demo case 文件不存在"""


def list_demo_cases() -> List[str]:
    """返回所有可用的 demo case ID（文件名去掉 .json）。"""
    if not SAMPLES_DIR.exists():
        return []
    return sorted(p.stem for p in SAMPLES_DIR.glob("*.json"))


def load_demo_case(case_id: str) -> ImportResult:
    """从 data/erp_samples/{case_id}.json 读 ImportResult。

    Demo case JSON 已经是 Pydantic-compatible dict，直接 ImportResult.model_validate。
    """
    file_path = SAMPLES_DIR / f"{case_id}.json"
    if not file_path.exists():
        available = list_demo_cases()
        raise DemoCaseNotFoundError(
            f"demo case {case_id!r} not found. available: {available}"
        )
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    return ImportResult.model_validate(raw)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd tax_agent && pytest tests/erp/test_erp_samples_loader.py -v`
Expected: FAIL with `FileNotFoundError: data/erp_samples/techflow_q1_2026.json`

(这个失败是预期的 — 还没有 sample JSON。Task 10 会创建。继续。)

- [ ] **Step 6: Skip until Task 10**

注：等 Task 10 完成后才能跑通。标记 `# Skipped until Task 10`。

- [ ] **Step 7: Commit (with TODO marker)**

```bash
cd /root/TAXI
git add tax_agent/erp/audit_events.py tax_agent/erp/erp_samples_loader.py tax_agent/tests/erp/test_erp_samples_loader.py
git commit -m "feat(erp): audit event constants + demo case JSON loader (samples pending Task 10)"
```

---

## Task 5: /api/erp/* Router

**Files:**
- Create: `tax_agent/server/erp.py`
- Modify: `tax_agent/server/main.py:65-70`
- Create: `tax_agent/tests/erp/test_erp_router.py`

- [ ] **Step 1: Write the failing test**

创建 `tax_agent/tests/erp/test_erp_router.py`：

```python
"""erp router 测试 — FastAPI TestClient"""
import io
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tax_agent.server.erp import router as erp_router
from tax_agent.models.erp_models import ERPNineBox


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


def test_load_demo_case_techflow(client):
    resp = client.get("/api/erp/cases/techflow_q1_2026")
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tax_agent && pytest tests/erp/test_erp_router.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tax_agent.server.erp'`

- [ ] **Step 3: Write server/erp.py**

创建 `tax_agent/server/erp.py`：

```python
"""/api/erp/* — ERP 数据接入 REST 端点

- GET  /api/erp/cases                — 列出所有 demo case
- GET  /api/erp/cases/{case_id}      — 加载 demo case → ImportResult
- POST /api/erp/import               — multipart 上传 CSV
- POST /api/erp/reconcile            — 调 reconcile 生成差异报告
- DELETE /api/erp/{import_id}        — 清 in-memory 缓存（v0）
"""
from __future__ import annotations

import hashlib
import io
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..erp.csv_parser import CsvParseError, parse_csv
from ..erp.erp_samples_loader import DemoCaseNotFoundError, list_demo_cases, load_demo_case
from ..erp.reconcile import compute_taxi_nine_box, reconcile
from ..models.erp_models import ImportResult


router = APIRouter(prefix="/erp", tags=["erp"])


@router.get("/cases")
def get_cases():
    """列出所有 demo case ID。"""
    return {"cases": list_demo_cases()}


@router.get("/cases/{case_id}")
def get_case(case_id: str):
    """加载指定 demo case 返回 ImportResult。"""
    try:
        result = load_demo_case(case_id)
    except DemoCaseNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return result.model_dump(mode="json")


@router.post("/import")
async def import_csv(file: UploadFile = File(...), profile: Optional[str] = Form(None)):
    """multipart 上传 CSV → ImportResult。

    v0 上限 10MB（spec §7 risks）。
    """
    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file exceeds 10MB limit")
    try:
        result = parse_csv(file_bytes, profile=profile)
    except CsvParseError as e:
        raise HTTPException(status_code=422, detail=f"CSV parse error: {e}") from e
    # 填充 source_filename
    result.source_filename = file.filename or "<uploaded>"
    return result.model_dump(mode="json")


@router.post("/reconcile")
def post_reconcile(payload: dict):
    """接收 ImportResult dict 和 erp_source → ReconciliationDelta。

    Request body: {"import_result": {...}, "erp_source": "csv:generic"}
    """
    try:
        ir = ImportResult.model_validate(payload["import_result"])
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"invalid ImportResult: {e}") from e
    taxi_boxes = compute_taxi_nine_box(ir.sales, ir.purchases)
    delta = reconcile(ir.erp_provided_boxes, taxi_boxes, erp_source=payload.get("erp_source", "unknown"))
    return delta.model_dump(mode="json")
```

- [ ] **Step 4: Register router in main.py**

修改 `tax_agent/server/main.py`，在 `app.include_router(...)` 区域加一行：

```python
from .erp import router as erp_router
# ... existing routers ...
app.include_router(erp_router)  # 新加这一行
```

- [ ] **Step 5: Run test to verify it passes (部分)**

Run: `cd tax_agent && pytest tests/erp/test_erp_router.py -v`
Expected: 3 of 4 passed (test_load_demo_case 失败因 sample JSON 还没建)

- [ ] **Step 6: Commit**

```bash
cd /root/TAXI
git add tax_agent/server/erp.py tax_agent/server/main.py tax_agent/tests/erp/test_erp_router.py
git commit -m "feat(server): /api/erp/* router for demo cases + CSV import + reconcile"
```

---

## Task 6: UK calculator 加 mode 形参 + reconcile 分支

**Files:**
- Modify: `tax_agent/jurisdictions/uk/vat/calculator.py`
- Modify: `tax_agent/jurisdictions/__init__.py:43` (`calculate` 抽象方法签名)

- [ ] **Step 1: Read current calculator.py**

Read: `tax_agent/jurisdictions/uk/vat/calculator.py`（43 行，已读过）

- [ ] **Step 2: Modify calculator.py — add `mode` parameter and reconcile branch**

修改 `tax_agent/jurisdictions/uk/vat/calculator.py`：

```python
"""UK VAT Calculator — 9-box VAT 计算逻辑

HMRC MTD for VAT API 规范:
- Box 3 = Box 1 + Box 2
- Box 5 = |Box 3 − Box 4| (必须为非负值)
- Box 6-9 为整磅数（无小数位）

v0 修订：加 `mode` 形参。
- mode="recompute" (默认，向后兼容): 旧行为，breakdown 来自 data.line_items
- mode="reconcile": breakdown 来自 data.metadata["erp_provided_boxes"]，
  同时调 reconcile 生成 discrepancy_report
"""
from decimal import Decimal
from typing import Optional

from tax_agent.models.tax_data import TaxData
from tax_agent.models.results import CalculationResult, BreakdownItem
from tax_agent.erp.reconcile import compute_taxi_nine_box, reconcile, ReconciliationDelta
from tax_agent.models.erp_models import ERPNineBox


def calculate_uk_vat(data: TaxData, mode: str = "recompute") -> CalculationResult:
    """计算 UK VAT Return 9-box 值

    Box 3 = Box 1 + Box 2
    Box 5 = |Box 3 − Box 4|  (HMRC 要求 netVatDue 必须 ≥ 0)

    mode='reconcile' 时，breakdown 取自 data.metadata['erp_provided_boxes']，
    discrepancy_report 用 T.A.X.I. 算的 9-Box 与 ERP 报的对比。
    """
    # ── reconcile mode ──
    if mode == "reconcile":
        erp_boxes_dict = data.metadata.get("erp_provided_boxes")
        if not erp_boxes_dict:
            # 没传 ERP 9-Box → 退回 recompute
            mode = "recompute"
        else:
            erp_boxes = ERPNineBox.model_validate(erp_boxes_dict)
            sales = data.metadata.get("sales_transactions", [])
            purchases = data.metadata.get("purchase_transactions", [])
            taxi_boxes = compute_taxi_nine_box(sales, purchases)
            delta = reconcile(erp_boxes, taxi_boxes, erp_source=data.metadata.get("source", "unknown"))

            breakdown = [
                BreakdownItem(category="vat_due_sales", amount=erp_boxes.box1_vat_due_sales),
                BreakdownItem(category="vat_due_acquisitions", amount=erp_boxes.box2_vat_due_acquisitions),
                BreakdownItem(category="total_vat_due", amount=erp_boxes.box3_total_vat_due),
                BreakdownItem(category="vat_reclaimed_purchases", amount=erp_boxes.box4_vat_reclaimed),
                BreakdownItem(category="net_vat_due", amount=erp_boxes.box5_net_vat_due),
            ]
            warnings: list[str] = list(delta.notes)
            if (erp_boxes.box3_total_vat_due - erp_boxes.box4_vat_reclaimed) < 0:
                warnings.append("Net VAT due is negative (repayment due from HMRC) — Box 5 shown as positive per HMRC requirements")
            return CalculationResult(
                total_tax_due=erp_boxes.box5_net_vat_due,
                breakdown=breakdown,
                warnings=warnings,
                discrepancy_report=delta,
                compute_mode="reconcile",
            )

    # ── recompute mode (default) ──
    line_map = {li.category: li.amount for li in data.line_items}

    box1 = line_map.get("vat_due_sales", Decimal("0"))
    box2 = line_map.get("vat_due_acquisitions", Decimal("0"))
    box3 = box1 + box2
    box4 = line_map.get("vat_reclaimed_purchases", Decimal("0"))
    box5 = abs(box3 - box4)  # HMRC: netVatDue must be positive

    return CalculationResult(
        total_tax_due=box5,
        breakdown=[
            BreakdownItem(category="vat_due_sales", amount=box1),
            BreakdownItem(category="vat_due_acquisitions", amount=box2),
            BreakdownItem(category="total_vat_due", amount=box3),
            BreakdownItem(category="vat_reclaimed_purchases", amount=box4),
            BreakdownItem(category="net_vat_due", amount=box5),
        ],
        warnings=(
            ["Net VAT due is negative (repayment due from HMRC) — Box 5 shown as positive per HMRC requirements"]
            if (box3 - box4) < 0
            else []
        ),
        discrepancy_report=None,
        compute_mode="recompute",
    )
```

- [ ] **Step 3: Update CalculationResult to include new fields**

修改 `tax_agent/models/results.py` 的 `CalculationResult` 类：

```python
@dataclass
class CalculationResult:
    """计算结果"""
    total_tax_due: Decimal
    breakdown: list[BreakdownItem] = field(default_factory=list)
    deductions: list[DeductionItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    discrepancy_report: Optional["ReconciliationDelta"] = None
    compute_mode: str = "recompute"
```

注意：原文件用的是 `@dataclass` 风格，**不是** Pydantic。**Plan Mode 早期 Explore 代理报错说 models 是 Pydantic — 实际 results.py 是 dataclass。** 继续保持 dataclass 风格，避免破坏现有代码。

- [ ] **Step 4: Add `mode` to adapter base class**

修改 `tax_agent/jurisdictions/__init__.py` `JurisdictionAdapter.calculate` 抽象方法：

```python
@abstractmethod
def calculate(self, tax_type, data, mode: str = "recompute") -> CalculationResult:
    """mode='reconcile' 时返回 discrepancy_report（v0 新增）"""
    ...
```

- [ ] **Step 5: Run existing tests to ensure no regression**

Run: `cd tax_agent && pytest tests/ -v -x`
Expected: 现有测试全 pass

- [ ] **Step 6: Commit**

```bash
cd /root/TAXI
git add tax_agent/jurisdictions/uk/vat/calculator.py tax_agent/jurisdictions/__init__.py tax_agent/models/results.py
git commit -m "feat(uk-vat): calculate_uk_vat supports 'reconcile' mode, discrepancy_report on result"
```

---

## Task 7: Orchestrator 加 _stage_import

**Files:**
- Modify: `tax_agent/orchestrator.py`

- [ ] **Step 1: Read orchestrator.py around line 31**

Read: `tax_agent/orchestrator.py:31-100` (已读过)

- [ ] **Step 2: Modify Orchestrator.run signature**

修改 `tax_agent/orchestrator.py`：

1. 在文件顶部 import 加：
```python
from .models.erp_models import ImportResult
from .erp.erp_samples_loader import load_demo_case
from .erp.csv_parser import parse_csv, CsvParseError
from .erp.audit_events import (
    ERP_IMPORT_STARTED, ERP_IMPORT_PARSED, ERP_IMPORT_FAILED,
)
```

2. 修改 `Orchestrator.run` 签名加 `import_payload: Optional[dict] = None` 形参：
```python
async def run(
    self,
    adapter: JurisdictionAdapter,
    tax_type: TaxType,
    data: TaxData,
    import_payload: Optional[dict] = None,
) -> FilingResult:
    """执行完整申报管线。import_payload 形如:
       {"source": "demo", "case_id": "techflow_q1_2026"}
       或
       {"source": "csv", "csv_bytes_b64": "..."}
    """
    # 阶段 0：IMPORT (新加)
    if import_payload:
        import_result = self._stage_import(filing_id=None_pending, data=data, payload=import_payload)
        if import_result is None:
            # 导入失败
            result = FilingResult(...)
            ...
            return result
```

3. 在 `_stage_precheck` 之前加 `_stage_import` 调用逻辑

4. 在文件底部加 `_stage_import` 方法：

```python
async def _stage_import(
    self, filing_id: str, data: TaxData, payload: dict,
) -> Optional[ImportResult]:
    """新阶段：解析 demo case / CSV → ImportResult，写入 data.metadata。

    失败时返 None + 记录 audit + 抛 FilingStatus.ERROR（由调用方处理）。
    """
    self.audit.record(filing_id, "IMPORT", ERP_IMPORT_STARTED, {"source": payload.get("source")})
    try:
        if payload["source"] == "demo":
            ir = load_demo_case(payload["case_id"])
        elif payload["source"] == "csv":
            import base64
            csv_bytes = base64.b64decode(payload["csv_bytes_b64"])
            ir = parse_csv(csv_bytes, profile=payload.get("profile"))
        else:
            raise ValueError(f"unknown import source: {payload['source']!r}")
    except (DemoCaseNotFoundError, CsvParseError, ValueError) as e:
        self.audit.record(filing_id, "IMPORT", ERP_IMPORT_FAILED, {"error": str(e)})
        return None

    # 写入 TaxData.metadata
    data.metadata["erp_provided_boxes"] = ir.erp_provided_boxes.model_dump(mode="json")
    data.metadata["sales_transactions"] = ir.sales
    data.metadata["purchase_transactions"] = ir.purchases
    data.metadata["source"] = ir.source_profile
    data.metadata["compute_mode"] = data.metadata.get("compute_mode", "reconcile")
    data.metadata["import_warnings"] = ir.warnings
    data.metadata["import_rejected_rows"] = ir.rejected_rows

    self.audit.record(filing_id, "IMPORT", ERP_IMPORT_PARSED, {
        "source_profile": ir.source_profile,
        "sales_count": len(ir.sales),
        "purchases_count": len(ir.purchases),
        "warnings_count": len(ir.warnings),
        "rejected_count": len(ir.rejected_rows),
    })
    return ir
```

- [ ] **Step 3: Run existing tests**

Run: `cd tax_agent && pytest tests/ -v -x`
Expected: 现有测试全 pass（新参数是可选，向后兼容）

- [ ] **Step 4: Commit**

```bash
cd /root/TAXI
git add tax_agent/orchestrator.py
git commit -m "feat(orchestrator): new _stage_import for demo/CSV, writes data.metadata"
```

---

## Task 8: Filings router 响应补 audit_trail + import_summary

**Files:**
- Modify: `tax_agent/server/routers/filings.py:131-161`

- [ ] **Step 1: Read filings.py current submit_filing**

Read: `tax_agent/server/routers/filings.py:119-161` (已读过)

- [ ] **Step 2: Add audit_trail and import_summary to response**

修改 `submit_filing` 函数 (`tax_agent/server/routers/filings.py:119-161`)，在 `filing_record` dict 里加 2 个 key：

```python
filing_record = {
    "filing_id": result.filing_id,
    "status": result.status.value,
    "receipt": { ... },  # 已有
    "errors": [...],  # 已有
    "stage_results": { ... },  # 已有
    "audit_trail": [  # 新加
        {
            "stage": e.stage,
            "action": e.action,
            "detail": e.detail,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in result.audit_trail
    ],
    "import_summary": {  # 新加
        "source": data.metadata.get("source"),
        "compute_mode": data.metadata.get("compute_mode", "reconcile"),
        "sales_count": len(data.metadata.get("sales_transactions", [])),
        "purchases_count": len(data.metadata.get("purchase_transactions", [])),
        "import_warnings": data.metadata.get("import_warnings", []),
        "import_rejected_rows_count": len(data.metadata.get("import_rejected_rows", [])),
    } if data.metadata.get("source") else None,
    "jurisdiction": req.jurisdiction,  # 已有
    "tax_type": req.tax_type,  # 已有
    "period": req.period.model_dump(),  # 已有
    "taxpayer": req.taxpayer.model_dump(),  # 已有
}
```

- [ ] **Step 3: Same for preview_filing**

同样在 `preview_filing` 函数响应里加 `audit_trail` + `import_summary`（不调 orchestrator.run，但可以调 `_stage_import` 直接进 preview）。

- [ ] **Step 4: Run existing tests**

Run: `cd tax_agent && pytest tests/ -v -x`
Expected: 现有测试全 pass（响应字段扩展是加法）

- [ ] **Step 5: Commit**

```bash
cd /root/TAXI
git add tax_agent/server/routers/filings.py
git commit -m "feat(filings): response includes audit_trail + import_summary"
```

---

## Task 9: Agent MCP tools — ingest_erp_data + filter_invoices

**Files:**
- Modify: `tax_agent/jurisdictions/uk/vat/agent_tools.py`

- [ ] **Step 1: Read current agent_tools.py structure**

Read: `tax_agent/jurisdictions/uk/vat/agent_tools.py:56-100` (已读过 — 6 个现有 tools)

- [ ] **Step 2: Add `ingest_erp_data` and `filter_invoices` methods**

修改 `tax_agent/jurisdictions/uk/vat/agent_tools.py`，在 `UKVATAgentToolSet` 类内加 2 个方法（放在 `validate_vat_return` 之后）：

```python
# ── ERP 集成 MCP tools (v0 新加) ──

async def ingest_erp_data(self, source: str, case_id: Optional[str] = None, csv_base64: Optional[str] = None, profile: Optional[str] = None) -> dict:
    """MCP tool: 加载 demo case 或解析 CSV base64。

    Returns: ImportResult (Pydantic dict) + 推荐 case 列表（如 case_id 不存在）。
    """
    from tax_agent.erp.erp_samples_loader import list_demo_cases, load_demo_case, DemoCaseNotFoundError
    from tax_agent.erp.csv_parser import parse_csv, CsvParseError
    import base64

    try:
        if source == "demo":
            if not case_id:
                return _tool_error("case_id is required for source='demo'", detail={"available_cases": list_demo_cases()})
            try:
                ir = load_demo_case(case_id)
            except DemoCaseNotFoundError as e:
                return _tool_error(str(e), detail={"available_cases": list_demo_cases()})
        elif source == "csv":
            if not csv_base64:
                return _tool_error("csv_base64 is required for source='csv'")
            csv_bytes = base64.b64decode(csv_base64)
            if len(csv_bytes) > 10 * 1024 * 1024:
                return _tool_error("file exceeds 10MB limit")
            try:
                ir = parse_csv(csv_bytes, profile=profile)
            except CsvParseError as e:
                return _tool_error(f"CSV parse error: {e}")
        else:
            return _tool_error(f"unknown source: {source!r}")
    except Exception as e:
        return _tool_error(f"unexpected error: {e}")

    return _tool_ok({
        "success": True,
        "import_result": ir.model_dump(mode="json"),
        "summary": {
            "source_profile": ir.source_profile,
            "source_hash": ir.source_hash,
            "sales_count": len(ir.sales),
            "purchases_count": len(ir.purchases),
            "warnings_count": len(ir.warnings),
            "rejected_count": len(ir.rejected_rows),
        },
    })


async def filter_invoices(
    self,
    txn_type: Optional[str] = None,  # "sale" | "purchase" | None
    flagged_only: bool = False,  # 只返有差异的发票（v0 暂未实现，用 reserved）
    invoice_ids: Optional[list[str]] = None,  # 限制到这些 ID
) -> dict:
    """MCP tool: 列出当前 session 里的发票（用 session.uploaded_data 缓存）。

    v0 简化：从 import_result 缓存读，不查 DB。
    """
    # v0 暂不接入 session 缓存 → 返空 + 提示
    return _tool_ok({
        "success": True,
        "invoices": [],
        "note": "v0: InvoiceMultiSelectPanel loads from /api/erp/cases/{case_id} directly, not via this tool",
    })
```

- [ ] **Step 3: Register new tools in get_tool_metadata**

在 `get_tool_metadata` 方法返回的 list 里加 2 个 entry：

```python
{
    "name": "ingest_erp_data",
    "description": "Load demo case (source='demo', case_id='...') or parse CSV (source='csv', csv_base64='...'). Returns ImportResult for the Agent to use in subsequent calculations.",
    "input_schema": {
        "type": "object",
        "properties": {
            "source": {"type": "string", "enum": ["demo", "csv"]},
            "case_id": {"type": "string", "description": "demo case ID, e.g. 'techflow_q1_2026'"},
            "csv_base64": {"type": "string", "description": "base64-encoded CSV bytes"},
            "profile": {"type": "string", "description": "force CSV profile, e.g. 'generic'"},
        },
        "required": ["source"],
    },
},
{
    "name": "filter_invoices",
    "description": "Filter/list invoices from current session's ImportResult. v0 stub — InvoiceMultiSelectPanel uses direct API.",
    "input_schema": {
        "type": "object",
        "properties": {
            "txn_type": {"type": "string", "enum": ["sale", "purchase"]},
            "flagged_only": {"type": "boolean"},
            "invoice_ids": {"type": "array", "items": {"type": "string"}},
        },
    },
},
```

- [ ] **Step 4: Run existing tests**

Run: `cd tax_agent && pytest tests/ -v -x`
Expected: 现有测试全 pass（新方法是加法）

- [ ] **Step 5: Commit**

```bash
cd /root/TAXI
git add tax_agent/jurisdictions/uk/vat/agent_tools.py
git commit -m "feat(uk-vat-mcp): add ingest_erp_data + filter_invoices MCP tools"
```

---

## Task 10: Demo case JSON 数据文件 (3 个)

**Files:**
- Create: `tax_agent/data/erp_samples/techflow_q1_2026.json`
- Create: `tax_agent/data/erp_samples/cross_border_eu_2026.json`
- Create: `tax_agent/data/erp_samples/generic_sales_template.csv`
- Create: `tax_agent/scripts/convert_realcase_to_erp_sample.py`

- [ ] **Step 1: Write the converter script**

创建 `tax_agent/scripts/convert_realcase_to_erp_sample.py`：

```python
"""把 tax_agent/data/realCaseData.json 转成 data/erp_samples/techflow_q1_2026.json

Usage: python -m tax_agent.scripts.convert_realcase_to_erp_sample
"""
import json
from decimal import Decimal
from datetime import date
from pathlib import Path

from tax_agent.models.erp_models import (
    SalesTransaction, PurchaseTransaction, ERPNineBox, ImportResult,
)


REALCASE = Path(__file__).parent.parent / "data" / "realCaseData.json"
OUTPUT = Path(__file__).parent.parent / "data" / "erp_samples" / "techflow_q1_2026.json"


def to_decimal(v) -> Decimal:
    return Decimal(str(v))


def convert_sale(s: dict) -> SalesTransaction:
    return SalesTransaction(
        id=s.get("id", "S-UNKNOWN"),
        txn_date=date.fromisoformat(s["date"]),
        counterparty=s.get("customer", "Unknown"),
        net_amount=to_decimal(s["net"]),
        vat_amount=to_decimal(s["vat"]),
        gross_amount=to_decimal(s["gross"]),
        vat_rate=to_decimal("0.20") if s.get("type", "standard") == "standard" else Decimal("0"),
        tax_code="T1" if s.get("type", "standard") == "standard" else "T0",
        is_eu=s.get("is_eu", False),
        is_reverse_charge=s.get("reverse_charge", False),
    )


def convert_purchase(p: dict) -> PurchaseTransaction:
    return PurchaseTransaction(
        id=p.get("id", "P-UNKNOWN"),
        txn_date=date.fromisoformat(p["date"]),
        counterparty=p.get("supplier", "Unknown"),
        net_amount=to_decimal(p["net"]),
        vat_amount=to_decimal(p["vat"]),
        gross_amount=to_decimal(p["gross"]),
        vat_rate=to_decimal("0.20") if p.get("type", "standard") == "standard" else Decimal("0"),
        tax_code="T1" if p.get("type", "standard") == "standard" else "T0",
        is_recoverable=p.get("recoverable", True),
        is_eu_acquisition=p.get("is_eu", False),
    )


def main():
    raw = json.loads(REALCASE.read_text(encoding="utf-8"))
    sales = [convert_sale(s) for s in raw.get("sales_invoices", [])]
    purchases = [convert_purchase(p) for p in raw.get("purchase_invoices", [])]
    # 9-Box 用 v0 简化计算
    from tax_agent.erp.reconcile import compute_taxi_nine_box
    nine_box = compute_taxi_nine_box(sales, purchases)
    # 故意埋 1 个小差异（demo wow 效果）：ERP 报的 box1 +3.50
    erp_box = nine_box.model_copy(deep=True)
    erp_box.box1_vat_due_sales = erp_box.box1_vat_due_sales + Decimal("3.50")
    ir = ImportResult(
        sales=sales, purchases=purchases,
        erp_provided_boxes=erp_box,
        source_profile="demo",
        source_filename="techflow_q1_2026.json",
        source_hash="techflow-2026-q1",
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(ir.model_dump(mode="json"), indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT} ({len(sales)} sales, {len(purchases)} purchases)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the converter**

Run: `cd tax_agent && python -m tax_agent.scripts.convert_realcase_to_erp_sample`
Expected: `Wrote .../techflow_q1_2026.json (26 sales, 22 purchases)`

- [ ] **Step 3: Verify the JSON file**

Run: `python -c "from tax_agent.erp.erp_samples_loader import load_demo_case; r = load_demo_case('techflow_q1_2026'); print(r.erp_provided_boxes.box1_vat_due_sales)"`
Expected: prints Decimal value (42520.00 + 3.50 = 42523.50)

- [ ] **Step 4: Write cross_border_eu_2026.json by hand**

创建 `tax_agent/data/erp_samples/cross_border_eu_2026.json` (手工构造 ~10KB)：

```json
{
  "sales": [
    {"id": "S-EU-001", "txn_date": "2026-01-15", "counterparty": "Deutsche GmbH (DE)", "net_amount": "5000.00", "vat_amount": "0.00", "gross_amount": "5000.00", "vat_rate": "0.00", "tax_code": "T9", "is_eu": true},
    {"id": "S-EU-002", "txn_date": "2026-01-20", "counterparty": "French SARL (FR)", "net_amount": "3000.00", "vat_amount": "0.00", "gross_amount": "3000.00", "vat_rate": "0.00", "tax_code": "T9", "is_eu": true}
  ],
  "purchases": [
    {"id": "P-EU-001", "txn_date": "2026-01-18", "counterparty": "Italian SpA (IT)", "net_amount": "2000.00", "vat_amount": "0.00", "gross_amount": "2000.00", "vat_rate": "0.00", "tax_code": "T2", "is_recoverable": true, "is_eu_acquisition": true}
  ],
  "erp_provided_boxes": {
    "box1_vat_due_sales": "0.00", "box2_vat_due_acquisitions": "0.00",
    "box3_total_vat_due": "0.00", "box4_vat_reclaimed": "0.00",
    "box5_net_vat_due": "0.00",
    "box6_total_sales_ex_vat": 8000, "box7_total_purchases_ex_vat": 2000,
    "box8_total_goods_supplied_eu": 8000, "box9_total_goods_acquired_eu": 2000,
    "scheme_flags": []
  },
  "source_profile": "demo",
  "source_filename": "cross_border_eu_2026.json",
  "source_hash": "cross-border-eu-2026"
}
```

- [ ] **Step 5: Write generic_sales_template.csv by hand**

创建 `tax_agent/data/erp_samples/generic_sales_template.csv`：

```csv
txn_date,txn_type,counterparty,net,vat,gross,vat_rate,tax_code
2026-01-10,sale,ACME Corp,1000.00,200.00,1200.00,0.20,T1
2026-01-15,sale,Beta Ltd,500.00,100.00,600.00,0.20,T1
2026-01-20,sale,Gamma Inc,0.00,0.00,0.00,0.00,T0
2026-01-25,purchase,Office Supplies,200.00,40.00,240.00,0.20,T1
2026-01-30,purchase,Utilities Co,100.00,20.00,120.00,0.20,T1
```

- [ ] **Step 6: Run all erp tests**

Run: `cd tax_agent && pytest tests/erp/ -v`
Expected: all pass (test_erp_samples_loader 之前失败的现在通过)

- [ ] **Step 7: Commit**

```bash
cd /root/TAXI
git add tax_agent/data/erp_samples/ tax_agent/scripts/convert_realcase_to_erp_sample.py
git commit -m "feat(data): 3 demo case files (techflow Q1, cross-border EU, generic CSV template)"
```

---

## Task 11: 前端 — erp namespace in client.ts + 新 types

**Files:**
- Modify: `tax_agent/frontend/src/api/client.ts`
- Modify: `tax_agent/frontend/src/types/index.ts`

- [ ] **Step 1: Read current client.ts structure**

Read: `tax_agent/frontend/src/api/client.ts:1-60` (已读过)

- [ ] **Step 2: Add erp namespace to client.ts**

修改 `tax_agent/frontend/src/api/client.ts`：

在 import 区域加：
```typescript
import type {
  ImportResult, ReconciliationDelta, DemoCaseSummary,
} from '../types';
```

在 `api` 对象里加 `erp` 命名空间（紧跟 `channel` 之后）：
```typescript
erp: {
  listCases: () =>
    fetchApi<{ cases: string[] }>('/api/erp/cases'),
  getCase: (caseId: string) =>
    fetchApi<ImportResult>(`/api/erp/cases/${encodeURIComponent(caseId)}`),
  importCsv: (file: File, profile?: string) => {
    const form = new FormData();
    form.append('file', file);
    if (profile) form.append('profile', profile);
    return fetchApi<ImportResult>('/api/erp/import', { method: 'POST', body: form });
  },
  reconcile: (importResult: ImportResult, erpSource: string) =>
    fetchApi<ReconciliationDelta>('/api/erp/reconcile', {
      method: 'POST',
      body: JSON.stringify({ import_result: importResult, erp_source: erpSource }),
    }),
},
```

- [ ] **Step 3: Add new types**

修改 `tax_agent/frontend/src/types/index.ts`，在文件末尾加：

```typescript
// ERP integration types (v0)
export interface SalesTransaction {
  id: string;
  txn_date: string;
  counterparty: string;
  net_amount: string;
  vat_amount: string;
  gross_amount: string;
  vat_rate: string;
  tax_code: string;
  is_eu?: boolean;
  is_reverse_charge?: boolean;
}

export interface PurchaseTransaction {
  id: string;
  txn_date: string;
  counterparty: string;
  net_amount: string;
  vat_amount: string;
  gross_amount: string;
  vat_rate: string;
  tax_code: string;
  is_recoverable?: boolean;
  is_eu_acquisition?: boolean;
}

export interface ERPNineBox {
  box1_vat_due_sales: string;
  box2_vat_due_acquisitions: string;
  box3_total_vat_due: string;
  box4_vat_reclaimed: string;
  box5_net_vat_due: string;
  box6_total_sales_ex_vat: number;
  box7_total_purchases_ex_vat: number;
  box8_total_goods_supplied_eu: number;
  box9_total_goods_acquired_eu: number;
  scheme_flags?: string[];
}

export interface ImportResult {
  sales: SalesTransaction[];
  purchases: PurchaseTransaction[];
  erp_provided_boxes: ERPNineBox;
  source_profile: string;
  source_filename: string;
  source_hash: string;
  warnings?: string[];
  rejected_rows?: Array<{ row_index: number; reason: string; raw: Record<string, string> }>;
}

export interface ReconciliationDelta {
  box_diffs: Record<string, string>;
  total_abs_diff: string;
  within_tolerance: boolean;
  erp_source: string;
  notes: string[];
}

export interface DemoCaseSummary {
  id: string;
  title: string;
  description: string;
}

export interface ImportSummary {
  source?: string;
  compute_mode: string;
  sales_count: number;
  purchases_count: number;
  import_warnings: string[];
  import_rejected_rows_count: number;
}
```

- [ ] **Step 4: Verify build**

Run: `cd tax_agent/frontend && npm run build`
Expected: 0 type errors

- [ ] **Step 5: Commit**

```bash
cd /root/TAXI
git add tax_agent/frontend/src/api/client.ts tax_agent/frontend/src/types/index.ts
git commit -m "feat(frontend): erp API namespace + 7 new types (ImportResult, ERPNineBox, ...)"
```

---

## Task 12: 前端 — ErpConnectionToggle + ClearDataButton + demoStore 扩展

**Files:**
- Create: `tax_agent/frontend/src/components/ErpConnectionToggle.tsx`
- Create: `tax_agent/frontend/src/components/ClearDataButton.tsx`
- Modify: `tax_agent/frontend/src/stores/demoStore.ts`

- [ ] **Step 1: Extend demoStore with clearAll**

修改 `tax_agent/frontend/src/stores/demoStore.ts`：

```typescript
import { create } from 'zustand';

interface DemoState {
  selectedPreset: string | null;
  erpConnectionOn: boolean;
  setSelectedPreset: (preset: string | null) => void;
  setErpConnection: (on: boolean) => void;
  clearAll: () => void;
}

export const useDemoStore = create<DemoState>((set) => ({
  selectedPreset: null,
  erpConnectionOn: false,
  setSelectedPreset: (preset) => set({ selectedPreset: preset }),
  setErpConnection: (on) => set({ erpConnectionOn: on }),
  clearAll: () => {
    set({ selectedPreset: null, erpConnectionOn: false });
    // 同步清 localStorage
    if (typeof window !== 'undefined') {
      try {
        Object.keys(localStorage)
          .filter((k) => k.startsWith('taxi:') || k.startsWith('tax_agent:'))
          .forEach((k) => localStorage.removeItem(k));
      } catch (e) {
        // localStorage 不可用，忽略
      }
    }
  },
}));
```

- [ ] **Step 2: Write ErpConnectionToggle component**

创建 `tax_agent/frontend/src/components/ErpConnectionToggle.tsx`：

```tsx
import { GlobeAltIcon, InformationCircleIcon } from '@heroicons/react/24/outline';
import { useDemoStore } from '../stores/demoStore';

export default function ErpConnectionToggle() {
  const erpOn = useDemoStore((s) => s.erpConnectionOn);
  const setErp = useDemoStore((s) => s.setErpConnection);

  return (
    <div className="card p-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <GlobeAltIcon className="w-5 h-5 text-fg-muted" />
        <div>
          <p className="text-sm font-medium text-fg">接入 ERP</p>
          <p className="text-xs text-fg-dim">
            {erpOn ? '未来从 ERPNext 实时拉取' : '当前走 Demo Case 数据'}
          </p>
        </div>
      </div>
      <label className="inline-flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={erpOn}
          onChange={(e) => setErp(e.target.checked)}
          className="sr-only"
        />
        <span
          className={`relative inline-block w-10 h-5 rounded-full transition-colors ${
            erpOn ? 'bg-accent' : 'bg-bg-elevated'
          }`}
        >
          <span
            className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
              erpOn ? 'translate-x-5' : 'translate-x-0.5'
            }`}
          />
        </span>
      </label>
      {erpOn && (
        <div className="ml-3 flex items-center gap-1 text-xs text-warning">
          <InformationCircleIcon className="w-4 h-4" />
          <span>Coming soon — v0 仍走 Demo Case</span>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Write ClearDataButton component**

创建 `tax_agent/frontend/src/components/ClearDataButton.tsx`：

```tsx
import { useState } from 'react';
import { TrashIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import { useDemoStore } from '../stores/demoStore';

export default function ClearDataButton() {
  const clearAll = useDemoStore((s) => s.clearAll);
  const [confirming, setConfirming] = useState(false);
  const [cleared, setCleared] = useState(false);

  const handleClear = () => {
    clearAll();
    setCleared(true);
    setTimeout(() => {
      setConfirming(false);
      setCleared(false);
    }, 1500);
  };

  if (confirming) {
    return (
      <div className="flex items-center gap-2 p-2 rounded-lg border border-error/30 bg-error-muted">
        <ExclamationTriangleIcon className="w-5 h-5 text-error shrink-0" />
        <p className="text-xs text-error flex-1">
          清空所有 demo 数据 + Agent 上传数据？此操作不可撤销。
        </p>
        <button
          onClick={handleClear}
          className="btn btn-sm bg-error text-white hover:bg-error/90"
          disabled={cleared}
        >
          {cleared ? '已清空' : '确认清空'}
        </button>
        <button
          onClick={() => setConfirming(false)}
          className="btn btn-sm btn-ghost"
          disabled={cleared}
        >
          取消
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={() => setConfirming(true)}
      className="btn btn-ghost text-fg-dim hover:text-error"
      title="清空当前 demo 数据"
    >
      <TrashIcon className="w-4 h-4" />
      清空数据
    </button>
  );
}
```

- [ ] **Step 4: Verify build**

Run: `cd tax_agent/frontend && npm run build`
Expected: 0 type errors

- [ ] **Step 5: Commit**

```bash
cd /root/TAXI
git add tax_agent/frontend/src/stores/demoStore.ts tax_agent/frontend/src/components/ErpConnectionToggle.tsx tax_agent/frontend/src/components/ClearDataButton.tsx
git commit -m "feat(frontend): ErpConnectionToggle + ClearDataButton + demoStore.clearAll"
```

---

## Task 13: 前端 — DashboardPage 集成 3 控件 + CasePresetCard 选中高亮

**Files:**
- Modify: `tax_agent/frontend/src/pages/DashboardPage.tsx`
- Modify: `tax_agent/frontend/src/components/CasePresetCard.tsx`

- [ ] **Step 1: Read CasePresetCard.tsx**

Read: `tax_agent/frontend/src/components/CasePresetCard.tsx` (已读过)

- [ ] **Step 2: Modify CasePresetCard to support selected state**

修改 `tax_agent/frontend/src/components/CasePresetCard.tsx`：

```tsx
import { FileText, TrendingDown, CircleDashed, AlertTriangle, CircleDot, Building2, CheckCircleIcon } from 'lucide-react';
import type { CasePreset } from '../data/casePresets';

interface CasePresetCardProps {
  preset: CasePreset;
  onLoad: (preset: CasePreset) => void;
  isSelected?: boolean;  // 新加
}

const iconMap: Record<string, React.ElementType> = {
  FileText, TrendingDown, CircleDashed, AlertTriangle, Building2,
};

export default function CasePresetCard({ preset, onLoad, isSelected = false }: CasePresetCardProps) {
  const Icon = iconMap[preset.icon] || CircleDot;

  return (
    <div
      className={`bg-white rounded-xl border p-5 transition-all duration-200 flex flex-col gap-4 ${
        isSelected
          ? 'border-accent ring-2 ring-accent/30 shadow-md'
          : 'border-gray-200 hover:shadow-md'
      }`}
    >
      <div className="flex items-start gap-4">
        <div className="w-11 h-11 rounded-lg bg-blue-50 flex items-center justify-center shrink-0">
          <Icon className="w-5 h-5 text-blue-600" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-medium text-gray-900">{preset.title}</h3>
            {isSelected && (
              <span className="inline-flex items-center gap-1 text-xs font-medium text-accent bg-accent-muted px-2 py-0.5 rounded-full">
                <CheckCircleIcon className="w-3 h-3" />
                已加载
              </span>
            )}
          </div>
          <p className="text-sm text-gray-500 mt-1">{preset.description}</p>
        </div>
      </div>
      <button
        type="button"
        onClick={() => onLoad(preset)}
        className="w-full py-2 px-4 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 active:bg-blue-800 transition-colors duration-200"
      >
        {isSelected ? '重新加载此 Case' : '加载此 Case'}
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Modify DashboardPage to integrate 3 new controls**

修改 `tax_agent/frontend/src/pages/DashboardPage.tsx`：

1. import 加：
```tsx
import ErpConnectionToggle from '../components/ErpConnectionToggle'
import ClearDataButton from '../components/ClearDataButton'
```

2. 在 `handleLoadCase` 函数下方加 `handleSwitchCase`：
```tsx
const handleSwitchCase = (preset: CasePreset) => {
  if (window.confirm(`切换到 "${preset.title}"？当前数据将被清空。`)) {
    setSelectedPreset(null)
    handleLoadCase(preset)
  }
}
```

3. 修改 `handleLoadCase` 接受可选 `clearFirst` 参数：
```tsx
const handleLoadCase = (preset: CasePreset) => {
  setSelectedPreset(preset.id)
  navigate('/filings/new', { state: { presetId: preset.id } })
}
```

4. 在 Dashboard JSX 顶部（`<h2>快速演示场景</h2>` 上方）加：
```tsx
{/* Dashboard 控件三件套 (v0 修订) */}
<div className="flex items-center justify-between gap-4 fade-in">
  <div className="flex-1">
    <ErpConnectionToggle />
  </div>
  <ClearDataButton />
</div>

{selectedPreset && (
  <div className="card p-4 flex items-center justify-between fade-in">
    <p className="text-sm text-fg-muted">
      已加载 Case: <span className="font-medium text-fg">
        {casePresets.find(p => p.id === selectedPreset)?.title}
      </span>
    </p>
    <button
      onClick={() => {
        const cur = casePresets.find(p => p.id === selectedPreset)
        if (cur) handleSwitchCase(cur)
      }}
      className="btn btn-sm btn-ghost"
    >
      切换 Case
    </button>
  </div>
)}
```

5. 修改 case 网格渲染，把 `handleLoadCase` 改为 `handleSwitchCase`（如果已选），并传 `isSelected`：
```tsx
{casePresets.map((preset) => (
  <CasePresetCard
    key={preset.id}
    preset={preset}
    onLoad={preset.id === selectedPreset ? handleSwitchCase : handleLoadCase}
    isSelected={preset.id === selectedPreset}
  />
))}
```

- [ ] **Step 4: Verify build**

Run: `cd tax_agent/frontend && npm run build`
Expected: 0 type errors

- [ ] **Step 5: Commit**

```bash
cd /root/TAXI
git add tax_agent/frontend/src/pages/DashboardPage.tsx tax_agent/frontend/src/components/CasePresetCard.tsx
git commit -m "feat(frontend): Dashboard 三件套 (ERP toggle + clear + 切换) + CasePresetCard 选中高亮"
```

---

## Task 14: 前端 — QuickActionButton + AgentChatPage 加 2 个一键按钮

**Files:**
- Create: `tax_agent/frontend/src/components/QuickActionButton.tsx`
- Modify: `tax_agent/frontend/src/pages/AgentChatPage.tsx`

- [ ] **Step 1: Write QuickActionButton component**

创建 `tax_agent/frontend/src/components/QuickActionButton.tsx`：

```tsx
import type { ReactNode } from 'react';

interface QuickActionButtonProps {
  icon: ReactNode;
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary';
  disabled?: boolean;
}

export default function QuickActionButton({
  icon, label, onClick, variant = 'secondary', disabled = false,
}: QuickActionButtonProps) {
  const baseClass = 'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors';
  const variantClass = variant === 'primary'
    ? 'bg-accent text-white hover:bg-accent/90'
    : 'bg-bg-elevated text-fg hover:bg-bg-elevated/80 border border-fg-dim/20';

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`${baseClass} ${variantClass} ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      {icon}
      {label}
    </button>
  );
}
```

- [ ] **Step 2: Read AgentChatPage to find where to insert quick actions**

Read: `tax_agent/frontend/src/pages/AgentChatPage.tsx:60-80` (输入框附近)

- [ ] **Step 3: Add quick action buttons + case summary banner**

修改 `tax_agent/frontend/src/pages/AgentChatPage.tsx`：

1. import 加：
```tsx
import { MagnifyingGlassIcon, ChartBarIcon } from '@heroicons/react/24/outline'
import QuickActionButton from '../components/QuickActionButton'
import { useDemoStore } from '../stores/demoStore'
import { casePresets } from '../data/casePresets'
```

2. 在组件内（已有 hooks 之后）加：
```tsx
const selectedPreset = useDemoStore((s) => s.selectedPreset)
const currentCase = selectedPreset
  ? casePresets.find((p) => p.id === selectedPreset)
  : null

const handleAnalyzeData = () => {
  if (!currentCase) {
    alert('请先在 Dashboard 选择一个 Demo Case')
    return
  }
  setInput('帮我分析目前的财务数据')
  // 自动发送（调 setInput + 模拟 Enter）
  setTimeout(() => {
    const form = document.querySelector('form') as HTMLFormElement
    form?.requestSubmit()
  }, 100)
}

const handleCalculateAndFile = () => {
  if (!currentCase) {
    alert('请先在 Dashboard 选择一个 Demo Case')
    return
  }
  setInput('帮我计算本年增值税并申报')
  setTimeout(() => {
    const form = document.querySelector('form') as HTMLFormElement
    form?.requestSubmit()
  }, 100)
}
```

3. 在 chat 消息列表上方（`<ChatBubbleLeftRightIcon>` 后面）加 case banner + 一键按钮：
```tsx
{/* Case summary banner */}
{currentCase && (
  <div className="card p-3 flex items-center gap-2 fade-in">
    <BuildingOfficeIcon className="w-5 h-5 text-fg-muted" />
    <p className="text-sm text-fg-muted">
      当前 Case: <span className="font-medium text-fg">{currentCase.title}</span>
    </p>
  </div>
)}

{/* Quick action buttons */}
{currentCase && (
  <div className="flex gap-2 fade-in">
    <QuickActionButton
      icon={<MagnifyingGlassIcon className="w-4 h-4" />}
      label="🔍 帮我分析目前的财务数据"
      onClick={handleAnalyzeData}
    />
    <QuickActionButton
      icon={<ChartBarIcon className="w-4 h-4" />}
      label="📊 帮我计算本年增值税并申报"
      onClick={handleCalculateAndFile}
      variant="primary"
    />
  </div>
)}
```

- [ ] **Step 4: Verify build**

Run: `cd tax_agent/frontend && npm run build`
Expected: 0 type errors

- [ ] **Step 5: Commit**

```bash
cd /root/TAXI
git add tax_agent/frontend/src/components/QuickActionButton.tsx tax_agent/frontend/src/pages/AgentChatPage.tsx
git commit -m "feat(agent-chat): case summary banner + 2 quick action buttons (analyze + calculate-and-file)"
```

---

## Task 15: 前端 — InvoiceMultiSelectPanel + ErrorTableCard + NineBoxDiffTable

**Files:**
- Create: `tax_agent/frontend/src/components/InvoiceMultiSelectPanel.tsx`
- Create: `tax_agent/frontend/src/components/ErrorTableCard.tsx`
- Create: `tax_agent/frontend/src/components/NineBoxDiffTable.tsx`

- [ ] **Step 1: Write ErrorTableCard component**

创建 `tax_agent/frontend/src/components/ErrorTableCard.tsx`：

```tsx
import { ExclamationTriangleIcon } from '@heroicons/react/24/outline';

interface ErrorTableCardProps {
  errorCode: string;
  errorMessage: string;
  tool: string;
  timestamp: string;
  suggestions: string[];
}

export default function ErrorTableCard({
  errorCode, errorMessage, tool, timestamp, suggestions,
}: ErrorTableCardProps) {
  return (
    <div className="my-2 border border-error/30 rounded-lg overflow-hidden">
      <div className="bg-error-muted px-4 py-2 flex items-center gap-2">
        <ExclamationTriangleIcon className="w-5 h-5 text-error" />
        <p className="font-medium text-error">❌ 出错</p>
      </div>
      <table className="w-full text-sm">
        <tbody>
          <tr className="border-t border-error/10">
            <td className="px-4 py-2 text-fg-dim w-1/4">错误码</td>
            <td className="px-4 py-2 font-mono text-fg">{errorCode}</td>
          </tr>
          <tr className="border-t border-error/10">
            <td className="px-4 py-2 text-fg-dim">错误信息</td>
            <td className="px-4 py-2 text-fg">{errorMessage}</td>
          </tr>
          <tr className="border-t border-error/10">
            <td className="px-4 py-2 text-fg-dim">工具</td>
            <td className="px-4 py-2 font-mono text-fg">{tool}</td>
          </tr>
          <tr className="border-t border-error/10">
            <td className="px-4 py-2 text-fg-dim">时间</td>
            <td className="px-4 py-2 font-mono text-fg-dim">{timestamp}</td>
          </tr>
        </tbody>
      </table>
      {suggestions.length > 0 && (
        <div className="px-4 py-2 border-t border-error/10 bg-bg-elevated">
          <p className="text-xs text-fg-dim mb-1">💡 建议操作</p>
          <ul className="text-sm text-fg space-y-1">
            {suggestions.map((s, i) => (
              <li key={i}>• {s}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Write NineBoxDiffTable component**

创建 `tax_agent/frontend/src/components/NineBoxDiffTable.tsx`：

```tsx
import type { ERPNineBox, ReconciliationDelta } from '../types';
import { CheckCircleIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';

interface NineBoxDiffTableProps {
  erpBoxes: ERPNineBox;
  taxiBoxes: ERPNineBox;
  delta: ReconciliationDelta;
  tolerance?: number;
}

const BOX_LABELS: Array<[string, string, keyof ERPNineBox]> = [
  ['box1', 'Box 1 (销项 VAT)', 'box1_vat_due_sales'],
  ['box2', 'Box 2 (EC 进项 VAT)', 'box2_vat_due_acquisitions'],
  ['box3', 'Box 3 (VAT 合计)', 'box3_total_vat_due'],
  ['box4', 'Box 4 (进项抵扣)', 'box4_vat_reclaimed'],
  ['box5', 'Box 5 (净 VAT)', 'box5_net_vat_due'],
  ['box6', 'Box 6 (总销额 £)', 'box6_total_sales_ex_vat'],
  ['box7', 'Box 7 (总采额 £)', 'box7_total_purchases_ex_vat'],
  ['box8', 'Box 8 (对欧供货 £)', 'box8_total_goods_supplied_eu'],
  ['box9', 'Box 9 (欧进采购 £)', 'box9_total_goods_acquired_eu'],
];

function formatAmount(value: string | number, isInt: boolean): string {
  if (isInt) return String(value);
  return Number(value).toFixed(2);
}

function isIntBox(boxKey: string): boolean {
  return boxKey.startsWith('box6') || boxKey.startsWith('box7')
      || boxKey.startsWith('box8') || boxKey.startsWith('box9');
}

export default function NineBoxDiffTable({
  erpBoxes, taxiBoxes, delta, tolerance = 0.5,
}: NineBoxDiffTableProps) {
  return (
    <div className="my-2 border border-fg-dim/20 rounded-lg overflow-hidden">
      <div className="bg-bg-elevated px-4 py-2 flex items-center justify-between">
        <p className="font-medium text-fg">📊 9-Box 复核结果</p>
        <p className={`text-xs ${delta.within_tolerance ? 'text-success' : 'text-warning'}`}>
          tolerance £{tolerance.toFixed(2)} · 总差异 £{Number(delta.total_abs_diff).toFixed(2)}
          {delta.within_tolerance ? ' ✅' : ' ⚠️'}
        </p>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-bg-elevated/50 text-xs text-fg-dim">
            <th className="px-3 py-2 text-left">Box</th>
            <th className="px-3 py-2 text-right">ERP 算的</th>
            <th className="px-3 py-2 text-right">T.A.X.I. 算的</th>
            <th className="px-3 py-2 text-right">差异</th>
            <th className="px-3 py-2 text-center">状态</th>
          </tr>
        </thead>
        <tbody>
          {BOX_LABELS.map(([key, label, erpKey]) => {
            const isInt = isIntBox(key);
            const erpVal = erpBoxes[erpKey] as any;
            const taxiVal = taxiBoxes[erpKey] as any;
            const diff = Number(delta.box_diffs[key] || 0);
            const overTolerance = Math.abs(diff) > tolerance;
            return (
              <tr
                key={key}
                className={`border-t border-fg-dim/10 ${
                  overTolerance ? 'bg-error-muted animate-pulse' : ''
                }`}
              >
                <td className="px-3 py-2 text-fg-dim">{label}</td>
                <td className="px-3 py-2 text-right font-mono text-fg">
                  {formatAmount(erpVal, isInt)}
                </td>
                <td className="px-3 py-2 text-right font-mono text-fg">
                  {formatAmount(taxiVal, isInt)}
                </td>
                <td className={`px-3 py-2 text-right font-mono ${
                  overTolerance ? 'text-error font-semibold' : 'text-fg-dim'
                }`}>
                  {diff >= 0 ? '+' : ''}{diff.toFixed(isInt ? 0 : 2)}
                </td>
                <td className="px-3 py-2 text-center">
                  {overTolerance ? (
                    <ExclamationTriangleIcon className="w-4 h-4 text-error inline" />
                  ) : (
                    <CheckCircleIcon className="w-4 h-4 text-success inline" />
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {!delta.within_tolerance && (
        <div className="px-4 py-2 border-t border-error/20 bg-error-muted text-xs text-error">
          ⚠️ 差异超 tolerance: {delta.notes.join('; ')}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Write InvoiceMultiSelectPanel component**

创建 `tax_agent/frontend/src/components/InvoiceMultiSelectPanel.tsx`：

```tsx
import { useState } from 'react';
import { XMarkIcon, PaperAirplaneIcon } from '@heroicons/react/24/outline';
import type { SalesTransaction, PurchaseTransaction } from '../types';

interface InvoiceMultiSelectPanelProps {
  invoices: Array<SalesTransaction | PurchaseTransaction>;
  invoiceType: 'sale' | 'purchase';
  onSend: (selectedIds: string[]) => void;
  onClose: () => void;
}

export default function InvoiceMultiSelectPanel({
  invoices, invoiceType, onSend, onClose,
}: InvoiceMultiSelectPanelProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };

  const toggleAll = () => {
    if (selected.size === invoices.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(invoices.map((i) => i.id)));
    }
  };

  const totalNet = invoices
    .filter((i) => selected.has(i.id))
    .reduce((sum, i) => sum + Number(i.net_amount), 0);
  const totalVat = invoices
    .filter((i) => selected.has(i.id))
    .reduce((sum, i) => sum + Number(i.vat_amount), 0);

  return (
    <div className="my-2 border border-fg-dim/30 rounded-lg overflow-hidden bg-bg-elevated">
      <div className="px-4 py-2 flex items-center justify-between border-b border-fg-dim/20">
        <p className="font-medium text-fg">
          选择{invoiceType === 'sale' ? '销售' : '采购'}发票 ({invoices.length} 张可选)
        </p>
        <button onClick={onClose} className="text-fg-dim hover:text-fg">
          <XMarkIcon className="w-5 h-5" />
        </button>
      </div>

      <div className="max-h-80 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="bg-bg sticky top-0">
            <tr className="text-xs text-fg-dim">
              <th className="px-3 py-2 text-left w-10">
                <input
                  type="checkbox"
                  checked={selected.size === invoices.length && invoices.length > 0}
                  onChange={toggleAll}
                />
              </th>
              <th className="px-3 py-2 text-left">ID</th>
              <th className="px-3 py-2 text-left">日期</th>
              <th className="px-3 py-2 text-left">对方</th>
              <th className="px-3 py-2 text-right">净额</th>
              <th className="px-3 py-2 text-right">VAT</th>
              <th className="px-3 py-2 text-right">总额</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((inv) => (
              <tr
                key={inv.id}
                className={`border-t border-fg-dim/10 cursor-pointer hover:bg-bg-elevated/50 ${
                  selected.has(inv.id) ? 'bg-accent-muted' : ''
                }`}
                onClick={() => toggle(inv.id)}
              >
                <td className="px-3 py-2">
                  <input
                    type="checkbox"
                    checked={selected.has(inv.id)}
                    onChange={() => toggle(inv.id)}
                    onClick={(e) => e.stopPropagation()}
                  />
                </td>
                <td className="px-3 py-2 font-mono text-xs text-fg">{inv.id}</td>
                <td className="px-3 py-2 text-fg-dim">{inv.txn_date}</td>
                <td className="px-3 py-2 text-fg">{inv.counterparty}</td>
                <td className="px-3 py-2 text-right font-mono text-fg">
                  £{Number(inv.net_amount).toFixed(2)}
                </td>
                <td className="px-3 py-2 text-right font-mono text-fg">
                  £{Number(inv.vat_amount).toFixed(2)}
                </td>
                <td className="px-3 py-2 text-right font-mono text-fg">
                  £{Number(inv.gross_amount).toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="px-4 py-3 border-t border-fg-dim/20 flex items-center justify-between bg-bg">
        <p className="text-sm text-fg-muted">
          已选 <span className="font-medium text-fg">{selected.size}</span> 张 · 净额
          <span className="font-mono ml-1 text-fg">£{totalNet.toFixed(2)}</span> ·
          VAT <span className="font-mono ml-1 text-fg">£{totalVat.toFixed(2)}</span>
        </p>
        <button
          onClick={() => onSend(Array.from(selected))}
          disabled={selected.size === 0}
          className="btn btn-sm btn-primary disabled:opacity-50"
        >
          <PaperAirplaneIcon className="w-4 h-4" />
          发送选中的发票
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Verify build**

Run: `cd tax_agent/frontend && npm run build`
Expected: 0 type errors

- [ ] **Step 5: Commit**

```bash
cd /root/TAXI
git add tax_agent/frontend/src/components/ErrorTableCard.tsx tax_agent/frontend/src/components/NineBoxDiffTable.tsx tax_agent/frontend/src/components/InvoiceMultiSelectPanel.tsx
git commit -m "feat(frontend): InvoiceMultiSelectPanel + ErrorTableCard + NineBoxDiffTable"
```

---

## Task 16: 前端 — AgentChatPage 集成 Panel/Card/Table

**Files:**
- Modify: `tax_agent/frontend/src/pages/AgentChatPage.tsx`

- [ ] **Step 1: Add state for panel and result cards**

修改 `tax_agent/frontend/src/pages/AgentChatPage.tsx`：

1. import 加：
```tsx
import InvoiceMultiSelectPanel from '../components/InvoiceMultiSelectPanel'
import ErrorTableCard from '../components/ErrorTableCard'
import NineBoxDiffTable from '../components/NineBoxDiffTable'
import { api } from '../api/client'
import type { ImportResult, ReconciliationDelta, ERPNineBox } from '../types'
```

2. 在 `useState` 区加新 state：
```tsx
const [showInvoicePanel, setShowInvoicePanel] = useState<{ type: 'sale' | 'purchase' } | null>(null)
const [importResult, setImportResult] = useState<ImportResult | null>(null)
const [lastDiff, setLastDiff] = useState<{ erp: ERPNineBox; taxi: ERPNineBox; delta: ReconciliationDelta } | null>(null)
```

3. 加载 case 数据 effect（在 `useEffect` 块附近）：
```tsx
useEffect(() => {
  if (selectedPreset && !importResult) {
    api.erp.getCase(selectedPreset)
      .then(setImportResult)
      .catch((err) => console.error('Failed to load case:', err))
  }
}, [selectedPreset, importResult])
```

4. 找到 chat 消息渲染区（在 messages 数组的 `.map((msg) =>` 里），加 Panel 渲染逻辑：
```tsx
{showInvoicePanel && importResult && (
  <InvoiceMultiSelectPanel
    invoices={showInvoicePanel.type === 'sale' ? importResult.sales : importResult.purchases}
    invoiceType={showInvoicePanel.type}
    onSend={(ids) => {
      setShowInvoicePanel(null)
      const idList = ids.join(', ')
      setInput(`我选了这些发票: ${idList}`)
    }}
    onClose={() => setShowInvoicePanel(null)}
  />
)}

{/* 错误卡片示例：在消息内容包含 'error_table' 标记时 */}
{lastDiff && <NineBoxDiffTable {...lastDiff} />}
```

5. 加一个临时触发按钮（仅 dev 演示用）— 在 chat 输入框附近：
```tsx
<button
  onClick={() => setShowInvoicePanel({ type: 'sale' })}
  className="btn btn-sm btn-ghost"
  disabled={!importResult}
  title="开发演示用: 打开发票多选面板"
>
  📋 选择发票 (dev)
</button>
```

- [ ] **Step 2: Verify build**

Run: `cd tax_agent/frontend && npm run build`
Expected: 0 type errors

- [ ] **Step 3: Commit**

```bash
cd /root/TAXI
git add tax_agent/frontend/src/pages/AgentChatPage.tsx
git commit -m "feat(agent-chat): integrate InvoiceMultiSelectPanel + NineBoxDiffTable + load case data"
```

---

## Task 17: 前端 — CsvImportWizard

**Files:**
- Create: `tax_agent/frontend/src/components/CsvImportWizard.tsx`

- [ ] **Step 1: Write CsvImportWizard component**

创建 `tax_agent/frontend/src/components/CsvImportWizard.tsx`：

```tsx
import { useState } from 'react';
import { CloudArrowUpIcon, XMarkIcon, ExclamationCircleIcon } from '@heroicons/react/24/outline';
import { api } from '../api/client';
import type { ImportResult } from '../types';

interface CsvImportWizardProps {
  onImported: (result: ImportResult) => void;
  onClose: () => void;
}

export default function CsvImportWizard({ onImported, onClose }: CsvImportWizardProps) {
  const [file, setFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);

  const handleFile = (f: File) => {
    if (f.size > 10 * 1024 * 1024) {
      setError('文件超过 10MB 上限');
      return;
    }
    setFile(f);
    setError(null);
    setResult(null);
  };

  const handleImport = async () => {
    if (!file) return;
    setImporting(true);
    setError(null);
    try {
      const ir = await api.erp.importCsv(file);
      setResult(ir);
    } catch (err: any) {
      setError(err?.message || '导入失败');
    } finally {
      setImporting(false);
    }
  };

  const handleConfirm = () => {
    if (result) onImported(result);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <div className="bg-bg rounded-xl max-w-3xl w-full max-h-[80vh] overflow-y-auto">
        <div className="px-6 py-4 flex items-center justify-between border-b border-fg-dim/20">
          <h2 className="text-lg font-semibold text-fg">上传 CSV</h2>
          <button onClick={onClose} className="text-fg-dim hover:text-fg">
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {!file && (
            <label className="block border-2 border-dashed border-fg-dim/30 rounded-lg p-8 text-center cursor-pointer hover:border-accent">
              <CloudArrowUpIcon className="w-12 h-12 text-fg-dim mx-auto mb-2" />
              <p className="text-sm text-fg-muted">点击或拖拽 CSV 文件到此处</p>
              <p className="text-xs text-fg-dim mt-1">最大 10MB</p>
              <input
                type="file"
                accept=".csv"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              />
            </label>
          )}

          {file && !result && (
            <div>
              <p className="text-sm text-fg-muted mb-2">
                已选文件: <span className="font-mono text-fg">{file.name}</span> (
                {(file.size / 1024).toFixed(1)} KB)
              </p>
              <button
                onClick={handleImport}
                disabled={importing}
                className="btn btn-primary w-full"
              >
                {importing ? '解析中...' : '解析 CSV'}
              </button>
            </div>
          )}

          {error && (
            <div className="border border-error/30 bg-error-muted rounded-lg p-4 flex items-start gap-2">
              <ExclamationCircleIcon className="w-5 h-5 text-error shrink-0 mt-0.5" />
              <p className="text-sm text-error">{error}</p>
            </div>
          )}

          {result && (
            <div>
              <p className="text-sm text-fg-muted mb-2">
                ✅ 解析成功: {result.sales.length} 张销售 + {result.purchases.length} 张采购
              </p>
              {result.rejected_rows && result.rejected_rows.length > 0 && (
                <div className="border border-warning/30 bg-warning-muted rounded-lg p-3 mb-3">
                  <p className="text-sm text-warning">
                    ⚠️ {result.rejected_rows.length} 行被拒绝:
                  </p>
                  <ul className="text-xs text-fg-dim mt-1 space-y-1 max-h-32 overflow-y-auto">
                    {result.rejected_rows.slice(0, 10).map((r) => (
                      <li key={r.row_index}>Row {r.row_index}: {r.reason}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="flex gap-2">
                <button onClick={handleConfirm} className="btn btn-primary flex-1">
                  使用此数据继续
                </button>
                <button onClick={() => { setFile(null); setResult(null); }} className="btn btn-ghost">
                  重新选择
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd tax_agent/frontend && npm run build`
Expected: 0 type errors

- [ ] **Step 3: Commit**

```bash
cd /root/TAXI
git add tax_agent/frontend/src/components/CsvImportWizard.tsx
git commit -m "feat(frontend): CsvImportWizard for drag-drop CSV with rejected rows display"
```

---

## Task 18: 测试 — conftest.py + test_csv_parser.py + test_reconcile.py (实际写在 Task 2/3，此 Task 是补全 pytest 配置)

**Files:**
- Create: `tax_agent/tests/__init__.py`
- Create: `tax_agent/tests/erp/__init__.py`
- Create: `tax_agent/tests/conftest.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Create test package init files**

创建 `tax_agent/tests/__init__.py` (空) 和 `tax_agent/tests/erp/__init__.py` (空)。

- [ ] **Step 2: Create conftest.py**

创建 `tax_agent/tests/conftest.py`：

```python
"""Shared pytest fixtures"""
import pytest
from pathlib import Path


@pytest.fixture
def erp_samples_dir() -> Path:
    return Path(__file__).parent.parent / "data" / "erp_samples"


@pytest.fixture
def techflow_case_id() -> str:
    return "techflow_q1_2026"
```

- [ ] **Step 3: Add pytest config to pyproject.toml**

修改 `pyproject.toml` 加 `[tool.pytest.ini_options]` section：

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-ra --strict-markers"
```

- [ ] **Step 4: Run all tests**

Run: `cd tax_agent && pytest tests/ -v`
Expected: 之前 Task 2/3/4/5 写的所有测试都通过

- [ ] **Step 5: Commit**

```bash
cd /root/TAXI
git add tax_agent/tests/__init__.py tax_agent/tests/erp/__init__.py tax_agent/tests/conftest.py pyproject.toml
git commit -m "test: pytest config + conftest shared fixtures"
```

---

## Task 19: 测试 — test_erp_samples_loader + test_erp_router (实际写在 Task 4/5，此 Task 验证通过)

**Files:**
- Run existing tests

- [ ] **Step 1: Run all erp tests**

Run: `cd tax_agent && pytest tests/erp/ -v`
Expected: 所有测试通过 (Task 4 之前因 JSON 缺失失败的部分现在通过)

- [ ] **Step 2: If any fail, debug and fix**

- [ ] **Step 3: Commit (if any changes)**

```bash
cd /root/TAXI
git status
# 如果有未提交的修改：
git add -A
git commit -m "test: verify erp_samples_loader + erp_router tests pass after Task 10"
```

---

## Task 20: 测试 — test_orchestrator_e2e + test_agent_chat

**Files:**
- Create: `tax_agent/tests/erp/test_orchestrator_e2e.py`
- Create: `tax_agent/tests/erp/test_agent_chat.py`

- [ ] **Step 1: Write orchestrator E2E test**

创建 `tax_agent/tests/erp/test_orchestrator_e2e.py`：

```python
"""Orchestrator 端到端：demo case → import → submit pipeline"""
import pytest
import base64
from datetime import date
from decimal import Decimal

from tax_agent.orchestrator import Orchestrator
from tax_agent.jurisdictions.uk import UKJurisdictionAdapter
from tax_agent.models.tax_data import (
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
```

- [ ] **Step 2: Write agent chat test**

创建 `tax_agent/tests/erp/test_agent_chat.py`：

```python
"""Agent chat MCP tool 测试 (v0 暂用 mock mode)"""
import pytest
from tax_agent.jurisdictions.uk.vat.agent_tools import UKVATAgentToolSet


@pytest.mark.asyncio
async def test_ingest_erp_data_demo_case():
    tools = UKVATAgentToolSet()
    result = await tools.ingest_erp_data(source="demo", case_id="techflow_q1_2026")
    assert "content" in result
    text = result["content"][0]["text"]
    assert "techflow" in text or "import_result" in text


@pytest.mark.asyncio
async def test_ingest_erp_data_missing_case_id():
    tools = UKVATAgentToolSet()
    result = await tools.ingest_erp_data(source="demo")
    assert result.get("is_error") is True
    text = result["content"][0]["text"]
    assert "case_id" in text


@pytest.mark.asyncio
async def test_ingest_erp_data_case_not_found():
    tools = UKVATAgentToolSet()
    result = await tools.ingest_erp_data(source="demo", case_id="nonexistent")
    assert result.get("is_error") is True


@pytest.mark.asyncio
async def test_ingest_erp_data_csv_base64():
    import base64
    csv = (
        b"txn_date,txn_type,counterparty,net,vat,gross,vat_rate,tax_code\n"
        b"2026-01-15,sale,ACME,1000,200,1200,0.20,T1\n"
    )
    tools = UKVATAgentToolSet()
    result = await tools.ingest_erp_data(
        source="csv", csv_base64=base64.b64encode(csv).decode(),
    )
    assert "content" in result
```

- [ ] **Step 3: Run all erp tests**

Run: `cd tax_agent && pytest tests/erp/ -v`
Expected: all pass

- [ ] **Step 4: Verify coverage**

Run: `cd tax_agent && pytest tests/erp/ --cov=tax_agent.erp --cov-report=term-missing`
Expected: ≥70% coverage on `tax_agent/erp/`

- [ ] **Step 5: Commit**

```bash
cd /root/TAXI
git add tax_agent/tests/erp/test_orchestrator_e2e.py tax_agent/tests/erp/test_agent_chat.py
git commit -m "test: orchestrator e2e (import→submit) + agent chat MCP tools"
```

---

## Task 21: 文档 — erp_integration.md + 验证清单

**Files:**
- Create: `tax_agent/docs/erp_integration.md`
- Modify: `tax_agent/CLAUDE.md` (Common Tasks 表加一行)

- [ ] **Step 1: Write erp_integration.md**

创建 `tax_agent/docs/erp_integration.md`：

```markdown
# T.A.X.I. — ERP Integration v0 用户/开发者文档

> **状态**：v0 demo 可用
> **日期**：2026-06-10

## 概述

T.A.X.I. v0 的 ERP 集成层让用户从 Demo Case / CSV / 未来真连 ERPNext 拉取数据，
走 T.A.X.I. 6 阶段管线（其中 CALCULATE/VALIDATE 由 Agent 主导），最后
用户点 Submit 一键提交到 HMRC mock。

## 用户流程

1. **Dashboard 选 Case** → "🔍 帮我分析目前的财务数据" 一键按钮
2. **Agent 弹发票多选面板** → 勾选要分析的发票
3. **Agent 调 calculate_vat_return** → 在 chat 流展示 9-Box 差异表
4. **Agent 调 validate_vat_return** → 报告校验结果
5. **用户点 "Submit to HMRC"** → 法律声明勾选 → 提交
6. **Agent 显示 HMRC 回执卡片**

## 开发者文档

### 关键模块

| 模块 | 路径 | 职责 |
|---|---|---|
| 数据模型 | `tax_agent/models/erp_models.py` | Pydantic ImportResult 等 |
| CSV 解析 | `tax_agent/erp/csv_parser.py` | bytes → ImportResult |
| Profile | `tax_agent/erp/profiles.py` | GenericProfile (v0 唯一) |
| Reconcile | `tax_agent/erp/reconcile.py` | compare 9-Box, £0.50 tolerance |
| Sample loader | `tax_agent/erp/erp_samples_loader.py` | data/erp_samples/*.json |
| Audit | `tax_agent/erp/audit_events.py` | action 常量 |
| Router | `tax_agent/server/erp.py` | /api/erp/* |
| Orchestrator | `tax_agent/orchestrator.py::_stage_import` | 新阶段 |
| UK calc | `tax_agent/jurisdictions/uk/vat/calculator.py` | +reconcile mode |
| Agent tool | `tax_agent/jurisdictions/uk/vat/agent_tools.py` | +ingest_erp_data |

### 添加新 CSV Profile (v1)

1. `tax_agent/erp/profiles.py` 加新 class
2. `_PROFILES` dict 注册
3. 加 unit test

### 添加新 Demo Case

1. 构造 JSON 写 `data/erp_samples/<id>.json` (用 `ImportResult.model_dump()` schema)
2. 后端自动发现（`list_demo_cases()` 扫目录）

## 已知限制 (v0 显式不做)

- ❌ Sage / Xero / QBO 多 Profile — v1
- ❌ FRS / Cash / Annual / Margin scheme — v1
- ❌ 真 ERPNext 凭证 — v1
- ❌ 真 HMRC sandbox — 继续走 mock
- ❌ 多租户 — v1

## HMRC Production 注册清单 (v1 必做)

- [ ] 在 HMRC MTD Software Register 注册 T.A.X.I.
- [ ] 申请 sandbox user
- [ ] 6 年 audit retention 实现
- [ ] API key 加密存储
- [ ] 用户授权页面合规
```

- [ ] **Step 2: Update CLAUDE.md**

修改 `tax_agent/CLAUDE.md`，在 "Common Tasks" 表加一行：

```markdown
| **Add CSV profile** | `tax_agent/erp/profiles.py` (新 class + 注册到 `_PROFILES`) |
| **Add demo case** | 写 JSON 到 `data/erp_samples/<id>.json` |
```

- [ ] **Step 3: Commit**

```bash
cd /root/TAXI
git add tax_agent/docs/erp_integration.md tax_agent/CLAUDE.md
git commit -m "docs: erp_integration.md (user/dev guide) + CLAUDE.md Common Tasks"
```

---

## Final Verification

**End-to-end manual test**:

```bash
# Terminal 1: 后端
cd tax_agent
pip install -e ".[server,dev]"
python run_backend.py
# 监听 :8765

# Terminal 2: 前端
cd tax_agent/frontend
npm install
npm run dev
# 监听 :9000
```

**Manual test flow**:

1. 打开 <http://localhost:9000/>
2. Dashboard → 点 "TechFlow Q1 2026" → 卡片高亮 + 顶部 "已加载" 徽章
3. 顶部 "清空数据" → 二次确认 → 数据清空
4. 重新选 "TechFlow Q1 2026" → 自动 navigate
5. `/filings/new` → Step 1-2 选 UK VAT + VRN → Step 3 看到 "已从 Demo 案例加载" + 数据 Preview
6. Step 4 → 9-Box 差异表 (有 1 个 £3.50 差异)
7. Step 5 → 法律声明勾选 → 提交
8. `/filings/{id}` → 看到 audit_trail 数组含 6 个阶段，import_summary 有 source/demo
9. `/agent` → 顶部 2 个一键按钮 → 点 "帮我计算本年增值税并申报" → 走 ⑨-⑮

**Automated tests**:

```bash
cd tax_agent
pytest tests/ -v
pytest tests/erp/ --cov=tax_agent.erp --cov-report=term-missing  # ≥70% cov
ruff check .
```

**Expected**: All tests pass, coverage ≥ 70% on `tax_agent/erp/`, no lint errors.

---

## Self-Review Checklist (Run before completion)

- [ ] Every spec requirement has a task implementing it (see below)
- [ ] No placeholders / "TBD" / "implement later" in any step
- [ ] All function/method names consistent across tasks
- [ ] All file paths exact
- [ ] All test code complete (not pseudo-code)
- [ ] Every commit message follows `<type>(<scope>): <subject>` convention
- [ ] pytest config in pyproject.toml (Task 18)
- [ ] Frontend build passes (every Task 11-17 has `npm run build` step)
- [ ] All `ImportResult.model_dump(mode="json")` consistent
- [ ] All `_tool_ok` / `_tool_error` consistent in agent_tools

**Spec coverage**:
- §1 Architecture: Tasks 1, 5, 6, 7, 8, 9, 10
- §2 Components: Tasks 1-5, 11-17
- §3 Data Flow: Tasks 7, 8, 12, 13, 14, 15, 16
- §4 Error Handling: Tasks 2 (CsvParseError), 4 (DemoCaseNotFoundError), 17 (CSV 上限 10MB)
- §5 Testing: Tasks 18, 19, 20
- §6 UX Demo: Tasks 14, 15, 16 (3 wow 画面 = QuickAction + DiffTable + 后续的 HMRCReceiptCard 增强在 v0 末尾)
- §7 Risks: covered by Task 17 (10MB limit) + Task 12 (clear data 按钮)
- §8 Out of Scope: explicitly NOT implemented (v0 文档中)

---

## Execution Handoff

Plan complete and saved to `/root/TAXI/tax_agent/docs/superpowers/plans/2026-06-10-erp-integration-v0.md`.

Two execution options:
1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks
2. **Inline Execution** — Execute tasks in this session using executing-plans

Which approach?
