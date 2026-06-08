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
| HMRC 9-box VAT Adapter | 100% | 与 OpenAPI 规范完全一致 |
| OAuth 2.0 流程 | 100% | Authorization Code Grant + 自动 refresh |
| 欺诈预防头 | 100% | 11 个 Gov-Client-* / Gov-Vendor-* 头 |
| 沙盒 E2E 测试 | ✅ 完成 | 2026-06-01 提交 18A1 获 formBundleNumber 321591334754 |
| 文档与代码一致性 | 100% | 已交叉验证 |
| TaxAgent 全 6 阶段管线 | ✅ 已集成 | PRECHECK→PREPARE→CALCULATE→VALIDATE→SUBMIT→TRACK |
| 单元测试 | < 30% | 待补充 |
| Self Assessment 申报 | 📋 规划 | SA UTR + ITSA 流程未实现 |
| Production 切换 | 📋 规划 | 需申请真实 Government Gateway 账户 |

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
