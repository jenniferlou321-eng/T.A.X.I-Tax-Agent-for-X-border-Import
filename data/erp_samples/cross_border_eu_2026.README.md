# Case 3 · cross_border_eu_2026 — 极简 EU B2B 单元测试案例

> **角色**:**最小 EU B2B 单元测试**,跑得快。  
> **文件**:`data/erp_samples/cross_border_eu_2026.json`(22 行 ImportResult)  
> **演示目的**:纯净的"全部 0% 出口"场景 + VIES 校验 + 客户 VAT 号格式校验。

---

## 🏢 实体

- UK 子公司,向 DE/FR 客户供货
- (无第三方细节,本 case 是"假想"客户)

---

## 💼 业务详情

| 维度 | 数值 |
|---|---|
| 销售发票数 | 2 张(全部 EU B2B) |
| 采购发票数 | 1 张(EU acq) |
| 总销售额 | £8,000 |
| 总采购额 | £2,000 |
| 业务规模 | < £100,000 |

---

## 🧾 交易明细

| 交易 | 日期 | 客户/供应商 | 国家 | 净额 | VAT | 税率 | 税码 |
|---|---|---|---|---|---|---|---|
| S-EU-001 | 2026-01-15 | Deutsche GmbH | 🇩🇪 DE | £5,000 | £0 | 0% | T9(B2B) |
| S-EU-002 | 2026-01-20 | French SARL | 🇫🇷 FR | £3,000 | £0 | 0% | T9(B2B) |
| P-EU-001 | 2026-01-18 | Italian SpA | 🇮🇹 IT | £2,000 | £0 | 0% | T2(EU acq) |

---

## 📊 9-Box(预期全 0 销项税)

| Box | 数值 | 备注 |
|---|---|---|
| Box 1 | 0 | 无本地销售 |
| Box 2 | 0 | 反向 charge 0%(无 VAT) |
| Box 3 | 0 | = Box1 + Box2 |
| Box 4 | 0 | 无进项税 |
| Box 5 | **0** | 净 VAT(应付 0) |
| Box 6 | 8,000 | 仅 B2B 销项 |
| Box 7 | 2,000 | 仅 EU 采购 |
| Box 8 | **= Box 6** = 8,000 | 全部 B2B,0% |
| Box 9 | 2,000 | EU 采购 |

**scheme_flags**:`[]`(空 —— 没有 Capital Goods Scheme、C79、TP 等复杂规则)

---

## 🌍 跨境触点(3 国)

| 国家 | 角色 | 触点 |
|---|---|---|
| 🇩🇪 **德国** | B2B 客户 | £5,000 销(0% reverse charge) |
| 🇫🇷 **法国** | B2B 客户 | £3,000 销(0% reverse charge) |
| 🇮🇹 **意大利** | 供应商 | £2,000 采(0% reverse charge) |

---

## 🧪 测试用途

- ✅ VIES 客户 VAT 号格式校验(DE 9 位 + FR 11 位字符)
- ✅ 零税率路径(全部 0% 出口,无本地销项)
- ✅ EU 采购 reverse charge(Box 2、Box 9 同时增加,但都是 0)
- ✅ 极简 fixture,跑得**最快**(毫秒级)

---

## 📂 文件结构

```
data/erp_samples/cross_border_eu_2026.json
  ├── sales[]              2 张
  ├── purchases[]          1 张
  ├── erp_provided_boxes   9-Box 数字
  ├── source_profile       "demo"
  ├── source_hash          "cross-border-eu-2026"
  ├── warnings[]           空
  └── rejected_rows[]      空
```

---

## 💡 演示价值

- **极简** — 单测用途,跑得快
- **VIES 校验** — 演示客户 VAT 号格式校验(DE + FR + IT)
- **零税率路径** — 纯净的"全部 0% 出口"场景
- **CI 友好** — 不需要 API key,无外部依赖

---

## 🔗 关联

- **后端旗舰**:`data/erp_samples/techflow_q1_2026.json`(EU 4 国 B2B + 2 国 acq 复杂版)
- **集团目录式**:`data/erp_samples/cn_parent_uk_sub_q1_2026/`(集团 + TP 复杂版)
- **集团主 case**:`frontend/src/data/realCaseData.json`(完整 8 国触点)
