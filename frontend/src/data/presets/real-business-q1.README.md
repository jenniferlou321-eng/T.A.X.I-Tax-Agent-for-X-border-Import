# Case 7 · real-business-q1 — 真实企业季度申报(前端旗舰卡片)

> **角色**:**前端"明星卡片"** —— 当用户问"能不能给我看一个真实点的例子?",这就是答案。  
> **文件**:`frontend/src/data/casePresets.ts` lines 80–99  
> **ID**:`real-business-q1`  
> **图标**:🏢 Building2  
> **演示目的**:与后端 ERP fixture `techflow_q1_2026.json` 的 9-Box 数字**严格一致**,让前端卡片与后端 orchestrator 跑出来的结果**1:1 对应**。

---

## 🏢 实体

- **名称**:TechFlow Distribution Ltd(UK 子公司)
- **VRN**:960606228
- **VAT 期间**:2026 Q1(periodKey 25A1,截止 2026-05-07)
- **与后端一致性**:`data/erp_samples/techflow_q1_2026.json` 的 `erp_provided_boxes` 字段**完全相等**

---

## 💼 业务详情(与 C1 1:1 对应)

| 维度 | 数值(£) |
|---|---|
| Box 1 | 41,523.50(国内 £41,520 + 零税率调整 £3.50) |
| Box 2 | 13,700(EU acq reverse charge:DE 10,000 + NL 3,700) |
| Box 4 | 47,612(进项税抵扣) |
| **Box 5 净 VAT** = 55,223.50 - 47,612 | **7,611.50**(应付) |
| Box 6 | 282,750(27 笔销售) |
| Box 7 | 240,460(24 笔采购) |
| Box 8 | 42,450(EU B2B 4 国) |
| Box 9 | 68,500(EU acq 2 国) |

---

## 📊 9-Box(完整版)

| Box | 数值 | 拆解 |
|---|---|---|
| **Box 1** | 41,523.50 | £41,520 国内 20% + £3.50 零税率调整 |
| **Box 2** | 13,700 | DE £10,000(20%)+ NL £3,700(20%)reverse charge |
| **Box 3** | 55,223.50 | = Box1 + Box2 |
| **Box 4** | 47,612 | 全部可抵扣进项税(含 EU acq reverse charge) |
| **Box 5** | **7,611.50** | = Box3 - Box4,应付 HMRC |
| **Box 6** | 282,750 | 21 国内 + 4 EU B2B + 2 零税率 |
| **Box 7** | 240,460 | 21 UK + 2 EU acq + 1 免税保险 |
| **Box 8** | 42,450 | DE 12,500 + FR 15,000 + ES 8,750 + SE 6,200 |
| **Box 9** | 68,500 | DE 50,000 + NL 18,500 |

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

---

## 🧾 涉及的特殊规则(scheme_flags)

| Flag | 含义 |
|---|---|
| **Zero-rating adjustment** | Box 1 包含 £3.50 零税率调整(舍入) |
| **EU B2B reverse charge** | 出口 0%(Box 8 累计),客户 reverse charge |
| **EU acquisition reverse charge** | UK 自计:Box 2 + Box 4 同增 |
| **Import C79** | UK 关税收讫,Box 4 抵扣 |
| **Non-recoverable** | 部分进项税不可抵扣(本 case 已剔除) |

---

## 💡 演示价值

- **最复杂单国场景** — 6 国触点但只走 UK 通道
- **数字可信** — 用户点"演示"按钮,后端算出来一模一样,**没有"演示漂移"**
- **"明星案例"** — 当用户问"能不能给我看一个真实点的例子?",这是答案
- **教学与实战并重** — 既有 4 国 EU B2B、2 国 EU acq、零税率调整等"教科书场景",又真实到能直接用于合规培训

---

## 🔗 关联(本卡片的核心价值是"前后端一致")

| 关联 | 文件 | 关系 |
|---|---|---|
| **后端旗舰** | `data/erp_samples/techflow_q1_2026.json` | 9-Box 数字**完全一致**(都经过 Python 自洽核对) |
| **集团主 case** | `frontend/src/data/realCaseData.json` | 同一实体(TechFlow UK Ltd)+ 同期间(2026 Q1) |
| **集团目录式** | `data/erp_samples/cn_parent_uk_sub_q1_2026/` | 同一集团架构,但数字/期间/触点不同 |

> **核心承诺**:本卡片展示什么数字,后端 orchestrator 就跑出什么数字。这条不变量是 T.A.X.I. "演示闭环"的核心。
