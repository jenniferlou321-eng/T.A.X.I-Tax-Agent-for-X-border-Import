# Case A · case-a-uk-subsidiary — 中英跨境集团 UK 子公司申报(前端卡片)

> **角色**:**跨境集团 — UK 子公司视角**。同一集团(CN 母 + HK 控 + UK 子)Q1 2026 报税,以 UK 子公司为主体。  
> **文件**:`frontend/src/data/casePresets.ts` 第 2 项(原 `real-business-q1` 改名)  
> **前端 ID**:`case-a-uk-subsidiary`  
> **后端 fixture**:`data/erp_samples/case-a-uk-subsidiary/`(完整目录式)  
> **演示目的**:UK 单国旗舰 + 6 国 B2B 触点 + 进口 C79;数字与后端 fixture 严格一致。

---

## 🏢 实体

- **名称**:TechFlow Distribution Ltd
- **VRN**:960606228
- **EORI**:GB960606228000
- **VAT 期间**:2026 Q1(periodKey 25A1,截止 2026-05-07)

---

## 💼 业务详情(与后端 fixture 1:1 对应)

| 维度 | 数值(£) |
|---|---|
| 销售发票数 | 27(21 国内 + 4 EU B2B + 2 零税率) |
| 采购发票数 | 24(21 UK 本地 + 2 EU 采购 + 1 免税保险) |
| 进口 C79 | 2 笔(£85,000 货值) |
| Box 1 | 41,523.50(国内 £41,520 + 零税率调整 £3.50) |
| Box 2 | 13,700(EU acq reverse charge:DE 10,000 + NL 3,700) |
| Box 4 | 47,612(进项税抵扣) |
| **Box 5 净 VAT** = 55,223.50 - 47,612 | **7,611.50**(应付) |
| Box 6 | 282,750 |
| Box 7 | 240,460 |
| Box 8 | 42,450(EU B2B 4 国) |
| Box 9 | 68,500(EU acq 2 国) |

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

## 💡 演示价值

- **最复杂单国场景** — 6 国触点 + 进口 + 零税率调整
- **数字可信** — 用户点"演示"按钮,后端算出来一模一样,**没有"演示漂移"**
- **"明星案例"** — 当用户问"能不能给我看一个真实点的例子?",这是答案
- **ERPNext 兼容** — `source_docs/*.json` 是 `Sales Invoice` / `Purchase Invoice` DocType 标准 JSON

---

## 🔗 关联(本卡片的核心价值是"前后端一致")

| 关联 | 文件 | 关系 |
|---|---|---|
| **后端 fixture** | `data/erp_samples/case-a-uk-subsidiary/` | 9-Box 数字**完全一致** |
| **同集团 CN 视角** | `casePresets.ts#case-b-cn-parent` | 同一集团,不同视角 |
| **入门 case** | `casePresets.ts#case-x-uk-standard` | 简化教学版 |
| **集团主 case**(Agent 兜底) | `frontend/src/data/realCaseData.json` | 集团完整数据(独立入口) |

> **核心承诺**:本卡片展示什么数字,后端 orchestrator 就跑出什么数字。
