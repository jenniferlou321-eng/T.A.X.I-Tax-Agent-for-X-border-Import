# 🇬🇧 UK VAT 报税流程（Filing Workflow）

> 基于 **HMRC MTD for VAT API v1.0** 规范的端到端申报流程

## 🗺️ 流程总览

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  1. Precheck │ ──▶ │  2. Prepare  │ ──▶ │ 3. Calculate │ ──▶ │ 4. Validate  │
│  字段校验    │     │  认证+格式   │     │  税额计算    │     │  一致性检查  │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                                                       │
       ┌───────────────────────────────────────────────────────────────┘
       ▼
┌──────────────┐     ┌──────────────┐
│   5. Submit  │ ──▶ │   6. Track   │
│  提交至 HMRC │     │  状态轮询    │
└──────────────┘     └──────────────┘
```

---

## 阶段 1: Precheck（前置检查）

**目的：** 验证用户输入的字段完整性和范围

| 检查项 | 来源 | 规则 |
|--------|------|------|
| 必填字段 | `template.fields[].required` | 必填字段必须有值 |
| 数值范围 | `template.fields[].validation.min/max` | 不能小于 min，不能大于 max |
| 字段类型 | `template.fields[].field_type` | number/text/select/date |
| 模板版本 | `template.version` | 必须为当前支持的版本 |

**失败处理：** 任一字段错误即终止，状态变为 `ERROR`，filing 不会被提交。

**实现：** `tax_agent/orchestrator.py::_stage_precheck`

---

## 阶段 2: Prepare（数据准备）

**目的：** 完成 OAuth 认证 + 转换为 HMRC JSON 格式

### 2a. OAuth 认证

```
1. 检查本地 token 缓存（data/oauth_token.json）
2. 如果过期，用 refresh_token 刷新
3. 如果无 token / refresh 失败，触发用户授权流程
4. 用户在浏览器完成 Government Gateway 登录 + 授权
5. 用 authorization code 交换 access_token
6. 持久化 token（4 小时有效）
```

### 2b. 格式转换

将 `LineItem` 列表转换为 HMRC 标准 JSON：

```python
{
    "periodKey": "18A1",                  # 4字符，由 HMRC 分配
    "vatDueSales": 100.00,                # Box 1
    "vatDueAcquisitions": 0.00,           # Box 2
    "totalVatDue": 100.00,                # Box 3 = Box 1 + Box 2
    "vatReclaimedCurrPeriod": 50.00,      # Box 4
    "netVatDue": 50.00,                   # Box 5 = |Box 3 - Box 4|, 必须 ≥ 0
    "totalValueSalesExVAT": 500,          # Box 6, 整磅
    "totalValuePurchasesExVAT": 300,      # Box 7, 整磅
    "totalValueGoodsSuppliedExVAT": 0,    # Box 8, 整磅
    "totalAcquisitionsExVAT": 0,          # Box 9, 整磅
    "finalised": true                     # 必须为 true
}
```

**实现：** `tax_agent/jurisdictions/uk/vat/__init__.py::to_filing_format`

---

## 阶段 3: Calculate（税务计算）

**目的：** 自动计算 Box 3 和 Box 5

### 公式

```
Box 3 (totalVatDue)        = Box 1 + Box 2
Box 5 (netVatDue)           = abs(Box 3 - Box 4)   # 必须 ≥ 0
```

**示例：**
- Box 1 = 100, Box 2 = 0 → Box 3 = 100
- Box 4 = 50 → Box 5 = |100 - 50| = 50

**HMRC 强约束：** Box 5 必须是 **非负值**。如果 Box 4 > Box 3（即净退税），Box 5 显示为正值，HMRC 会发起退款。

**实现：** `tax_agent/jurisdictions/uk/vat/calculator.py::calculate_uk_vat`

---

## 阶段 4: Validate（一致性校验）

**目的：** 在提交前发现潜在问题，避免被 HMRC 驳回

### 校验项

| 检查 | 严重度 | 触发条件 |
|------|--------|---------|
| 必填字段缺失 | Error | VAT 4, 6, 7 必填 |
| 金额为负 | Error | 任何 Box 负值 |
| 小数精度 | Warning | Box 1-5 超过 2 位小数 |
| Box 1 > 0 但 Box 6 = 0 | Warning | VAT due 但 sales 为零 |
| Box 4 远超 Box 1 | Warning | 退税异常，触发 HMRC 审查 |
| 严格模式 | Error | 配置 `warn_policy="strict"` 时警告升级为错误 |

**实现：** `tax_agent/jurisdictions/uk/vat/validator.py::validate_uk_vat`

---

## 阶段 5: Submit（提交申报）

**目的：** 调用 HMRC POST `/organisations/vat/{vrn}/returns`

### 5a. 欺诈预防头（Fraud Prevention Headers）

每个请求必须包含：

```http
POST /organisations/vat/123456789/returns HTTP/1.1
Host: test-api.service.hmrc.gov.uk
Authorization: Bearer {access_token}
Content-Type: application/json
Accept: application/vnd.hmrc.1.0+json
Gov-Client-Connection-Method: DESKTOP_APP_DIRECT
Gov-Client-Device-ID: {uuid}
Gov-Client-User-IDs: user=123456789
Gov-Client-Timezone: UTC+00:00
Gov-Client-Local-IPs: 192.168.1.100
Gov-Client-Public-IP: 203.0.113.1
Gov-Client-Screens: width=1920&height=1080&scaling-factor=1.0&colour-depth=24
Gov-Client-Window-Size: width=1440&height=900
Gov-Vendor-Version: 0.1.0
Gov-Vendor-Product-Name: TaxAgent Global
```

**实现：** `tax_agent/channels/fraud_headers.py`

### 5b. 提交响应

**成功 (201 Created)：**
```json
{
    "processingDate": "2017-05-06T10:00:00.000+0000",
    "paymentIndicator": "BANK_TRANSFER_DUE",
    "formBundleNumber": "1234567890",
    "chargeRefNumber": "ABC123456"
}
```

**错误：**
- `400 BAD_REQUEST` - 数据格式错误（如 finalised=false, periodKey 无效）
- `403 FORBIDDEN` - 权限不足
- `409 CONFLICT` - 重复提交（DUPLICATE_SUBMISSION）
- `422 UNPROCESSABLE_ENTITY` - 业务规则违反

**重试策略：**
- 错误码 `RATE_LIMITED`, `SERVICE_UNAVAILABLE`, `NETWORK_ERROR` 等会自动重试
- 最多重试 3 次，指数退避（2s, 4s, 8s）
- 失败后写入 audit log

**实现：** `tax_agent/channels/api_channel.py::submit`

---

## 阶段 6: Track（状态轮询）

**目的：** 等待 HMRC 最终受理或驳回

VAT (MTD) 的提交是**同步的** — POST returns 端点返回 201 即表示 HMRC 已接受申报。无需轮询。

**但是** TaxAgent 仍实现了一个简化的 Track 阶段，用于：
- 调用 `GET /organisations/vat/{vrn}/returns/{periodKey}` 验证 HMRC 端数据
- 检查状态变化（Fulfilled, Failed, etc.）
- 触发后续业务逻辑（发送邮件、生成 PDF 收据）

**实现：** `tax_agent/orchestrator.py::_stage_track`

---

## 📊 状态机

```
PENDING ──▶ IN_PROGRESS ──┬──▶ SUBMITTED ──▶ ACCEPTED
                          │                      │
                          ├──▶ REJECTED          └──▶ COMPLETED
                          │                        
                          └──▶ ERROR
```

| 状态 | 含义 | 终态？ |
|------|------|--------|
| `pending` | 已创建，未执行 | ❌ |
| `in_progress` | 管线执行中 | ❌ |
| `submitted` | 已提交至 HMRC | ❌ |
| `accepted` | HMRC 已受理 | ✅ |
| `rejected` | HMRC 驳回 | ✅ |
| `error` | 内部错误 | ✅ |

---

## 🔄 完整调用示例

```bash
# 1. 获取申报义务
curl "http://localhost:8765/api/filings/obligations/uk/vat?vrn=123456789&from_date=2024-01-01&to_date=2024-12-31"

# 2. 选择 periodKey (e.g. "24A1")，录入数据

# 3. 预览计算
curl -X POST "http://localhost:8765/api/filings/preview" \
  -H "Content-Type: application/json" \
  -d '{
    "jurisdiction": "uk",
    "tax_type": "vat",
    "period": {"year": 2024, "period_type": "quarterly", "period_key": "24A1", "start_date": "2024-01-01", "end_date": "2024-03-31"},
    "taxpayer": {"name": "ACME Ltd", "tax_id": "123456789", "tax_id_type": "vrn"},
    "data": [
      {"category": "vat_due_sales", "amount": 1000.00, "currency": "GBP"},
      {"category": "vat_reclaimed_purchases", "amount": 200.00, "currency": "GBP"},
      {"category": "total_sales_ex_vat", "amount": 5000, "currency": "GBP"},
      {"category": "total_purchases_ex_vat", "amount": 1000, "currency": "GBP"}
    ]
  }'

# 4. 提交申报
curl -X POST "http://localhost:8765/api/filings/submit" -d '{ ...同上 }'
```

---

## 🚨 常见错误处理

| 错误码 | 原因 | 解决 |
|--------|------|------|
| `INVALID_CREDENTIALS` | Token 过期或无效 | 重新 OAuth 授权 |
| `RESOURCE_FORBIDDEN` | Application 未订阅 VAT API | 在 Developer Hub 添加 |
| `DUPLICATE_SUBMISSION` | 该 periodKey 已提交 | 选择其他开放义务 |
| `INVALID_DATE_RANGE` | 查询日期范围超过 366 天 | 缩小范围 |
| `finalised` must be true | 提交时 finalised=false | 自动设置（修复后的代码） |
