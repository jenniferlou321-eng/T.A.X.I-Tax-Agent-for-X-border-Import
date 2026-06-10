# 新加坡报税系统接入调研报告

> 调研日期：2026/06/03
> 调研目标：评估 TaxAgent Global 平台接入新加坡 GST 报税系统的可行性

---

## 一、新加坡税制概览

### 1.1 主要税种

| 税种 | 英文 | 说明 |
|------|------|------|
| **消费税** | GST (Goods and Services Tax) | 新加坡最主要的间接税，当前税率 **9%** |
| 企业所得税 | Corporate Income Tax | 标准税率 17%，有免税额度 |
| 个人所得税 | Individual Income Tax | 累进税率 0%-24% |
| 印花税 | Stamp Duty | 房产、股票交易等 |
| 预扣税 | Withholding Tax | 对外支付的特定收入 |

### 1.2 GST 税率结构（2026年）

| 供应类型 | 税率 | 说明 |
|----------|------|------|
| **标准税率** (Standard-Rated) | **9%** | 大多数商品和服务 |
| **零税率** (Zero-Rated) | **0%** | 出口商品、国际运输服务、跨境电子服务 |
| **免税** (Exempt) | 不适用 | 金融服务、投资交易、住宅租赁、教育、医疗 |
| **非应税** (Out-of-scope) | 不适用 | 私人交易、非商业活动 |

### 1.3 GST 注册门槛

- **强制注册**：年营业额超过 **100 万新币 (SGD)**
- **自愿注册**：年营业额低于 100 万新币也可申请
- **豁免注册**：若销售额全部为零税率供应，可申请豁免

---

## 二、IRAS 数字化报税系统

### 2.1 管理机构

**IRAS** (Inland Revenue Authority of Singapore) — 新加坡国内税务局

### 2.2 申报方式

- **myTax Portal**：网页端申报门户
- **IRAS API**：开发者接口（2020年后开放）
- **ASR+ 认证软件**：通过 IRAS 认证的会计软件直接提交

### 2.3 申报周期

| 类型 | 条件 | 频率 |
|------|------|------|
| 季度申报 | 默认 | 每季度（1-3月、4-6月、7-9月、10-12月） |
| 月度申报 | 年营业额 > 500 万新币 | 每月 |
| 半年度申报 | 特别批准的小企业 | 每半年 |

申报截止日：申报期结束后 **1 个月**内（如 Q1 4月30日前）

---

## 三、GST 申报表格结构

### 3.1 主要表格

| 表格 | 用途 | 说明 |
|------|------|------|
| **GST F5** | 常规申报 | 每季度/月/半年提交 |
| **GST F7** | 纠错申报 | 更正已提交的 F5/F7/F8 中的错误 |
| **GST F8** | 申请退税 | 申请 GST 退税 |

### 3.2 GST F5 表格字段（推测结构）

基于 IRAS 文档和 NetSuite GST F5 报告，F5 表格包含以下核心数据：

#### 供应（Sales/Supplies）

| 字段 | 说明 |
|------|------|
| **Box 1** | 标准税率供应总值（含税）Standard-rated supplies (Value) |
| **Box 2** | 标准税率供应的 GST 金额 Standard-rated supplies (GST amount) |
| **Box 3** | 零税率供应总值 Zero-rated supplies |
| **Box 4** | 免税供应总值 Exempt supplies |
| **Box 5** | 总供应值（1+3+4）Total value of supplies |
| **Box 6** | 出口总值（不计入 Box 5）Exports |

#### 采购（Purchases）

| 字段 | 说明 |
|------|------|
| **Box 7** | 标准税率采购总值（含税）Standard-rated purchases (Value) |
| **Box 8** | 标准税率采购的 GST 金额（可抵扣）Input tax claimed |
| **Box 9** | 零税率采购总值 Zero-rated purchases |
| **Box 10** | 免税采购总值 Exempt purchases |

#### 税额计算

| 字段 | 计算方式 |
|------|----------|
| **Box 11** | 应缴 GST = Box 2 (Output Tax) |
| **Box 12** | 可抵扣 GST = Box 8 (Input Tax) |
| **Box 13** | 净 GST = Box 11 - Box 12（正数=应缴，负数=退税）|

> **注意**：以上为基于 HMRC 9-box 和 NetSuite GST F5 的推测结构，实际 IRAS F5 字段命名和结构需通过 IRAS API 文档确认。

### 3.3 与英国 VAT 9-Box 对比

| 对比项 | 英国 HMRC VAT | 新加坡 IRAS GST |
|--------|---------------|-----------------|
| 税率 | 20% 标准税率 | 9% 标准税率 |
| 申报表 | 9-Box | ~13 Box（推测） |
| 零税率 | 有（儿童服装、书籍等） | 有（出口商品、国际服务） |
| 免税 | 有（保险、邮政） | 有（金融、医疗、教育） |
| EU 特殊规则 | 有（Box 8/9） | 无（新加坡非欧盟） |
| 反向征收 | 有（B2B 数字服务） | 有（海外服务） |
| 退税 | 可以 | 可以（Box 13 为负时） |
| 申报截止 | 次月 7 日 | 次月末 |

---

## 四、IRAS API 系统

### 4.1 API 开发者门户

- **生产环境**：`https://apiservices.iras.gov.sg/`
- **沙盒环境**：`https://apisandbox.iras.gov.sg/`

### 4.2 已开放的 API

基于 IRAS 开发者门户公开信息：

| API | 版本 | 说明 |
|-----|------|------|
| **Submission of GST Returns (CorpPass)** | 1.0.4 | 企业 GST F5/F7 申报提交 |
| **CorpPass Authentication** | 2.0.1 | CorpPass 企业身份认证 |
| **Submission of Commission Records (CorpPass)** | 1.0.2 | 佣金记录提交 |
| **SingPass Authentication** | 2.0.1 | SingPass 个人身份认证 |
| **eStamping** | 1.0.3 | 电子印花税 |
| **Organisation Search (Sandbox)** | 1.0.6 | 企业信息查询（沙盒） |

### 4.3 认证方式

#### CorpPass（企业用户）
- 新加坡政府企业数字身份系统
- 类似英国的 Government Gateway
- 企业管理员分配子账号权限
- API 调用需要 CorpPass JWT Token

#### SingPass（个人用户）
- 新加坡国民数字身份系统
- 用于个人所得税等个人税务申报
- 通过 SingPass API 获取访问令牌

### 4.4 API 接入流程（推测）

```
1. 注册 IRAS API 开发者账号
   ↓
2. 申请 CorpPass 接入（企业需要 UEN - Unique Entity Number）
   ↓
3. 获取 API Key / Client ID / Client Secret
   ↓
4. 通过 CorpPass Authentication API 获取 Access Token
   ↓
5. 使用 Token 调用 GST Returns Submission API
   ↓
6. 接收 IRAS 回执（Receipt ID + 处理状态）
```

---

## 五、IRAS ASR+ 软件认证

### 5.1 什么是 ASR+

**ASR+** (Accounting Software Register Plus) 是 IRAS 的会计软件认证计划。

- **Tier 1**：基础认证（软件符合 GST 计算规范）
- **Tier 2**：增强认证（支持 GST 申报数据导出）
- **Tier 3**：高级认证（支持直接通过 API 提交 GST 申报到 IRAS）

### 5.2 对 TaxAgent Global 的意义

若平台要支持直接向 IRAS 提交 GST 申报：
- 需要通过 **ASR+ Tier 3** 认证
- 认证要求软件符合 IRAS 的数据格式和校验规则
- 需要与 IRAS 建立正式合作关系

**替代方案**：不直接提交，而是生成 IRAS 认可的申报数据文件，由用户手动上传到 myTax Portal。

---

## 六、与 TaxAgent Global 架构的对接评估

### 6.1 可行性评估

| 维度 | 评估 | 说明 |
|------|------|------|
| **API 可用性** | ✅ 可行 | IRAS 已开放 GST 申报 API |
| **认证复杂度** | ⚠️ 中等 | CorpPass 认证比 HMRC OAuth2 更复杂 |
| **数据模型适配** | ⚠️ 中等 | GST F5 字段与 HMRC 9-Box 不同但类似 |
| **ASR+ 认证** | ❌ 需要额外工作 | 直接提交需 Tier 3 认证 |
| **法规知识** | ⚠️ 需补充 | 新加坡 GST 规则与 UK VAT 有差异 |
| **多语言支持** | ✅ 支持 | IRAS 支持英文，平台无需中文适配 |

### 6.2 需要实现的内容

#### 后端（Python）

```
jurisdictions/sg/
├── __init__.py              # SGJurisdictionAdapter
└── gst/
    ├── __init__.py          # SGSTAdapter (模板、计算、校验、通道)
    ├── calculator.py        # GST 计算逻辑 (9% 标准税率)
    ├── validator.py         # F5 表格校验规则
    ├── template.py          # GST F5 数据模板
    ├── iras_service.py      # IRAS API 客户端
    ├── config.py            # IRAS API 配置
    └── agent_tools.py       # SGSTAgentToolSet (6 个工具)
```

#### 核心差异

| 模块 | 英国 UK | 新加坡 SG |
|------|---------|-----------|
| 税率 | 20% | 9% |
| 申报表 | 9-Box | ~13 Box（F5） |
| 认证 | OAuth2 | CorpPass JWT |
| API Base URL | api.hmrc.gov.uk | apiservices.iras.gov.sg |
| 特殊字段 | EU Box 8/9 | 出口、反向征收 |
| 通道类型 | REST API | REST API + CorpPass |

#### 前端（React）

- 新增新加坡 Case Presets
- 新增 GST F5 表单模板（标准税率、零税率、免税分类）
- 新增新加坡 GST 法规知识到 Agent 提示

### 6.3 工作量估算

| 工作项 | 工作量 | 优先级 |
|--------|--------|--------|
| IRAS API 调研 + 沙盒测试 | 2-3 天 | 高 |
| SGSTAdapter 实现 | 3-5 天 | 高 |
| SGSTAgentToolSet 实现 | 2-3 天 | 高 |
| Agent 提示（新加坡 GST 法规） | 1-2 天 | 中 |
| 前端 GST F5 模板和 Case Presets | 2-3 天 | 中 |
| CorpPass 认证集成 | 3-5 天 | 高 |
| IRAS ASR+ Tier 3 认证申请 | 2-4 周 | 低（可先不认证） |
| **总计** | **约 2-3 周** | |

---

## 七、关键风险与建议

### 7.1 风险

1. **IRAS API 文档不完整**：公开信息有限，实际 API 细节需申请开发者账号后才能获取
2. **CorpPass 认证门槛**：需要新加坡注册企业（UEN）才能申请 CorpPass
3. **ASR+ 认证周期长**：Tier 3 认证可能需要数周审核
4. **税率变动**：新加坡 GST 从 7% → 8% → 9%，未来可能继续上调

### 7.2 建议

1. **第一阶段：数据生成**（无需 ASR+ 认证）
   - 实现 GST F5 计算和校验
   - 生成 IRAS 认可的申报数据
   - 用户手动上传到 myTax Portal

2. **第二阶段：API 直连**（需要 ASR+ Tier 3）
   - 申请 IRAS 开发者账号
   - 申请 CorpPass 接入
   - 申请 ASR+ Tier 3 认证
   - 实现直接提交

3. **建议先对接的市场**：
   - 新加坡华人企业数量多，GST 是主要税种
   - 税率结构相对简单（单一标准税率 9%）
   - 无复杂的多级税率或 EU 特殊规则

---

## 八、参考链接

- IRAS 官网：https://www.iras.gov.sg/
- IRAS API 开发者门户：https://apiservices.iras.gov.sg/
- IRAS API 沙盒：https://apisandbox.iras.gov.sg/
- IRAS GST 申报指南：https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/filing-gst
- IRAS ASR+ 软件认证：https://www.iras.gov.sg/digital-collaboration/for-software-developers/accounting-tax-software
- CorpPass 官网：https://www.corppass.gov.sg/
- NetSuite GST F5 报告文档：https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/article_1220053256.html

---

## 九、结论

**新加坡 GST 接入在技术上完全可行**，主要优势：

1. ✅ IRAS 已提供官方 API（GST Returns Submission）
2. ✅ 单一标准税率（9%），无复杂的多税率计算
3. ✅ 英语环境，无需本地化
4. ✅ TaxAgent Global 的多国架构已解耦，新增国家只需实现标准接口

**主要障碍**：

1. ⚠️ 需要新加坡注册企业身份才能申请 CorpPass 和 IRAS API 接入
2. ⚠️ 直接提交需要 IRAS ASR+ Tier 3 认证
3. ⚠️ IRAS API 详细文档需申请开发者账号后才能获取

**推荐路径**：
- 短期：实现 GST F5 计算 + 数据导出（用户手动上传）
- 中期：申请 IRAS 开发者账号，在沙盒测试 API
- 长期：申请 ASR+ Tier 3，实现全自动提交
