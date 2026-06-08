# 🌍 扩展新国家指南

> 如何在 TaxAgent Global 中添加新的国家/税种支持

## 📋 概览

添加新国家/税种涉及 **6 个层面**：

1. 后端数据模型
2. 适配器实现
3. 注册到 Registry
4. 申报模板
5. 前端 UI
6. 测试

预计工作量：
- **简单国家**（有完整 API，如英国）：~2 周
- **中等国家**（部分 API + 浏览器自动化）：~6 周
- **复杂国家**（纯浏览器 + 复杂表单）：~10 周

---

## 🎯 Step 1: 评估 API 可用性

### 决策树

```
该国税务局是否提供 REST API？
├── 是 → 使用 API Channel
│   ├── 文档完整？ → 直接对接
│   └── 文档不完整？ → 反编译 + 流量分析
├── 否 → 该国是否有官方浏览器申报？
│   ├── 是 → 使用 Browser Channel (Playwright)
│   └── 否 → 需第三方 / EDI 软件
```

| 国家 | API 状态 | 实施方式 |
|------|---------|---------|
| 🇬🇧 UK | ✅ 完整 | API Channel |
| 🇩🇪 DE | ⚠️ 限制 | 浏览器 + EDI 混合 |
| 🇫🇷 FR | ❌ 无 | 浏览器 (Playwright) |
| 🇨🇳 CN | ❌ 无 | 浏览器 (Playwright) |

---

## 🛠️ Step 2: 创建目录结构

```bash
mkdir -p tax_agent/jurisdictions/{code}/{tax_type}
```

例如添加德国：
```bash
mkdir -p tax_agent/jurisdictions/de/vat
```

最终结构：
```
tax_agent/jurisdictions/de/
├── __init__.py             # DEJurisdictionAdapter
├── config.py                # German config
└── vat/
    ├── __init__.py         # DEVATAdapter
    ├── template.py          # UStVA template
    ├── calculator.py        # Calculator
    ├── validator.py         # Validator
    └── channel.py           # DE-specific channel
```

---

## 📝 Step 3: 数据模型

### 3a. 添加 TaxType（如果需要）

**位置：** `tax_agent/models/tax_data.py`

```python
class TaxType(Enum):
    VAT = "vat"
    SELF_ASSESSMENT = "self_assessment"
    CORPORATION_TAX = "corporation_tax"
    # 新增（如果需要）
    BUSINESS_TAX = "business_tax"
```

### 3b. 添加 ChannelType（如果需要）

```python
class ChannelType(Enum):
    API = "api"
    BROWSER = "browser"
```

---

## ⚙️ Step 4: 配置文件

**位置：** `tax_agent/jurisdictions/{code}/config.py`

参考 `uk/config.py`：

```python
"""{Country} {Authority} 配置"""

import os
from dataclasses import dataclass
from tax_agent.channels.oauth import OAuth2Config


@dataclass
class {Country}Config:
    sandbox: bool = os.environ.get("{COUNTRY}_SANDBOX", "true").lower() == "true"

    @property
    def base_url(self) -> str:
        if self.sandbox:
            return "https://test-api.{authority}.{tld}"
        return "https://api.{authority}.{tld}"

    @property
    def oauth(self) -> OAuth2Config:
        return OAuth2Config(
            authorize_url=f"{self.base_url}/oauth/authorize",
            token_url=f"{self.base_url}/oauth/token",
            client_id=os.environ.get("{COUNTRY}_CLIENT_ID", ""),
            client_secret=os.environ.get("{COUNTRY}_CLIENT_SECRET", ""),
            redirect_uri=os.environ.get("{COUNTRY}_REDIRECT_URI", "..."),
            scopes=[...],
        )

    # 端点
    VAT_SUBMIT_ENDPOINT = "..."


{code}_config = {Country}Config()
```

`.env` 添加：
```bash
{COUNTRY}_CLIENT_ID=...
{COUNTRY}_CLIENT_SECRET=...
{COUNTRY}_SANDBOX=true
```

---

## 🔌 Step 5: Adapter 实现

**位置：** `tax_agent/jurisdictions/{code}/{tax_type}/__init__.py`

```python
from tax_agent.jurisdictions import JurisdictionAdapter
from tax_agent.models.tax_data import TaxType, TaxData
from .template import {TAX}_TEMPLATE
from .calculator import calculate_{tax}
from .validator import validate_{tax}


class {Country}{Tax}Adapter:
    tax_type = TaxType.{TAX}

    def __init__(self):
        self._channel = APIChannel(
            base_url={code}_config.base_url,
            oauth_config={code}_config.oauth,
            submit_endpoint={code}_config.{TAX}_SUBMIT_ENDPOINT,
        )

    def get_template(self, tax_type: TaxType) -> DataTemplate:
        return {TAX}_TEMPLATE

    def calculate(self, tax_type: TaxType, data: TaxData) -> CalculationResult:
        return calculate_{tax}(data)

    def validate(self, tax_type: TaxType, data: TaxData) -> ValidationReport:
        return validate_{tax}(data)

    def get_channel(self, tax_type: TaxType) -> FilingChannel:
        return self._channel

    def to_filing_format(self, tax_type: TaxType, data: TaxData) -> FilingPayload:
        """转换为 {Country} 税局要求的 JSON 格式"""
        # 实现数据格式转换
        ...
```

---

## 📋 Step 6: 数据模板

**位置：** `tax_agent/jurisdictions/{code}/{tax_type}/template.py`

```python
from datetime import date
from tax_agent.models.template import (
    DataTemplate, TemplateSection, TemplateField,
    FieldType, FieldValidation,
)
from tax_agent.models.tax_data import TaxType


{TYPE}_TEMPLATE = DataTemplate(
    tax_type=TaxType.{TYPE},
    jurisdiction="{code}",
    version="1.0",
    valid_from=date(YYYY, M, D),
    sections=[
        TemplateSection(
            title="...",
            description="...",
            fields=[
                TemplateField(
                    key="field_key",
                    label="显示名称",
                    field_type=FieldType.NUMBER,
                    required=True,
                    hint="提示信息",
                    validation=FieldValidation(min=0, decimal_places=2),
                ),
                # ...更多字段
            ],
        ),
        # ...更多 sections
    ],
)
```

---

## 🧮 Step 7: 计算器

**位置：** `tax_agent/jurisdictions/{code}/{tax_type}/calculator.py`

```python
from decimal import Decimal
from tax_agent.models.tax_data import TaxData
from tax_agent.models.results import CalculationResult, BreakdownItem


def calculate_{tax}(data: TaxData) -> CalculationResult:
    """{Country} 税种计算
    
    关键公式:
    - Box A = ... (示例)
    - Box B = Box A × rate (示例)
    """
    line_map = {li.category: li.amount for li in data.line_items}
    
    # 实现计算逻辑
    field_a = line_map.get("field_a", Decimal("0"))
    field_b = field_a * Decimal("0.20")  # 20% 税率
    total = field_b
    
    return CalculationResult(
        total_tax_due=total,
        breakdown=[
            BreakdownItem(category="field_a", amount=field_a),
            BreakdownItem(category="field_b", amount=field_b),
            BreakdownItem(category="total", amount=total),
        ],
        warnings=[],
    )
```

---

## ✅ Step 8: 校验器

**位置：** `tax_agent/jurisdictions/{code}/{tax_type}/validator.py`

```python
from tax_agent.models.tax_data import TaxData
from tax_agent.models.results import ValidationReport, ValidationError


def validate_{tax}(data: TaxData) -> ValidationReport:
    errors = []
    warnings = []
    
    line_map = {li.category: li.amount for li in data.line_items}
    
    # 必填字段检查
    required = ["field_a", "field_b"]
    for key in required:
        if key not in line_map:
            errors.append(ValidationError(
                field=key,
                message=f"Required field missing: {key}",
                severity="error",
            ))
    
    # 业务规则
    if line_map.get("field_a", 0) > 0 and line_map.get("field_b", 0) == 0:
        warnings.append(ValidationError(
            field="field_b",
            message="...",
            severity="warning",
        ))
    
    return ValidationReport(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
```

---

## 📡 Step 9: 注册到 Registry

**位置：** `tax_agent/server/main.py`

```python
from tax_agent.jurisdictions.{code} import {Country}JurisdictionAdapter

registry = JurisdictionRegistry()
registry.register(UKJurisdictionAdapter())
registry.register({Country}JurisdictionAdapter())  # 新增
```

---

## 🌐 Step 10: 前端 UI

### 10a. 翻译文件

**位置：** `tax_agent/frontend/src/i18n/{lang}.json`

```json
{
  "jurisdictions": {
    "uk": "英国",
    "de": "德国",
    "fr": "法国",
    "cn": "中国"
  }
}
```

### 10b. 国家选择器

**位置：** `tax_agent/frontend/src/pages/NewFilingPage.tsx`

```tsx
<select>
  <option value="uk">🇬🇧 英国 (United Kingdom)</option>
  <option value="de">🇩🇪 德国 (Deutschland)</option>
  <option value="fr">🇫🇷 法国 (France)</option>
  <option value="cn">🇨🇳 中国 (China)</option>
</select>
```

### 10c. 国家特定 UI

如果申报表单差异大，创建 `NewFiling{CC}Page.tsx`。

---

## 🧪 Step 11: 测试

### 11a. 单元测试

**位置：** `tests/jurisdictions/{code}/`

```python
# tests/jurisdictions/de/test_vat_calculator.py
import pytest
from decimal import Decimal
from tax_agent.jurisdictions.de.vat.calculator import calculate_de_vat
from tax_agent.models.tax_data import TaxData, FiscalPeriod, TaxpayerInfo, LineItem


def test_calculate_vat_standard_rate():
    data = TaxData(
        tax_type=TaxType.VAT,
        period=FiscalPeriod(...),
        taxpayer=TaxpayerInfo(...),
        line_items=[
            LineItem(category="sales_19", amount=Decimal("1000"), currency="EUR"),
            LineItem(category="input_vat", amount=Decimal("100"), currency="EUR"),
        ],
    )
    result = calculate_de_vat(data)
    assert result.total_tax_due == Decimal("90")  # 1000*19% - 100 = 90
```

### 11b. 集成测试

测试端到端流程：

```python
# tests/integration/de/test_filing.py
async def test_full_vat_filing_de():
    # Mock 德国 BZSt API
    with mock_bzst_api():
        data = TaxData(...)
        orchestrator = Orchestrator()
        result = await orchestrator.run(de_adapter, TaxType.VAT, data)
        assert result.status == FilingStatus.ACCEPTED
```

### 11c. 沙盒 E2E（如果有沙盒）

类似 UK 沙盒测试流程。

---

## 📋 Step 12: 文档

参考 [UK 文档结构](../jurisdictions/uk/README.md)：

```
docs/jurisdictions/{code}/
├── README.md              # 国家概览
├── {tax}-workflow.md     # 报税流程
├── {tax}-rules.md        # 报税规则与计算
├── oauth.md              # 认证流程
└── sandbox-testing.md    # 沙盒测试指南
```

---

## ✅ 完成检查清单

- [ ] 数据模型（TaxType / ChannelType）
- [ ] 配置文件（config.py）
- [ ] Adapter 实现
- [ ] 模板（template.py）
- [ ] 计算器（calculator.py）
- [ ] 校验器（validator.py）
- [ ] Channel（如果需要自定义）
- [ ] 注册到 Registry
- [ ] 前端 UI（国家选择、表单）
- [ ] i18n 翻译
- [ ] 单元测试
- [ ] 集成测试
- [ ] E2E 测试（如果有沙盒）
- [ ] 文档（README + workflow + rules）

---

## 📚 实际案例

参考 [UK 实施案例](../jurisdictions/uk/README.md)：
- HMRC 有完整 API → API Channel
- 9-box 模板设计
- OAuth 2.0 完整流程
- 沙盒测试 + 真实验证

---

## 🔗 相关文档

- [系统架构总览](./overview.md)
- [Orchestrator 6 阶段管线](./pipeline.md)
- [UK 实施案例](../jurisdictions/uk/README.md)
