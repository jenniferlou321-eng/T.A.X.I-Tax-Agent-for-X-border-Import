# Case 6 · zero-filing — 零值申报(强制申报演示)

> **角色**:**强制申报义务**演示 —— 即便没业务也要按时报。  
> **文件**:`frontend/src/data/casePresets.ts` lines 60–79  
> **ID**:`zero-filing`  
> **图标**:⭕ CircleDashed  
> **演示目的**:9 个 Box 全 0 的 nil return,演示 State Machine 完整走通一遍 PENDING → SUBMITTED → ACCEPTED。

---

## 🏢 实体

- **名称**:NewCo Consulting Ltd(咨询公司,淡季)
- **VRN**:960606228
- **行业**:管理咨询

---

## 💼 业务详情

**全部 9 个 Box 均为 0**

| Box | 数值 |
|---|---|
| Box 1 | 0 |
| Box 2 | 0 |
| Box 3 | 0 |
| Box 4 | 0 |
| Box 5 | 0 |
| Box 6 | 0 |
| Box 7 | 0 |
| Box 8 | 0 |
| Box 9 | 0 |

---

## 📊 9-Box(全 0)

```
   Box 1(0) ─┐
              ├─→ Box 3(0) ─→ Box 5(0) ─→ HMRC (无动作)
   Box 2(0) ─┘                ↑
                               │ Box 4(0)
```

---

## 🌍 跨境触点

- 🇬🇧 **英国** — 唯一申报国,**但申报动作仍必须发生**(HMRC 仍要求提交 nil return)

---

## 💡 演示价值

- **强制申报义务** — 即便没业务也要按时报
- **State Machine 演示** — `PENDING → SUBMITTED → ACCEPTED`,完整走通一遍
- **低风险路径** — 无需 orchestrator 做复杂计算,纯流程演示
- **合规教育** — 提醒用户漏报会有 £100+ 罚款(3 个月内)或 £400+(超期)
- **教学补充** — 与 `standard-taxable` 配合,演示"无业务" vs "有业务"两种申报

---

## 🔗 关联

- **同层级卡片**:`casePresets.ts#standard-taxable`(正常)、`#net-refund`(退税)、`#real-business-q1`(旗舰)
- **State Machine**:`backend/services/state_machine.py`(定义 PENDING / SUBMITTED / ACCEPTED 等状态)
