# 🇫🇷 FR — France 法国

> **规划中** — TaxAgent Global 扩展目标

## 📋 基本信息

| 项 | 值 |
|----|-----|
| 国家代码 | `fr` |
| 国家名称 | France |
| 主管税局 | **DGFiP** (Direction Générale des Finances Publiques) |
| 主要税种 | TVA (Taxe sur la Valeur Ajoutée) |
| 报税制度 | **EDI / Mode déclaratif** |
| 监管法规 | Code général des impôts (CGI) |
| 官方系统 | **Impots.gouv.fr** + **EDI-PAIEMENTS** |
| 标准税率 | **20%** (Taux normal) |
| 低税率 | **10%** (restauration, transport) |
| 更低税率 | **5.5%** (alimentation, livres) |
| 特别低 | **2.1%** (médicaments remboursés) |
| 申报频率 | 月 (Mensuelle) / 季 (Trimestrielle) |
| 截止日期 | 申报期结束后 **15-24 日** |

---

## 🔑 关键概念

### Numéro de TVA Intracommunautaire
- 法国 VAT 号格式：`FR` + 2 位校验位 + 9 位 SIREN 号
- 例：`FR12345678901`
- SIREN 号由 INSEE 分配（如 `123456789`）

### Régime de TVA
- **Réel normal**：月报（CA3）
- **Réel simplifié**：年报 + 季度预估（CA12）
- **Franchise de TVA**：年营业额 ≤ €36,800（服务）/ €91,900（商品）可豁免

### Déclaration CA3
- 月度/季度标准 VAT 申报表
- 通过 EDI 提交或 impots.gouv.fr 手动申报
- 含多个 TVA rate 分项

### 电子商务与 OSS
- 2021 年 7 月起，跨境 B2C 销售使用 EU OSS
- 法国提供专门的 OSS 申报模块

---

## 📊 法国 TVA vs 英国 VAT 差异

| 项 | 法国 🇫🇷 | 英国 🇬🇧 |
|----|---------|---------|
| 标准税率 | 20% | 20% |
| 税率数量 | 4 个 (20%/10%/5.5%/2.1%) | 3 个 (20%/5%/0%) |
| 申报频率 | 月/季 | 季/月/年 |
| 截止日 | 15-24 日 | 37 日 |
| 表格 | CA3 (月) / CA12 (年) | 9-box |
| 认证 | impots.gouv.fr + EDI | HMRC OAuth 2.0 |
| 货币 | EUR | GBP |
| 申报媒介 | EDI / impots.gouv.fr | MTD 软件 |

---

## 🧮 法国 TVA 计算逻辑

### CA3 表格关键字段

| 字段 | 含义 | 计算 |
|------|------|------|
| **CA3-1** | 20% 销售额 | 销项总额（20% 税率）|
| **CA3-2** | 20% 销项 TVA | CA3-1 × 20% |
| **CA3-3** | 10% 销售额 | 销项总额（10% 税率）|
| **CA3-4** | 10% 销项 TVA | CA3-3 × 10% |
| **CA3-5** | 5.5% 销售额 | 销项总额（5.5% 税率）|
| **CA3-6** | 5.5% 销项 TVA | CA3-5 × 5.5% |
| **CA3-7** | 2.1% 销售额 | 销项总额（2.1% 税率）|
| **CA3-8** | 2.1% 销项 TVA | CA3-7 × 2.1% |
| **CA3-20** | 可抵扣进项 TVA | 采购发票 TVA |
| **CA3-22** | 应付 TVA | 销项 - 进项 |
| **CA3-23** | 应收 TVA (退款) | 进项 > 销项 时 |

### 计算示例

**场景：法国企业 2024 Q1（3 个月汇总申报）**

| 销售类别 | 销售额（不含 TVA）| 销项 TVA |
|---------|----------------|---------|
| 标准 20% (电子) | €50,000 | €10,000 |
| 餐饮 10% | €8,000 | €800 |
| 食品 5.5% | €5,000 | €275 |
| 药品 2.1% | €2,000 | €42 |
| 跨境（reverse charge）| €15,000 | €0 |

**进项 TVA：**
- 采购：€30,000（含 TVA €4,200）
- 其他：€2,000（含 TVA €400）
- 合计可抵扣进项 TVA：€4,600

| 字段 | 值 |
|------|-----|
| CA3-1 20% 销售 | 50,000.00 |
| CA3-2 20% 销项 TVA | 10,000.00 |
| CA3-3 10% 销售 | 8,000.00 |
| CA3-4 10% 销项 TVA | 800.00 |
| CA3-5 5.5% 销售 | 5,000.00 |
| CA3-6 5.5% 销项 TVA | 275.00 |
| CA3-7 2.1% 销售 | 2,000.00 |
| CA3-8 2.1% 销项 TVA | 42.00 |
| CA3-20 进项 TVA | 4,600.00 |
| **CA3-22 应付 TVA** | **6,517.00** |

---

## 📡 API 集成（规划）

### impots.gouv.fr
- 法国税务局在线申报门户
- **无完整公共 API**（EDI 需通过认证的中间件）
- 主流方式：使用 EDI-PAIEMENTS 服务

### EDI-PAIEMENTS
- 法国主要电子申报服务
- 通过 EDI 标准化协议交换数据
- 需申请 EDI 认证（专业软件厂商可批量申请）

### 替代方案：Portus / Chorus Pro
- Portus：法国国家采购门户（与 VAT 申报无关）
- Chorus Pro：政府采购电子发票系统

---

## 🔮 实施计划

### Phase 1: 基础架构（6 周）
- `tax_agent/jurisdictions/fr/__init__.py` 创建 `FRJurisdictionAdapter`
- `tax_agent/jurisdictions/fr/config.py` 配置
- `tax_agent/jurisdictions/fr/vat/` 子模块
  - `template.py` - CA3 字段定义（多税率）
  - `calculator.py` - 4 税率计算器
  - `validator.py` - CA3 一致性检查

### Phase 2: 浏览器自动化（8 周）
- 由于无 API，使用 Playwright 自动化 impots.gouv.fr
- 实现 `BrowserChannel`
- 实现 SIREN/SIRET 验证
- 多页面表单填写

### Phase 3: 文档生成（3 周）
- 自动生成 CA3 PDF
- 自动生成 EDI XML
- 与 EDI 认证软件商对接

---

## 📂 项目文件结构（规划）

```
tax_agent/jurisdictions/fr/
├── __init__.py             # FRJurisdictionAdapter
├── config.py                # French config
└── vat/
    ├── __init__.py         # FRVATAdapter
    ├── template.py          # CA3 template
    ├── calculator.py        # 4-rate calculator
    ├── validator.py         # CA3 validation
    ├── browser_channel.py  # Playwright automation
    └── ca3_xml.py          # EDI XML generation
```

---

## 📚 相关参考

- [Code général des impôts](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006307577/)
- [Impots.gouv.fr 专业区](https://www.impots.gouv.fr/professionnel)
- [EDI-PAIEMENTS 文档](https://www.impots.gouv.fr/edi)
- [EU OSS 法国实现](https://www.impots.gouv.fr/oss)

---

## 🚧 当前状态

```
[ ] 配置文件          tax_agent/jurisdictions/fr/config.py
[ ] Adapter            tax_agent/jurisdictions/fr/__init__.py
[ ] CA3 模板           tax_agent/jurisdictions/fr/vat/template.py
[ ] 多税率计算器       tax_agent/jurisdictions/fr/vat/calculator.py
[ ] CA3 校验器         tax_agent/jurisdictions/fr/vat/validator.py
[ ] Browser Channel    tax_agent/jurisdictions/fr/vat/browser_channel.py
[ ] 前端 UI            tax_agent/frontend/src/pages/...
[ ] API 路由           tax_agent/server/routers/jurisdictions.py
[ ] 单元测试           tests/fr/
[ ] 集成测试           tests/integration/fr/
```

优先级：**Phase 1（基础架构）** 在 EU 客户超过 3 家时启动
