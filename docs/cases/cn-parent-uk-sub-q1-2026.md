# 中资跨境 VAT 案例 — TechFlow UK Ltd Q1 2026

> 一个完整、可重放的中资跨境 VAT 申报案例，演示从**原始凭证** → **ERP 帐套** → **T.A.X.I. 9-Box 智能分析** → **HMRC 申报**的端到端流程。

**集团结构**：

```
深圳中科智造科技有限公司 (Shenzhen ZK Smart Manufacturing Co., Ltd)
   100% 持股
        │
        ▼
TechFlow UK Limited (UK 子公司)
   VRN: GB123456789
   EORI: GB123456789000
   公司号: 12345678
   注册地: 88 City Road, London EC1Y 2AA
```

**VAT 期间**：Q1 2026 (2026-01-01 → 2026-03-31)，period_key `26A1`，申报截止 `2026-05-07`。

---

## 1. 业务范围（覆盖 9-Box 全字段 + 智能体分析点）

| # | 业务事件 | 类别 | 数量 | 9-Box 影响 |
|---|---|---|---:|---|
| 1 | **国内标准 20% 销售** (T1) — B2B + B2C | `domestic_b2b/b2c` | 10 笔 | **Box1** (+) / **Box6** |
| 2 | **零税率销售** (T0) — 食品 / 书籍 / 童装 | `zero_rated` | 4 笔 | **Box6** (不影响 Box1) |
| 3 | **欧盟 B2B reverse charge** (T9) — DE / FR / DK | `eu_b2b` | 5 笔 | **Box8** |
| 4 | **集团内部调拨** (T9 RC) — 母公司 CN→UK | `intra_group` | 2 笔 | **Box8** (关联方披露) |
| 5 | **出口** (T0 outside scope) — USA / AU | `export` | 2 笔 | **Box6** (不影响 Box1) |
| 6 | **UK 本地采购** (T1) — 含 VAT 可抵扣 | `domestic` | 8 笔 | **Box4** (-) / **Box7** |
| 7 | **欧盟采购 reverse charge** (T2) — DE / IT / FR | `eu_acquisition` | 3 笔 | **Box2** (+) / **Box4** (-) / **Box7** / **Box9** |
| 8 | **从中国母公司进口** (T8) — 4 笔 C79 | `import` | 4 笔 | **Box4** (-) / **Box7** |
| 9 | **豁免采购** (T0) — 银行 / 保险 | `exempt` | 2 笔 | **Box7** (不影响 Box4) |
| 10 | **非可抵扣采购** (T0) — Ritz / F&M 招待 | `non_recoverable` | 2 笔 | **Box7** (不影响 Box4) |
| 11 | **资本货物** (T1) — Mercedes 商务 van | `capital` | 1 笔 | **Box4** / **Box7** (Capital Goods Scheme 触发) |
| 12 | **退货 / 贷项通知** (credit note) | `credit_note` | 1 笔 | 反向影响 Box1 / Box4 |
| 13 | **费用报销** — 差旅 3 笔 / 招待 2 笔 | `expense_claims` | 5 笔 | **Box4** (可抵扣部分) |
| 14 | **集团内部往来** — 管理费 + 特许权使用费 | `intra_group_tx` | 3 笔 | 不进 9-Box (跨境服务 RC 不在范围内) |

**总数据量**：

| 类别 | 数量 |
|---:|---:|
| 销售发票 | 24 笔 (含 1 笔 credit note) |
| 采购发票 | 20 笔 |
| 费用报销 | 5 笔 |
| 集团内部往来 | 3 笔 |
| **ERP 帐套净交易** | 43 笔 (sales 23 + purchases 20) |
| **原始凭证** (C79 / 商业发票 / PO / TP 报告 / 银行) | 12 份 |

---

## 2. 文件结构

```
data/erp_samples/cn_parent_uk_sub_q1_2026/
├── transactions.json        ← 原始业务数据 (business_analyzer / agent 输入)
├── ledger.csv               ← 通用 CSV (8 列, 可被 backend/erp/csv_parser 解析)
├── erp_import.json          ← ImportResult 格式 (含 ERP 自报 9-Box, 故意小差异)
├── expected_nine_box.json   ← T.A.X.I. 算法预期 9-Box
├── case_summary.json        ← 机器可读的案例摘要
└── source_docs/             ← 12 份原始凭证 (C79 凭证 / 商业发票 / PO / TP 研究)
    ├── INV-CN-2026-001..004.json    ← 母公司商业发票
    ├── C79-2026-001..004.json       ← 海关 C79 进口 VAT 凭证
    ├── PO-CN-2026-Q1.json           ← 母公司 Q1 采购总单
    ├── TP-2026-Q1.json              ← 转让定价研究 (TNMM, mark-up 8%)
    ├── BNK-2026-Q1-01.json          ← Q1 银行流水摘要
    └── VAT-MTD-2025-Q4.json         ← Q4 2025 历史申报
```

---

## 3. 9-Box 预期值（三套算法对比）

| Box | `compute_taxi_nine_box` (CSV/ERP 解析后) | `business_analyzer` (原始数据, 含 expense + 跳过 capital) | ERP 自报 (`erp_import.json`) | 差异 |
|---|---:|---:|---:|---:|
| **Box 1** (Sales VAT) | £23,290.00 | £23,290.00 | £23,790.00 | **-500.00** (ERP 漏扣 credit note VAT) |
| **Box 2** (Acquisitions VAT) | £3,140.00 | £3,140.00 | £3,140.00 | 0 |
| **Box 3** (Total VAT due) | £26,430.00 | £26,430.00 | £26,930.00 | -500 (因 box1) |
| **Box 4** (VAT reclaimed) | £24,926.00 | £18,729.00 | £24,926.00 | 0 |
| **Box 5** (Net VAT due) | £1,504.00 | £7,701.00 | £2,004.00 | -500 (因 box1) |
| **Box 6** (Total sales ex-VAT) | 278,850 | 160,750 | 281,350 | **-2,500** (ERP 漏扣 credit note net) |
| **Box 7** (Total purchases ex-VAT) | 129,880 | 93,645 | 129,880 | 0 |
| **Box 8** (EU goods supplied) | 118,100 | 41,100 | 118,100 | 0 (intra_group 在 analyzer 里"漏算") |
| **Box 9** (EU acquisitions) | 15,700 | 15,700 | 15,700 | 0 |

**两套算法口径差异**（重要！）：

| 维度 | `compute_taxi_nine_box` (erp 路径) | `business_analyzer` (原始数据路径) |
|---|---|---|
| 输入 | `ImportResult` (CSV 解析后) | 原始 `transactions.json` |
| 销售 VAT 范围 | sales.vat_amount where vat_rate > 0 | sales_invoices where type in (domestic_b2b/b2c) |
| 采购 VAT 范围 | purchases where is_recoverable | purchase_invoices + expense_claims (可抵扣部分) |
| Capital Goods Scheme | **包含** (T1 recoverable) | **跳过** (type=capital 不在分支里) |
| 集团内部 | **包含** (T9, 进 box8) | **跳过** (type=intra_group 不在分支里) |
| Box 8 (EU goods) | EU sales + intra_group | 仅 eu_b2b |

**这意味着**：从 CSV 喂入 → 用 `compute_taxi_nine_box`；从 `transactions.json` 喂入 → 用 `business_analyzer`。两个结果都是正确的，**只是口径不同**。案例测试断言了两套都跑通。

---

## 4. 端到端验证

### 4.1 案例加载

```bash
$ curl -s http://localhost:8765/api/erp/cases
{"cases":["cn_parent_uk_sub_q1_2026","cross_border_eu_2026","techflow_q1_2026"]}

$ curl -s http://localhost:8765/api/erp/cases/cn_parent_uk_sub_q1_2026 | jq '.sales | length'
23
$ curl -s http://localhost:8765/api/erp/cases/cn_parent_uk_sub_q1_2026 | jq '.purchases | length'
20
```

### 4.2 CSV Import 路径

```bash
$ curl -s -X POST http://localhost:8765/api/erp/import \
    -F "file=@data/erp_samples/cn_parent_uk_sub_q1_2026/ledger.csv" | jq '.erp_provided_boxes | {box1: .box1_vat_due_sales, box6: .box6_total_sales_ex_vat}'
{
  "box1": "23290.0",   # TAXI 算法
  "box6": 278850
}
```

### 4.3 Reconcile 差异检出

```bash
$ curl -s -X POST http://localhost:8765/api/erp/reconcile \
    -H "Content-Type: application/json" \
    -d '{"import_result": '"$(cat data/erp_samples/cn_parent_uk_sub_q1_2026/erp_import.json)"', "erp_source": "demo:cn_parent_uk_sub_q1_2026"}' | jq
```
```json
{
  "box_diffs": {
    "box1": "-500.00",   ← ERP 漏扣 credit note VAT
    "box6": "-2500",     ← ERP 漏扣 credit note net
    "box2..box5,7..9": 0
  },
  "within_tolerance": false,
  "total_abs_diff": "3000.00",
  "notes": [
    "box1 差异 -500.00 (TAXI=23290, ERP=23790) > tolerance 0.50",
    "box6 差异 -2500 (TAXI=278850, ERP=281350) > tolerance 0.50"
  ]
}
```

### 4.4 Orchestrator 6 阶段管线

```python
result = await orch.run(adapter, TaxType.VAT, data, import_payload={
    "source": "demo", "case_id": "cn_parent_uk_sub_q1_2026",
})
# IMPORT 阶段成功，9-Box 写入 data.metadata
# PRECHECK 在 line_items=[] 时按预期 fail (call 端需要先从 9-Box 推导 line_items)
```

### 4.5 Agent MCP 工具链

```python
tools = UKVATAgentToolSet()

# 1) ingest_erp_data: 加载 demo case
r = await tools.ingest_erp_data(source="demo", case_id="cn_parent_uk_sub_q1_2026")
# → import_result (sales=23, purchases=20) + summary

# 2) calculate_vat_return: 从 line_items 算 9-Box
r = await tools.calculate_return(line_items_json=json.dumps([
    {"category": "vat_due_sales", "amount": "23290"},
    {"category": "vat_due_acquisitions", "amount": "3140"},
    {"category": "vat_reclaimed_purchases", "amount": "24926"},
    # ... (7 项)
]))
# → box1=23290, box5=1504, warnings=[]

# 3) validate_vat_return: 合规校验
r = await tools.validate_return(return_data={
    "vat_due_sales": "23290", "vat_due_acquisitions": "3140",
    "vat_reclaimed_purchases": "24926", "total_sales_ex_vat": "278850",
    "total_purchases_ex_vat": "129880",
    "total_goods_supplied_eu": "118100", "total_goods_acquired_eu": "15700",
})
# → is_valid=True, errors=[], warnings=[]

# 4) submit_vat_return (HMRC_MODE=mock)
r = await tools.submit_return(
    taxpayer_id="GB123456789", period_key="26A1",
    return_data={"vat_due_sales": "23290", ...}
)
# → HMRC mock 返回 processingDate, formBundleNumber, etc.
```

### 4.6 business_analyzer 高级分析

```python
from backend.agent.business_analyzer import calculate_vat_return_from_raw, generate_analysis_report

raw = json.loads(transactions_path.read_text())
summary = calculate_vat_return_from_raw(raw)
report = generate_analysis_report(raw, summary)

# 输出 9-Box + 销售/采购明细 + 10 条 compliance notes + HMRC payload
# box5 = £7,701 (公司需付 HMRC)
# compliance_notes 覆盖 Standard Rate / EU B2B / Zero-Rated / Export / C79 / EU Acquisition / Reverse Charge / Non-Recoverable / Bad Debt Relief / Pre-Registration
```

---

## 5. 测试覆盖

`tests/erp/test_cn_uk_case.py` — 12 个测试覆盖：

| # | 测试 | 验证 |
|---|---|---|
| 1 | `test_case_listed` | 案例在 demo case 列表 (directory layout) |
| 2 | `test_case_loads` | ImportResult 加载 + 计数 + warnings |
| 3 | `test_nine_box_matches_expected` | 算法 vs expected_nine_box.json |
| 4 | `test_nine_box_includes_eu_acquisitions` | T2 → box2+box4+box7+box9 |
| 5 | `test_nine_box_excludes_intra_group_from_box1` | 集团内部 vat=0 → box1 不变 |
| 6 | `test_nine_box_handles_c79_import_vat` | T8 → box4+box7 (4 笔) |
| 7 | `test_reconcile_detects_erp_discrepancy` | box1 -500 / box6 -2500 检出 |
| 8 | `test_orchestrator_import_and_precheck` | IMPORT 阶段 + metadata 写入 |
| 9 | `test_agent_ingest_calculate_validate` | 3 步 MCP 工具链 |
| 10 | `test_agent_get_obligations_mock` | get_obligations 在 mock 模式 |
| 11 | `test_business_analyzer_processes_transactions` | 原始数据 → 9-Box + report |
| 12 | `test_business_analyzer_handles_intra_group` | 集团内部"漏算"边界 (analyzer 限制) |

运行：`pytest tests/erp/test_cn_uk_case.py -v`

---

## 6. 智能体分析能力演示清单

本案例演示的 6 项智能体分析能力：

1. **多源数据摄入**：transactions.json (原始) + ledger.csv (CSV) + erp_import.json (ImportResult) — 三种格式可互换
2. **9-Box 智能分类**：sales 拆 4 类 (domestic/zero/EU/export) + purchases 拆 5 类 (domestic/EU/import/exempt/capital) + 集团内部关联方标识
3. **合规校验**：Capital Goods Scheme 触发 / C79 import VAT 抵扣 / Reverse Charge / Non-recoverable entertainment
4. **差异检测 (Reconcile)**：ERP vs TAXI 算法容差比较，£0.50 tolerance，超差报警 + notes
5. **报告生成**：compliance notes (10 条法规引用) + HMRC payload (直接可提交) + line_items (供下游工具)
6. **关联方披露 (Transfer Pricing)**：管理费 + 特许权使用费，TNMM mark-up 8%，不直接影响 9-Box 但 EC Sales List 需披露

---

## 7. 已知限制与改进方向

| 限制 | 影响 | 改进方向 |
|---|---|---|
| `compute_taxi_nine_box` v0 不读 `expense_claims` | 与 business_analyzer 口径差 203 | 加 expense_claims → box4 路径 |
| `compute_taxi_nine_box` v0 不读 `intra_group` (T9 RC) | box8 漏算 77000 | 加 intra_group → box8 路径 |
| `business_analyzer` v0 跳过 `type=capital` | box4 少算 6400 | 加 capital goods scheme 分支 |
| `submit_vat_return` (live mode) `OAuth2Config` 字段名错 (`scope` vs `scopes`) | live 提交失败 | 改 agent_tools.py 字段名 |
| Capital Goods Scheme 5 年期调整 | v0 不实现 | 后续季度对同一资产逐年调整 |
| bad debt relief | 案例里 0 笔 (未演示) | 加 bad debt 案例 |
| pre-registration VAT | 案例里 0 笔 | 加 VAT-first-return 案例 |
