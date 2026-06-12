# Case A · case-a-uk-subsidiary — 中英跨境集团 UK 子公司申报

> **角色**:**跨境集团 — UK 子公司视角**。同一集团(CN 母 + HK 控 + UK 子)Q1 2026 报税,以 UK 子公司为主体。  
> **目录**:`data/erp_samples/case-a-uk-subsidiary/`(完整目录式)  
> **前端 ID**:`case-a-uk-subsidiary`(`casePresets.ts` 第 2 项)  
> **演示目的**:UK 单国旗舰 + 6 国 B2B 触点 + 进口 C79;数字与前端卡片**严格一致**。

---

## 🏢 实体

| 字段 | 值 |
|---|---|
| 名称 | **TechFlow Distribution Ltd** |
| VRN | 960606228 |
| EORI | GB960606228000 |
| VAT 期间 | 2026-01-01 ~ 2026-03-31(Q1, periodKey 25A1) |
| 申报截止 | 2026-05-07 |
| 集团角色 | 子公司(Shenzhen TechFlow 100% → HK TechFlow Holdings 100% → 本实体) |

---

## 💼 业务详情

| 维度 | 数值 |
|---|---|
| 销售发票数 | 27(21 国内 + 4 EU B2B + 2 零税率) |
| 采购发票数 | 24(21 UK 本地 + 2 EU 采购 + 1 免税保险) |
| 进口 C79 | 2 笔(2 月、3 月各一,总 £85,000 货值) |
| 源文档数 | 54(销售 27 + 采购 24 + C79 2 + MTD 1) |

---

## 📊 9-Box 自洽核对(Python 求和验证)

| Box | 内容 | 数值 |
|---|---|---|
| **Box 1** | 销售 VAT | **41,523.50** (£41,520 国内 + £3.50 零税率调整) |
| **Box 2** | EU 采购 reverse charge VAT | **13,700** (DE 10,000 + NL 3,700) |
| **Box 3** | VAT 总应付 = Box1 + Box2 | **55,223.50** |
| **Box 4** | 抵扣进项税 | **47,612** (含 EU acq reverse charge + C79 £17,000) |
| **Box 5** | 净 VAT = Box3 - Box4 | **7,611.50** (应付 HMRC) |
| **Box 6** | 销售总额(不含 VAT) | **282,750** |
| **Box 7** | 采购总额(不含 VAT) | **240,460** |
| **Box 8** | EU B2B 销售额 | **42,450** (DE 12,500 + FR 15,000 + ES 8,750 + SE 6,200) |
| **Box 9** | EU 采购额 | **68,500** (DE 50,000 + NL 18,500) |

---

## 🌍 跨境触点(6 国)

| 国家 | 角色 | 触点金额(£) |
|---|---|---|
| 🇬🇧 **英国** | 主体申报 | 全部 9 盒 |
| 🇩🇪 **德国** | B2B 客户 + 供应商 | 12,500 销 + 50,000 采 + 10,000 reverse charge |
| 🇫🇷 **法国** | B2B 客户 | 15,000 销 |
| 🇪🇸 **西班牙** | B2B 客户 | 8,750 销 |
| 🇸🇪 **瑞典** | B2B 客户 | 6,200 销 |
| 🇳🇱 **荷兰** | 供应商 | 18,500 采 + 3,700 reverse charge |
| 🇨🇳 **中国** | 母公司(进口来源) | £85,000 进口(2 笔 C79) |

---

## 🧾 scheme_flags

| Flag | 含义 |
|---|---|
| **Zero-rating adjustment** | Box 1 包含 £3.50 零税率调整(舍入) |
| **EU B2B reverse charge** | 出口 0%(Box 8 累计),客户 reverse charge |
| **EU acquisition reverse charge** | UK 自计:Box 2 + Box 4 同增 |
| **Import C79** | UK 关税收讫,Box 4 抵扣(2 笔) |

---

## 📂 文件结构

```
case-a-uk-subsidiary/
├── README.md                          ← 本文件
├── case_summary.json                  ← 案例摘要
├── erp_import.json                    ← 16,640 B (从 techflow_q1_2026.json 迁移)
├── expected_nine_box.json             ← 教学对照 9-Box
└── source_docs/                       ← 54 份原始凭证(ERPNext Sales/Purchase Invoice 格式)
    ├── TECHFLOW-SINV-2026-001..027.json    (27 张销售发票)
    ├── TECHFLOW-PINV-2026-001..024.json    (24 张采购发票)
    ├── TECHFLOW-C79-2026-001..002.json     (2 张 C79 进口凭证)
    └── TECHFLOW-VAT-MTD-2025-Q4.json      (上季 HMRC 申报回执)
```

---

## 💡 演示价值

- **与前端 A5' 卡片 100% 一致**(虽然原卡片已改名为 `case-a-uk-subsidiary`,但 9-Box 数字不变)
- **覆盖几乎所有 UK VAT 复杂度** — 零税率、reverse charge、进口 C79、Box 1 舍入
- **最严格的"4 国 EU B2B + 2 国 EU acq + 1 国进口"演示**
- **ERPNext 真接兼容** — `source_docs/*.json` 是 `Sales Invoice` / `Purchase Invoice` DocType 标准 JSON,可直接 `POST` 到 ERPNext

---

## 🔗 关联

| 关联 | 文件 | 关系 |
|---|---|---|
| **同集团 CN 视角** | `case-b-cn-parent/` | 同一集团(CN 母 + HK 控 + UK 子),不同视角 |
| **入门 case** | `case-x-uk-standard/` | 数字简化,9-Box 自洽教学 |
| **集团主 case**(Agent 兜底) | `frontend/src/data/realCaseData.json` | 集团完整数据,Agent 演示用 |
| **前端卡片** | `casePresets.ts#case-a-uk-subsidiary` | Dashboard 第 2 张卡 |

> **核心承诺**:本目录的 9-Box 与前端卡片显示**完全一致**;本目录的 source_docs 是 ERPNext DocType 标准 JSON,可直连。
