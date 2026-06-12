# Case 4 · standard-taxable — 标准应税申报(入门卡片)

> **角色**:**产品演示第一页** —— 让用户 5 秒理解 UK VAT 9-Box 怎么填。  
> **文件**:`frontend/src/data/casePresets.ts` lines 21–39  
> **ID**:`standard-taxable`  
> **图标**:📄 FileText  
> **演示目的**:数字小、关系清晰、20% 税率一眼看懂的"零复杂度入门"场景。

---

## 🏢 实体

- **名称**:Anker UK Ltd(消费电子跨境大佬的 UK 子公司)
- **VRN**:960606228
- **行业**:消费电子零售

---

## 💼 业务详情

| 维度 | 数值(£) |
|---|---|
| Box 1 销项税 | 250(£1,250 × 20%) |
| Box 2 采购 reverse charge | 50 |
| Box 4 抵扣进项税 | 120 |
| **Box 5 净 VAT** = Box1 + Box2 - Box4 | **180**(应付 HMRC) |
| Box 6 销售总额 | 1,250 |
| Box 7 采购总额 | 600 |
| Box 8 EU 销售 | 100(假设有少量 B2B) |
| Box 9 EU 采购 | 50(假设有少量 acq) |

---

## 📊 9-Box 关系图(用户第一眼看到的"教学图")

```
   Box 1(250) ─┐
                ├─→ Box 3(300) ─→ Box 5(180) ─→ HMRC
   Box 2(50)  ─┘                  ↑
                                   │ Box 4(120) 抵扣
```

---

## 🌍 跨境触点

- 🇬🇧 **英国** — 唯一申报国
- 欧盟 B2B / 采购量都很小(Box 8 = 100,Box 9 = 50),**不是主菜**

---

## 💡 演示价值

- **0 复杂度入门** — 数字小、关系清晰、20% 税率一眼看懂
- **正常应交场景** — Box 5 为正,触发"付款给 HMRC"流程
- **适合产品演示第一页** — 让用户 5 秒理解 UK VAT 9-Box 怎么填
- **教学层级** — 9-Box 自洽(Box 1+Box 2 = Box 3,Box 3-Box 4 = Box 5)

---

## 🔗 关联

- **同层级卡片**:`casePresets.ts#net-refund`(退税)、`#zero-filing`(零值)、`#real-business-q1`(旗舰)
- **后端对应**:`data/erp_samples/techflow_q1_2026.json`(同 UK 通道,数字大 100 倍)
