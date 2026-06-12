# Case 1 · techflow_q1_2026 — UK VAT 旗舰季度案例(后端 E2E 旗舰)

> **角色**:orchestrator 6 阶段管线 E2E 测试 + 与前端 `casePresets.ts#real-business-q1` 数字**严格一致**。  
> **文件**:`data/erp_samples/techflow_q1_2026.json`(634 行 ImportResult)  
> **演示目的**:覆盖 UK VAT 几乎所有复杂度(零税率调整、EU B2B、EU acq reverse charge、进口 C79),数字经过 Python 自洽核对。

---

## 🏢 实体

- **名称**:TechFlow Distribution Ltd
- **VRN**:960606228
- **EORI**:GB960606228000
- **VAT 期间**:2026-01-01 ~ 2026-03-31(Q1,periodKey 25A1)
- **申报截止**:2026-05-07

---

## 💼 业务详情

| 维度 | 数值 |
|---|---|
| 销售发票数 | 27 张(21 国内 + 4 EU B2B + 2 零税率) |
| 采购发票数 | 24 张(21 UK 本地 + 2 EU 采购 + 1 免税保险) |
| 国内销售 VAT | £41,520 |
| 零税率调整 | £3.50(舍入) |
| EU B2B 销售 | DE £12,500 + FR £15,000 + ES £8,750 + SE £6,200 = **£42,450** |
| EU 采购 reverse charge | DE £50,000 + NL £18,500 = **£68,500** |
| 进口 C79 | UK 关税收讫,可全额抵扣(Box 4) |

---

## 📊 9-Box 自洽核对(已 Python 求和验证)

| Box | 内容 | 数值 |
|---|---|---|
| **Box 1** | 销售 VAT | **41,523.50**(41,520 + 3.50 零税率调整) |
| **Box 2** | EU 采购 reverse charge VAT | **13,700**(DE 10,000 + NL 3,700) |
| **Box 3** | VAT 总应付 = Box1 + Box2 | **55,223.50** |
| **Box 4** | 抵扣进项税 | **47,612**(含 EU acq reverse charge) |
| **Box 5** | 净 VAT = Box3 - Box4 | **7,611.50**(应付 HMRC) |
| **Box 6** | 销售总额(不含 VAT) | **282,750** |
| **Box 7** | 采购总额(不含 VAT) | **240,460** |
| **Box 8** | EU B2B 销售额 | **42,450** |
| **Box 9** | EU 采购额 | **68,500** |

> **校验方式**:对每张 sales_invoice 累加 `net_amount` 与 `vat_amount`,与 `erp_provided_boxes` 数值完全一致。

---

## 🌍 跨境触点(6 国)

| 国家 | 角色 | 触点金额 |
|---|---|---|
| 🇩🇪 **德国** | B2B 客户 + 供应商 | £12,500 销 + £50,000 采 + £10,000 reverse charge |
| 🇫🇷 **法国** | B2B 客户 | £15,000 销 |
| 🇪🇸 **西班牙** | B2B 客户 | £8,750 销 |
| 🇸🇪 **瑞典** | B2B 客户 | £6,200 销 |
| 🇳🇱 **荷兰** | 供应商 | £18,500 采 + £3,700 reverse charge |
| 🇬🇧 **英国** | 主体申报 | 全部 9 盒 |

---

## 🧾 scheme_flags 涉及的特殊规则

| Flag | 含义 |
|---|---|
| **EU B2B reverse charge** | 出口 0%(Box 8 累计),客户在其本国 reverse charge |
| **EU acquisition reverse charge** | UK 进口自计:Box 2 + Box 4 同时增加 |
| **Import C79** | UK 关税收讫,Box 4 抵扣进项税 |
| **Zero-rating adjustment** | Box 1 包含 £3.50 零税率调整(舍入差) |
| **Non-recoverable VAT** | 部分进项税不可抵扣(如娱乐费用,本 case 已剔除) |

---

## 📂 文件结构

```
data/erp_samples/techflow_q1_2026.json    ← flat JSON, ImportResult 格式
  ├── sales_invoices[]                    27 张销售发票
  ├── purchase_invoices[]                 24 张采购发票
  ├── expense_claims[]                    费用报销
  ├── intra_group_transactions[]          集团内部往来
  ├── erp_provided_boxes                  ERP 已计算的 9-Box(用于对比)
  ├── source_profile / source_hash
  ├── warnings[]
  └── rejected_rows[]
```

---

## 💡 演示价值

- **数字已与 A5' 卡片 100% 对齐** — 用户点击"真实企业季度申报"卡片,后端 orchestrator 跑出来的 Box 6/7/8/9 与卡片显示完全一致
- **覆盖几乎所有 UK VAT 复杂度** — 零税率、reverse charge、进口 C79、Box 1 舍入
- **最严格的"4 国 EU B2B + 2 国 EU acq"演示**
- **数据来源**:`techflow_q1_2026.json` 是从真实跨境电商 Q1 脱敏而来,数字"看起来真实"

---

## 🔗 关联

- **前端卡片对应**:`frontend/src/data/casePresets.ts#real-business-q1`(A5',9-Box 数字严格一致)
- **集团主 case**:`frontend/src/data/realCaseData.json`(完整 3 层集团)
- **集团目录式 fixture**:`data/erp_samples/cn_parent_uk_sub_q1_2026/`(CN 母 + HK 控 + UK 子,带源文档)
