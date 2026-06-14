# UK Withholding Tax (WHT) — 预提税

> 状态 (2026-06-13): 所有数据已对照 HMRC 文档 (gov.uk, HMRC DT internal manual, UK-China DTA 2011, UK-Hong Kong DTA 2010) 核实。

## 概要

UK 对向非居民支付的特定款项征收 **outbound withholding tax**,主要包括三类:
- **利息 (Interest)** WHT
- **股息 (Dividend)** WHT
- **特许权使用费 (Royalties)** WHT

**重要**: UK **没有独立的 WHT 申报 API**。这三类税通过以下途径申报:
- 利息/特许权 WHT: 嵌入 **Corporation Tax return (CT600)**
- DTA 减免: 通过纸面表单 DTTP1 (passport scheme) 或 DT-Company (repayment claim)

UK WHT **不是独立的 TaxType**,而是 CT600 报表中的特定栏目。

---

## 三类 WHT 税率 (2024/25)

| 类别 | 默认 UK 税率 (无 DTA) | 申报途径 | 依据 |
|------|----------------------|----------|------|
| **利息 Interest** | 20% (基本税率) | CT600 + 预扣时上缴 HMRC | HMRC DT1820; ICTA88/S348 |
| **股息 Dividend** | **N/A — UK 从不预扣股息税** | 不适用 | 长期实践;非税率是 0%,而是该税不存在 |
| **特许权使用费 Royalties** | 20% (基本税率) | CT600 + 预扣时上缴 HMRC | HMRC DT1820; ICTA88/S349 |

> **更正说明**: 之前文档中"dividend WHT is 0% for most cases since 2009"的说法不准确。准确表述是 **UK 从未对非居民股息预扣税**,2009 年的政策是取消了非居民的"名义税收抵免"(notional tax credit),与预扣税无关。

---

## DTA (Double Taxation Agreement) 减免税率

UK 与 100+ 国家签有 DTA。常见协定税率:

### UK → 中国 (UK-China DTA 2011, as amended 2013)

| 类别 | DTA 税率 | 条件 |
|------|----------|------|
| 股息 | **5%** | 持股 ≥ 25% 资本 |
| 股息 | **10%** | 其他情况 |
| 股息 | **15%** | REIT property-income dividends |
| 利息 | **10%** | 默认;政府/银行/上市欧元债可享 0% |
| 特许权 | **10%** | 默认;设备租赁按 60% 调整基数 |

来源: [UK-China DTA 2011 (gov.uk)](https://www.gov.uk/government/publications/china-tax-treaties/2011-uk-china-double-taxation-agreement-as-amended-in-2013-in-force)

### UK → 香港 (UK-Hong Kong DTA 2010)

| 类别 | DTA 税率 | 条件 |
|------|----------|------|
| 股息 | **0%** | 来源国(UK)完全免税 — 这是 UK-HK 协定的特殊优惠 |
| 股息 | **15%** | REIT property-income dividends |
| 利息 | **0%** | 满足受益所有人条件(政府/个人/上市公司/银行/上市欧元债/养老基金等) |
| 特许权 | **3%** | 默认 |

来源: [UK-Hong Kong DTA 2010 (gov.uk)](https://www.gov.uk/government/publications/hong-kong-tax-treaties/2010-uk-hong-kong-double-taxation-agreement-in-force)

---

## CT600 中的相关栏目

WHT 预扣金额和 DTA 减免通常在 CT600 的以下部分体现:

| CT600 栏目 | 描述 |
|-----------|------|
| **Section A: Trading income** | 含已预扣税的利息/特许权收入(净额申报) |
| **Section B: Non-trading income** | 非贸易贷款关系(non-trading loan relationships)的利息 |
| **Section C: Chargeable gains** | 资产处置利得 |
| **Section D: Charges & Reliefs** | 含 DTA 减免 (double taxation relief) |
| **Supplementary Pages CT600A/B/C** | 视业务性质附加 |

**Chargeable gains on shares** 走 CGT(嵌入 SA),不在 WHT 范畴。

---

## DTA 减免申请流程

### 方式 1: 源泉减免 (Relief at Source)
通过 **Double Taxation Treaty Passport Scheme**:
1. 海外贷款人填写 **DTTP1** 申请护照
2. HMRC 批准后,借款人提交 **DTTP2** (按笔贷款通知)
3. 预扣时按 DTA 税率扣减

### 方式 2: 退税申请 (Repayment)
1. 海外收款人填写 **DT-Company** 表单
2. 附 DTA 文本、Certificate of Residence、扣税凭证
3. HMRC 审核后退税

---

## Case B (CN parent → UK sub) 跨境场景的 WHT

Case B (`data/erp_samples/case-b-cn-parent/`) 模拟一家 **中国母公司** 持有 **英国子公司** 收取特许权使用费和管理费的场景。

**重点**: 该 fixture 的 WHT 数据是 **CN 视角** (中国对 UK 来源收入的预提税),不是 UK 视角的预提税。

- `royalty_wht_rate: 0.07` (7%) — 这是 **CN** 对 UK→CN 方向特许权使用费的预提税率,依据中港税收安排 (DTA 内 10%,但可能适用更低的国内法)
- `dividend_wht_rate: 0.00` (0%) — 母子公司之间未发生股息分配

**UK 子公司** 在 CT600 中:
- 收到的特许权使用费/管理费属于 **trading income** 或 **non-trading income**
- 不需要从源头预扣
- 母公司后续在 CN 申报时凭 DTA 减免证明

---

## Agent 处理建议

当用户询问 "UK 的利息/股息/特许权预提税" 时:

1. **不要**把它作为独立 TaxType 申报 (UK 视角下没有此能力)
2. **建议** 走 CT600 流程 (在 `UKCTAgentToolSet` 中处理)
3. **如需 DTA 减免**,告知用户需要 Certificate of Residence 和 DTA 文本
4. **跨境场景**(如 Case B),区分开 UK 视角和对方国家视角的 WHT
5. **股息 WHT**: 明确告诉用户 UK 不征,与"0% 税率"是不同概念

---

## 相关文件

- `data/tax_knowledge/uk/corporation_tax.md` — CT600 完整说明
- `data/erp_samples/case-b-cn-parent/expected_outputs.json` — CN 视角 WHT fixture
- HMRC DT 内部手册: [DT1820](https://www.gov.uk/hmrc-internal-manuals/double-taxation-relief/dt1820), DT1835, DT1836
- [DTR for companies (gov.uk)](https://www.gov.uk/guidance/double-taxation-relief-for-companies)
- [DTTP guidance (gov.uk)](https://www.gov.uk/guidance/double-taxation-treaty-passport-scheme)
