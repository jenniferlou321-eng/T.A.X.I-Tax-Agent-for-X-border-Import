# PayPal Sandbox 集成研究报告

> **状态**: 调研完成
> **日期**: 2026-06-14
> **关联文档**: `docs/erp_integration.md`, `JIAHANG_TAX_ROADMAP.md`

## 1. 概述

PayPal 提供官方 Sandbox 环境，开发者可以创建测试买家/卖家账号，获取 sandbox API credentials，用于测试完整的支付流程。对于 T.A.X.I. 平台，PayPal Sandbox 可以支撑以下核心展示场景：

> 跨境收款平台 → Agent 拉取收款/退款记录 → 判断是否与销售平台收入一致

## 2. PayPal Sandbox 环境搭建

### 2.1 注册与账号

1. 访问 [PayPal Developer Dashboard](https://developer.paypal.com/)
2. 注册开发者账号（可用真实 PayPal 账号登录）
3. Sandbox → Accounts：系统自动创建 Business 和 Personal 测试账号
   - **Business 账号**：卖家账号，含虚拟余额
   - **Personal 账号**：买家账号，含测试信用卡
4. 每个 Sandbox 账号自动生成：
   - Email 地址（`-facilitator@business.example.com` 格式）
   - 虚拟余额（默认 $9999）
   - 测试卡号（Visa/Mastercard）

### 2.2 API 凭证获取

在 Dashboard → My Apps & Credentials 创建 REST API 应用：

| 凭证 | 用途 | 环境区分 |
|------|------|----------|
| **Client ID** | OAuth2 客户端标识 | Sandbox 和 Live 各一套 |
| **Secret** | OAuth2 签名密钥 | Sandbox 和 Live 各一套 |
| **Sandbox Base URL** | `https://api-m.sandbox.paypal.com` | 仅 Sandbox |
| **Live Base URL** | `https://api-m.paypal.com` | 仅生产 |

> **重要**：Sandbox 和 Live 的 Client ID/Secret 完全不同，不可混用。

## 3. PayPal REST API 核心端点

### 3.1 OAuth2 认证

```
POST /v1/oauth2/token
Authorization: Basic base64(client_id:secret)
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials

Response:
{
  "scope": "https://uri.paypal.com/services/reporting/search/read ...",
  "access_token": "A21AA...",
  "token_type": "Bearer",
  "app_id": "APP-80W284485P519543T",
  "expires_in": 32400
}
```

- Token 有效期：8 小时（28800 秒）
- 使用方式：`Authorization: Bearer {access_token}`
- 无需用户交互（Client Credentials 模式）

### 3.2 交易查询（核心对账 API）

**列出交易**：
```
GET /v1/reporting/transactions
  ?start_date=2023-01-01T00:00:00-0700
  &end_date=2023-01-31T23:59:59-0700
  &fields=all
  &page_size=100
  &page=1
```

返回字段（关键）：
| 字段 | 类型 | 说明 |
|------|------|------|
| `transaction_info.transaction_id` | string | PayPal 交易 ID |
| `transaction_info.transaction_event_code` | string | T0001(PayPal checkout), T1107(refund) |
| `transaction_info.transaction_initiation_date` | datetime | 交易时间 |
| `transaction_info.transaction_amount.value` | decimal | 交易金额 |
| `transaction_info.transaction_amount.currency_code` | string | 币种(GBP/USD/EUR...) |
| `transaction_info.transaction_status` | string | S(成功)/D(拒绝)/P(待处理) |
| `transaction_info.fee_amount.value` | decimal | PayPal 手续费 |
| `transaction_info.ending_balance.value` | decimal | 交易后余额 |
| `payer_info.payer_name.alternate_full_name` | string | 付款人姓名 |
| `payer_info.payer_email` | string | 付款人邮箱 |
| `shipping_info.name` | string | 收货人姓名 |

**单笔支付详情**：
```
GET /v2/payments/captures/{capture_id}
```

**退款记录**：
```
GET /v1/payments/sale/{sale_id}/refund
```

### 3.3 交易事件代码（transaction_event_code）

| 代码 | 含义 | 对账用途 |
|------|------|----------|
| T0001 | PayPal Checkout (收款) | 正向收入 |
| T0002 | Recurring Payment | 订阅收入 |
| T0006 | Express Checkout | 快速结账 |
| T1107 | Refund (退款) | 收入调减 |
| T1201 | Chargeback | 争议扣款 |
| T2101 | Currency Conversion | 币种转换 |
| T0302 | Withdrawal to Bank | 提现 |

### 3.4 交易报告（批量异步）

```
POST /v1/reporting/transactions
Content-Type: application/json

{
  "start_date": "2023-01-01T00:00:00Z",
  "end_date": "2023-01-31T23:59:59Z",
  "fields": ["transaction_info", "payer_info", "shipping_info"],
  "page_size": 500,
  "page": 1
}
```

> 适合每月对账场景：一次拉取全月数据，避免分页遍历。

## 4. TAXI 集成方案

### 4.1 架构位置

PayPal Channel 应该作为 **新的 Channel 类型**，与现有的 `APIChannel`（HMRC 申报）平行：

```
backend/channels/
├── __init__.py          ← FilingChannel ABC (现有)
├── api_channel.py       ← HMRC REST API (现有)
├── oauth.py             ← OAuth2 Manager (现有，PayPal 可复用)
├── fraud_headers.py     ← HMRC 专属 (PayPal 不需要)
│
└── payment/             ← ⭐ 新增：支付网关渠道
    ├── __init__.py      ← PaymentChannel ABC
    ├── paypal.py        ← PayPalChannel 实现
    └── stripe.py        ← (未来) StripeChannel
```

### 4.2 抽象接口设计

```python
# backend/channels/payment/__init__.py

class PaymentChannel(ABC):
    """支付网关抽象基类 — 与 FilingChannel 平行，用于收款数据拉取"""

    channel_name: str                   # "paypal", "stripe"

    @abstractmethod
    async def authenticate(self) -> AuthResult:
        """OAuth2 Client Credentials / API Key 认证"""
        ...

    @abstractmethod
    async def list_transactions(
        self, start_date: date, end_date: date, page_size: int = 100
    ) -> list[PaymentTransaction]:
        """拉取交易列表"""
        ...

    @abstractmethod
    async def get_transaction(self, txn_id: str) -> PaymentTransaction:
        """获取单笔交易详情"""
        ...

    @abstractmethod
    async def list_refunds(
        self, start_date: date, end_date: date
    ) -> list[RefundRecord]:
        """拉取退款记录"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """渠道可用性检查"""
        ...
```

### 4.3 PayPal 交易 → TAXI HubInvoice 映射

PayPal 交易可映射到现有 `HubInvoice` 模型：

| PayPal 字段 | HubInvoice 字段 | 映射逻辑 |
|-------------|----------------|----------|
| `transaction_id` | `id` | 加前缀 `PP-` 标识来源 |
| `transaction_initiation_date` | `txn_date` | 直接映射 |
| `payer_info.payer_name` | `counterparty` | 付款人 → 对手方 |
| `transaction_amount.value` | `gross_amount` | 收款金额 |
| `fee_amount.value` | — | 存入 `metadata` |
| `transaction_amount.currency_code` | — | 存入 `metadata` |
| — | `net_amount` | gross - fee（近似） |
| — | `vat_amount` | 需从订单关联计算 |
| — | `tax_code` | 默认 "T1"（标准税率） |
| `transaction_event_code` | — | 存入 `metadata` |
| `"paypal"` | `source` | 固定值 |

### 4.4 现有基础设施复用

| 现有能力 | 复用方式 |
|----------|----------|
| `backend/channels/oauth.py` → `OAuth2Manager` | PayPal 同样使用 OAuth2 Client Credentials，直接复用 |
| `backend/models/erp_models.py` → `HubInvoice` | 已有 `source` 字段，新增 `source="paypal"` 即可 |
| `backend/erp/reconcile.py` | 已有 £0.50 容差对账，可直接用于 PayPal vs ERP 收入比对 |
| `backend/erp/erp_samples_loader.py` | 可新增 PayPal 样本数据加载方式 |

### 4.5 缺失能力清单

| 能力 | 优先级 | 说明 |
|------|--------|------|
| `PaymentChannel` ABC | P0 | 支付网关抽象基类 |
| `PayPalChannel` 实现 | P0 | OAuth2 + Transactions API |
| `PaymentTransaction` 数据模型 | P0 | Pydantic 模型，含 `txn_event_code`、`fee`、`currency` |
| PayPal→HubInvoice 转换器 | P1 | 交易标准化映射 |
| 三方对账引擎 | P1 | PayPal vs ERP vs HMRC 三方金额比对 |
| 退款匹配逻辑 | P1 | PayPal refund 与 ERP credit note 配对 |
| 多币种转换 | P2 | PayPal 外币交易 → 本币折算 |
| 争议管理 | P2 | Chargeback/Dispute 状态跟踪 |

## 5. 跨境收款对账场景演示

### 5.1 场景流程

```
1. Agent 对话：用户说 "帮我对一下 PayPal Q1 收款和 Shopify 销售"
2. Agent 调用 get_paypal_transactions(Q1) → 获取收款列表
3. Agent 调用 get_erp_sales_data(Q1) → 获取 ERP 销售数据
4. Agent 调用 reconcile_payment_vs_sales() → 三方对账
5. Agent 返回差异报告：
   - 匹配：45 笔，总额 £120,500.00
   - PayPal 有但 ERP 无：3 笔，£2,150.00（可能是线下收款）
   - ERP 有但 PayPal 无：1 笔，£500.00（可能未支付）
   - 金额差异：2 笔，差额 £12.50（手续费差异）
6. 用户确认 → 差异项标记为 "已审核"
```

### 5.2 Agent 工具注册

```python
# backend/jurisdictions/uk/vat/agent_tools.py 新增方法

class UKVATAgentToolSet(AgentToolSet):
    async def get_paypal_transactions(self, period_key: str) -> dict:
        """拉取 PayPal 交易记录用于对账"""
        ...

    async def reconcile_payment_gateway(
        self, gateway: str, period_key: str
    ) -> ReconciliationReport:
        """支付网关 vs ERP 收入对账"""
        ...
```

## 6. PayPal Payouts API（跨境付款）

### 6.1 适用场景

对于跨境企业，PayPal Payouts API 可用于：
- 向海外供应商/承包商付款
- 向子公司资金调拨
- 向员工报销

### 6.2 核心端点

```
POST /v1/payments/payouts           # 创建批量付款
GET  /v1/payments/payouts/{id}      # 查询付款状态
POST /v1/payments/payouts-item/{id}/cancel  # 取消
```

### 6.3 与 TAXI 的关联

- 付款记录 → 对应 ERP 中的 Purchase Transaction
- 可与 ERP 采购数据做对账（付款是否与采购发票一致）
- 跨境付款涉及预扣税（WHT）场景

## 7. 安全注意事项

1. **Client ID/Secret 存储**：使用 `.env` 文件（已在 `.gitignore`），格式：
   ```
   PAYPAL_CLIENT_ID=sandbox_client_id
   PAYPAL_CLIENT_SECRET=sandbox_secret
   PAYPAL_MODE=sandbox
   ```
2. **Token 缓存**：复用现有 `OAuth2Manager` 的 token 缓存机制
3. **数据脱敏**：PayPal 交易中的 `payer_email`、`payer_name` 等 PII 在日志中脱敏
4. **速率限制**：PayPal Reporting API 限制为每分钟 30 请求

## 8. 参考资源

- PayPal Developer Dashboard: https://developer.paypal.com/
- REST API 文档: https://developer.paypal.com/docs/api/overview/
- Transaction Search API: https://developer.paypal.com/docs/api/transaction-search/v1/
- Payouts API: https://developer.paypal.com/docs/api/payments.payouts-batch/v1/
- Sandbox 测试指南: https://developer.paypal.com/tools/sandbox/
- Postman Collection: https://www.postman.com/paypal/
