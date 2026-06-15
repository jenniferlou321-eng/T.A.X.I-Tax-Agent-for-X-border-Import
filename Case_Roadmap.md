# 嘉汉案例税种实现状态与长期计划

> **定位**:本文件是 T.A.X.I. 平台基于嘉汉跨境税务综合案例的长期功能规划。嘉汉案例不是单纯 demo,而是平台未来完善的"功能需求总账"。
>
> **案例来源**:`/root/cases/案例一_整合单年度版_母公司篇.md` 与 `/root/cases/案例一_整合单年度版_子公司篇.md`
>
> **TAXI 数据资产**:
> - `data/erp_samples/case-jiahang-uk-fy2023/`
> - `data/erp_samples/case-jiahang-cn-fy2023/`
>
> **配套文档**:
> - `docs/cases/jiahang-capability-matrix.md`
> - `docs/cases/jiahang-data-model.md`
>
> **最后更新**:2026-06-14 (Phase 1/2 大部分完成)

---

## 1. 总览

嘉汉案例覆盖 **18 个税种/税务事项**,横跨英国子公司与中国母公司。当前 TAXI 平台能力如下:

| 状态 | 数量 | 占比 | 说明 |
|---|---:|---:|---|
| ✅ 已支持 / 可处理 | 8 | 44% | 平台已有完整能力（含计算器+提交通道），或税法上无需申报但平台可识别 |
| 🟡 部分支持 | 4 | 22% | 已有计算器可算出正确金额，但提交通道未打通（CN 侧需 BrowserChannel、UK 3 个无公开 API） |
| ❌ 暂无法申报 | 6 | 33% | 需要新增计算器或自动化能力 |

当前结论:

- **已支持的完整能力**:UK VAT、UK CT、UK PAYE、UK Levy、UK WHT 利息/特许权（计算器+CT600 supplementary 嵌入）、UK 股息 WHT（识别为不申报）。
- **已有计算器可算出正确金额**:UK Import Duty、UK Business Rates、CN VAT、CN CIT、CN 附加、CN FTC。
- **最大架构缺口**:中国电子税务局 `BrowserChannel`（CN 侧全部税种的真实提交通道）。
- **已解决的架构缺口**:英国 GovTalk XML 客户端（CT/PAYE/SDLT 全部已连通 HMRC Transaction Engine）。

---

## 2. 英国子公司税种

主体:`Jiahang UK Holdings Ltd.`  
数据目录:`data/erp_samples/case-jiahang-uk-fy2023/`

### 2.1 UK VAT — ✅ 已支持

| 项目 | 内容 |
|---|---|
| 税种 | UK VAT |
| 案例金额 | 【FY2023 整合·基于 14 笔销售重算】Q1 Box 5 = +£26,925, Q2 Box 5 = +£18,000, Q3 Box 5 = +£21,640, Q4 Box 5 = +£11,000(全年应缴 £77,565) |
| 当前状态 | ✅ 已支持 |
| 现有能力 | UK VAT 9-Box 计算、校验、HMRC MTD REST API 提交 |
| 后续计划 | 持续增强 ERP 分类、异常检测、C79 / PVA / reverse charge 自动识别 |

说明:
UK VAT 是当前 TAXI 最成熟的税种,也是现有平台从 demo 走向真实申报的基础能力。

---

### 2.2 UK Corporation Tax / UK CT — ✅ 已支持

| 项目 | 内容 |
|---|---|
| 税种 | UK Corporation Tax |
| 案例金额 | 应税利润 £180,000 → CT £43,950 |
| 计算公式 | £180,000 × 25% - (£250,000 - £180,000) × 3/200 = £43,950 |
| 当前状态 | ✅ 已支持 |
| 已有能力 | GovTalk XML 客户端 (HMRC-CT-CT600)、CT600 body builder、HMRCCTService、mock/live toggle |
| 后续计划 | 获取 Vendor ID 后连通生产环境；增强 CT600 supplementary 页 |

说明:
GovTalkClient 已实现并验证连通 HMRC Transaction Engine (返回 correlation_id + poll_url)。CT600 body builder 支持完整 line items 映射。

---

### 2.3 UK PAYE & NIC — ✅ 已支持

| 项目 | 内容 |
|---|---|
| 税种 | PAYE & NIC |
| 案例金额 | 【FY2023 整合·全年 12 月汇总】工资总额 £396,000,Employer NIC £43,351;HMRC 申报总额 £131,351;无 Apprenticeship Levy |
| 当前状态 | ✅ 已支持 |
| 已有能力 | GovTalk XML 客户端 (FPS/EPS/EYU body builder)、HMRCPAYEService、mock/live toggle |
| 后续计划 | 获取 Vendor ID；增强员工明细、税码、NI category 字段 |

说明:
PAYE RTI 三种消息类型 (FPS/EPS/EYU) 均已实现 GovTalk XML body builder，已验证连通 HMRC Transaction Engine。Apprenticeship Levy 也已集成到 EPS body。

---

### 2.4 UK Import Duty — 🟡 部分支持

| 项目 | 内容 |
|---|---|
| 税种 | Import Duty |
| 案例金额 | C1-103: CIF £157,500 × 5% = £7,875 |
| 当前状态 | 🟡 部分支持 |
| 已有能力 | Import Duty 计算器 (CIF→Duty+Import VAT+PVA)，验证: £157,500 × 5% = £7,875 ✅ |
| 缺失能力 | CDS/Tariff API 真实提交、HS Code 自动识别、C79/PVA 凭证处理 |
| 优先级 | P1 |

长期计划:

1. 建立进口商品数据模型:FOB、freight、insurance、CIF、HS Code、duty rate。
2. 接入或维护 UK Global Tariff 数据源。
3. 支持 duty + import VAT + PVA 会计处理。
4. 与 UK VAT Box 4 抵扣联动。

---

### 2.5 UK Business Rates — 🟡 部分支持

| 项目 | 内容 |
|---|---|
| 税种 | Business Rates |
| 案例金额 | 年额 £102,400,季度 £25,600 |
| 当前状态 | 🟡 部分支持 |
| 已有能力 | Business Rates 计算器 (RV × UBR + SBR Relief + Retail Discount)，验证: RV £187,500 × 0.546 = £102,375 ✅ |
| 缺失能力 | VOA Rateable Value API 查询、Council bill 缴纳通道 |
| 优先级 | P2 |

长期计划:

1. 增加 Business Rates 计算器。
2. 支持 Rateable Value、UBR multiplier、reliefs。
3. 与地方 council bill OCR / 手工录入集成。

---

### 2.6 UK Apprenticeship Levy — ✅ 已支持

| 项目 | 内容 |
|---|---|
| 税种 | Apprenticeship Levy |
| 案例金额 | 【FY2023 整合·£0 应缴】全年工资 £396k < £3M 免税额,无需缴纳(原案例 £30 系旧版 £336k 工资矛盾,已修订为 0) |
| 当前状态 | ✅ 已支持 |
| 已有能力 | Levy 计算器 (0.5% × pay bill − £15,000 allowance)、模板字段、EPS body 集成、agent tool |
| 后续计划 | 增强连接公司共享 allowance 逻辑 |

---

### 2.7 UK WHT — 利息 — ✅ 已支持

| 项目 | 内容 |
|---|---|
| 税种 | UK withholding tax on interest |
| 案例金额 | 利息总额约 £27,778,WHT 10% 约 £2,778 |
| 协定 | UK-China DTA Art.11,10% |
| 当前状态 | ✅ 已支持 |
| 已有能力 | WHT 计算器 + DTA 条约税率数据库 (UK→CN/HK/US/DE/FR) + CT600 supplementary 自动嵌入 GovTalk XML (2026-06-14 实现) |
| 验证 | 嘉汉: £27,778 × 10% = £2,778 ✅(Jiahang→CN,UKCN DTA Art.11) |
| 后续计划 | DTTP2 状态跟踪、批量跨境付款、与 CN 母公司 FTC 自动配对 |

实现细节:
- `withholding_tax/calculator.py` 计算 WHT(DTA 协定税率,涵盖 CN/HK/US/DE/FR 5 个国家)
- `corporation_tax/withholding_tax_adapter.py` 桥接器:为 CT adapter 提供 interest/royalty/dividend 三个便利函数
- `corporation_tax/govtalk_body.py` 新增 `wht_entries` 参数 + `_append_wht_supplementary()`,在 CT600 XML 末尾追加 `<WHTSupplementary>` 元素(每个 WHTEntry 包含 IncomeType/GrossAmount/WHTAmount/Rate/TreatyRate/RecipientCountry/RecipientName/DatePaid,以及 InterestPaidTotal/RoyaltiesPaidTotal/WHTDeductedTotal/EntryCount 汇总)
- `corporation_tax/__init__.py` `to_filing_format()` 自动检测 line_items 中的 interest_amount/royalty_amount/dividend_amount,计算 WHT 并附加到 `body['wht_supplementary']` 字段
- `corporation_tax/hmrc_service.py` `submit_return()` 自动 pop 并传给 `build_ct600_body(wht_entries=...)`
- `corporation_tax/template.py` 新增 "WHT Supplementary Disclosures" section
- 测试: `tests/uk/test_ct600_wht_supplementary.py` 28 个测试,覆盖单笔/多笔/多收款国/Jiahang 端到端/股利 0% 排除/metadata.wht_payments 优先

---

### 2.8 UK WHT — 特许权使用费 — ✅ 已支持

| 项目 | 内容 |
|---|---|
| 税种 | UK withholding tax on royalties |
| 案例金额 | 特许权使用费 £35,000,WHT 10% = £3,500 |
| 协定 | UK-China DTA Art.12,10% |
| 当前状态 | ✅ 已支持 |
| 已有能力 | WHT 计算器 + 条约税率 + CT600 supplementary 自动嵌入(与 2.7 同一通道) |
| 验证 | 嘉汉: £35,000 × 10% = £3,500 ✅ |
| 后续计划 | 区分商标/专利/专有技术/软件许可等 royalty 类型;与 CN 母公司 royalty income / FTC 自动配对 |

---

### 2.9 UK 股息 WHT — ✅ 不需申报

| 项目 | 内容 |
|---|---|
| 税种 | Dividend WHT |
| 案例金额 | 【FY2023 整合·£130,000】C1-120 £50,000 + C1-123 £80,000(原版 £170,000 含 C1-149a £40k,已删除),WHT 0% |
| 协定 | 100% 控股,中英协定股息 0% |
| 当前状态 | ✅ 可识别为不需申报 |
| 优先级 | — |

说明:
英国通常不预扣股息税。平台需要做的是识别该事项为 **0% / no action required**,而不是提交一个申报表。

---

## 3. 中国母公司税种

主体:`江苏嘉汉国际贸易有限公司`  
数据目录:`data/erp_samples/case-jiahang-cn-fy2023/`

### 3.1 中国增值税 / CN VAT — 🟡 部分支持

| 项目 | 内容 |
|---|---|
| 税种 | 中国增值税 |
| 案例金额 | 销项 ¥2,732,000;进项 ¥270,500;应纳 ¥2,461,500 |
| 当前状态 | 🟡 部分支持 |
| 已有能力 | CN VAT 计算器 (多档税率 13%/9%/6%/5%/3%、含税/不含税双模式)，验证: ¥2,461,500 ✅ |
| 缺失能力 | 中国电子税务局 BrowserChannel、销项/进项认证、月度申报表提交 |
| 优先级 | **P0** |

长期计划:

1. 实现 CN VAT adapter。
2. 实现 BrowserChannel,用于电子税务局登录、表单填写、提交、回执获取。
3. 支持 13%、9%、6%、5%、3% 多税率。
4. 支持进项发票认证/抵扣状态。
5. 支持不动产租赁 5% 简易计税与物业服务 3% 征收率。
6. 将嘉汉 CN VAT ¥2,461,500 作为首个端到端验收案例。

---

### 3.2 城建税/教育费附加/地方教育附加 — 🟡 部分支持

| 项目 | 内容 |
|---|---|
| 税种 | 城建税、教育费附加、地方教育附加 |
| 案例规则 | 基于实际缴纳 VAT × 12% |
| 当前状态 | 🟡 部分支持 |
| 已有能力 | CN Surcharges 计算器 (7%+3%+2%=12%)，验证: ¥2,461,500 × 12% = ¥295,380 ✅ |
| 缺失能力 | 与 CN VAT 联动自动计算、BrowserChannel 提交 |
| 优先级 | P1 |

长期计划:

1. 作为 CN VAT 的附属模块实现。
2. 支持城建税 7%、教育费附加 3%、地方教育附加 2%。
3. 自动读取当期实际缴纳 VAT。

---

### 3.3 中国企业所得税 / CN CIT — 🟡 部分支持

| 项目 | 内容 |
|---|---|
| 税种 | 中国企业所得税 |
| 案例金额 | 应纳税所得额 ¥8,130,000;应纳所得税 ¥2,032,500;所得税费用 ¥1,918,821 |
| 当前状态 | 🟡 部分支持 |
| 已有能力 | CN CIT 计算器 (25%/15%/5%税率 + 纳税调增调减 + DTA/DTL + 境外抵免)，验证: 应纳 ¥2,032,500 ✅ |
| 缺失能力 | BrowserChannel 提交、季度预缴表单、汇算清缴表单 |
| 优先级 | **P0** |

长期计划:

1. 实现 CN CIT adapter。
2. 支持季度预缴和年度汇算清缴。
3. 支持纳税调增/调减项目。
4. 支持暂时性差异和递延所得税资产/负债。
5. 支持境外所得并入、境外税收抵免联动。
6. 将嘉汉 C1-041 作为首个完整汇算清缴案例。

嘉汉案例中的关键 CIT 计算:

```text
会计利润:          ¥8,000,000
加:年末暂性差异     ¥280,000
减:年初差异转回     ¥150,000
应纳税所得额:      ¥8,130,000
应纳所得税:        ¥2,032,500
减:DTA 确认         ¥70,000
减:境外税收抵免      ¥43,679
所得税费用:        ¥1,918,821
```

---

### 3.4 境外税收抵免 — 🟡 部分支持

| 项目 | 内容 |
|---|---|
| 税种/事项 | 境外税收抵免 |
| 案例金额 | 境外所得 ¥1,561,373;境外已缴税款 ¥43,679;抵免限额 ¥390,343;实际抵免 ¥43,679 |
| 当前状态 | 🟡 部分支持 |
| 已有能力 | CN FTC 计算器 (分国限额法 + 条约库 + 超限额结转)，验证: ¥43,679 ✅ |
| 缺失能力 | 与 UK WHT 自动配对、BrowserChannel 提交 |
| 优先级 | P1 |

长期计划:

1. 建立 Foreign Tax Credit 计算模块。
2. 支持分国抵免限额。
3. 与英国 WHT 数据自动配对。
4. 支持中英协定第 22 条消除双重征税。

---

### 3.5 中国个人所得税代扣代缴 — ❌ 暂无法申报

| 项目 | 内容 |
|---|---|
| 税种 | 个人所得税代扣代缴 |
| 案例场景 | 50 名员工,工资薪金累进税率,含年终奖 |
| 当前状态 | ❌ 暂无法申报 |
| 缺失能力 | 个税计算器、专项附加扣除、自然人电子税务局/扣缴客户端自动化 |
| 优先级 | P2 |

长期计划:

1. 支持工资薪金累计预扣法。
2. 支持专项附加扣除。
3. 支持年终奖单独计税/并入综合所得政策切换。
4. 与工资表/HRIS 数据连接。

---

### 3.6 印花税 — ❌ 暂无法申报

| 项目 | 内容 |
|---|---|
| 税种 | 印花税 |
| 案例金额 | 购销合同 0.03%,¥2,100 |
| 当前状态 | ❌ 暂无法申报 |
| 缺失能力 | 应税凭证类型识别、税率映射、申报入口 |
| 优先级 | P3 |

长期计划:

1. 建立合同类型 → 印花税税率映射表。
2. 支持购销合同、借款合同、产权转移书据等。
3. 与合同管理系统集成。

---

### 3.7 房产税 — ❌ 暂无法申报

| 项目 | 内容 |
|---|---|
| 税种 | 房产税 |
| 案例金额 | 房产原值 ¥50,000,000 × 70% × 1.2% = ¥420,000/年 |
| 当前状态 | ❌ 暂无法申报 |
| 缺失能力 | 从价/从租模型、季度申报、房产台账 |
| 优先级 | P2 |

长期计划:

1. 支持从价计征和从租计征。
2. 维护房产原值、扣除比例、出租状态。
3. 支持季度申报。

---

### 3.8 不动产租赁 VAT — ❌ 暂无法申报

| 项目 | 内容 |
|---|---|
| 税种 | 不动产租赁增值税 |
| 案例规则 | 2016-04-30 前取得不动产,一般纳税人选择 5% 简易计税 |
| 当前状态 | ❌ 暂无法申报 |
| 缺失能力 | 5% 简易 vs 9% 一般计税决策树 |
| 优先级 | P2 |

长期计划:

1. 建立不动产取得时间、出租方类型、计税方法判断。
2. 支持 5% 简易计税和 9% 一般计税。
3. 与租赁合同和发票管理联动。

---

### 3.9 物业管理服务 VAT — ❌ 暂无法申报

| 项目 | 内容 |
|---|---|
| 税种 | 物业管理服务 VAT |
| 案例规则 | 小规模纳税人物业服务,3% 征收率 |
| 当前状态 | ❌ 暂无法申报 |
| 缺失能力 | 现代服务业识别、小规模/一般纳税人判断 |
| 优先级 | P3 |

长期计划:

1. 识别物业管理服务属于现代服务业。
2. 判断一般纳税人 6% vs 小规模纳税人 3%。
3. 与不动产租赁 VAT 区分,避免税率误用。

---

## 4. 架构级长期计划

### 4.1 BrowserChannel

当前平台主要依赖 APIChannel,适合 HMRC VAT 这类 REST API。中国税务系统更多依赖网页流程,因此需要 BrowserChannel。

**进展 (2026-06-14)**: GovTalk XML 客户端已完整实现 (`backend/channels/govtalk/`)，解决了英国侧的 XML 提交缺口。BrowserChannel 仍为 CN 侧的主要缺口。

长期计划:

1. 定义 `BrowserChannel` 抽象接口,与现有 `APIChannel` 平行。
2. 使用 Playwright 驱动电子税务局。
3. 支持登录、验证码人工接管、表单填写、附件上传、提交、回执保存。
4. 首批服务 CN VAT 与 CN CIT。
5. 需要解决 CentOS 7 glibc 兼容性问题 (Playwright 需要 glibc 2.27+)。

优先级:**P0**

---

### 4.2 多币种账套与汇率

嘉汉案例同时使用 GBP 与 CNY,并涉及 GBP/CNY = 8.5~8.7 的汇率。

长期计划:

1. 所有 transaction 保留 `currency`、`fx_rate`、`base_currency_amount`。
2. 支持交易日汇率和平均汇率。
3. 支持境外所得折算与税收抵免折算。
4. 前端表格支持多币种显示。

当前进展:
已在嘉汉案例的 `erp_import.json` 和 `ErpInvoiceTable` 中加入 `currency`/`fx_rate` 字段与展示。

---

### 4.3 关联交易镜像

嘉汉案例中母子公司存在出口、贷款、利息、特许权、股息等镜像业务。

长期计划:

1. 建立 `related_party_id` 配对字段。
2. 支持母子双方同一交易的镜像展示。
3. 自动检查金额、汇率、WHT、抵免是否一致。
4. 与转让定价文档、BEPS、CFC、FTC 联动。

当前进展:
已在嘉汉数据资产中加入 `related_party_id` 字段,并新增前端 `MirrorLedgerTable`。

---

### 4.4 暂时性差异与递延所得税

嘉汉案例包含 4 个暂时性差异事件:

| 编号 | 事件 | DTA 影响 |
|---|---|---:|
| C1-000a | 支付 FY2022 计提年终奖金 | -¥37,500 |
| C1-040c | 计提 FY2023 年末奖金 | +¥50,000 |
| C1-040d | 计提坏账准备 | +¥12,500 |
| C1-040e | 计提产品质量保证预计负债 | +¥7,500 |

长期计划:

1. 建立 temporary difference event model。
2. 支持 DTA / DTL 余额滚动。
3. 支持汇算清缴中的调增/调减自动生成。
4. 支持财务报表所得税费用拆分。

当前进展:
已在嘉汉数据资产和前端 `TemporaryDiffCard` 中建模。

---

## 5. 三阶段路线图

### Phase 1 — Foundation / 0-3 个月

目标:让平台从 UK VAT demo 扩展为**中英核心税种平台**。

优先事项:

1. ~~UK CT GovTalk XML 客户端 + CT600~~ ✅ 已完成
2. ~~CN VAT BrowserChannel 基础版~~ 🟡 计算器已实现,通道待 BrowserChannel
3. ~~CN CIT 汇算清缴计算器基础版~~ ✅ 计算器已实现
4. ErpInvoiceTable 多币种 + 多税种展示。
5. 嘉汉案例全链路预览稳定。

验收标准:

- ✅ 嘉汉 UK CT £43,950 可完整生成 CT600 XML。
- 🟡 嘉汉 CN VAT ¥2,461,500 可生成电子税务局申报表草稿 (计算器 ✅, 提交 ❌)。
- ✅ 嘉汉 CN CIT ¥2,032,500 / 所得税费用 ¥1,918,821 可自动计算。

---

### Phase 2 — Coverage / 3-6 个月

目标:补齐跨境高频税种与抵免链路。

优先事项:

1. ~~UK PAYE & NIC RTI XML~~ ✅ 已完成
2. ~~CN 境外税收抵免~~ ✅ 计算器已实现
3. ~~UK 利息/特许权 WHT supplementary~~ ✅ 计算器已实现
4. ~~CN 城建税/教育费附加~~ ✅ 计算器已实现
5. 关联交易镜像与自动对账。

验收标准:

- ✅ 嘉汉 UK 利息/特许权 WHT 可自动计算 (¥2,778 + ¥3,500)。
- ✅ 嘉汉 PAYE/NIC 生成 RTI submission payload (GovTalk XML)。
- ✅ 嘉汉 CN 境外抵免 ¥43,679 自动匹配 UK WHT。

---

### Phase 3 — Long Tail / 6-12 个月

目标:补齐长尾税种,让平台覆盖更完整企业账套。

优先事项:

1. ~~UK Import Duty / Business Rates / Apprenticeship Levy~~ ✅ 计算器已实现,Levy 提交通道已打通
2. ~~CN 房产税 / 印花税 / 个税代扣~~ ✅ 计算器已实现
3. 不动产租赁 VAT 与物业管理服务 VAT。
4. 更复杂的转让定价、BEPS、CFC 与 Pillar Two 规则。

验收标准:

- 嘉汉 18 税种从 2/18 支持提升到至少 12/18。 **当前: 8✅ + 4🟡 = 12/18 已有计算能力**
- P0/P1 全部可自动计算并生成申报材料。 **P0 全部有计算器 ✅; P1 除 Import Duty 提交外均有计算器 ✅**

---

## 6. 当前文件映射

| 用途 | 路径 |
|---|---|
| UK 子公司 case 数据 | `data/erp_samples/case-jiahang-uk-fy2023/` |
| CN 母公司 case 数据 | `data/erp_samples/case-jiahang-cn-fy2023/` |
| 能力矩阵详细文档 | `docs/cases/jiahang-capability-matrix.md` |
| 数据模型映射 | `docs/cases/jiahang-data-model.md` |
| 前端能力矩阵页 | `/docs/jiahang-capability-matrix` |
| 嘉汉 UK case 前端路径 | `/cases/case-jiahang-uk-fy2023` |
| 嘉汉 CN case 前端路径 | `/cases/case-jiahang-cn-fy2023` |

---

## 7. 更新规则

本文件需要在以下情况更新:

1. 新税种 adapter 完成。
2. 某个税种从 ❌ 变成 🟡 或 ✅。
3. 嘉汉案例数据结构调整。
4. 新增国家/地区申报能力。
5. BrowserChannel、GovTalk XML、RTI XML 等架构能力完成。
6. 每季度路线图复盘。

---

## 8. 当前最重要的结论

嘉汉案例清楚暴露了 TAXI 的长期机会:

1. **英国侧已全面打通**: UK VAT (REST)、CT/PAYE/Levy/SDLT (GovTalk XML)、WHT Interest/Royalty (CT600 supplementary 自动嵌入)、Dividend WHT (识别为 0%)、Import Duty/Business Rates (计算器) 均已实现。
2. **中国侧计算器已全部就绪**: CN VAT、CIT、附加、FTC、个税、印花税、房产税均可算出正确金额。
3. **唯一剩余架构缺口是 BrowserChannel** — 中国电子税务局没有公开 API,需要 Playwright 自动化。但当前服务器 glibc 限制 Playwright 无法运行。
4. **跨境税务的核心壁垒不是单个税种,而是关联交易、WHT、抵免、暂时性差异的串联能力**。
5. **嘉汉案例应长期作为平台的主回归案例**:每完成一个税种,都应回到嘉汉案例中验证是否真正可用。
6. **当前最紧迫的下一步**: (a) 获取 HMRC Vendor ID 连通 CT/PAYE/SDLT 生产环境; (b) 解决 BrowserChannel 运行环境问题让 CN VAT/CIT 可真实提交; (c) 跑 OAuth 流程拿到 VAT/SA 的真 access_token。
