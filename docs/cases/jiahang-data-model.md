# 嘉汉案例 — 数据模型说明

> **目的**:说明 `/root/cases/案例一_整合单年度版_*.md` 源文件与 TAXI 数据资产 `data/erp_samples/case-jiahang-{uk,cn}-fy2023/erp_import.json` 之间的**映射关系**。
>
> 这是开发者理解"如何把业务故事转成 Pydantic 兼容的 ImportResult"的关键文档。

---

## 一、整体映射原则

源文件每笔 `C1-xxx` 业务 → ImportResult 的 **1 行**(`sales` 或 `purchases` 数组中的一项)。

| 业务性质 | 落入 | 理由 |
|---|---|---|
| 销售 / 出口 / 收入确认 | `sales[]` | 产生应收/收入 |
| 采购 / 进口 / 费用 / 税款支付 / 工资发放 | `purchases[]` | 产生应付/费用/资产 |

> 重要例外:**股息支付 / 利息支付**作为 finance activity 走 `purchases`(因为是货币流出);
> **应收 / 应付** 走 sales / purchases(因为有 counterparty)。
> 工资发放走 `purchases`(公司角度是费用,也是对外支付)。

---

## 二、`txn_type` 枚举(自由扩展字段)

定义在 `erp_import.json` 每行的 `txn_type` 字段(Pydantic 默认忽略,仅前端展示用):

| 取值 | 含义 | 典型行 |
|---|---|---|
| `domestic_sale` | 本地销售(UK 标准税率 20%) | C1-101 / C1-105 / C1-115 |
| `export_eu` | 出口 EU(零税率) | C1-108 / C1-116 |
| `domestic_purchase` | 本地采购(可抵) | C1-113 / C1-114 |
| `eu_acquisition_rc` | EU 反向征收采购 | C1-106 / C1-128a |
| `import_goods` | 进口(中国 → UK) | C1-103 |
| `intra_group_export` | 集团内部出口(CN→UK) | C1-040a / C1-040b |
| `loan_disbursement` | 贷款本金借出 | C1-010a |
| `loan_repayment` | 贷款本金归还 | C1-121 / C1-121a / C1-121b |
| `interest_payment` | 利息支付(带 WHT) | C1-109 / C1-109a |
| `royalty_payment` | 特许权使用费支付(带 WHT) | C1-110 / C1-110a |
| `dividend_payment` | 股息支付(0% WHT) | C1-120 / C1-123 / C1-149a |
| `payroll` | 工资发放 | C1-104 / C1-118 / C1-122 |
| `office_rent` | 办公场地租金 | C1-111 |
| `business_rates` | 营业房产税 | C1-111(合并项) |
| `capital_asset` | 固定资产采购 | C1-119 / C1-148 |
| `cross_year_reversal` | 跨年度差异转回 | **C1-000a**(FY2022 计提本年支付) |
| `cross_year_collection` | 跨年度收款 | **C1-000b**(FY2022 销售本年收款) |
| `tax_payment` | 税款支付(VAT/CT/CIT 等) | C1-125(CT 缴款) / C1-107(VAT Q1 申报) |
| `tax_filing_recon` | 汇算清缴调整 | **C1-041**(CN 汇算清缴) |
| `import_vat_pva` | 进口 VAT PVA 递延(UK) | C1-103 进口 |

---

## 三、`tax_code` 枚举(自定义业务代码)

`tax_code` 字段是 Pydantic 必填 string 字段(原 schema 设计给 9-Box 体系),jiahang 案例扩展用以下编码:

### 3.1 UK 税种编码

| 编码 | 含义 | 9-Box 影响 |
|---|---|---|
| `T1-UK-STANDARD` | UK 标准税率 20% 销售 | Box 1(+) / Box 6 |
| `T0-UK-ZERO` | UK 零税率(出口 EU) | Box 6(不影响 Box 1) |
| `T2-UK-EU-RC` | UK EU 反向征收采购 | Box 2(+) / Box 4(-) / Box 7 / Box 9 |
| `T8-UK-IMPORT` | UK 进口(CIF + Duty) | Box 4(-) / Box 7 |
| `T1-UK-DOMESTIC-PURCHASE` | UK 本地采购(可抵) | Box 4(-) / Box 7 |
| `WH-INT-10` | WHT 利息支付(10% 中英协定) | 不入 9-Box,走 CT600 |
| `WH-ROY-10` | WHT 特许权使用费(10% 中英协定) | 不入 9-Box |
| `WH-DIV-0` | WHT 股息(0%,100% 控股豁免) | 不入 9-Box |
| `BR-UBR-512` | Business Rates(UBR 51.2p) | 不入 9-Box |
| `AL-EXEMPT` | Apprenticeship Levy(FY2023 < £3M 免税) | 不入 9-Box |
| `CT-FY2023` | UK CT 应付款 | 不入 9-Box |
| `EMP-NIC` | PAYE & NIC 代扣 | 不入 9-Box |
| `FX-LOAN-PRINCIPAL` | 关联方贷款本金(非应税) | 集团内 |
| `FX-DIV-RECEIVED` | 关联方股息收到(母公司端) | 集团内 |

### 3.2 CN 税种编码

| 编码 | 含义 | 备注 |
|---|---|---|
| `CN-VAT-13` | CN VAT 标准税率 13% | 销项-进项 |
| `CN-VAT-5-SIMPLE` | CN VAT 5% 简易计税(不动产租赁) | C1-006 |
| `CN-VAT-3-PS` | CN VAT 3% 征收率(小规模物业) | C1-006b |
| `CN-CIT-25` | CN CIT 25% | 季度预缴+汇算清缴 |
| `CN-FTC` | 境外税收抵免 | 中英协定第 22 条 |
| `CN-IIT-WH` | 个税代扣代缴 | 工资累进 |
| `CN-STAMP-003` | 印花税 0.03% 购销合同 | C1-056 |
| `CN-PROPERTY-12` | 房产税 1.2% | 自用 |
| `CN-SURTAX-12` | 城建税/教育费附加 12% | 基于 VAT |
| `CN-LOAN-PRINCIPAL` | 关联方贷款本金(非应税) | 集团内 |
| `CN-INT-RECEIVED` | 关联方利息收入 | 含 WHT 抵免 |
| `CN-DIV-RECEIVED` | 关联方股息收入 | 0% WHT |
| `CN-ROY-RECEIVED` | 关联方特许权使用费收入 | 含 WHT 抵免 |
| `CN-CROSS-YEAR` | 跨年度业务(暂性差异转回) | C1-000a |

---

## 四、metadata 字段扩展

`metadata` 是 Pydantic `ImportResult.metadata: Dict[str, Any]` 自由 dict,用于存放案例级别的元数据:

```ts
metadata: {
  company: string                       // "Jiahang UK Holdings Ltd."
  company_type: 'uk_subsidiary' | 'cn_parent'
  tax_id: string                        // "GB 987 6543 21" 或 "91320000MA1XXXXXX"
  currency: 'GBP' | 'CNY'
  fiscal_year: 'FY2023'
  period: string                        // "2023-01-01~2023-12-31"
  scenario: string                      // 案例场景描述
  related_case_ids: string[]            // 集团关联 case
  transaction_count: number
  tax_types_involved: string[]          // 该 case 涉及税种
  // 嘉汉案例扩展:
  fx_rate_avg: number                   // 平均汇率(GBP/CNY)
  cross_year_businesses: number         // 跨年度业务数
  temporary_diff_events: number         // 暂性差异事件数
  dta_beginning: number                 // DTA 期初余额(CNY)
  dta_ending: number                    // DTA 期末余额(CNY)
  foreign_tax_credit: number           // 境外税收抵免(CNY)
  related_party_total: number           // 关联交易总额(GBP 或 CNY)
}
```

---

## 五、C1-xxx 编号 → erp_import.json 行的精确映射

### 5.1 UK 子 FY2023(36 笔,见子公司篇)

| C1 编号 | 日期 | 业务 | sales/purchases | tax_code | 净额 | VAT |
|---|---|---|---|---|---:|---:|
| C1-101 | 2023-01-05 | 本地销售起重机 | sales | T1-UK-STANDARD | £80,000 | £16,000 |
| C1-102 | 2023-01-10 | 收到母公司追加出资 | purchases | FX-LOAN-PRINCIPAL | £2,000,000 | 0 |
| C1-103 | 2023-02-15 | 进口中国货物 | purchases | T8-UK-IMPORT | £150,000 | 0(Duty £7,875 + Import VAT £33,075 PVA) |
| C1-104 | 2023-03-10 | 工资发放(8人) | purchases | EMP-NIC | £28,000 | 0 |
| C1-105 | 2023-03-20 | 本地销售挖掘机配件 | sales | T1-UK-STANDARD | £100,000 | £20,000 |
| C1-106 | 2023-03-31 | EU 反向征收采购 | purchases | T2-UK-EU-RC | £51,000 | £10,200 |
| C1-107 | 2023-03-31 | Q1 VAT Return 申报 | purchases | CN-VAT-UK-Q1 | -£6,875(退税) | 0 |
| C1-108 | 2023-04-01 | 出口 EU(德国) | sales | T0-UK-ZERO | £85,000 | 0 |
| C1-109 | 2023-04-10 | 利息支付(第一期) | purchases | WH-INT-10 | £12,500(扣 £1,250 WHT) | 0 |
| C1-109a | 2023-07-10 | 利息支付(第二期) | purchases | WH-INT-10 | £12,500(扣 £1,250 WHT) | 0 |
| C1-110 | 2023-05-15 | 特许权使用费支付 | purchases | WH-ROY-10 | £20,000(扣 £2,000 WHT) | 0 |
| C1-110a | 2023-07-31 | 特许权使用费支付(第二笔) | purchases | WH-ROY-10 | £15,000(扣 £1,500 WHT) | 0 |
| C1-111 | 2023-05-20 | 办公场地租金 + Business Rates | purchases | BR-UBR-512 | £45,000 + £25,600 | 0 |
| C1-112 | 2023-06-30 | Q2 VAT Return | purchases | CN-VAT-UK-Q2 | £20,000 应缴 | 0 |
| C1-113 | 2023-07-15 | 本地采购辅助材料 | purchases | T1-UK-DOMESTIC-PURCHASE | £50,000 | £10,000 |
| C1-114 | 2023-08-05 | 本地采购办公用品 | purchases | T1-UK-DOMESTIC-PURCHASE | £20,000 | £4,000 |
| C1-115 | 2023-08-10 | 本地销售混凝土搅拌机 | sales | T1-UK-STANDARD | £150,000 | £30,000 |
| C1-116 | 2023-08-20 | 出口 EU(法国) | sales | T0-UK-ZERO | £68,000 | 0 |
| C1-128a | 2023-07-15 | EU 反向征收(法国) | purchases | T2-UK-EU-RC | £33,200 | £6,640 |
| C1-117 | 2023-09-30 | Q3 VAT Return | purchases | CN-VAT-UK-Q3 | £16,000 应缴 | 0 |
| C1-118 | 2023-10-05 | 工资发放(10人) | purchases | EMP-NIC | £38,000 | 0 |
| C1-119 | 2023-11-10 | 采购固定资产(叉车) | purchases | T1-UK-DOMESTIC-PURCHASE | £30,000 | £6,000 |
| C1-131a | 2023-09-01 | 学徒税计算 | purchases | AL-EXEMPT | £0 | 0 |
| C1-120 | 2023-11-20 | 宣告第一次股息 | purchases | WH-DIV-0 | £50,000 | 0 |
| C1-149a | 2023-07-20 | 宣告中期股息 | purchases | WH-DIV-0 | £40,000 | 0 |
| C1-121 | 2023-12-15 | 归还借款本金(200k) | purchases | FX-LOAN-PRINCIPAL | £200,000 | 0 |
| C1-121a | 2023-08-10 | 提前归还本金(200k + 利息) | purchases | FX-LOAN-PRINCIPAL+WH-INT-10 | £200,000 + £2,778(扣 £278 WHT) | 0 |
| C1-121b | 2023-10-05 | 归还尾款(100k + 利息) | purchases | FX-LOAN-PRINCIPAL+WH-INT-10 | £100,000 + £764(扣 £76 WHT) | 0 |
| C1-143a | 2023-09-15 | 新贷款协议签订 | purchases | FX-LOAN-PRINCIPAL | £400,000(新) | 0 |
| C1-122 | 2023-12-20 | 工资发放(12月,10人) | purchases | EMP-NIC | £38,000 | 0 |
| C1-123 | 2023-12-20 | 宣告第二次股息 | purchases | WH-DIV-0 | £80,000 | 0 |
| C1-124 | 2023-12-31 | Q4 VAT Return | purchases | CN-VAT-UK-Q4 | -£6,000 退税 | 0 |
| C1-125 | 2023-12-31 | UK CT 申报 | purchases | CT-FY2023 | £43,950 应缴 | 0 |

### 5.2 CN 母 FY2023(62 笔,见母公司篇)

| C1 编号 | 日期 | 业务 | sales/purchases | tax_code | 净额 | VAT/税 |
|---|---|---|---|---|---:|---:|
| **C1-000a** | 2023-01-03 | 支付 FY2022 年终奖金 | purchases | CN-CROSS-YEAR | ¥150,000 | DTA ¥37,500 转回 |
| **C1-000b** | 2023-01-08 | 收到 FY2022 末销售尾款 | sales | CN-VAT-13 | ¥500,000 / ¥565,000(含税) | 0(无差异) |
| C1-010a | 2023-01-01 | 借出贷款给 UK 子 | purchases | CN-LOAN-PRINCIPAL | £500,000 / ¥4,250,000 | 0 |
| C1-001 | 2023-01-05 | 采购钢材 | purchases | CN-VAT-13 | ¥200,000 | ¥26,000 进项 |
| C1-002 | 2023-01-10 | 销售数控加工中心 | sales | CN-VAT-13 | ¥1,000,000 | ¥130,000 销项 |
| C1-003 | 2023-01-15 | 工资发放(1月) | purchases | CN-IIT-WH | ¥1,500,000 | ¥85,000 IIT + ¥120,000 社保 |
| C1-004 | 2023-01-20 | 缴纳社保 | purchases | — | ¥300,000 | 0 |
| C1-001a | 2023-01-25 | 支付南京钢铁 | purchases | — | ¥226,000 | 0 |
| C1-005 | 2023-02-05 | 采购办公设备 | purchases | CN-VAT-13 | ¥50,000 | ¥6,500 进项 |
| **C1-006** | 2023-02-10 | 办公场地租金(5% 简易) | purchases | CN-VAT-5-SIMPLE | ¥60,000 | ¥3,000 进项 |
| **C1-006b** | 2023-02-10 | 物业管理费(3% 小规模) | purchases | CN-VAT-3-PS | ¥20,000 | ¥600 进项 |
| **C1-040a** | 2023-02-10 | 出口销售给 UK 子 | sales | CN-INTRA-GROUP-EXPORT | £150,000 / ¥1,290,000 | 0(出口零税率) |
| C1-007 | 2023-02-15 | 销售塔式起重机 | sales | CN-VAT-13 | ¥4,000,000 | ¥520,000 销项 |
| C1-008 | 2023-02-28 | 申报增值税(2月) | purchases | CN-VAT-13 | ¥613,900 应缴 | 0 |
| C1-009 | 2023-03-05 | 缴纳城建税 | purchases | CN-SURTAX-12 | ¥73,668 | 0 |
| **C1-010** | 2023-03-10 | 收到 UK 子股息 | sales | CN-DIV-RECEIVED | £50,000 / ¥425,000 | 0(0% WHT) |
| **C1-011** | 2023-03-15 | 收到 UK 子利息(第一期) | sales | CN-INT-RECEIVED | £11,250 / ¥96,750(净)+£1,250 WHT/¥10,750 | 抵免 |
| C1-007a | 2023-03-17 | 收到苏州货款 | sales | — | ¥3,164,000 | 0 |
| C1-012 | 2023-03-20 | 销售数控车床 | sales | CN-VAT-13 | ¥2,000,000 | ¥260,000 销项 |
| C1-013 | 2023-04-05 | 缴纳房产税(Q1) | purchases | CN-PROPERTY-12 | ¥105,000 | 0 |
| C1-014 | 2023-04-10 | 采购电机 | purchases | CN-VAT-13 | ¥200,000 | ¥26,000 进项 |
| C1-002a | 2023-04-10 | 银行承兑汇票兑现 | sales | — | ¥1,130,000 | 0 |
| C1-015 | 2023-04-15 | 销售龙门铣床 | sales | CN-VAT-13 | ¥4,000,000 | ¥520,000 销项 |
| C1-016 | 2023-04-15 | 工资发放(4月) | purchases | CN-IIT-WH | ¥1,500,000 | ¥90,000 IIT |
| C1-017 | 2023-04-20 | 缴纳社保 | purchases | — | ¥300,000 | 0 |
| **C1-018** | 2023-04-20 | 收到 UK 子特许权 | sales | CN-ROY-RECEIVED | £18,000 / ¥154,800(净)+£2,000 WHT/¥17,200 | 抵免 |
| C1-019 | 2023-05-05 | 采购钢材 | purchases | CN-VAT-13 | ¥120,000 | ¥15,600 进项 |
| C1-020 | 2023-05-10 | 销售起重机 | sales | CN-VAT-13 | ¥1,500,000 | ¥196,000 销项 |
| C1-021 | 2023-05-15 | 工资发放(5月) | purchases | CN-IIT-WH | ¥1,500,000 | ¥88,000 IIT |
| C1-022 | 2023-05-31 | 申报增值税 | purchases | CN-VAT-13 | ¥180,400 | 0 |
| C1-021a | 2023-06-05 | 缴纳社保 | purchases | — | ¥300,000 | 0 |
| C1-023 | 2023-06-05 | 采购固定资产(数控中心) | purchases | CN-VAT-13 | ¥300,000 | ¥39,000 进项 |
| C1-001b | 2023-06-10 | 支付南京钢铁 | purchases | — | ¥135,600 | 0 |
| C1-020a | 2023-06-10 | 收到杭州货款 | sales | — | ¥1,696,000 | 0 |
| C1-024 | 2023-06-10 | 销售精密数控车床 | sales | CN-VAT-13 | ¥2,500,000 | ¥326,000 销项 |
| C1-025 | 2023-06-15 | 工资发放(6月) | purchases | CN-IIT-WH | ¥1,500,000 | ¥92,000 IIT |
| C1-025a | 2023-06-20 | 缴纳社保 | purchases | — | ¥300,000 | 0 |
| C1-022a | 2023-06-30 | 缴纳城建税(5月) | purchases | CN-SURTAX-12 | ¥21,648 | 0 |
| C1-026 | 2023-06-30 | 申报增值税(6月) | purchases | CN-VAT-13 | ¥287,000 | 0 |
| C1-027 | 2023-07-05 | 缴纳城建税(上半年) | purchases | CN-SURTAX-12 | ¥34,440 | 0 |
| C1-028 | 2023-07-05 | 缴纳房产税(Q2) | purchases | CN-PROPERTY-12 | ¥105,000 | 0 |
| **C1-029** | 2023-07-10 | 收到 UK 子利息(第二期) | sales | CN-INT-RECEIVED | £11,250 / ¥97,875(净)+£1,250 WHT/¥10,875 | 抵免 |
| **C1-030** | 2023-07-31 | 收到 UK 子特许权(第二笔) | sales | CN-ROY-RECEIVED | £13,500 / ¥117,450(净)+£1,500 WHT/¥13,050 | 抵免 |
| C1-031 | 2023-08-05 | 缴纳房产税(Q3) | purchases | CN-PROPERTY-12 | ¥105,000 | 0 |
| **C1-032** | 2023-08-10 | 收到 UK 子归还本金 + 利息 | sales | CN-LOAN-PRINCIPAL+CN-INT-RECEIVED | £200,000 本金 + £2,500 利息(扣 £278 WHT) | 抵免 |
| C1-033 | 2023-09-05 | 缴纳房产税(Q4) | purchases | CN-PROPERTY-12 | ¥105,000 | 0 |
| C1-024a | 2023-09-08 | 银行承兑汇票兑现 | sales | — | ¥2,826,000 | 0 |
| **C1-034** | 2023-10-05 | 办公场地租金(Q4, 5% 简易) | purchases | CN-VAT-5-SIMPLE | ¥180,000 | ¥9,000 进项 |
| **C1-034b** | 2023-10-05 | 物业管理费(Q4, 3% 小规模) | purchases | CN-VAT-3-PS | ¥60,000 | ¥1,800 进项 |
| C1-035 | 2023-10-10 | 工资发放(10月) | purchases | CN-IIT-WH | ¥1,500,000 | ¥85,000 IIT |
| C1-035a | 2023-10-20 | 缴纳社保 | purchases | — | ¥300,000 | 0 |
| C1-036 | 2023-11-05 | 申报个税 | purchases | — | ¥85,000 | 0 |
| **C1-037** | 2023-11-10 | 收到 UK 子归还尾款 + 利息 | sales | CN-LOAN-PRINCIPAL+CN-INT-RECEIVED | £100,000 本金 + £688 利息(扣 £76 WHT) | 抵免 |
| C1-038 | 2023-11-15 | 销售塔式起重机 | sales | CN-VAT-13 | ¥6,000,000 | ¥780,000 销项 |
| C1-039 | 2023-12-05 | 工资发放(12月+年终奖) | purchases | CN-IIT-WH | ¥2,000,000 | ¥220,000 IIT |
| C1-039a | 2023-12-20 | 缴纳社保 | purchases | — | ¥300,000 | 0 |
| **C1-040** | 2023-12-10 | 收到 UK 子第二次股息 | sales | CN-DIV-RECEIVED | £80,000 / ¥696,000 | 0(0% WHT) |
| **C1-040c** | 2023-12-31 | 计提年末奖金(未支付) | purchases | CN-CROSS-YEAR | ¥200,000 | DTA ¥50,000 确认 |
| **C1-040d** | 2023-12-31 | 计提坏账准备 | purchases | — | ¥50,000 | DTA ¥12,500 确认 |
| **C1-040e** | 2023-12-31 | 计提产品质量保证 | purchases | — | ¥30,000 | DTA ¥7,500 确认 |
| **C1-041** | 2023-12-31 | 汇算清缴 | purchases | CN-CIT-25+CN-FTC | ¥2,032,500(应纳)-¥43,679(抵免)=¥1,988,821 净应缴 | DTA ¥70,000 期末 |

---

## 六、暂性差异事件映射

| 业务编号 | 类型 | 金额 | DTA 影响 | 时点 |
|---|---|---:|---:|---|
| C1-000a | 跨年度转回 | ¥150,000 | -¥37,500 | 年初(2023-01-03) |
| C1-040c | 新增计提未发奖金 | ¥200,000 | +¥50,000 | 年末(2023-12-31) |
| C1-040d | 新增坏账准备 | ¥50,000 | +¥12,500 | 年末(2023-12-31) |
| C1-040e | 新增预计负债 | ¥30,000 | +¥7,500 | 年末(2023-12-31) |
| **合计** | | **¥130,000(净调增)** | **¥32,500(净增 DTA)** | 期末 ¥70,000 |

---

## 七、关联交易配对表(母→子)

| 业务类型 | 母公司 C1 | 子公司 C1 | 金额 | WHT | 备注 |
|---|---|---|---:|:--:|---|
| 出口货物 | C1-040a | C1-103 | £150,000 | — | 出口零税率 |
| 贷款本金 | C1-010a | C1-102 | £500,000 | — | 5%, 3年 |
| 利息支付(第一期) | C1-011 | C1-109 | £12,500 | 10% | 中英协定 |
| 利息支付(第二期) | C1-029 | C1-109a | £12,500 | 10% | 中英协定 |
| 特许权(第一笔) | C1-018 | C1-110 | £20,000 | 10% | 中英协定 |
| 特许权(第二笔) | C1-030 | C1-110a | £15,000 | 10% | 中英协定 |
| 归还本金(¥200k) | C1-032 | C1-121a | £200,000 + £2,500 利息 | 10% | 部分归还 |
| 归还尾款(¥100k) | C1-037 | C1-121b | £100,000 + £688 利息 | 10% | 尾款清零 |
| 股息(第一笔) | C1-010 | C1-120 | £50,000 | 0% | 100% 控股 |
| 股息(第二笔) | C1-040 | C1-123 | £80,000 | 0% | 100% 控股 |

---

**本文档维护**:任何新案例加入(扩展 C1-xxx 编号)或 schema 变化时同步更新。
