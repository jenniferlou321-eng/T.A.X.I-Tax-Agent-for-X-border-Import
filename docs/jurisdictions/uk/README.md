# 🇬🇧 UK — United Kingdom 英国

## 📋 基本信息

| 项 | 值 |
|----|-----|
| 国家代码 | `uk` |
| 国家名称 | United Kingdom |
| 主管税局 | **HMRC** (Her Majesty's Revenue and Customs) |
| 主要税种 | VAT (Value Added Tax, 增值税) |
| 报税制度 | **MTD** (Making Tax Digital) |
| 监管法规 | VAT Act 1994, Finance Act 2015 |
| 官方 API | [VAT (MTD) API v1.0](https://developer.service.hmrc.gov.uk/api-documentation/docs/api/service/vat-api/1.0) |
| 标准税率 | **20%** (Standard rate) |
| 低税率 | **5%** (Reduced rate, e.g. 家用能源、童座椅) |
| 零税率 | **0%** (Zero rate, e.g. 大部分食品、书籍) |
| 申报频率 | 季 (Quarterly) / 月 (Monthly) / 年 (Annual) |
| 截止日期 | 申报期结束后 **37 天** 内 (e.g. 1-3 月的申报，5 月 7 日截止) |

---

## 🔑 关键概念

### MTD (Making Tax Digital)
英国从 **2019 年 4 月 1 日** 起强制实施 MTD for VAT：
- 所有 VAT-registered 企业的申报必须通过 **兼容 MTD 的软件**（TaxAgent Global 即此类软件）提交
- 不再接受纸质申报或 Excel 模板
- 必须使用 **OAuth 2.0** 获取授权后通过 REST API 提交

### Period Key
- 4 字符字符串，如 `18A1`、`24A1`、`#001`
- 由 HMRC 在生成 obligations 时自动分配
- 来源：GET `/organisations/vat/{vrn}/obligations`
- **绝不能**在 UI 中展示给最终用户

### VRN (VAT Registration Number)
- 9 位数字，如 `123456789`
- 用于标识 VAT 注册企业
- 在所有 API 调用中作为路径参数

---

## 📡 API 端点总览

| 操作 | HTTP | 端点 | 用途 | 沙盒实测 |
|------|------|------|------|---------|
| 申报义务 | GET | `/organisations/vat/{vrn}/obligations` | 获取开放/已完成的申报期 | ✅ 200 |
| 提交申报 | POST | `/organisations/vat/{vrn}/returns` | 提交 VAT Return | ✅ 201 + formBundleNumber |
| 查看申报 | GET | `/organisations/vat/{vrn}/returns/{periodKey}` | 查询已提交的 VAT Return | ✅ 200 |
| 负债信息 | GET | `/organisations/vat/{vrn}/liabilities` | 查询 VAT 负债 | ⚠️ 沙盒 NOT_FOUND |
| 付款信息 | GET | `/organisations/vat/{vrn}/payments` | 查询 VAT 付款记录 | ⚠️ 沙盒 NOT_FOUND |
| 罚款信息 | GET | `/organisations/vat/{vrn}/penalties` | 查询 VAT 罚款 | ✅ 200 + 详细数据 |
| 客户信息 | GET | `/organisations/vat/{vrn}` | 查询 VAT 注册信息 | ⚠️ 沙盒 NOT_FOUND |

详细规范：[HMRC VAT (MTD) API v1.0](https://developer.service.hmrc.gov.uk/api-documentation/docs/api/service/vat-api/1.0)

---

## ✅ 当前实现完成度

| 模块 | 完成度 | 说明 |
|------|--------|------|
| HMRC 9-box VAT Adapter | 100% | **REST API**,v1.0 - 沙箱 E2E 已测 |
| HMRC Corporation Tax Adapter | 🟡 计算+适配器完整,API client 走 mock | **HMRC 实际 API 是 XML**（Corporation Tax Online XML API）,非 REST;当前代码用 JSON 占位,需 XML 客户端才能联通真实接口 |
| HMRC PAYE (RTI) Adapter | 🟡 计算+适配器完整,API client 走 mock | **HMRC 实际 API 是 XML**（Real Time Information online）,非 REST;FPS/EPS/EYU 均为 XML 消息类型 |
| Apprenticeship Levy 计算 | ✅ 已实现 | 0.5% × 薪资总额 - £15,000 免税额,通过 PAYE RTI EPS 申报（XML 消息） |
| Self Assessment 申报 | 🟡 适配器完整,仅 mock | 个人税种,ITS A API 走 REST,未对接 |
| Stamp Duty Land Tax (SDLT) | 🟡 适配器完整,仅 mock | 房产交易税,非企业经营主要税种 |
| OAuth 2.0 流程 | 100% | Authorization Code Grant + 自动 refresh |
| 欺诈预防头 | 100% | 11 个 Gov-Client-* / Gov-Vendor-* 头 |
| 沙盒 E2E 测试 | ✅ 完成 | 2026-06-01 VAT 提交 18A1 获 formBundleNumber 321591334754 |
| TaxAgent 全 6 阶段管线 | ✅ 已集成 | PRECHECK→PREPARE→CALCULATE→VALIDATE→SUBMIT→TRACK |

### ⚠️ 重要：CT 和 PAYE 实际是 XML API（不是 REST）

经过 2026-06-13 对 HMRC Developer Hub 的复核：

- **VAT** 是 REST API（`/api/service/vat-api/1.0`） ✅
- **Corporation Tax** 是 **XML API**（`/api/xml/Corporation Tax Online`），通过 Government Gateway 的 XML 网关通信 ❌ 当前代码错误地使用 REST 路径
- **PAYE/RTI** 是 **XML API**（`/api/xml/Real Time Information online`），FPS/EPS/EYU 是 XML 消息类型 ❌ 当前代码错误地使用 REST 路径
- **Business Rates** 实际有 REST API（`/api/service/business-rates-api/2.0`），但**仅用于 VOA 估值查询和上诉**（Check case / Challenge case），**不包含 council 账单**。原文档"无 API"的说法不准确。

要让 CT 和 PAYE 真正联通 HMRC，需要：
1. 用 `httpx` 改 XML 请求（或库如 `lxml`），而非 JSON
2. POST 到 Government Gateway 的 XML endpoint（不是 `/company/corporation-tax/returns` 这种 REST 路径）
3. 处理 GovTalk 协议封装（HMRC XML API 用 GovTalk 消息包装器）

---

## ⚠️ 不在 T.A.X.I. 范围内（明确边界）

| 税种 | 原因 | 处理方式 |
|------|------|----------|
| **Withholding Tax (利息/特许权使用费预提税)** | UK 的 outward WHT 通过 CT600 申报(DTA 减免通过 DTTP1/DT-Company 纸面表单),没有独立 API。UK 对股息**从不征收 WHT**（不只是 0%）。Case B 测试 fixture 包含 CN 视角的 WHT 数据(用于跨境场景演示),不构成独立的 UK tax type | 已在 `data/tax_knowledge/uk/withholding_tax.md` 文档化规则;agent 不会把它们作为独立 TaxType 申报 |
| **Capital Gains Tax / National Insurance** | 已在 `TaxType` 枚举中预留,但仅作占位,无独立申报流程(CGT 嵌入 SA;NIC 嵌入 PAYE) | 后续如需独立能力,建议走 SA/PAYE 扩展 |
| **Council Tax / Business Rates billing** | 商业房产税的**计费**仍由各地方政府（council）征收;HMRC 也不管辖 | VOA 上诉和估值查询可走 `business-rates-api/2.0`,账单仍需直接对接 council |

---

## 🔐 认证

HMRC 使用 **OAuth 2.0 Authorization Code Grant**：
- Scopes: `read:vat`, `write:vat`
- Token 有效期：4 小时
- Refresh token 有效期：18 个月

详见 [HMRC OAuth 2.0 授权](./oauth.md)

---

## 📂 项目结构

```
tax_agent/
├── jurisdictions/uk/
│   ├── __init__.py             # UKJurisdictionAdapter
│   ├── config.py                # HMRCConfig (env vars)
│   └── vat/
│       ├── __init__.py         # UKVATAdapter
│       ├── template.py          # 9-box VAT Return 模板
│       ├── calculator.py        # Box 3/5 自动计算
│       ├── validator.py         # 字段校验 + 一致性检查
│       └── hmrc_service.py      # HMRC API 封装
├── channels/
│   ├── oauth.py                 # OAuth2Manager (authorization_code 流程)
│   ├── api_channel.py           # REST API 提交渠道
│   └── fraud_headers.py         # Gov-Client-* 欺诈预防头
```

---

## 🔗 相关文档

- [UK VAT 报税流程](./vat-workflow.md) — 6 阶段管线详细说明
- [UK VAT 9-Box 规则与计算](./vat-rules.md) — 各 Box 的业务含义和计算公式
- [HMRC OAuth 2.0 授权](./oauth.md) — 授权流程详解
- [HMRC 沙盒测试指南](./sandbox-testing.md) — Developer Hub 凭据和测试步骤
