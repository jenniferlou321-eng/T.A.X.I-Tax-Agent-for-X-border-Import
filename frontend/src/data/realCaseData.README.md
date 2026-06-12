# Case 0 · TechFlow Group 跨境集团 2026 Q1(Agent 兜底主案例)

> **角色**:AgentChatPage 在用户点击"加载示例"时的兜底数据。  
> **文件**:`realCaseData.json`(单源,后端 `/api/agent/sample-data` 也读它)  
> **演示目的**:完整跨境集团结构下的多国税务协同 —— 1 个 UK 子公司触发的申报义务,实际牵动 8 个司法管辖区。

---

## 🏢 集团架构

```
🇨🇳 深圳拓弗科技 (母公司)              ← 一般纳税人, 适用 13% 增值税率
        │ 100%
        ↓
🇭🇰 TechFlow Holdings (HK) Ltd         ← 区域 IP 控股 + 财资中心
        │ 100%
        ↓
🇬🇧 TechFlow Distribution Ltd           ← 实际申报实体, B2C 跨境电商
        VRN: 960606228
        EORI: GB960606228000
        期间: 2026 Q1 (25A1, 申报截止 2026-05-07)
```

**关联方认定**:OECD Article 9 / UK CTA 2010 s.518 —— 共同控制。

---

## 💼 业务画像

- **行业**:消费电子跨境电商(B2B 批发 + B2C 零售)
- **销售渠道**:Currys / John Lewis / Argos(B2B)+ Amazon UK + Shopify(B2C)
- **Q1 2026 规模**:
  - 销售 ~£1.2M(英国本地为主 + 部分 EU B2B)
  - 采购 ~£0.9M(UK 本地供应商 + EU 采购 + 1 笔 CN 进口)
  - 集团内部服务费:CN 母公司向 UK 子公司收取 IT 系统费、商标授权费
- **集团内部服务费**:CN 母公司向 UK 子公司收取 IT 系统费、商标授权费

---

## 🌍 跨境触点(为什么"牵动 8 国")

| 跨境元素 | 涉及国家 | 会计处理 | 申报税种 |
|---|---|---|---|
| UK → DE/FR/ES/SE B2B 销售 | 4 国 | UK 报 0%(Box 8 累计);客户 reverse charge | UK VAT + 客户本国 VAT |
| UK ← DE/NL 采购 | 2 国 | UK 做 reverse charge:Box 2 + Box 4 同增 | UK VAT |
| UK 进口 C79 | 🇬🇧 UK + 提单始发 🇭🇰 | Box 4 抵扣进项税 | UK VAT + 关税 |
| CN 母公司收 UK 服务费 | 🇨🇳 CN | 6% VAT + 25% CIT + 预提税(中港税收协定可降至 5%) | CN VAT / CIT / WHT |
| HK 控股收 UK 股息 / 授权费 | 🇭🇰 HK | 地域来源原则,股息不课税;授权费 4.95% | HK Profits Tax |
| 集团内部 TP 安排 | 🇨🇳🇭🇰🇬🇧 | Cost Plus 8-12%(集团服务);BEPS 2.0 Pillar Two 风险 | 转让定价同期资料 |
| DAC6 强制披露 | 🇬🇧 UK | 跨境架构达到 hallmark 阈值,需向 HMRC 报告 | DAC6 |
| US/AU 出口(超 VAT 范围) | 🇺🇸🇦🇺 | 0% 出口, EC Sales List 不含 | UK VAT 0% |

---

## 📋 申报矩阵

| 国家 | 申报税种 | 状态 | 渠道 | 备注 |
|---|---|---|---|---|
| 🇬🇧 **英国** | VAT (MTD) | ✅ live | HMRC API | 季度 + 进口 C79 + DAC6 |
| 🇨🇳 **中国** | VAT + 企所税 + 预提税 | 🟡 placeholder | Browser Channel(未来) | 集团服务 6% / CIT 25%(可减按 10% 高新) |
| 🇭🇰 **香港** | 利得税 | 🟡 placeholder | Manual(暂) | 8.25% / 16.5% 两级制(地域来源) |
| 🇩🇪🇫🇷🇪🇸🇸🇪 **EU 4 国** | VAT B2B 0% | 🟡 placeholder | UK 开 0% 发票,客户 reverse charge | 仅 VIES 留痕 |
| 🇩🇪🇳🇱 **EU 2 国** | VAT reverse charge | 🟡 placeholder | UK 自计(Box 2 + Box 4) | 客户国家无动作 |
| 🌐 **OECD** | DAC6 / BEPS | 🟡 placeholder | 文档 | 跨境架构 hallmark A、C |
| 🇺🇸🇦🇺 | (出口,超 VAT 范围) | — | 仅 UK 0% 出口 | EC Sales List 不含 |

---

## 📂 数据结构(field 速查)

| 顶层 key | 内容 |
|---|---|
| `case_metadata` | case 名称、场景、版本号 |
| `group_structure` | 3 层股权链 + 关联方认定依据 |
| `uk_subsidiary` | 申报实体的完整交易明细(sales_invoices / purchase_invoices / period) |
| `intra_group_transactions` | 集团内部往来:管理费、特许权使用费、股息 |
| `tp_documentation` | TP 同期资料 + BEPS 2.0 Pillar Two GloBE 规则 |
| `dac6_disclosures` | DAC6 强制披露 5 大 hallmark |
| `expected_outputs` | 预期 9-Box + EC Sales List + 申报金额 |

---

## 💡 演示价值

- **完整集团图谱** — 不只是"UK 一家",而是 8 国主体
- **多税种协同** — VAT / CIT / IIT / 预提税 / TP / DAC6 全在视野内
- **AI Agent 用例** — 当用户问"我们集团 Q1 怎么报税",Agent 必须先定位 4 个主要申报国,再依次展开每个国家的表单

---

## 🔗 关联

- **后端旗舰 ERP fixture**:`data/erp_samples/case-a-uk-subsidiary/`(UK 子公司 Q1 数字严格一致)
- **集团目录式 fixture**:`data/erp_samples/case-b-cn-parent/`(CN 母 + HK 控 + UK 子,目录式 + 38 份源文档)
- **前端卡片对应**:`casePresets.ts#case-a-uk-subsidiary`(A,数字与此 case 严格一致)
