# UK 报税路径总览 (Filing Path Matrix)

> 2026-06-13 复核,所有数据对照 HMRC Developer Hub 核实 (`/api/service/*` vs `/api/xml/*` 分类)。

## 税种总览

| # | 税种 (英文 / 中文) | 申报渠道 | 格式 | T.A.X.I. 现状 | 难度 |
|---|------------------|---------|------|---------------|------|
| 1 | **VAT** (增值税) | REST API | JSON | 🟢 **真联通** | ✅ 已完成 |
| 2 | **Corporation Tax** (公司税) | XML API | GovTalk XML | 🟡 计算+适配完整,client mock | 🔴 高 |
| 3 | **PAYE / RTI** (雇主代扣) | XML API | GovTalk XML | 🟡 计算+适配完整,client mock | 🔴 高 |
| 4 | **Self Assessment** (个人申报) | REST API | JSON | 🟡 计算+适配完整,client mock | 🟢 低-中 |
| 5 | **Stamp Duty (SDLT)** (印花税) | XML API | GovTalk XML | 🟡 计算+适配完整,client mock | 🔴 高 |
| 6 | **Apprenticeship Levy** (学徒税) | 走 PAYE RTI EPS | XML | 🟢 **已实现**(计算+EPS字段),client mock | 🟡 中 |
| 7 | **Withholding Tax** (利息/特许权预提) | 走 CT600 + DTTP1 纸面 | XML (CT600) | ⚪ 无独立能力(已文档化) | ⚪ N/A |
| 8 | **Business Rates** (商业房产税) | Council 账单 + VOA 上诉 API | REST (估值/上诉) | ⚪ 无独立能力(已文档化) | 🟢 低(只做估值) |
| 9 | **Capital Gains Tax** (资本利得) | 嵌入 SA | JSON (SA) | ⚪ 走 SA 路径,无独立 | ⚪ N/A |
| 10 | **National Insurance** (国民保险) | 嵌入 PAYE | XML (PAYE) | ⚪ 走 PAYE 路径,无独立 | ⚪ N/A |

---

## 详细申报路径

### 1. VAT ✅ 真联通
- **HMRC API**: `/api/service/vat-api/1.0` (REST, JSON)
- **端点**: obligations / returns / liabilities / payments
- **OAuth scope**: `read:vat` / `write:vat`
- **T.A.X.I. 实现**: `HMRCVATService` (`backend/jurisdictions/uk/vat/hmrc_service.py`)
- **沙箱 E2E**: ✅ 2026-06-01 提交 18A1 获 formBundleNumber `321591334754`
- **结论**: 唯一完全可用的真联通税种

### 2. Corporation Tax (CT) 🟡 需大改
- **HMRC API**: `/api/xml/Corporation Tax Online` (**XML**, 非 REST)
- **协议**: GovTalk (HMRC 专有的 XML 消息框架, 不是简单 XML POST)
- **OAuth scope**: `read:corporation-tax` / `write:corporation-tax`
- **T.A.X.I. 现状**:
  - ✅ 计算器、模板、CT600 line item 映射:完整
  - ❌ `HMRCCTService` 用假 REST 路径,不会联通真实接口
  - 🟡 沙箱仅供 mock 模式使用
- **接通真实 HMRC 需做**:
  1. 写 GovTalk XML 消息生成器 (使用 `lxml` 或类似)
  2. POST 到 Government Gateway XML endpoint (`/submission/...`)
  3. 处理 GovTalk 包装 (CorrelationID, SubmitTime 等)
  4. 处理异步 polling (HMRC XML 提交后 30s~30min 才知道 acceptance)
  5. 处理 GovTalk 错误码
- **难度**: 🔴 **高** (GovTalk 协议复杂,3-5 天)

### 3. PAYE / RTI 🟡 需大改
- **HMRC API**: `/api/xml/Real Time Information online` (**XML**, 非 REST)
- **消息类型**: FPS / EPS / EYU 都是 RTI 消息类型,不是 endpoint
- **OAuth scope**: `read:paye` / `write:paye`
- **T.A.X.I. 现状**:
  - ✅ 计算器 (含学徒税)、模板、agent tools:完整
  - ❌ `HMRCPAYEService` 用假 REST 路径
  - 🟡 学徒税计算已实现,EPS body 构造完成,仅缺真 XML 客户端
- **接通真实 HMRC 需做**:
  1. 同 CT — GovTalk XML 客户端
  2. 学徒税字段已映射,直接迁移
- **难度**: 🔴 **高** (GovTalk + 3 种消息类型,4-6 天)

### 4. Self Assessment (SA) 🟢 易接通
- **HMRC API**: 一整套 REST APIs
  - `/api/service/self-assessment-accounts-api/4.0` (账户)
  - `/api/service/self-assessment-individual-details-api/2.0` (个人详情)
  - `/api/service/individual-calculations-api/8.0` (计算)
  - `/api/service/individuals-*` 一系列 (各类收入: 雇佣/储蓄/股息/资本利得/...)
  - `/api/service/self-assessment-liability-api/1.0` (负债)
  - `/api/service/self-assessment-biss-api/3.0` (Business Income Source Summary)
  - `/api/service/self-assessment-bsas-api/7.0` (Business Statement Adjustments)
- **OAuth scope**: `read:self-assessment` / `write:self-assessment`
- **T.A.X.I. 现状**:
  - ✅ 计算器、模板、agent tools:完整
  - ❌ 仍是 mock
- **接通真实 HMRC 需做**:
  1. 类似 VAT 的 REST client (json + httpx + OAuth)
  2. 需要多 API 协同 (BISS → 计算 → submit)
  3. SA100 是分布式,需要分别 submit employment / self-employment / property / savings / dividends / capital gains
- **难度**: 🟢 **中** (跟 VAT 架构相同,但 API 多,2-3 天)

### 5. Stamp Duty (SDLT) 🟡 需大改
- **HMRC API**: `/api/xml/Stamp Taxes Online` (**XML**, 非 REST)
- **T.A.X.I. 现状**: 计算器、模板完整,client mock
- **难度**: 🔴 **高** (GovTalk XML,2-3 天)

### 6. Apprenticeship Levy 🟢 已实现
- **HMRC API**: 通过 PAYE RTI 的 EPS 消息
- **T.A.X.I. 现状**:
  - ✅ 计算器 (`calculate_apprenticeship_levy`):已实现
  - ✅ 模板字段 (`apprenticeship_levy_payable`, `total_pay_bill`):已添加
  - ✅ Agent tool (`calculate_apprenticeship_levy`):已暴露
  - ✅ EPS body 构造:已映射到 `apprenticeshipLevy` 字段
  - ❌ 真联通需 GovTalk XML 客户端 (跟 PAYE 一起)
- **难度**: 🟡 **中** (本身轻量,搭 PAYE 顺风车)

### 7. Withholding Tax ⚪ 不需独立实现
- **真实路径**:
  - 利息/特许权 WHT: 嵌入 **CT600** 的 Section A/B (non-trading)
  - 申报人(payer)在预扣时即向 HMRC 上缴
  - DTA 减免通过 DTTP1 (passport) 或 DT-Company (claim repayment) 纸面表单
- **UK 从不征股息 WHT** (注意: 不是 0% 税率, 而是该税不存在)
- **T.A.X.I. 现状**:
  - ⚪ 无独立 TaxType/适配器
  - ✅ 文档化在 `data/tax_knowledge/uk/withholding_tax.md`
- **接通真实 HMRC 需做**:
  - 通过 CT600 一并提交 (依赖 CT 的 GovTalk XML 客户端)
  - DTA 减免纸面表单不在平台范围
- **难度**: ⚪ **N/A** (跟随 CT)

### 8. Business Rates ⚪ 已文档化
- **真实路径**:
  - 账单: 由各地方 council 发出,无统一 API
  - 估值/上诉: VOA (`/api/service/business-rates-api/2.0` REST)
  - Check case (基础核实) 和 Challenge case (正式上诉) 是 VOA API 主要功能
- **T.A.X.I. 现状**:
  - ⚪ 无独立 TaxType/适配器
  - ✅ 文档化在 `docs/jurisdictions/uk/README.md`
- **接通真实 HMRC 需做**:
  - 仅对接 VOA API 即可 (REST, 跟 VAT 同架构)
  - council 账单不在平台能力范围
- **难度**: 🟢 **低** (REST, 但仅估值/上诉, 用户价值有限)

### 9. Capital Gains Tax (CGT) ⚪ 嵌入 SA
- **真实路径**: 嵌入 Self Assessment,使用 `/api/service/individuals-capital-gains-income-api/3.0`
- **T.A.X.I. 现状**: `TaxType.CAPITAL_GAINS` 枚举占位,无独立能力
- **接通真实 HMRC 需做**:
  - 不需要新代码,在 SA 集成中调 capital-gains-income-api
  - 配合 `individuals-disclosures-api` 申报 PDF 报表
- **难度**: ⚪ **N/A** (随 SA)

### 10. National Insurance (NIC) ⚪ 嵌入 PAYE
- **真实路径**: 通过 PAYE RTI 的 FPS 申报
- **T.A.X.I. 现状**: `TaxType.NATIONAL_INSURANCE` 枚举占位,无独立能力
- **接通真实 HMRC 需做**:
  - 不需要新代码,在 PAYE 集成中已含 NIC 字段
- **难度**: ⚪ **N/A** (随 PAYE)

---

## 总结与建议

### 按接入难度分级

#### 🟢 1 天内可搞定 (REST, 沿用 VAT 模式)
- **Self Assessment** — 多个 REST API 协同, 但架构同 VAT
- **Business Rates (仅 VOA 部分)** — REST, 但仅估值查询/上诉,价值有限

#### 🟡 中等难度 (2-5 天)
- **Apprenticeship Levy** — 跟 PAYE 走,只是 EPS 多了字段

#### 🔴 高难度 (需 1-2 周写 GovTalk XML 客户端)
- **Corporation Tax** — GovTalk XML, 需新写 client
- **PAYE / RTI** — GovTalk XML, 含 FPS/EPS/EYU 三种消息类型
- **Stamp Duty** — GovTalk XML

#### ⚪ 不需独立 (嵌入或随主税种)
- **Withholding Tax** — 随 CT600
- **Capital Gains** — 随 SA
- **National Insurance** — 随 PAYE

### 推荐路线 (按 ROI 排序)

1. **Self Assessment** (2-3 天, 高 ROI)
   - 唯一欠缺的"个人税"支柱, 个人用户真实需要
   - 架构成熟,沿用 VAT 模式

2. **Corporation Tax + PAYE (GovTalk XML 共享客户端)** (1-2 周, 中 ROI)
   - 一次性写 GovTalk 通用客户端,两个税种受益
   - 决定所有 UK 企业税种能否真联通

3. **Apprenticeship Levy** (随 PAYE,免费)

4. **Business Rates VOA 部分** (1 天, 低 ROI)
   - 估值/上诉价值有限,但实现简单

5. **SDLT** (1 周, 低 ROI)
   - GovTalk XML 但商业场景少 (主要是个人买房), 非企业经营主要需求

### 不建议做

- 独立 CGT / NIC TaxType (无意义, 应嵌入主税种)
- WHT 独立申报路径 (UK 不存在该能力)
- Council Tax 账单系统 (50+ 独立系统, 集成成本巨大)
