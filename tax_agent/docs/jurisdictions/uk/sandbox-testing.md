# 🧪 HMRC 沙盒测试指南

> HMRC Sandbox 是一个**完全隔离**的测试环境，可放心进行真实 API 调用而不会影响生产数据。

## 🌐 环境对比

| 维度 | Sandbox | Production |
|------|---------|------------|
| Base URL | `https://test-api.service.hmrc.gov.uk` | `https://api.service.hmrc.gov.uk` |
| Authorize URL | `https://test-www.tax.service.gov.uk` | `https://www.tax.service.gov.uk` |
| OAuth | `https://test-api.service.hmrc.gov.uk/oauth/*` | `https://api.service.hmrc.gov.uk/oauth/*` |
| 数据 | 模拟，30 天未用自动清理 | 真实，影响纳税 |
| Test Users | 自动生成，3 个月未用清理 | Government Gateway 真实账号 |
| 错误码 | 同样格式 | 同样格式 |

---

## 📋 Sandbox 配置检查清单

### ✅ 1. 注册 Developer Hub 账号
- 访问 https://developer.service.hmrc.gov.uk/developer/login
- 用邮箱注册并激活

### ✅ 2. 创建 Application
- **Name**: 任意（如 `MyApp`）
- **Environment**: **Sandbox**（重要！）
- **Description**: 可选

### ✅ 3. 订阅 VAT (MTD) API
- 在 Application 详情 → **APIs** → **Add**
- 搜索 `VAT (MTD)`，选择 **Version 1.0**
- 保存

### ✅ 4. 配置 Redirect URI
- 在 Application 详情 → **Redirect URIs** → **Change**
- 添加：`http://localhost:8080`（开发用）
- 保存

### ✅ 5. 创建 Client Secret
- 在 Application 详情 → **Client secrets** → **Create**
- ⚠️ **立即复制并保存**（只显示一次！）
- 填入 TaxAgent 的 `.env`

### ✅ 6. 创建 Test User
- 在 Developer Hub 左侧 → **Test users** → **Create**
- 选择 **Organisation**（VAT 申报需要）
- 完成后 HMRC 自动生成：
  - **User ID**（如 `664155084356`）
  - **Password**（如 `6ah0eYT1NlJ4`）
  - **VRN**（如 `960606228`）
  - 各种 tax identifiers（NINO, SA UTR, etc.）

---

## 🔧 TaxAgent 配置

`tax_agent/.env`：
```bash
HMRC_CLIENT_ID=2U9ktG6rDRDpxUG1kNJ4Mld8y6Fl
HMRC_CLIENT_SECRET=ef505ced-ee2c-4797-85b6-c673de1e9121
HMRC_SANDBOX=true
HMRC_REDIRECT_URI=http://localhost:8080
```

**重要：** `HMRC_SANDBOX=true` 时自动使用沙盒 URL。

---

## 🚀 端到端测试流程

### Step 1: 启动服务

```bash
# 后端
cd tax_agent
PYTHONPATH=. python3 -m uvicorn server.main:app --port 8765

# 前端
cd tax_agent/frontend
npm run dev
```

### Step 2: 通过 API 完成 OAuth

```bash
# 1. 获取 auth URL
curl http://localhost:8765/api/channel/uk/vat/auth-url
```

### Step 3: 用 Playwright 自动化登录

或**手动**：在浏览器中打开 auth_url，使用 Test User 凭据登录，授权。

### Step 4: 交换 Code 换 Token

```bash
curl -X POST http://localhost:8765/api/channel/uk/vat/callback \
  -H "Content-Type: application/json" \
  -d '{"code": "AUTHORIZATION_CODE"}'
```

### Step 5: 测试 Obligations

```bash
curl "http://localhost:8765/api/filings/obligations/uk/vat?vrn=960606228&from_date=2024-01-01&to_date=2024-12-31"
```

返回示例：
```json
{
  "obligations": [
    {
      "start": "2017-01-01", "end": "2017-03-31", "due": "2017-05-07",
      "status": "F", "period_key": "18A1", "received": "2017-05-06"
    },
    {
      "start": "2017-04-01", "end": "2017-06-30", "due": "2017-08-07",
      "status": "O", "period_key": "18A2", "received": null
    }
  ]
}
```

### Step 6: 提交 VAT Return

```bash
curl -X POST http://localhost:8765/api/filings/submit \
  -H "Content-Type: application/json" \
  -d '{
    "jurisdiction": "uk",
    "tax_type": "vat",
    "period": {"year": 2017, "period_type": "quarterly", "period_key": "18A2", "start_date": "2017-04-01", "end_date": "2017-06-30"},
    "taxpayer": {"name": "ACME Ltd", "tax_id": "960606228", "tax_id_type": "vrn"},
    "data": [
      {"category": "vat_due_sales", "amount": 200.00, "currency": "GBP"},
      {"category": "vat_reclaimed_purchases", "amount": 100.00, "currency": "GBP"},
      {"category": "total_sales_ex_vat", "amount": 1000, "currency": "GBP"},
      {"category": "total_purchases_ex_vat", "amount": 500, "currency": "GBP"}
    ]
  }'
```

---

## 🔍 已验证的真实测试结果

TaxAgent Global 已通过完整的端到端沙盒测试（2026-06-01）：

| 测试项 | 状态 | 证据 |
|--------|------|------|
| OAuth Authorization Code | ✅ | 成功获取 code |
| Token Exchange | ✅ | 返回 4h 有效 token |
| Obligations Query (status=O) | ✅ | 返回 18A1 (Open) + 18A2 (Open) |
| Obligations Query (status=F) | ✅ | 返回 18A1 (Fulfilled) |
| VAT Return Submit | ✅ | HMRC 返回 `formBundleNumber: 321591334754` |
| VAT Return View | ✅ | HMRC 返回完整 9-box 数据 |
| VAT Penalties | ✅ | 完整 lateSubmission/latePayment 数据 |
| Box 6 整磅校验 | ✅ | 500.99 正确被拒 |
| Box 1 精度校验 | ✅ | 100.123 正确被拒 |
| netVatDue ≥ 0 校验 | ✅ | -100 正确被拒 |
| periodKey 格式校验 | ✅ | "INVALID" 正确被拒 |
| 重复提交 | ✅ | DUPLICATE_SUBMISSION |

**实测 18A1 提交响应：**
```json
{
  "processingDate": "2026-06-01T12:54:25.410Z",
  "formBundleNumber": "321591334754",
  "paymentIndicator": "DD",
  "chargeRefNumber": "4a5TBj3HWkqLSFjv"
}
```

**实测 18A1 提交后从 HMRC 拉回：**
```json
{
  "periodKey": "18A1",
  "vatDueSales": 250,
  "vatDueAcquisitions": 50,
  "totalVatDue": 300,
  "vatReclaimedCurrPeriod": 120,
  "netVatDue": 180,
  "totalValueSalesExVAT": 1250,
  "totalValuePurchasesExVAT": 600,
  "totalValueGoodsSuppliedExVAT": 100,
  "totalAcquisitionsExVAT": 50
}
```

---

## ⚠️ 沙盒特有行为

### 1. 周期（Periods）
沙盒只提供**固定历史周期**用于测试。常见 periodKey：
- `18A1`, `18A2`, `18A3`, `18A4`
- `#001` - 特殊格式
- 取决于创建 Test User 时的设置

### 2. 重复提交错误
提交同一 periodKey 第二次时会返回 `DUPLICATE_SUBMISSION`：
```json
{
  "code": "BUSINESS_ERROR",
  "errors": [{
    "code": "DUPLICATE_SUBMISSION",
    "message": "The VAT return was already submitted for the given period."
  }]
}
```

### 3. Token 生命周期
- access_token: **4 小时**（生产也是）
- refresh_token: **18 个月**（生产也是）
- 沙盒 token 不会跨应用共享

### 4. Application 自动清理
- **30 天**未调用任何 API 的 Application 会被自动删除
- **6 个月**内没有 API 调用的 Application 也会被删除

---

## 🛠️ 故障排查

### 错误：`redirect_uri is invalid`
**原因：** redirect_uri 未在 Developer Hub 注册  
**解决：** 添加 `http://localhost:8080` 到 Redirect URIs

### 错误：`RESOURCE_FORBIDDEN`
**原因：** Application 未订阅 VAT (MTD) API  
**解决：** 在 Application → APIs → Add VAT (MTD) v1.0

### 错误：`INVALID_CREDENTIALS`
**原因：** Token 过期或无效  
**解决：** 重新 OAuth 授权

### 错误：`INVALID_DATE_RANGE`
**原因：** obligations 查询日期范围超过 **366 天**  
**解决：** 缩小查询范围

### 错误：`CLIENT_OR_AGENT_NOT_AUTHORISED`
**原因：** VRN 与 token 绑定的用户不匹配  
**解决：** 使用创建 Test User 时生成的 VRN

### Token 状态
- access_token 即将过期（< 5 分钟）→ 自动刷新
- 刷新失败 → 触发新的授权流程
- **不要**手动存储 token 到数据库（自动持久化到 `data/oauth_token.json`）

---

## 📊 沙盒 vs 生产 切换

```bash
# 沙盒（默认）
HMRC_SANDBOX=true

# 生产
HMRC_SANDBOX=false
HMRC_REDIRECT_URI=https://yourapp.com/callback
```

**注意：** 生产环境的 Client ID/Secret 不同于沙盒，需要在 Developer Hub 申请。

---

## 🔗 相关资源

- [HMRC Developer Hub](https://developer.service.hmrc.gov.uk/)
- [VAT (MTD) API v1.0 文档](https://developer.service.hmrc.gov.uk/api-documentation/docs/api/service/vat-api/1.0)
- [Testing in the sandbox 指南](https://developer.service.hmrc.gov.uk/api-documentation/docs/testing)
- [User-restricted endpoints 授权](https://developer.service.hmrc.gov.uk/api-documentation/docs/authorisation/user-restricted-endpoints)
- [Test users, test data and stateful behaviour](https://developer.service.hmrc.gov.uk/api-documentation/docs/testing/test-users-test-data-stateful-behaviour)

---

## 🧪 直接 cURL 测试（绕过 TaxAgent）

无需运行后端服务，直接用 cURL 调用 HMRC 沙盒 API 进行探索。

### 设置环境变量

```bash
export HMRC_BASE=https://test-api.service.hmrc.gov.uk
export TOKEN=$(cat data/oauth_token.json | python3 -c "import json,sys;print(json.load(sys.stdin)['access_token'])")
export VRN=960606228

# 通用 fraud headers
declare -a FRAUD=(
  -H "Gov-Client-Connection-Method: DESKTOP_APP_DIRECT"
  -H "Gov-Client-Device-ID: taxagent-exploration"
  -H "Gov-Client-User-IDs: user=$VRN"
  -H "Gov-Client-Timezone: UTC+00:00"
  -H "Gov-Client-Local-IPs: 127.0.0.1"
  -H "Gov-Client-Public-IP: 127.0.0.1"
  -H "Gov-Client-Screens: width=1920&height=1080&scaling-factor=1.0&colour-depth=24"
  -H "Gov-Client-Window-Size: width=1440&height=900"
  -H "Gov-Vendor-Version: 0.1.0"
  -H "Gov-Vendor-License-ID: "
  -H "Gov-Vendor-Product-Name: TaxAgent Global"
)
```

### 1. 查询 Open obligations

```bash
curl -s "$HMRC_BASE/organisations/vat/$VRN/obligations?from=2017-01-01&to=2017-12-31&status=O" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.hmrc.1.0+json" \
  "${FRAUD[@]}"
```

**响应：**
```json
{"obligations":[{"periodKey":"18A1","start":"2017-01-01","end":"2017-03-31","due":"2017-05-07","status":"O"}]}
```

### 2. 查询 Fulfilled obligations

```bash
curl -s "$HMRC_BASE/organisations/vat/$VRN/obligations?from=2017-01-01&to=2017-12-31&status=F" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.hmrc.1.0+json" \
  "${FRAUD[@]}"
```

### 3. 查看已提交 return

```bash
curl -s "$HMRC_BASE/organisations/vat/$VRN/returns/18A1" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.hmrc.1.0+json" \
  "${FRAUD[@]}"
```

### 4. 提交新 return

```bash
curl -s -X POST "$HMRC_BASE/organisations/vat/$VRN/returns" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.hmrc.1.0+json" \
  -H "Content-Type: application/json" \
  "${FRAUD[@]}" \
  -d '{
    "periodKey": "18A1",
    "vatDueSales": 250,
    "vatDueAcquisitions": 50,
    "totalVatDue": 300,
    "vatReclaimedCurrPeriod": 120,
    "netVatDue": 180,
    "totalValueSalesExVAT": 1250,
    "totalValuePurchasesExVAT": 600,
    "totalValueGoodsSuppliedExVAT": 100,
    "totalAcquisitionsExVAT": 50,
    "finalised": true
  }'
```

### 5. 边界场景：错误场景测试

```bash
# 5a. 负 netVatDue
curl -s -X POST "$HMRC_BASE/organisations/vat/$VRN/returns" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "${FRAUD[@]}" \
  -d '{"periodKey":"99A1","netVatDue":-100,...}'
# → INVALID_MONETARY_AMOUNT on /netVatDue

# 5b. Box 6 小数
curl -s -X POST "$HMRC_BASE/organisations/vat/$VRN/returns" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "${FRAUD[@]}" \
  -d '{"periodKey":"99A1","totalValueSalesExVAT":500.99,...}'
# → INVALID_MONETARY_AMOUNT on /totalValueSalesExVAT

# 5c. 缺 periodKey
curl -s -X POST "$HMRC_BASE/organisations/vat/$VRN/returns" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "${FRAUD[@]}" \
  -d '{"vatDueSales":100,...}'
# → MANDATORY_FIELD_MISSING on /periodKey

# 5d. periodKey 格式错
curl -s -X POST "$HMRC_BASE/organisations/vat/$VRN/returns" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  "${FRAUD[@]}" \
  -d '{"periodKey":"INVALID",...}'
# → PERIOD_KEY_INVALID
```

### 6. Gov-Test-Scenario header

`Gov-Test-Scenario` header 可在沙盒模拟特定错误：

| Scenario | 触发错误 | 说明 |
|----------|----------|------|
| `DUPLICATE_SUBMISSION` | 重复提交同 period | BUSINESS_ERROR + DUPLICATE_SUBMISSION |
| `INVALID_DATE_RANGE` | 超出 366 天 | INVALID_DATE_RANGE |
| `INVALID_MONETARY_AMOUNT` | 金额超范围 | INVALID_MONETARY_AMOUNT |
| `PERIOD_KEY_INVALID` | periodKey 不正确 | PERIOD_KEY_INVALID |
| `RESOURCE_FORBIDDEN` | 未订阅 API | RESOURCE_FORBIDDEN |
| `AGENT_NOT_SUBSCRIBED` | Agent 未授权 | CLIENT_OR_AGENT_NOT_AUTHORISED |

**注意：** HMRC 的 `Gov-Test-Scenario` 严格匹配大小写和精确字符串。如果报 `RULE_INCORRECT_GOV_TEST_SCENARIO`，说明 scenario 名称在当前 API 版本中不存在 — 请参考官方文档列表。

```bash
# 示例：模拟重复提交
curl -s -X POST "$HMRC_BASE/organisations/vat/$VRN/returns" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -H "Gov-Test-Scenario: DUPLICATE_SUBMISSION" \
  "${FRAUD[@]}" \
  -d '{...valid 9-box JSON...}'
```

### 7. Liabilities & Payments & Penalties

```bash
# Liabilities（注意日期范围 ≤ 366 天，且必须含已提交 period）
curl -s "$HMRC_BASE/organisations/vat/$VRN/liabilities?from=2017-01-01&to=2017-12-31" \
  -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.hmrc.1.0+json" \
  "${FRAUD[@]}"

# Payments
curl -s "$HMRC_BASE/organisations/vat/$VRN/payments?from=2017-01-01&to=2017-12-31" \
  -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.hmrc.1.0+json" \
  "${FRAUD[@]}"

# Penalties（无日期参数）
curl -s "$HMRC_BASE/organisations/vat/$VRN/penalties" \
  -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.hmrc.1.0+json" \
  "${FRAUD[@]}"
```

**注意：** 沙盒中 liababilities/payments 端点可能返回 `NOT_FOUND`（HMRC 不为该 Test User 生成 liabilities/payments），这与生产环境不同。

---

## 📊 错误码速查（实测）

| 错误码 | 触发条件 | 解决 |
|--------|---------|------|
| `MANDATORY_FIELD_MISSING` | JSON 缺少必填字段（如 periodKey） | 补全字段 |
| `PERIOD_KEY_INVALID` | periodKey 不是 4 字符 | 用 `from /obligations` 拉取的合法 key |
| `INVALID_MONETARY_AMOUNT` | 金额超范围/精度错/Box 5 < 0 | Box 1-5 2 位小数；Box 6-9 整磅；Box 5 ≥ 0 |
| `DUPLICATE_SUBMISSION` | 同一 periodKey 已提交 | 用 Open period；或 amend（不通过此 API） |
| `INVALID_DATE_RANGE` | obligations 查询 > 366 天 | 缩小到 ≤ 366 天 |
| `BUSINESS_ERROR` | 业务规则违反（含 DUPLICATE） | 查看 `errors[]` 子码 |
| `NOT_FOUND` | liabilities/payments 沙盒无数据 | 沙盒预期行为 |
| `MATCHING_RESOURCE_NOT_FOUND` | customer info 端点沙盒无数据 | 沙盒预期行为 |
| `RESOURCE_FORBIDDEN` | Application 未订阅 API | 在 Developer Hub Add VAT (MTD) v1.0 |
| `CLIENT_OR_AGENT_NOT_AUTHORISED` | VRN 与 token 用户不匹配 | 确认 token 是为该 VRN 授权的 |
| `INVALID_CREDENTIALS` | token 过期或无效 | 重新 OAuth |
| `RULE_INCORRECT_GOV_TEST_SCENARIO` | test scenario 名称不存在 | 查官方文档确认拼写 |
| `SERVER_ERROR` / 5xx | HMRC 内部错误 | 指数退避重试 |

---

## 🎯 沙盒探索的注意事项

### 1. 沙盒状态可重置
- HMRC 沙盒数据可被平台周期性重置
- 之前提交的 return 可能变回 Open 状态（不是删除，而是 obligation 重新 Open）
- **重要：** 不要假设沙盒数据持久

### 2. 真实生产环境差异
- **真实 VRN** 需要 Government Gateway 账户
- **真实数据** 影响企业纳税 — 错误提交有罚款
- 沙盒测试应覆盖所有边界场景后才上生产

### 3. 4 小时 token TTL
- access_token 4 小时过期
- refresh_token 18 个月有效，但**只能使用一次**
- TaxAgent `OAuth2Manager` 自动检测过期并刷新

### 4. Fraud headers 是法律要求
- 缺失或错误填写的 `Gov-Client-*` header 在生产环境可能被视为欺诈企图
- 沙盒不强制但仍应正确填写以模拟生产行为

### 5. Accept header 决定 API 版本
- 错误：`-H "Accept: application/json"`
- 正确：`-H "Accept: application/vnd.hmrc.1.0+json"`
- TaxAgent 已在 `api_channel.py` 中自动设置
