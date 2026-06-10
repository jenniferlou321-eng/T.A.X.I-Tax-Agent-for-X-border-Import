# 🔄 Orchestrator 6 阶段管线

> 所有国家共享的税务申报编排流程，定义在 `tax_agent/orchestrator.py`

## 📊 6 阶段总览

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  1. Precheck │ ▶ │  2. Prepare  │ ▶ │ 3. Calculate │
│  字段校验     │   │  认证+格式    │   │  税额计算     │
└──────────────┘   └──────────────┘   └──────────────┘
                                               │
       ┌───────────────────────────────────────┘
       ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ 4. Validate  │ ▶ │  5. Submit   │ ▶ │  6. Track    │
│  一致性检查   │   │  提交至税局   │   │  状态轮询     │
└──────────────┘   └──────────────┘   └──────────────┘
```

---

## 🎯 设计原则

1. **声明式** — 适配器只描述"做什么"，不关心"怎么做"
2. **幂等性** — 同一申报可重复执行，结果一致
3. **可恢复** — 任一阶段失败可重试，无需从头开始
4. **可观测** — 每个阶段都有 audit log 记录
5. **可扩展** — 适配器新增方法不影响 Orchestrator 主体

---

## 阶段 1: Precheck（前置检查）

**目标：** 在做网络请求前发现并修复基本错误

### 输入
- 用户提交的 `LineItem` 列表
- 当前 `JurisdictionAdapter` 的 `DataTemplate`

### 逻辑

```python
async def _stage_precheck(result, filing_id, adapter, tax_type, data):
    template = adapter.get_template(tax_type)
    
    errors = []
    for section in template.sections:
        for field in section.fields:
            # 必填字段
            if field.required:
                if not has_value(field.key, data):
                    errors.append(...)
            
            # 数值范围
            if field.field_type == "number":
                v = field.validation
                if v.min is not None and value < v.min:
                    errors.append(...)
                if v.max is not None and value > v.max:
                    errors.append(...)
    
    if errors:
        return False  # 终止
    return True
```

### 失败处理
- 任一字段错误 → 状态 `ERROR`，终止管线
- 不消耗 API quota
- 用户可立即修复

### 实现
`tax_agent/orchestrator.py::_stage_precheck`

---

## 阶段 2: Prepare（数据准备）

**目标：** 完成 OAuth 认证 + 转换为目标格式

### 2a. 认证（OAuth）

```python
auth_result = await channel.authenticate()
if not auth_result.success:
    fail(stage="PREPARE", code="auth_failed", recoverable=True)
```

**Recoverable=true** 表示用户可重试（重新 OAuth 授权）

### 2b. 格式转换

```python
payload = adapter.to_filing_format(tax_type, data)
payload.idempotency_key = filing_id
```

每个适配器实现自己的 `to_filing_format()`，例如 UK VAT：
- LineItem → HMRC 9-box JSON
- Box 1-5: `float(round(x, 2))`
- Box 6-9: `int(x)`
- `finalised: True`

### 实现
`tax_agent/orchestrator.py::_stage_prepare`

---

## 阶段 3: Calculate（税务计算）

**目标：** 自动计算 Box 3 / Box 5 等派生字段

### 逻辑

```python
calc = adapter.calculate(tax_type, data)
# UK VAT: Box 3 = Box 1 + Box 2, Box 5 = abs(Box 3 - Box 4)
```

### 警告

计算器返回 `warnings: list[str]`，例如：
- "Net VAT due is negative (repayment due from HMRC)"

### 实现
`tax_agent/orchestrator.py::_stage_calculate`

---

## 阶段 4: Validate（业务规则校验）

**目标：** 在提交前捕获业务规则违反

### 逻辑

```python
report = adapter.validate(tax_type, data)
if not report.is_valid:
    for err in report.errors:
        errors.append(FilingError(...))
```

### 严格模式

```python
if config.warn_policy == "strict":
    for w in report.warnings:
        errors.append(FilingError(...))
```

### 常见规则（UK VAT 示例）
- Box 1 > 0 但 Box 6 = 0 → 警告
- Box 4 远超 Box 1（> 3x）→ 警告（可能触发 HMRC 审查）
- Box 5 超过 99,999,999.99 → 错误

### 实现
`tax_agent/orchestrator.py::_stage_validate`

---

## 阶段 5: Submit（提交申报）

**目标：** 调用目标税局 API/UI 实际提交

### 5a. 重试策略

```python
for attempt in range(max_retries):
    try:
        result = await channel.submit(payload)
        if result.success:
            return True
    except:
        if attempt < max_retries:
            await asyncio.sleep(2 ** attempt)  # 指数退避
            continue
        fail(...)
```

**重试的错误码：**
- `RATE_LIMITED`
- `SERVICE_UNAVAILABLE`
- `NETWORK_ERROR`
- `GATEWAY_TIMEOUT`

**不重试的错误码：**
- `DUPLICATE_SUBMISSION`
- `INVALID_PAYLOAD`
- `BUSINESS_ERROR`
- `RESOURCE_FORBIDDEN`

### 5b. Receipt

成功后保存 `Receipt`：
```python
result.receipt = Receipt(
    receipt_id="1234567890",  # 来自 HMRC formBundleNumber
    submitted_at=datetime.now(timezone.utc),
    raw_response=...
)
```

### 实现
`tax_agent/orchestrator.py::_stage_submit`

---

## 阶段 6: Track（状态追踪）

**目标：** 等待 HMRC 最终受理或驳回

### 逻辑

```python
deadline = now + config.track_timeout_hours * 3600
while now < deadline:
    status = await channel.get_status(receipt)
    if is_terminal(status):
        return
    await asyncio.sleep(poll_interval)
```

### 终态判定

```python
class StateMachine:
    @staticmethod
    def is_terminal(status):
        return status in {
            FilingStatus.ACCEPTED,
            FilingStatus.REJECTED,
        }
```

### UK VAT 特例
HMRC MTD VAT Return 是**同步提交**（POST 即返回 201），无需轮询。
但 TaxAgent 仍实现 Track 阶段用于：
- 验证 HMRC 端数据一致性（`GET /returns/{periodKey}`）
- 发送通知邮件
- 触发后续业务逻辑

### 实现
`tax_agent/orchestrator.py::_stage_track`

---

## 📊 状态机

```
                    PENDING
                       │
                       ▼ start
                 IN_PROGRESS
                  /    │    \
                 /     │     \
                ▼      ▼      ▼
        PRECHECK  PREPARE  CALCULATE
        failed    failed   failed
                │       │
                └───────┴──▶ ERROR
                            │
                            ▼ (operator retry)
                       IN_PROGRESS
                            │
                            ▼
                         SUBMIT
                          │
                          ▼
                       ACCEPTED ← ─┐
                          │        │ (poll until)
                       REJECTED ← ─┘
```

### 终态 vs 临时状态

| 状态 | 类型 | 含义 |
|------|------|------|
| `pending` | 临时 | 已创建 |
| `in_progress` | 临时 | 管线运行中 |
| `submitted` | 临时 | 已提交 |
| `accepted` | **终态** | HMRC 受理 |
| `rejected` | **终态** | HMRC 驳回 |
| `error` | **终态** | 内部错误 |

---

## 🔧 配置项

**位置：** `tax_agent/config.py`

```python
class FilingConfig:
    max_retries: int = 3                    # SUBMIT 重试次数
    track_timeout_hours: int = 168          # TRACK 超时（7天）
    track_poll_interval_seconds: int = 60   # 轮询间隔
    warn_policy: str = "lenient"            # "lenient" or "strict"
```

---

## 🛡️ Audit Log（审计日志）

每个阶段都记录到 `AuditLog`：

```python
self.audit.record(filing_id, stage, action, detail)
```

**结构：**
```python
@dataclass
class AuditEntry:
    filing_id: str
    stage: str           # "PRECHECK" / "PREPARE" / ...
    action: str          # "passed" / "failed" / "submitted" / ...
    detail: dict         # 上下文信息
    timestamp: datetime
```

**持久化：**
- 默认：内存（重启后丢失）
- 计划：写入 `data/audit/{filing_id}.json`

---

## 🧪 测试

### 单元测试

每个阶段独立测试：

```python
# tests/test_orchestrator.py

def test_precheck_required_field_missing():
    # Arrange
    data = TaxData(...)  # 缺少必填字段
    adapter = MockAdapter()
    
    # Act
    result = await orchestrator.run(adapter, TaxType.VAT, data)
    
    # Assert
    assert result.status == FilingStatus.ERROR
    assert any(e.code == "MISSING_REQUIRED_FIELD" for e in result.errors)
```

### 集成测试

模拟完整管线：

```python
def test_full_pipeline_success():
    # Mock 整个 HMRC API
    with mock_hmrc_api():
        data = TaxData(...)
        result = await orchestrator.run(adapter, TaxType.VAT, data)
        
        assert result.status == FilingStatus.ACCEPTED
        assert result.receipt is not None
```

### E2E 测试

对真实 HMRC 沙盒运行（手动 / 定时任务）：
- 创建一个测试 Test User
- 完整 OAuth 流程
- 提交 VAT Return
- 验证 HMRC 端数据

详见 [HMRC 沙盒测试指南](../jurisdictions/uk/sandbox-testing.md)

---

## 🔗 相关文档

- [系统架构总览](./overview.md)
- [UK VAT 报税流程](../jurisdictions/uk/vat-workflow.md)
- [扩展新国家指南](./adding-new-jurisdiction.md)
