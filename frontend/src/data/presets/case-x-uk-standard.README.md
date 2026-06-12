# Case X · case-x-uk-standard — 入门:UK VAT 标准应交(前端卡片)

> **角色**:**产品演示第一页** —— 让用户 5 秒理解 UK VAT 9-Box 怎么填。  
> **文件**:`frontend/src/data/casePresets.ts` 第 1 项(原 `standard-taxable` 改名)  
> **前端 ID**:`case-x-uk-standard`  
> **后端 fixture**:`data/erp_samples/case-x-uk-standard/`(完整目录式)  
> **演示目的**:数字小、关系清晰、20% 税率一眼看懂的"零复杂度入门"场景。

---

## 🏢 实体

- **名称**:Anker UK Ltd(消费电子零售)
- **VRN**:960606228
- **VAT 期间**:2026 Q1

---

## 💼 业务详情

| 维度 | 数值(£) |
|---|---|
| 销售发票数 | 7(6 国内 20% + 1 EU B2B 0%) |
| 采购发票数 | 6(5 UK 本地 + 1 EU acq 0%) |
| Box 1 销项税 | 250(£1,250 × 20%) |
| Box 2 采购 reverse charge | 50 |
| Box 4 抵扣进项税 | 120 |
| **Box 5 净 VAT** = Box1 + Box2 - Box4 | **180**(应付 HMRC) |
| Box 6 销售总额 | 1,250 |
| Box 7 采购总额 | 600 |
| Box 8 EU 销售 | 100 |
| Box 9 EU 采购 | 50 |

---

## 📊 9-Box 关系图(教学图)

```
   Box 1(250) ─┐
                ├─→ Box 3(300) ─→ Box 5(180) ─→ HMRC 付款
   Box 2(50)  ─┘                  ↑
                                   │ Box 4(120) 抵扣
```

---

## 🌍 跨境触点

- 🇬🇧 **英国** — 唯一申报国
- 🇩🇪 德国:1 笔 B2B 客户(£100 销)
- 🇮🇹 意大利:1 笔供应商(£50 采,reverse charge)
- 触点都很小,**不是主菜** —— 入门演示

---

## 💡 演示价值

- **0 复杂度入门** — 数字小、关系清晰、20% 税率一眼看懂
- **正常应交场景** — Box 5 为正,触发"付款给 HMRC"流程
- **适合产品演示第一页** — 让用户 5 秒理解 UK VAT 9-Box 怎么填
- **教学层级** — 9-Box 自洽(Box 1+Box 2 = Box 3, Box 3-Box 4 = Box 5)
- **ERPNext 兼容** — `source_docs/*.json` 是 `Sales Invoice` / `Purchase Invoice` DocType 标准 JSON

---

## 🔗 关联

| 关联 | 文件 | 关系 |
|---|---|---|
| **同集团 UK 子公司** | `casePresets.ts#case-a-uk-subsidiary` | 升级版(集团 + 多国) |
| **同集团 CN 母视角** | `casePresets.ts#case-b-cn-parent` | 同一集团,不同视角 |
| **后端 fixture** | `data/erp_samples/case-x-uk-standard/` | 完整目录式 |
| **Agent 兜底** | `frontend/src/data/realCaseData.json` | 集团完整数据(独立入口) |
