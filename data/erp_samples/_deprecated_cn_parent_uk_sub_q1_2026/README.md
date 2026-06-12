# Case 2 · cn_parent_uk_sub_q1_2026 — 中资跨境集团季度案例(目录式 fixture)

> **角色**:**集团级**跨境 E2E(单一 ERP fixture,带 12 份源文档)。  
> **路径**:`data/erp_samples/cn_parent_uk_sub_q1_2026/`  
> **演示目的**:CN 母公司 + HK 中间控股 + UK 子公司的集团内部往来(服务费、授权费、股息)如何影响 9-Box + EC Sales List + TP 文档。

---

## 🏢 实体

| 层级 | 名称 | 国家 | 关键识别号 | 角色 |
|---|---|---|---|---|
| 母公司 | Shenzhen ZK Smart Manufacturing Co., Ltd. | 🇨🇳 CN | 统一社会信用代码 | 一般纳税人,制造商 |
| 中间控股 | (HK 控股公司) | 🇭🇰 HK | BR 编号 | IP 持有 + 财资中心 |
| UK 子公司 | **TechFlow UK Ltd** | 🇬🇧 GB | **VRN: GB123456789** | 实际申报实体 |

---

## 💼 业务详情(Q1 2026)

| 维度 | 数值 |
|---|---|
| 销售发票数 | 24 张(UK 国内 + EU B2B + 集团内部) |
| 采购发票数 | 20 张(UK 本地 + EU acq + 集团内部) |
| 费用报销 | 5 笔 |
| **集团内部往来** | **3 笔**(核心) |
| 源文档 | 12 份 |
| VAT 期间 | 2026 Q1(periodKey 26A1,截止 2026-05-07) |

---

## 🧾 scheme_flags(本 case 独有)

| Flag | 含义 | 对应单据 |
|---|---|---|
| **Capital Goods Scheme** | 货车 > £50,000 阈值,5 年期调整 | PI-2026-CAP-001 |
| **Intra-group B2B services reverse charge** | 集团内部服务费,EC Sales List 强制披露 | IG-2026-* |
| **C79 import VAT reclaim** | > £1,000/月 规则适用 | PI-2026-IMP-001..004 |

---

## 📊 9-Box(UK 视角)

| Box | 数值 | 备注 |
|---|---|---|
| Box 1 | 23,290.00 | UK 国内销售 VAT |
| Box 2 | 3,140.00 | EU acq reverse charge |
| Box 3 | 26,430.00 | = Box1 + Box2 |
| Box 4 | 24,926.00 | 抵扣进项税(含 C79) |
| Box 5 | **1,504.00** | 净 VAT(应付) |
| Box 6 | 160,750 | UK 总销售 |
| Box 7 | 129,880 | UK 总采购 |
| Box 8 | 118,100 | EU 出口(0%) |
| Box 9 | 15,700 | EU 采购 |

> **注意**:本 case 的 Box 1/2/4/5/6/7/8/9 与后端旗舰 `techflow_q1_2026.json` 不完全一致 —— 这是设计上的"两个独立集团故事",分别覆盖不同的复杂度维度。

---

## 🌍 跨境触点(3 国 + 集团层)

| 国家 | 申报税种 | 触发点 |
|---|---|---|
| 🇨🇳 **中国** | VAT(母公司)+ 企所税 + 预提税 | 集团内部服务费(6% VAT)、TP 同期资料(国税总局 6 号公告) |
| 🇭🇰 **香港** | 利得税 + 印花税(股权转让) | HK 控股收股息、特许权使用费 |
| 🇬🇧 **英国** | VAT (MTD) + 预提税 | UK 子公司本地 VAT、向 HK 控股付授权费(4% 预提,中港税收安排) |

---

## 📂 文件结构(目录式 fixture,带源文档)

```
cn_parent_uk_sub_q1_2026/
├── README.md                       ← 本文件
├── case_summary.json               ← 案例摘要 + scenarios_covered
├── expected_nine_box.json          ← 期望 9-Box + scheme_flags
├── erp_import.json                 ← ERP 导入主文件(ImportResult)
├── transactions.json               ← 原始业务数据(供 business_analyzer)
├── ledger.csv                      ← CSV 解析器输入
└── source_docs/                    ← 12 份"原始凭证"JSON
    ├── BNK-2026-Q1-01.json         ← 银行对账单
    ├── C79-2026-001..004.json      ← 4 份进口 C79(逐月)
    ├── INV-CN-2026-001..004.json   ← 4 份 CN 母公司开来的发票
    ├── PO-CN-2026-Q1.json          ← 采购订单
    ├── TP-2026-Q1.json             ← 转让定价同期资料
    └── VAT-MTD-2025-Q4.json        ← 上季度 VAT MTD 申报回执
```

**`source_docs/*.json` 12 份分类:**

| 类型 | 数量 | 文件 |
|---|---|---|
| C79 进口凭证 | 4 | C79-2026-001..004 |
| CN 母公司发票 | 4 | INV-CN-2026-001..004 |
| 银行 | 1 | BNK-2026-Q1-01 |
| 采购订单 | 1 | PO-CN-2026-Q1 |
| 转让定价 | 1 | TP-2026-Q1 |
| VAT 申报回执 | 1 | VAT-MTD-2025-Q4 |

---

## 🎯 scenarios_covered(本 case 覆盖的所有业务场景)

| # | 场景 | 涉及规则 |
|---|---|---|
| T1 | 国内标准 20%(B2B + B2C) | UK VAT 标准税率 |
| T0 | 零税率(食品/书籍/童装) | Zero-rating schedule |
| T9 | EU B2B reverse charge(DE/FR/DK) | EU VAT Directive Art. 138 |
| 集团内部 | 母公司 CN→子公司 UK 转移 | OECD TP Art. 9 |
| 出口 | 美国/澳大利亚(超 VAT 范围) | Export outside scope |
| T2 | EU 采购 reverse charge(DE/IT/FR) | EU VAT Directive Art. 40 |
| T8 | 第三方进口(CN→UK)C79 抵扣 | UK VAT Notice 702 |
| T0 | 免税采购(银行费、保险) | Exempt supplies |
| T0 | 不可抵扣(娱乐费) | Section 24(2) VATA 1994 |
| T1 | Capital Goods Scheme(货车 > £50k) | Notice 706/2 |
| 贷项通知单 | 销售退回 | Credit note |
| 转让定价 | 管理费、特许权使用费披露 | OECD TP Guidelines |

---

## 💡 演示价值

- **带 12 份源文档** — 测试 ERP 导入流(JSON 凭证 + CSV 解析)
- **集团内部服务费** — 演示 TP 风险(高利润压 UK、低利润放 CN)
- **中港税收协定** — 预提税从 10% 降至 5% 需要 HK 居民身份证明
- **目录式 fixture** — 与 flat JSON 的 `techflow_q1_2026.json` 对比,展示 loader 两种格式都能吃
- **3 个集团层** — 演示 AI Agent 在多国主体间的协同调度

---

## 🔗 关联

- **后端旗舰**:`data/erp_samples/techflow_q1_2026.json`(UK 子公司单国旗舰)
- **集团主 case**:`frontend/src/data/realCaseData.json`(完整 3 层集团 + 8 国触点)
- **loader**:`backend/erp/erp_samples_loader.py`(同时支持 flat + 目录两种格式)
