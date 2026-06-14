# 电商平台数据接入研究报告

> **状态**: 调研完成
> **日期**: 2026-06-14
> **关联文档**: `docs/erp_integration.md`, `docs/integration/paypal-sandbox.md`

## 1. 概述

T.A.X.I. 平台的愿景是从电商平台/ERP 系统接入数据，自动完成税务申报。当前 `backend/erp/` 模块已支持 CSV 导入和 ERPNext pull，但尚未接入 Shopify、Amazon 等主流电商平台。

本报告重点调研 **Shopify** 的数据接入方式，并横向对比 Amazon Seller Central、eBay、WooCommerce 等平台，最终给出集成架构建议。

## 2. Shopify 数据接入

### 2.1 API 体系概览

Shopify 提供两套 API：

| 特性 | REST Admin API | GraphQL Admin API |
|------|---------------|-------------------|
| **端点** | `https://{shop}.myshopify.com/admin/api/{version}/` | `https://{shop}.myshopify.com/admin/api/{version}/graphql.json` |
| **认证** | OAuth2 (Access Token) | OAuth2 (Access Token) |
| **版本** | `2024-01`, `2024-04` 等 | 同 REST，但查询能力独立演进 |
| **数据拉取** | 资源级端点 (`/orders.json`) | 灵活查询（`orders` query） |
| **分页** | Link header (cursor-based) | `pageInfo` + `edges` (Relay) |
| **批量操作** | 逐页遍历 | `bulkOperationRunQuery` (大批量) |
| **Webhook** | REST 资源事件 | 同 REST webhook 机制 |

**推荐**：新项目使用 GraphQL Admin API，原因：
- 可按需查询字段（减少数据传输）
- `bulkOperationRunQuery` 适合月度对账的大批量数据拉取
- Relay cursor 分页更稳定

### 2.2 认证 (OAuth2)

```
1. 用户在 Shopify Partner Dashboard 创建 App
2. 获取 API Key + API Secret Key
3. OAuth2 Authorization Code Flow：
   GET https://{shop}.myshopify.com/admin/oauth/authorize
     ?client_id={api_key}
     &scope=read_orders,read_products,read_analytics
     &redirect_uri={callback_url}
4. 用户授权后回调 → 获取 authorization code
5. POST https://{shop}.myshopify.com/admin/oauth/access_token
   → 获取 permanent access_token
```

**关键点**：
- Access token 是永久的（不自动过期）
- Scope 决定可访问的资源范围
- 同一 App 可安装到多个商店

### 2.3 GraphQL 查询订单数据

**基础订单查询**：
```graphql
query GetOrders($first: Int!, $after: String, $query: String) {
  orders(first: $first, after: $after, query: $query) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        name                    # 订单号, e.g. "#1001"
        createdAt
        totalPriceSet {
          shopMoney { amount currencyCode }  # 店铺币种
          presentmentMoney { amount currencyCode }  # 展示币种
        }
        subtotalPriceSet { shopMoney { amount currencyCode } }
        totalTaxSet { shopMoney { amount currencyCode } }
        totalShippingPriceSet { shopMoney { amount currencyCode } }
        totalDiscountsSet { shopMoney { amount currencyCode } }
        totalRefundedSet { shopMoney { amount currencyCode } }
        lineItems(first: 50) {
          edges {
            node {
              title
              quantity
              originalTotalSet { shopMoney { amount currencyCode } }
              taxLines { title rate percentage }
              variant { sku barcode }
            }
          }
        }
        transactions(first: 5) {
          id
          gateway                 # "paypal", "shopify_payments", "manual"
          kind                    # "sale", "refund", "authorization"
          status                  # "success", "failure", "pending"
          amountSet { shopMoney { amount currencyCode } }
          createdAt
        }
        customer {
          displayName
          email
        }
        shippingAddress {
          countryCodeV2
          province
          city
        }
        displayFulfillmentStatus
        refunds(first: 5) {
          id
          createdAt
          totalRefundedSet { shopMoney { amount currencyCode } }
        }
      }
    }
  }
}
```

**按日期范围筛选**：
```graphql
query {
  orders(first: 50, query: "created_at:>=2023-01-01T00:00:00Z AND created_at:<2023-04-01T00:00:00Z") {
    edges { node { id name createdAt totalPriceSet { shopMoney { amount currencyCode } } } }
  }
}
```

**批量操作 (Bulk Operation)**：
```graphql
mutation {
  bulkOperationRunQuery(
    query: """
    {
      orders {
        edges {
          node {
            id name createdAt
            totalPriceSet { shopMoney { amount currencyCode } }
            totalTaxSet { shopMoney { amount currencyCode } }
            transactions { gateway kind status amountSet { shopMoney { amount currencyCode } } }
            refunds { totalRefundedSet { shopMoney { amount currencyCode } } }
          }
        }
      }
    }
    """
  ) {
    bulkOperation { id status url }
    userErrors { field message }
  }
}
```
- 结果写入 JSONL 文件，通过 `url` 字段下载
- 适合月度/季度全量对账

### 2.4 Webhook 实时事件

Shopify Webhook 支持以下关键事件：

| Webhook Topic | 触发时机 | 对账用途 |
|---------------|----------|----------|
| `orders/create` | 新订单创建 | 实时记录销售 |
| `orders/updated` | 订单更新（退款、取消等） | 同步状态变更 |
| `orders/paid` | 订单支付完成 | 确认收入 |
| `orders/fulfilled` | 订单发货 | 确认交付 |
| `refunds/create` | 退款创建 | 收入调减 |
| `order_transactions/create` | 交易记录创建 | 支付确认 |

**Webhook 接收端点**（TAXI 需要实现）：
```
POST /api/webhooks/shopify
Headers:
  X-Shopify-Hmac-SHA256: {hmac_signature}   # 验证请求来源
  X-Shopify-Shop-Domain: {shop}.myshopify.com
  X-Shopify-Topic: orders/create
Body: { order JSON }
```

### 2.5 关于 "SessionStart" Hook

**Shopify 没有名为 "SessionStart" 的 hook。** 经过调研，可能指的是以下之一：

1. **Shopify Session Token**：用于嵌入式 App 的认证机制，与数据拉取无关
   - 新 App 使用 `shopify.authenticate.session(request)` 创建 session
   - 这是 App 内的概念，不是 webhook 事件

2. **Shopify Flow**：Shopify 内置的自动化工具，可以在订单创建等事件时触发自定义流程
   - 但也不叫 "SessionStart"

3. **可能的混淆**：某些第三方 ERP 桥接工具（如 Zapier/Make）在连接 Shopify 时有一个 "Session Start" 配置步骤，但这不是 Shopify 原生概念

**对于 TAXI 场景，正确的数据接入方式是：**
- **实时**：Shopify Webhooks（`orders/create`, `refunds/create`）
- **批量**：GraphQL Bulk Operation（月度对账）
- **按需**：GraphQL Admin API 查询（Agent 触发）

### 2.6 订单 → UK VAT 9-Box 映射

| Shopify Order 字段 | VAT Box | 映射逻辑 |
|---------------------|---------|----------|
| `totalPriceSet` - `totalTaxSet` | **Box 6** (total_sales_ex_vat) | 总销售额（不含 VAT） |
| `totalTaxSet` (shopMoney) | **Box 1** (vat_due_sales) | 销项 VAT |
| `totalShippingPriceSet` (不含VAT部分) | Box 6 子项 | 运费计入销售额 |
| `refunds.totalRefundedSet` (tax部分) | **Box 1 调减** | 退款 VAT 冲减 |
| `refunds.totalRefundedSet` (不含tax) | **Box 6 调减** | 退款销售额冲减 |
| 非 UK 地址订单 | Box 6 + Box 8 | 区分 domestic vs EU |
| EU 地址订单（B2B, 有 VAT ID） | Box 6 + Box 8 | EC Sales List |
| EU 地址订单（B2C, 超阈值） | Box 1 (OSS) 或 Box 1 (local) | 根据注册地 |

**复杂场景处理：**
- **多税率**：Shopify `lineItems[].taxLines[].rate` 区分 20%/5%/0%
- **免税订单**：`totalTaxSet == 0` + 非 EU 地址 → Box 6 但不计入 Box 1
- **跨境 B2B**：EU B2B 零税率 → Box 6 + Box 8（EC Sales），不计入 Box 1
- **多币种**：`presentmentMoney` vs `shopMoney`，需要用 HMRC 公布的月度汇率折算

## 3. 其他电商平台对比

### 3.1 Amazon Seller Central (SP-API)

| 特性 | 说明 |
|------|------|
| **API 名称** | Selling Partner API (SP-API) |
| **协议** | REST (JSON) |
| **认证** | OAuth2 + AWS IAM (Login with Amazon) |
| **复杂度** | ⭐⭐⭐⭐⭐ 最高 |
| **核心端点** | `GET /orders/v0/orders`, `GET /finances/v0/transactions` |
| **报表** | `GET /reports/2021-06-30/reports` (异步生成) |
| **Webhook** | SQS Notification (orders, payments) |
| **沙盒** | 有 Sandbox 环境 |
| **时效** | Finance API 有 48h 延迟 |

**Amazon 独特之处：**
- 需要 AWS IAM Role + SP-API 双重认证
- 数据分散在多个 API（Orders, Finances, Reports, FBA）
- FBA (Fulfilled by Amazon) 有独立的结算周期
- Marketplace Facilitator Tax（美国/欧洲 marketplace VAT）由 Amazon 代缴

### 3.2 eBay

| 特性 | 说明 |
|------|------|
| **API** | eBay REST APIs (Sell/Finances/Fulfillment) |
| **认证** | OAuth2 Authorization Code Grant |
| **核心端点** | `GET /sell/finances/v1/transaction`, `GET /sell/fulfillment/v1/order` |
| **沙盒** | 有 Sandbox 环境 |
| **复杂** | ⭐⭐⭐ 中等 |

### 3.3 WooCommerce

| 特性 | 说明 |
|------|------|
| **API** | WooCommerce REST API |
| **认证** | OAuth 1.0a 或 API Key (Basic Auth) |
| **核心端点** | `GET /wp-json/wc/v3/orders`, `GET /wp-json/wc/v3/reports/sales` |
| **沙盒** | 无官方沙盒，需自建测试站点 |
| **复杂度** | ⭐⭐ 较低 |

### 3.4 电商平台对比总结

| 维度 | Shopify | Amazon SP-API | eBay | WooCommerce |
|------|---------|---------------|------|-------------|
| API 风格 | GraphQL + REST | REST | REST | REST |
| 认证复杂度 | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ |
| 沙盒 | ✅ | ✅ | ✅ | ❌ (需自建) |
| 实时 Webhook | ✅ | ✅ (SQS) | ✅ | ✅ |
| 批量数据 | ✅ Bulk Query | ✅ Reports | 🟡 分页 | 🟡 分页 |
| 手续费数据 | ✅ transactions | ✅ Finances | ✅ Finances | ❌ (插件) |
| 退款数据 | ✅ GraphQL | ✅ Finances | ✅ Finances | ✅ REST |
| 多币种 | ✅ | ✅ | ✅ | 🟡 (插件) |
| 市场代缴税 | ❌ | ✅ (Marketplace) | 🟡 | ❌ |
| 文档质量 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **建议接入优先级** | **P0** | P1 | P2 | P1 |

## 4. TAXI 电商集成架构

### 4.1 目录结构

```
backend/channels/
├── __init__.py              ← FilingChannel ABC (现有)
├── api_channel.py           ← HMRC REST API (现有)
├── oauth.py                 ← OAuth2 Manager (现有)
├── fraud_headers.py         ← HMRC 专属 (现有)
│
├── ecommerce/               ← ⭐ 新增：电商平台渠道
│   ├── __init__.py          ← EcommerceChannel ABC
│   ├── shopify.py           ← ShopifyChannel (GraphQL)
│   ├── amazon.py            ← AmazonChannel (SP-API, 未来)
│   ├── ebay.py              ← eBayChannel (未来)
│   └── woocommerce.py       ← WooCommerceChannel (未来)
│
└── payment/                 ← ⭐ 新增：支付网关渠道
    ├── __init__.py          ← PaymentChannel ABC
    └── paypal.py            ← PayPalChannel
```

### 4.2 抽象接口设计

```python
# backend/channels/ecommerce/__init__.py

class EcommerceChannel(ABC):
    """电商平台抽象基类"""

    platform_name: str                  # "shopify", "amazon", "ebay"

    # ── 认证 ──
    @abstractmethod
    async def authenticate(self) -> AuthResult:
        """OAuth2 / API Key 认证"""
        ...

    # ── 订单查询 ──
    @abstractmethod
    async def list_orders(
        self, start_date: date, end_date: date, **filters
    ) -> list[EcommerceOrder]:
        """拉取订单列表"""
        ...

    @abstractmethod
    async def get_order(self, order_id: str) -> EcommerceOrder:
        """获取单笔订单详情"""
        ...

    # ── 退款查询 ──
    @abstractmethod
    async def list_refunds(
        self, start_date: date, end_date: date
    ) -> list[EcommerceRefund]:
        """拉取退款记录"""
        ...

    # ── 批量操作 ──
    @abstractmethod
    async def bulk_export(
        self, start_date: date, end_date: date
    ) -> str:
        """全量导出（返回 JSONL 文件路径）"""
        ...

    # ── Webhook 验证 ──
    @abstractmethod
    def verify_webhook(self, body: bytes, signature: str) -> bool:
        """验证 webhook 请求签名"""
        ...

    # ── 健康检查 ──
    @abstractmethod
    async def health_check(self) -> bool:
        """渠道可用性检查"""
        ...
```

### 4.3 Shopify Channel 实现概要

```python
# backend/channels/ecommerce/shopify.py

class ShopifyChannel(EcommerceChannel):
    platform_name = "shopify"

    def __init__(self, shop_domain: str, access_token: str):
        self.shop_domain = shop_domain
        self.access_token = access_token
        self._client = httpx.AsyncClient(
            base_url=f"https://{shop_domain}/admin/api/2024-01",
            headers={
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
            },
        )

    async def list_orders(self, start_date: date, end_date: date, **filters):
        """使用 GraphQL 查询订单"""
        query = """
        query($first: Int!, $after: String, $query: String) {
          orders(first: $first, after: $after, query: $query) {
            pageInfo { hasNextPage endCursor }
            edges {
              node {
                id name createdAt
                totalPriceSet { shopMoney { amount currencyCode } }
                totalTaxSet { shopMoney { amount currencyCode } }
                totalShippingPriceSet { shopMoney { amount currencyCode } }
                totalRefundedSet { shopMoney { amount currencyCode } }
                transactions(first: 10) { gateway kind status amountSet { shopMoney { amount currencyCode } } }
                refunds(first: 5) { totalRefundedSet { shopMoney { amount currencyCode } } }
                shippingAddress { countryCodeV2 }
              }
            }
          }
        }
        """
        date_query = f"created_at:>={start_date.isoformat()}T00:00:00Z AND created_at:<{end_date.isoformat()}T00:00:00Z"
        variables = {"first": 50, "after": None, "query": date_query}

        all_orders = []
        while True:
            resp = await self._client.post("/graphql.json", json={"query": query, "variables": variables})
            data = resp.json()
            orders = data["data"]["orders"]
            all_orders.extend([edge["node"] for edge in orders["edges"]])
            if not orders["pageInfo"]["hasNextPage"]:
                break
            variables["after"] = orders["pageInfo"]["endCursor"]

        return [self._to_ecommerce_order(o) for o in all_orders]

    def verify_webhook(self, body: bytes, signature: str):
        """验证 Shopify webhook HMAC-SHA256 签名"""
        import hmac, hashlib
        computed = hmac.new(
            self.api_secret_key.encode(), body, hashlib.sha256
        ).digest()
        return hmac.compare_digest(
            signature, computed.hex()
        )
```

### 4.4 电商订单 → TAXI 标准模型映射

```python
# backend/models/ecommerce.py

@dataclass
class EcommerceOrder:
    """电商订单 — 平台无关的标准模型"""
    platform: str                       # "shopify", "amazon", "ebay"
    order_id: str
    order_number: str                   # 人类可读的订单号
    created_at: datetime
    currency: str                       # GBP, USD, EUR
    subtotal: Decimal                   # 不含税小计
    total_tax: Decimal                  # 税额
    total_shipping: Decimal             # 运费
    total_discounts: Decimal            # 折扣
    total_price: Decimal                # 含税总价
    total_refunded: Decimal             # 已退款金额
    payment_gateway: str                # "paypal", "shopify_payments"
    payment_status: str                 # "paid", "pending", "refunded"
    line_items: list[EcommerceLineItem]
    shipping_country: str               # ISO 3166-1 alpha-2
    customer_name: str
    customer_email: str
    is_b2b: bool                        # 是否 B2B (有 VAT ID)
    metadata: dict

@dataclass
class EcommerceLineItem:
    """订单行项目"""
    title: str
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    sku: str = ""

@dataclass
class EcommerceRefund:
    """退款记录"""
    platform: str
    refund_id: str
    order_id: str
    created_at: datetime
    amount: Decimal
    tax_amount: Decimal
    currency: str
    reason: str = ""
```

### 4.5 Webhook 接收端点

```python
# backend/routers/webhooks.py

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

@router.post("/shopify")
async def shopify_webhook(request: Request):
    """接收 Shopify webhook 事件"""
    body = await request.body()
    hmac_header = request.headers.get("X-Shopify-Hmac-SHA256", "")
    topic = request.headers.get("X-Shopify-Topic", "")
    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "")

    # 1. 验证签名
    channel = get_shopify_channel(shop_domain)
    if not channel.verify_webhook(body, hmac_header):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 2. 根据 topic 处理
    data = json.loads(body)
    if topic == "orders/create":
        order = channel.parse_order(data)
        await hub_service.upsert_order(order)
    elif topic == "refunds/create":
        refund = channel.parse_refund(data)
        await hub_service.upsert_refund(refund)
    elif topic == "orders/updated":
        order = channel.parse_order(data)
        await hub_service.upsert_order(order)

    return {"status": "ok"}
```

## 5. 端到端数据链：电商 → 支付 → 税务

### 5.1 完整数据流

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│   Shopify    │     │   PayPal     │     │    TAXI      │     │  HMRC    │
│  (销售平台)   │     │  (支付网关)   │     │  (对账+申报)  │     │  (税局)   │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘     └────┬─────┘
       │                    │                    │                  │
       │ 订单创建            │                    │                  │
       │──→ Webhook ────────→│                    │                  │
       │                    │ 支付确认            │                  │
       │                    │──→ Webhook ────────→│                  │
       │                    │                    │                  │
       │ 月度对账 (Agent触发)                     │                  │
       │←── GraphQL Query ──│←── Transactions ───│                  │
       │                    │                    │                  │
       │ 三方比对                               │                  │
       │ Shopify 销售额 = PayPal 收款 = VAT Box 6│                  │
       │                    │                    │                  │
       │ 差异报告生成                             │                  │
       │                    │                    │──→ VAT Return ──→│
       │                    │                    │                  │
```

### 5.2 三方对账算法

```python
# backend/erp/three_way_reconcile.py

async def three_way_reconcile(
    shopify_orders: list[EcommerceOrder],
    paypal_transactions: list[PaymentTransaction],
    erp_invoices: list[HubInvoice],
    period: FiscalPeriod,
) -> ReconciliationReport:
    """
    三方对账：
    1. Shopify 销售 vs ERP 发票（金额匹配）
    2. PayPal 收款 vs Shopify 销售（支付匹配）
    3. 差异分类：手续费差异、汇率差异、时间差异
    """
    report = ReconciliationReport()

    # Step 1: Shopify vs ERP
    shopify_total = sum(o.total_price for o in shopify_orders)
    erp_total = sum(i.gross_amount for i in erp_invoices if i.source == "shopify")
    report.add_comparison("shopify_vs_erp", shopify_total, erp_total)

    # Step 2: PayPal vs Shopify
    paypal_total = sum(t.gross_amount for t in paypal_transactions if t.txn_event_code == "T0001")
    paypal_refunds = sum(t.gross_amount for t in paypal_transactions if t.txn_event_code == "T1107")
    report.add_comparison("paypal_vs_shopify", paypal_total - paypal_refunds, shopify_total)

    # Step 3: Fee reconciliation
    paypal_fees = sum(t.fee_amount for t in paypal_transactions)
    report.add_detail("paypal_fees", paypal_fees)

    return report
```

## 6. 实施优先级

| 优先级 | 功能 | 说明 |
|--------|------|------|
| **P0** | `EcommerceChannel` ABC | 电商平台抽象基类 |
| **P0** | `EcommerceOrder` / `EcommerceRefund` 数据模型 | 平台无关的标准模型 |
| **P0** | Shopify GraphQL Client | 订单查询 + 批量导出 |
| **P1** | Shopify Webhook 接收 | 实时订单/退款事件 |
| **P1** | Shopify → HubInvoice 映射 | 订单标准化转换 |
| **P1** | Webhook 签名验证 | HMAC-SHA256 防伪造 |
| **P2** | 三方对账引擎 | Shopify vs PayPal vs ERP |
| **P2** | Amazon SP-API Adapter | 第二电商平台 |
| **P2** | WooCommerce Adapter | 开源电商平台 |
| **P3** | eBay Adapter | 第三电商平台 |
| **P3** | 订单→多国税务映射 | 非 UK VAT 的 tax mapping |

## 7. 配置示例

```bash
# .env 中新增电商平台配置
SHOPIFY_SHOP_DOMAIN=my-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_xxxxxxxxxxxx
SHOPIFY_API_SECRET=xxxxxxxxxxxx
SHOPIFY_WEBHOOK_SECRET=xxxxxxxxxxxx

AMAZON_SELLING_PARTNER_ID=xxxxxxxx
AMAZON_AWS_ACCESS_KEY=xxxxxxxx
AMAZON_AWS_SECRET_KEY=xxxxxxxx

# 电商平台模式: mock / live
ECOMMERCE_MODE=mock
```

## 8. 参考资源

- Shopify GraphQL Admin API: https://shopify.dev/docs/api/admin-graphql
- Shopify REST Admin API: https://shopify.dev/docs/api/admin-rest
- Shopify Webhooks: https://shopify.dev/docs/apps/webhooks
- Shopify Bulk Operations: https://shopify.dev/docs/api/usage/bulk-operations
- Amazon SP-API: https://developer-docs.amazon.com/sp-api/
- eBay REST APIs: https://developer.ebay.com/docs
- WooCommerce REST API: https://woocommerce.com/document/woocommerce-rest-api/
