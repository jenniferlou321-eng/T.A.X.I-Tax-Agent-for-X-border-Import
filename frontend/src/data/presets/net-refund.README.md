# Case 5 · net-refund — 净退税申报(退税卡片)

> **角色**:**退税场景演示** — Box 5 为负,触发"HMRC 应在 30 天内退款"流程。  
> **文件**:`frontend/src/data/casePresets.ts` lines 40–59  
> **ID**:`net-refund`  
> **图标**:📉 TrendingDown  
> **演示目的**:高进项税 / 重资产 / 制造业典型,演示 State Machine 流转到 REFUND_PENDING。

---

## 🏢 实体

- **名称**:British Manufacturing Ltd(典型 UK 本地制造企业)
- **VRN**:960606228
- **行业**:制造业(高进项税)

---

## 💼 业务详情

| 维度 | 数值(£) |
|---|---|
| Box 1 销项税 | 100(£500 × 20%) |
| Box 2 采购 reverse charge | 0 |
| Box 4 抵扣进项税 | **300**(高额抵扣) |
| **Box 5 净 VAT** = 100 - 300 | **-200**(HMRC 应退!) |
| Box 6 销售总额 | 500(低) |
| Box 7 采购总额 | 1,500(高,是销售的 3 倍) |
| Box 8 EU 销售 | 0 |
| Box 9 EU 采购 | 0 |

---

## 📊 9-Box 关系图(退税流)

```
   Box 1(100) ─┐
                ├─→ Box 3(100) ─→ Box 5(-200) ─→ HMRC 退款
                  无 Box 2          ↑
                                    │ Box 4(300) 大额抵扣
```

> **关键**:Box 5 为负 → State Machine 走到 `ACCEPTED → REFUND_PENDING`,用户 30 天内应收到 HMRC 打款。

---

## 🌍 跨境触点

- 🇬🇧 **英国** — 唯一申报国,**但金额进的是 UK 财政部退税账户**

---

## 💡 演示价值

- **退税场景** — Box 5 为负,触发"HMRC 应在 30 天内退款"流程
- **高进项税场景** — 重资产 / 制造业典型(原材料、设备、能源)
- **State Machine 演示** — `ACCEPTED → REFUND_PENDING` 状态流转
- **BDR 暗示** — Box 4 大 → 可能有坏账(Bad Debt Relief)需要审计
- **现金流展示** — 退税是 Q2 现金流入的重要一环

---

## 🔗 关联

- **同层级卡片**:`casePresets.ts#standard-taxable`(正常)、`#zero-filing`(零值)、`#real-business-q1`(旗舰)
- **BDR 概念**:`data/tax_knowledge/taxonomy/concepts.yaml#bad_debt_relief`
