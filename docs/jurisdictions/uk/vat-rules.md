# 🇬🇧 UK VAT 9-Box 规则与计算

> 9 个数字字段构成英国 VAT Return，HMRC 强制 MTD 软件必须按此格式提交

## 📊 9-Box 总览

| Box | 字段名 (HMRC API) | 业务含义 | 数据类型 | 公式 |
|-----|------------------|----------|----------|------|
| 1 | `vatDueSales` | 本期销售应缴 VAT | decimal(2dp) | - |
| 2 | `vatDueAcquisitions` | 从欧盟采购应缴 VAT | decimal(2dp) | - |
| **3** | **`totalVatDue`** | **VAT 总额** | **decimal(2dp)** | **Box 1 + Box 2** |
| 4 | `vatReclaimedCurrPeriod` | 本期可抵扣 VAT | decimal(2dp) | - |
| **5** | **`netVatDue`** | **净 VAT（应付/退税）** | **decimal(2dp) ≥ 0** | **abs(Box 3 - Box 4)** |
| 6 | `totalValueSalesExVAT` | 销售总额（不含 VAT） | **integer** | - |
| 7 | `totalValuePurchasesExVAT` | 采购总额（不含 VAT） | **integer** | - |
| 8 | `totalValueGoodsSuppliedExVAT` | 出口至欧盟总额 | **integer** | - |
| 9 | `totalAcquisitionsExVAT` | 从欧盟进口总额 | **integer** | - |

**`finalised`** = `true`（必填，声明用户已确认）

---

## 📖 各 Box 详细说明

### Box 1: VAT due on sales

- **业务含义：** 本期销售商品/提供服务产生的 VAT 销项税
- **数据来源：** 销售发票
- **计算：** 含税销售额 × VAT 税率 / (1 + VAT 税率)
  - 销售额 £1200（含 20% VAT）→ Box 1 = £200
- **典型错误：** 忘记分离 VAT、误用含税金额

### Box 2: VAT due on acquisitions

- **业务含义：** 从其他欧盟成员国采购商品应付的 VAT（post-Brexit 后基本为 0）
- **注：** 英国脱欧后（2021 年 1 月 1 日起），对欧盟销售/采购不再用 reverse charge VAT 机制
- **当前实践：** 大多数英国 VAT 注册企业 Box 2 = 0

### Box 3: Total VAT due

- **公式：** `Box 1 + Box 2`
- **HMRC 强校验：** 服务端会验证该值是否等于 Box 1 + Box 2，否则返回 400
- **TaxAgent 计算：** 提交时自动计算

### Box 4: VAT reclaimed (input tax)

- **业务含义：** 本期可以抵扣的进项 VAT（如采购原材料、办公用品、专业服务）
- **条件：**
  - 必须有合规 VAT 发票
  - 必须用于应税业务活动
  - 不能是用于免税活动的支出
- **典型错误：** 误将私人消费计入

### Box 5: Net VAT to pay (or reclaim)

- **公式：** `abs(Box 3 - Box 4)`
- **HMRC 强约束：** 必须是 **非负值**
  - 如果 Box 3 > Box 4：需要向 HMRC 付款
  - 如果 Box 4 > Box 3：HMRC 向企业退款（Box 5 显示为正值，但代表退税）
- **Payment indicator：** HMRC 决定通过何种方式收款（直接扣款 / 银行转账 / CHAPS）

### Box 6: Total value of sales

- **数据来源：** 销售发票
- **格式：** **整数（无小数位）** — HMRC 规范要求 `multipleOf: 1`
- **计算：** 销项发票总额 - VAT 销项税
- **常被误解：** 这里填的是 **不含 VAT 的销售额**，不是含税销售额

### Box 7: Total value of purchases

- **数据来源：** 采购发票
- **格式：** **整数**
- **计算：** 进项发票总额 - VAT 进项税

### Box 8: Total value of supplies to EU

- **业务含义：** 本期向欧盟成员国提供的商品总额（不含 VAT）
- **post-Brexit：** 此项对于从英国出口到欧盟的 **商品** 仍有意义（用于 Intrastat 申报）
- **多数企业：** Box 8 = 0

### Box 9: Total acquisitions from EU

- **业务含义：** 本期从欧盟成员国采购的商品总额
- **post-Brexit：** 主要用于北爱尔兰特殊协议

---

## 🔢 完整计算示例

### 场景 1: 标准应税销售

**输入：**
- 本期销售（含 VAT）：£6,000
- 销售 VAT（20%）：£1,000
- 本期采购（含 VAT）：£1,200  
- 采购 VAT（20%）：£200

**9-Box 值：**

| Box | 字段 | 值 |
|-----|------|-----|
| 1 | vatDueSales | 1,000.00 |
| 2 | vatDueAcquisitions | 0.00 |
| 3 | totalVatDue | 1,000.00 |
| 4 | vatReclaimedCurrPeriod | 200.00 |
| 5 | netVatDue | 800.00 |
| 6 | totalValueSalesExVAT | 5,000 |
| 7 | totalValuePurchasesExVAT | 1,000 |
| 8 | totalValueGoodsSuppliedExVAT | 0 |
| 9 | totalAcquisitionsExVAT | 0 |

**结果：** 应付 HMRC **£800**

---

### 场景 2: 净退税情况

**输入：**
- 销售 VAT：£100
- 采购 VAT：£300
- 销售（不含 VAT）：£500
- 采购（不含 VAT）：£1,500

**9-Box 值：**

| Box | 字段 | 值 |
|-----|------|-----|
| 1 | vatDueSales | 100.00 |
| 2 | vatDueAcquisitions | 0.00 |
| 3 | totalVatDue | 100.00 |
| 4 | vatReclaimedCurrPeriod | 300.00 |
| 5 | netVatDue | **200.00** ← abs(100 - 300) |
| 6 | totalValueSalesExVAT | 500 |
| 7 | totalValuePurchasesExVAT | 1,500 |

**结果：** HMRC 退税 **£200**（注意：Box 5 显示为正值 200，而不是负数 -200）

---

### 场景 3: 混合税率销售

**输入：**
- 标准税率销售：£2,000 + £400 VAT
- 低税率销售（5%）：£500 + £25 VAT
- 采购 VAT：£150

**9-Box 值：**

| Box | 字段 | 值 |
|-----|------|-----|
| 1 | vatDueSales | 425.00 (400 + 25) |
| 2 | vatDueAcquisitions | 0.00 |
| 3 | totalVatDue | 425.00 |
| 4 | vatReclaimedCurrPeriod | 150.00 |
| 5 | netVatDue | 275.00 |
| 6 | totalValueSalesExVAT | 2,500 (2,000 + 500) |

---

## 🚨 常见错误

### 1. 把 Box 5 填成负数
❌ `netVatDue: -200.00`  
✅ `netVatDue: 200.00` ← 退税时使用绝对值

### 2. Box 6-9 填小数
❌ `totalValueSalesExVAT: 1234.56`  
✅ `totalValueSalesExVAT: 1235` ← 整磅（HMRC 校验 `multipleOf: 1`）

### 3. Box 3 与 Box 1+2 不匹配
❌ Box 1 = 100, Box 2 = 50, Box 3 = 200  
✅ Box 1 = 100, Box 2 = 50, Box 3 = 150 ← 必须等于 Box 1+2

### 4. 漏掉 finalised
❌ `{}`（无 finalised 字段）  
✅ `{"finalised": true, ...}`

### 5. finalised 为 false
❌ `{"finalised": false, ...}`  
✅ `{"finalised": true, ...}` ← HM 必返回 400

### 6. 使用了过期的 periodKey
❌ periodKey 来自 2 年前的 obligations（已 FulFilled）  
✅ 使用最近从 `/obligations` 拉取的 status="O" 的 periodKey

---

## 📐 HMRC 强校验规则（来自 OpenAPI 规范 + 沙盒实测）

```yaml
# Box 1-5: monetary, 2 decimal places
vatDueSales:           { type: number, multipleOf: 0.01, range: -9,999,999,999,999.99 to 9,999,999,999,999.99 }
vatDueAcquisitions:    { type: number, multipleOf: 0.01, range: same as Box 1 }
totalVatDue:           { type: number, multipleOf: 0.01, range: same as Box 1, server-validated: = Box 1 + Box 2 }
vatReclaimedCurrPeriod:{ type: number, multipleOf: 0.01, range: same as Box 1 }
netVatDue:             { type: number, multipleOf: 0.01, min: 0, max: 9,999,999,999,999.99 }  # 强 ≥ 0

# Box 6-9: integer (no decimal places)
totalValueSalesExVAT:        { type: number, range: -9,999,999,999,999 to 9,999,999,999,999 }
totalValuePurchasesExVAT:    { type: number, range: same as Box 6 }
totalValueGoodsSuppliedExVAT:{ type: number, range: same as Box 6 }
totalAcquisitionsExVAT:      { type: number, range: same as Box 6 }

# Declaration
finalised: { type: boolean, enum: [true] }  # 只能为 true
```

### 沙盒实测的校验错误响应

| 触发 | HMRC 错误响应 |
|------|---------------|
| `netVatDue: -100` | `INVALID_MONETARY_AMOUNT: amount should be a monetary value (to 2 decimal places), between 0 and 99,999,999,999.99, path: /netVatDue` |
| `totalValueSalesExVAT: 500.99` | `INVALID_MONETARY_AMOUNT: The value must be between -9999999999999 and 9999999999999, path: /totalValueSalesExVAT` |
| `vatDueSales: 100.123` | `INVALID_MONETARY_AMOUNT: amount should be a monetary value (to 2 decimal places), between -9,999,999,999,999.99 and 9,999,999,999,999.99, path: /vatDueSales` |
| 缺 `periodKey` | `MANDATORY_FIELD_MISSING: a mandatory field is missing, path: /periodKey` |
| `periodKey: "INVALID"` | `PERIOD_KEY_INVALID: period key should be a 4 character string, path: /periodKey` |
| 重复提交同 periodKey | `BUSINESS_ERROR: ... DUPLICATE_SUBMISSION: The VAT return was already submitted for the given period.` |

**实现细节：**
- TaxAgent 在 `to_filing_format` 中自动转换：
  - `float(round(x, 2))` for Box 1-5
  - `int(x)` for Box 6-9
  - `finalised: True`
- 见 `tax_agent/jurisdictions/uk/vat/__init__.py`

---

## 🛡️ 法定声明（Legal Declaration）

提交前必须在 UI 显示（HMRC 要求）：

> **"When you submit this VAT information you are making a legal declaration that the information is true and complete. A false declaration can result in prosecution."**

中文翻译：  
> "您提交此 VAT 信息即视为作出法律声明，确认信息真实完整。虚假声明可能构成犯罪。"

如果是代办（Agent），声明变为：

> "I confirm that my client has received a copy of the information contained in this return and approved the information as being correct and complete to the best of their knowledge and belief."

TaxAgent 的 `NewFilingPage` 在 Step 5 强制要求用户勾选确认。

---

## ⏰ 关键时点

| 事件 | 时间 |
|------|------|
| MTD 强制实施 | 2019-04-01 |
| 季度申报截止 | 季度结束后 37 天 |
| 月度申报截止 | 月份结束后 37 天 |
| 年报截止 | 财年结束后 2 个月 |
| HMRC 处理周期 | 通常 1-3 工作日 |
| 退款支付周期 | 10-14 工作日（直接扣款账户 3-5 天） |

---

## 🔗 错误码速查

| HMRC 错误码 | 含义 | 实测响应示例 |
|-------------|------|-------------|
| `INVALID_DATE_RANGE` | obligations 查询日期范围 > 366 天 | `{"code":"INVALID_DATE_RANGE",...}` |
| `PERIOD_KEY_INVALID` | periodKey 格式错误（非 4 字符）| `path: /periodKey` |
| `DUPLICATE_SUBMISSION` | 该 periodKey 已申报 | `BUSINESS_ERROR` 包装，含 `errors[].code=DUPLICATE_SUBMISSION` |
| `MANDATORY_FIELD_MISSING` | JSON 缺少必填字段 | `path: /periodKey` 等 |
| `INVALID_MONETARY_AMOUNT` | 金额超范围/精度错 | Box 1-5 需 2 位小数；Box 6-9 需整磅；Box 5 ≥ 0 |
| `INVALID_PAYLOAD` | JSON schema 校验失败 | 顶层错误 |
| `BUSINESS_ERROR` | 业务规则违反 | 通常含子码 DUPLICATE_SUBMISSION 等 |
| `RESOURCE_FORBIDDEN` | Application 未订阅 VAT API | 需要 Developer Hub Add VAT (MTD) v1.0 |
| `CLIENT_OR_AGENT_NOT_AUTHORISED` | VRN 与 token 绑定用户不匹配 | 重新 OAuth 授权正确的 Test User |
| `NOT_FOUND` | 资源不存在（如 liabilities 在沙盒无数据）| 预期行为 |
| `MATCHING_RESOURCE_NOT_FOUND` | 客户信息端点沙盒无数据 | 预期行为 |
| `RULE_INCORRECT_GOV_TEST_SCENARIO` | `Gov-Test-Scenario` 名称拼写错 | 查官方文档确认拼写 |
| `INVALID_CREDENTIALS` | token 过期或无效 | 重新 OAuth |

---

## 🔄 与官方文档对齐情况

基于 2026-06-01 沙盒实测与官方 OpenAPI 规范比对：

| 规范项 | 官方要求 | TaxAgent 实现 | 状态 |
|--------|---------|--------------|------|
| 9 box 字段名 | camelCase（vatDueSales 等）| camelCase | ✅ |
| Box 1-5 数据类型 | number, 2dp | float(round(x, 2)) | ✅ |
| Box 6-9 数据类型 | integer | int(x) | ✅ |
| netVatDue ≥ 0 | 强制 | abs(box3-box4) | ✅ |
| finalised = true | 强制 | finalised: True | ✅ |
| periodKey 4 字符 | 强制 | 透传用户输入 | ✅ |
| Accept header | `application/vnd.hmrc.1.0+json` | 自动设置 | ✅ |
| 11 个 fraud headers | 法律要求 | FraudPreventionHeaders 构建 | ✅ |
| 错误格式 | `{code, message, errors[]}` | _parse_hmrc_errors 解析 | ✅ |
| OAuth scope | `read:vat` + `write:vat` | OAuth2Config.scopes | ✅ |
| OAuth PKCE | 可选 | 未实现 | ⚠️ 沙盒不强制 |
| Gov-Test-Scenario | 可选 header | 未使用 | ⚠️ 可增强 |
