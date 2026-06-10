# 🏗️ 系统架构总览

> TaxAgent Global 是一个面向中国跨境企业的多国智能税务申报 SaaS 平台

## 🎯 核心理念

**为跨境中国企业提供"一站式"税务合规服务：**
- 覆盖主要贸易国家（英国、欧盟、中国）
- 适配各国不同的税务法规
- 提供统一的产品体验
- 保证数据安全和合规性

## 🏛️ 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (React + TypeScript)               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Dashboard│  │Filing    │  │  Settings │  │  Login   │   │
│  └────┬─────┘  └────┬─────┘  └─────┬────┘  └────┬─────┘   │
│       │             │              │             │         │
│       └─────────────┴──────┬───────┴─────────────┘         │
│                            │                               │
│                     TanStack Query (HTTP)                  │
└────────────────────────────┼────────────────────────────────┘
                             │ HTTPS
┌────────────────────────────┼────────────────────────────────┐
│                     后端 (FastAPI)                            │
│  ┌───────────────────────▼──────────────────────────────┐  │
│  │                API Routers                           │  │
│  │  /api/jurisdictions  /api/filings  /api/channel     │  │
│  └────┬─────────────┬────────────┬──────────────────────┘  │
│       │             │            │                          │
│  ┌────▼────┐  ┌─────▼─────┐ ┌───▼────────┐                 │
│  │Registry │  │Orchestrator│ │OAuth Mgr   │                 │
│  └────┬────┘  └─────┬─────┘ └───┬────────┘                 │
│       │             │            │                          │
│  ┌────▼─────────────▼───────┐    │                          │
│  │  Jurisdiction Adapters  │    │                          │
│  │  ┌──────┐ ┌──────┐      │    │                          │
│  │  │  UK  │ │  DE  │  ... │    │                          │
│  │  └──┬───┘ └──┬───┘      │    │                          │
│  └─────┼────────┼──────────┘    │                          │
│        │        │               │                          │
│  ┌─────▼────────▼───────────────▼──────────┐               │
│  │         Channel Implementations          │               │
│  │  ┌──────────────┐  ┌────────────────┐   │               │
│  │  │ API Channel  │  │ Browser Channel │   │               │
│  │  └──────┬───────┘  └────────┬───────┘   │               │
│  └─────────┼──────────────────┼────────────┘               │
│            │                  │                            │
│  ┌─────────▼──────────────────▼────────────┐               │
│  │   Tax Authority APIs / Browsers         │               │
│  │   • HMRC (UK)                            │               │
│  │   • BZSt (DE) - 规划                    │               │
│  │   • DGFiP (FR) - 规划                   │               │
│  │   • SAT (CN) - 规划                     │               │
│  └──────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

## 📦 技术栈

### 前端
- **React 18** + **TypeScript** - 主流前端框架
- **Vite** - 构建工具
- **Tailwind CSS v4** - 样式系统（支持 dark/light theme）
- **TanStack Query** - 数据获取和缓存
- **React Router** - 路由
- **Heroicons** - 图标库
- **Zustand** - 轻量状态管理

### 后端
- **Python 3.10+** - 主语言
- **FastAPI** - Web 框架
- **Pydantic** - 数据验证
- **httpx** - 异步 HTTP 客户端
- **uvicorn** - ASGI 服务器
- **Playwright** - 浏览器自动化（中国/法国申报用）

### 集成
- **OAuth 2.0** - HMRC 认证
- **REST API** - 各国税局 API
- **Playwright** - 浏览器自动化（电子税务局等）

### 工具
- **uvicorn** - 后端服务
- **vite** - 前端开发
- **pytest** - 单元测试
- **Git** - 版本控制

---

## 🧩 核心组件

### 1. Jurisdiction Adapter（管辖地适配器）

**位置：** `tax_agent/jurisdictions/{country}/`

**作用：** 每个国家实现一个 `JurisdictionAdapter`，提供统一接口：

```python
class JurisdictionAdapter(ABC):
    country_code: str           # "uk", "de", "fr", "cn"
    country_name: str           # "United Kingdom"
    tax_types: list[TaxType]    # 支持的税种
    supported_channels: list    # API / Browser

    @abstractmethod
    def get_template(self, tax_type) -> DataTemplate: ...

    @abstractmethod
    def calculate(self, tax_type, data) -> CalculationResult: ...

    @abstractmethod
    def validate(self, tax_type, data) -> ValidationReport: ...

    @abstractmethod
    def get_channel(self, tax_type) -> FilingChannel: ...

    @abstractmethod
    def to_filing_format(self, tax_type, data) -> FilingPayload: ...
```

**实现：**
- 🇬🇧 `UKJurisdictionAdapter` ✅
- 🇩🇪 `DEJurisdictionAdapter` - 规划
- 🇫🇷 `FRJurisdictionAdapter` - 规划
- 🇨🇳 `CNJurisdictionAdapter` - 规划

### 2. Orchestrator（编排器）

**位置：** `tax_agent/orchestrator.py`

**作用：** 6 阶段管线，所有国家共享：

```python
class Orchestrator:
    async def run(adapter, tax_type, data) -> FilingResult:
        # 1. PRECHECK  - 字段校验
        # 2. PREPARE   - 认证 + 格式转换
        # 3. CALCULATE - 税务计算
        # 4. VALIDATE  - 一致性检查
        # 5. SUBMIT    - 提交申报
        # 6. TRACK     - 状态追踪
```

详细见 [pipeline.md](./pipeline.md)

### 3. Channel Implementations（渠道实现）

**位置：** `tax_agent/channels/`

#### API Channel
- 直接调用各国税局 REST API
- 适用于：英国 HMRC、计划中的德国 BZSt
- `tax_agent/channels/api_channel.py`

#### Browser Channel（规划）
- 浏览器自动化（Playwright）
- 适用于：中国电子税务局、法国 impots.gouv.fr
- `tax_agent/channels/browser_channel.py`

### 4. Data Models（数据模型）

**位置：** `tax_agent/models/`

| 模型 | 用途 |
|------|------|
| `TaxType` | 税种枚举（VAT, SA, CIT, IIT）|
| `PeriodType` | 申报周期（月/季/年）|
| `FiscalPeriod` | 财年 + 期间信息 |
| `TaxpayerInfo` | 纳税人信息（名称、税号、地址）|
| `LineItem` | 单行数据（金额、币种、类别）|
| `TaxData` | 完整申报数据 |
| `DataTemplate` | 字段模板（动态定义）|

---

## 🔄 数据流

### 一次完整申报的旅程

```
1. 用户登录系统
   │
2. 前端选择管辖地 + 税种
   │
3. 后端返回字段模板 (DataTemplate)
   │
4. 前端展示动态表单供用户填写
   │
5. 用户提交数据
   │
6. POST /api/filings/preview
   │
7. Orchestrator 触发 6 阶段管线
   ├─ 1. PRECHECK 验证字段
   ├─ 2. PREPARE  OAuth 认证 + 格式转换
   ├─ 3. CALCULATE 自动计算税额
   ├─ 4. VALIDATE  业务规则检查
   └─ 5. 返回预览结果（不提交）
   │
8. 前端显示预览和声明文本
   │
9. 用户确认无误
   │
10. POST /api/filings/submit
    │
11. Orchestrator 继续 6 阶段管线
    ├─ 1-4. 重复
    └─ 5. SUBMIT 实际提交到税局
    │
12. Channel (API/Browser) 提交数据
    │
13. HMRC 返回 receipt
    │
14. 前端跳转到详情页
    │
15. 定期轮询 / Track 阶段
```

---

## 🔌 扩展性

### 添加新国家

参考 [adding-new-jurisdiction.md](./adding-new-jurisdiction.md)

主要步骤：
1. 创建 `tax_agent/jurisdictions/{code}/` 目录
2. 实现 `JurisdictionAdapter` 接口
3. 注册到 `JurisdictionRegistry`
4. 添加前端的 LANG 翻译
5. 编写单元测试和集成测试

### 添加新税种

对于现有国家：
1. 在 `models/tax_data.py` 添加 `TaxType` 枚举
2. 在 `jurisdictions/{country}/` 创建子目录
3. 实现 `template`, `calculator`, `validator`
4. 添加对应的 Channel

---

## 🔒 安全

- ✅ OAuth 2.0 token 持久化到服务端文件系统（不在前端）
- ✅ Client Secret 仅服务端持有
- ✅ 欺诈预防头（Fraud Prevention Headers）符合 HMRC 要求
- ⚠️ 未来：TLS 1.3+、API rate limiting、审计日志
- ⚠️ 未来：密钥管理（AWS KMS / HashiCorp Vault）

---

## 📊 项目指标

| 指标 | 当前值 |
|------|--------|
| 支持国家 | 1/4 (UK ✅, DE/FR/CN 📋) |
| 支持税种 | 1 (UK VAT) |
| API 集成 | 1 (HMRC) |
| 代码行数 | ~3000 Python + ~3000 TypeScript |
| 测试覆盖 | <30% (待提高) |
| 文档完整度 | 80% (UK 完整, 其他规划) |

---

## 🔗 相关文档

- [Orchestrator 6 阶段管线](./pipeline.md)
- [扩展新国家指南](./adding-new-jurisdiction.md)
- [UK VAT 报税流程](../jurisdictions/uk/vat-workflow.md)
