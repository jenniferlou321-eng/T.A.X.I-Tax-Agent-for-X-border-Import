# 🇩🇪 DE — Deutschland 德国

> **规划中** — TaxAgent Global 下一步扩展目标

## 📋 基本信息

| 项 | 值 |
|----|-----|
| 国家代码 | `de` |
| 国家名称 | Deutschland |
| 主管税局 | **BZSt** (Bundeszentralamt für Steuern) |
| 主要税种 | VAT (Umsatzsteuer) |
| 报税制度 | **EU OSS** + 德国本地 VAT 申报 |
| 监管法规 | Umsatzsteuergesetz (UStG), Abgabenordnung (AO) |
| 官方 API | [Mehrwertsteuer-API (Beta)](https://developer.bzst.de/) |
| 标准税率 | **19%** (Regelsteuersatz) |
| 低税率 | **7%** (ermäßigter Steuersatz) - 食品、书籍、医疗等 |
| 申报频率 | 月 (Monatlich) / 季 (Quartal) / 年 (Jahr) |
| 截止日期 | 申报期结束后 **10 日** 内（次月 10 日）|

---

## 🔑 关键概念

### BZSt (Bundeszentralamt für Steuern)
- 德国联邦中央税务局
- 负责全国 VAT 监管
- 提供 BOP (Behörden Online Portal) 在线申报系统

### Steuer-ID vs USt-IdNr
- **Steuer-ID** (Tax ID)：11 位数字，分配给所有德国居民（如 `12345678901`）
- **USt-IdNr** (VAT ID)：格式 `DE` + 9 位数字（如 `DE123456789`）
  - 用于跨境 B2B 交易
  - 在所有 VAT 申报中使用

### Kleinunternehmer（小企业）
- 年营业额 ≤ €22,000 的小企业可豁免 VAT
- 但仍可能自愿注册以获得进项抵扣

### EU OSS (One Stop Shop)
- 2021 年 7 月 1 日起，跨境 B2C 销售可在单一欧盟国家申报
- 通过 ELSTER 系统的 OSS 申报模块

---

## 📊 德国 VAT 申报 vs 英国差异

| 项 | 德国 🇩🇪 | 英国 🇬🇧 |
|----|---------|---------|
| 标准税率 | 19% | 20% |
| 低税率 | 7% | 5% |
| 申报频率 | 月/季/年 | 季/月/年 |
| 截止日 | 10 日 | 37 日 |
| 表格 | UStVA (Umsatzsteuervoranmeldung) | 9-box |
| 认证 | ELSTER Zertifikat | HMRC OAuth 2.0 |
| 货币 | EUR | GBP |

---

## 🧮 德国 VAT 计算逻辑

### Umsatzsteuervoranmeldung (UStVA) 关键字段

| 字段 | 含义 | 计算 |
|------|------|------|
| **KZ 81** | 19% 税率销售额 | 销项总额（19% 税率）|
| **KZ 86** | 19% 税率 VAT | KZ 81 × 19% |
| **KZ 83** | 7% 税率销售额 | 销项总额（7% 税率）|
| **KZ 89** | 7% 税率 VAT | KZ 83 × 7% |
| **KZ 35** | 可抵扣进项 VAT | 采购发票的 VAT 总额 |
| **KZ 66** | EU 跨境采购 (≥ €12,500) | 从其他欧盟成员国采购（不含 VAT）|
| **KZ 61** | 19% 反向征税（进口 VAT）| 适用 reverse charge 机制 |
| **KZ 67** | 19% 应付 VAT | 销项 - 进项 |

### 计算示例

**场景：德国企业 2024 Q1**
- 国内 19% 销售：€10,000（不含 VAT）
- 19% 销项税：€1,900
- 7% 销售：€2,000
- 7% 销项税：€140
- 采购进项 VAT：€800
- 跨境 B2B 服务（reverse charge）：€5,000

| 行 | 描述 | 值 |
|----|------|-----|
| 81 | 19% 销售额 | 10,000.00 |
| 83 | 7% 销售额 | 2,000.00 |
| 86 | 19% 销项税 | 1,900.00 |
| 89 | 7% 销项税 | 140.00 |
| 66 | 跨境采购 | 5,000.00 |
| 35 | 可抵扣进项 VAT | 800.00 |
| 67 | 应付 VAT | 1,240.00 |

**结果：** 应付 €1,240 给德国税务局

---

## 📡 API 集成（规划）

### BZSt 官方 API（Beta）
- URL: `https://api.bzst.de/v1/`
- 文档: https://developer.bzst.de/
- 目前仅支持部分场景，主要是 OSS

### 替代方案：ELSTER
- 官方强制系统，但**无完整公共 API**
- 需使用 ELSTER 客户端 + 个人证书
- 商业报税软件通过 Mein ELSTER 集成

---

## 🔮 实施计划

### Phase 1: 基础架构（4 周）
- `tax_agent/jurisdictions/de/__init__.py` 创建 `DEJurisdictionAdapter`
- `tax_agent/jurisdictions/de/config.py` 配置
- `tax_agent/jurisdictions/de/vat/` 子模块
  - `template.py` - UStVA 字段定义
  - `calculator.py` - 19%/7% 双税率计算
  - `validator.py` - KZ 字段一致性检查

### Phase 2: ELSTER 集成（8 周）
- 集成 ERiC (ELSTER Rich Client) 或通过云服务
- 实现 Pkcs#7 签名
- 申报数据 XML 生成
- 申报状态轮询

### Phase 3: EU OSS 支持（4 周）
- 实现 OSS-IOSS (Import OSS) 模块
- 实现 OSS-Union (Union OSS) 模块
- 多语言申报

---

## 📂 项目文件结构（规划）

```
tax_agent/jurisdictions/de/
├── __init__.py             # DEJurisdictionAdapter
├── config.py                # German config
└── vat/
    ├── __init__.py         # DEVATAdapter
    ├── template.py          # UStVA template
    ├── calculator.py        # 19%/7% calculator
    ├── validator.py         # Field validation
    ├── elster_client.py     # ELSTER integration
    └── ustva_xml.py         # XML generation
```

---

## 📚 相关参考

- [BZSt 开发者文档](https://developer.bzst.de/)
- [Umsatzsteuergesetz (UStG)](https://www.gesetze-im-internet.de/ustg_1980/)
- [ELSTER Portal](https://www.elster.de/)
- [EU OSS 规则](https://ec.europa.eu/taxation_customs/business/vat/oss_en)

---

## 🚧 当前状态

```
[ ] 配置文件          tax_agent/jurisdictions/de/config.py
[ ] Adapter            tax_agent/jurisdictions/de/__init__.py
[ ] VAT 模板           tax_agent/jurisdictions/de/vat/template.py
[ ] VAT 计算器         tax_agent/jurisdictions/de/vat/calculator.py
[ ] VAT 校验器         tax_agent/jurisdictions/de/vat/validator.py
[ ] Channel 渠道       tax_agent/jurisdictions/de/vat/channel.py
[ ] ELSTER 集成        tax_agent/jurisdictions/de/vat/elster.py
[ ] 前端 UI            tax_agent/frontend/src/pages/...
[ ] API 路由           tax_agent/server/routers/jurisdictions.py
[ ] 单元测试           tests/de/
[ ] 集成测试           tests/integration/de/
```

优先级：**Phase 1（基础架构）** 在 EU 客户超过 5 家时启动
