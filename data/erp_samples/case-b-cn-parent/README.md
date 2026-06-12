# Case B · case-b-cn-parent — 中英跨境集团 CN 母公司申报

> **角色**:**跨境集团 — CN 母公司视角**。同一集团(CN 母 + HK 控 + UK 子)Q1 2026,以 CN 母为主体。  
> **目录**:`data/erp_samples/case-b-cn-parent/`(完整目录式)  
> **前端 ID**:`case-b-cn-parent`(`casePresets.ts` 第 3 项)  
> **演示目的**:中国主场 + 集团内部往来 + 预提税 + 转让定价 + DAC6 + BEPS 2.0。

---

## 🏢 实体

| 字段 | 值 |
|---|---|
| 名称 | **Shenzhen TechFlow Technology Co., Ltd.(深圳拓弗科技)** |
| 统一社会信用代码 | 91440300MA5DC9X |
| 纳税人类型 | 一般纳税人(13% / 6% 增值税) |
| VAT 期间 | 2026 Q1(月度申报) |
| 集团角色 | **终极母公司**(100% → HK TechFlow Holdings 100% → UK TechFlow Distribution Ltd) |

---

## 💼 业务详情

| 维度 | 数值 |
|---|---|
| 销售发票数 | 22 张(15 国内 13% + 5 现代服务 6% + 2 出口 0%) |
| 采购发票数 | 10 张 |
| 集团内部往来 | 3 笔(对 UK 子 IT 服务 ¥2,100,000) |
| TP 同期资料 | Master File + Local File 已备 |
| BEPS 2.0 Pillar Two | **不在范围内**(集团收入 < €750M) |
| DAC6 披露 | Hallmark C1(b) 跨境关联方 TP 安排 |

---

## 📊 CN 视角数字(非 9-Box 体系,见 `expected_outputs.json`)

### 增值税(CN VAT)

| 项 | 金额(¥) | 备注 |
|---|---|---|
| 销项税 13% | 845,000 | ¥6,500,000 国内货物销售 |
| 销项税 6% | 126,000 | ¥2,100,000 现代服务(含对 UK 子) |
| 进项税抵扣 | 420,000 | 原材料、设备、能源 |
| **应缴 VAT** | **551,000** | 月度申报,4 月 15 日前 |

### 企业所得税(CN CIT)

| 项 | 金额(¥) | 备注 |
|---|---|---|
| 营业收入 | 8,600,000 | 国内销售 ¥6.5M + 服务费 ¥2.1M |
| 营业成本 | 4,200,000 | 富士康 / 比亚迪采购 |
| 期间费用 | 600,000 | 管理/销售/财务 |
| **应纳税所得额** | 3,800,000 | |
| **CIT 应缴** | **950,000** | 25% 标准税率(Q1 预缴) |

### 预提税(中港税收安排)

| 项 | 金额(¥) | 税率 | 应缴 WHT(¥) |
|---|---|---|---|
| 股息(UK→HK) | 0(Q1 暂不分红) | 0% | 0 |
| 特许权使用费(UK→CN 经 HK) | 150,000 | 7% | 10,500 |
| 管理服务费(UK→CN 经 HK) | 2,100,000 | 5% | 105,000 |
| **合计 WHT** | | | **115,500** |

### 转让定价(Transfer Pricing)

| 项 | 金额/状态 |
|---|---|
| 集团内部往来总额 | ¥2,250,000(IT 服务 ¥1.5M + 管理咨询 ¥600k + 特许权 ¥150k) |
| TP 方法 | Cost Plus 8-12%(集团服务);CUP 5-10%(特许权) |
| **TP 调整额** | **+¥320,000**(补提应纳税所得额) |
| 同期资料 | Master File + Local File 已完成 |
| BEPS 2.0 | 集团合并收入 < €750M,不在 GloBE 范围内 |

### DAC6 强制披露(UK 视角联动)

| 项 | 状态 |
|---|---|
| Hallmark C1(b) 跨境关联方 TP 安排 | ✅ 触发 |
| 跨境报告金额(Cross-border RoD) | ¥2,250,000 |

---

## 🌍 跨境触点(3 国 + 集团层)

| 国家 | 角色 | 触点 |
|---|---|---|
| 🇨🇳 **中国** | 主体申报 | VAT + CIT + WHT + TP + DAC6 |
| 🇭🇰 **香港** | 中间控股 | 收特许权 ¥150k / 收管理费 ¥500k(0% VAT,经 CIT 流转) |
| 🇬🇧 **英国** | 子公司 | CN 母对 UK 子开 IT 服务费 ¥2,100,000(6% VAT) |
| 🇩🇪🇫🇷🇪🇸🇸🇪🇳🇱 | 触点 | UK 子在 EU 5 国的销售/采购(CN 母不直接看到,仅在合并报表层反映) |

---

## 🧾 scheme_flags

| Flag | 含义 |
|---|---|
| **CN VAT 13%** | 国内货物销售 |
| **CN VAT 6%** | 现代服务(IT/咨询/技术),含对 UK 子服务费 |
| **CN VAT 0%** | 跨境应税行为(出口服务到 HK) |
| **CN CIT 25%** | 标准税率(Q1 预缴) |
| **WHT 5%-7%** | 中港税收安排(经 HK 控股的关联方) |
| **Transfer Pricing** | Cost Plus 8-12% + CUP 5-10% |
| **DAC6 C1(b)** | 跨境关联方 TP 安排,UK 侧需披露 |
| **BEPS 2.0 GloBE** | 不在范围内(< €750M) |

---

## 📂 文件结构

```
case-b-cn-parent/
├── README.md                          ← 本文件
├── case_summary.json
├── erp_import.json                    ← CN 视角简化帐套(给 ErpInvoiceTable 渲染发票)
├── expected_outputs.json              ← CN VAT/CIT/WHT/TP 完整数字(非 9-Box)
└── source_docs/                       ← 38 份原始凭证(ERPNext DocType 格式)
    ├── ZKTECH-SINV-2026-001..022.json     (22 张销售发票,15 国内 + 5 服务 + 2 出口)
    ├── ZKTECH-PINV-2026-001..010.json     (10 张采购发票)
    ├── ZKTECH-IG-2026-001..003.json       (3 笔集团内部往来)
    ├── ZKTECH-TP-DOC-2026-Q1.json         (TP 同期资料)
    ├── ZKTECH-VAT-FILING-2025-12.json     (上月 VAT 申报回执)
    └── ZKTECH-CIT-2024-ANNUAL.json        (上年度 CIT 汇算清缴)
```

---

## 🔗 与 Case A 的对账(同一集团,不同视角)

| 视角 | Case A(UK 子报 UK VAT) | Case B(CN 母报 CN 税) |
|---|---|---|
| UK 子公司外销 | £282,750(Box 6) | — (CN 母不直接看到) |
| UK 子公司付 CN 母服务费 | — (费用化) | ¥2,100,000(CN 母 6% VAT 收入) |
| UK 子公司付 HK 控股特许权 | — (费用化) | ¥150,000(7% WHT 经 HK) |
| UK 子公司付 HK 控股股息 | — (利润分配) | £0 Q1(暂未分红) |

**对账说明**:两个数字在**不同报表层**,不矛盾。Case A 看到 UK 子**对外**销售;Case B 看到 CN 母**自身经营 + 集团内收入**。两个加起来才是集团 Q1 真实流水。

---

## 💡 演示价值

- **中国主场** — VAT 13% / 6% / 0% 三档税率 + CIT 25% + WHT 5%-7% + TP + DAC6
- **集团内部往来** — IT 服务 / 特许权 / 管理费 3 类典型关联交易
- **中港税收协定** — 5% / 7% 优惠税率(标准 10% / 10%)
- **TP 同期资料** — Master File + Local File + 调整额计算
- **DAC6 联动** — UK 子公司需要向 HMRC 披露同一笔关联交易
- **ERPNext 兼容** — `source_docs/*.json` 是 `Sales Invoice` / `Purchase Invoice` DocType 标准 JSON

---

## 🔗 关联

| 关联 | 文件 | 关系 |
|---|---|---|
| **同集团 UK 子视角** | `case-a-uk-subsidiary/` | 同一集团,不同视角,数字对账 |
| **入门 case** | `case-x-uk-standard/` | 简化教学,UK 单国 |
| **前端卡片** | `casePresets.ts#case-b-cn-parent` | Dashboard 第 3 张卡 |
| **Agent 兜底** | `frontend/src/data/realCaseData.json` | 集团完整数据(独立入口) |
