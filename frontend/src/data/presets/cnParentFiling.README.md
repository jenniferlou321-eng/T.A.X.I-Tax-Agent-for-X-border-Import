# cnParentFiling — Case B 的 CN 视角集团数据

> **角色**:Case B(`case-b-cn-parent`)的**集团数据 + 申报数字**展示数据,挂在 preset 的 `groupDataRef` 字段上。  
> **文件**:`frontend/src/data/cnParentFiling.json`  
> **被消费方**:`CasePreviewPage` 渲染 `CnGroupSummaryCard`,`AgentChatPage` 兜底链不读这个(兜底走 `realCaseData.json`)。

---

## 🏢 实体(同 Case A 集团,CN 母主场)

- **名称**:Shenzhen TechFlow Technology Co., Ltd.(深圳拓弗科技)
- **统一社会信用代码**:91440300MA5DC9X
- **VAT 期间**:2026 Q1(月度申报)

---

## 📊 关键数字(CN 视角)

| 税种 | 应缴(¥) | 备注 |
|---|---|---|
| 增值税(VAT) | 551,000 | 13% 内销 + 6% 服务 - 进项抵扣 |
| 企业所得税(CIT) | 950,000 | 25% × ¥3,800,000 应纳税所得 |
| 预提税(WHT) | 115,500 | 特许权 7% + 管理费 5%(中港税收安排) |
| **合计** | **1,616,500** | 月度 + Q1 预缴 |

---

## 🧾 TP / DAC6 / BEPS 2.0

| 项 | 状态 |
|---|---|
| TP 调整额 | +¥320,000(Cost Plus 8-12% 调整) |
| 同期资料 | Master File + Local File |
| DAC6 C1(b) | ✅ 跨境关联方 TP 安排,UK 子需向 HMRC 披露 |
| BEPS 2.0 Pillar Two | 不在范围内(< €750M) |

---

## 💡 演示价值

- **中国主场视角** — 不是 UK 9-Box 体系,改用 CN VAT/CIT/WHT/TP 完整数字
- **集团内部往来演示** — IT 服务 / 特许权 / 管理费 3 类典型关联交易
- **中港税收协定** — 5% / 7% 优惠税率(标准 10%)
- **与 Case A 数字对账** — 两个视角在**不同报表层**,不矛盾

---

## 🔗 关联

| 关联 | 文件 | 关系 |
|---|---|---|
| **Case A(UK 视角)** | `casePresets.ts#case-a-uk-subsidiary` | 同一集团,不同视角 |
| **后端 fixture** | `data/erp_samples/case-b-cn-parent/` | 帐套数据来源 |
| **预期输出** | `data/erp_samples/case-b-cn-parent/expected_outputs.json` | 数字来源 |
| **Agent 兜底** | `frontend/src/data/realCaseData.json` | 集团完整数据(独立入口) |
