# GovTalk XML 协议介绍 (HMRC)

## 一、什么是 GovTalk？

GovTalk 是 HMRC（及部分其他英国政府部门）使用的 **1990 年代遗留的 XML 消息协议**。它不是 REST API,也不是简单的 XML POST — 它是一种有状态、异步的消息框架。

**关键事实**:
- 所有 Corp Tax、PAYE/RTI、SDLT 都走 GovTalk
- 这三个税种 **共用同一个网关 endpoint**,通过 envelope 里的 `<Class>` 字段区分
- 需要先在 HMRC 注册为软件开发商获取 **Vendor ID** 才能访问沙箱
- 当前仍在维护,未被 MTD REST API 取代

---

## 二、核心概念

### 2.1 Transaction Engine

```
提交: POST /submission  → 即时响应 (含 Poll URL)
轮询: POST /poll        → 异步响应 (Pending / Accepted / Rejected)
```

HMRC 的 **Transaction Engine (TE)** 是 GovTalk 的网关:
- 接收 XML envelope
- 验证 GovTalk 格式 (对 GovTalk schema 校验)
- 验证提交者凭据
- 路由到后端处理
- 返回 Poll URL 供异步查询

**端点 URL**:

| 环境 | 提交 URL | Poll URL |
|------|---------|----------|
| **开发测试 (ETS)** | `https://test-transaction-engine.tax.service.gov.uk/submission` | `https://test-transaction-engine.tax.service.gov.uk/poll` |
| **生产** | `https://transaction-engine.tax.service.gov.uk/submission` | `https://transaction-engine.tax.service.gov.uk/poll` |
| **TPVS (仅 body 校验)** | 详见各 technical pack | N/A |

### 2.2 GovTalkMessage Envelope

每条消息都是一个 `<GovTalkMessage>` XML 文档,包含 3 个部分:

```
GovTalkMessage
 ├── EnvelopeVersion    (固定 "1.0")
 ├── Header
 │    ├── MessageDetails
 │    │    ├── Class          (如 "HMRC-CT-CT600")
 │    │    ├── Qualifier      ("request" / "response")
 │    │    ├── CorrelationID  (提交方生成的 UUID)
 │    │    ├── SubmitTime     (ISO 时间戳)
 │    │    └── GatewayTest    ("1" = 测试, "0" = 生产)
 │    └── SenderDetails
 │         └── IDAuthentication
 │              ├── SenderID  (Vendor ID 或 UserName)
 │              └── Authentication
 │                   ├── Method   ("clear" / "OAuth2")
 │                   └── Value    (Password 或 Token)
 ├── Body
 │    └── IRenvelope         (各税种特有的业务 XML)
 │         └── ...            (具体的 schema 定义的内容)
 └── (IRmark — 可选,位置在 Body 外)
```

### 2.3 Message Class (Class 字段)

每个税种对应一个唯一的 Class 标识符:

| 税种 | Class | TIL 后缀 |
|------|-------|---------|
| **Corporation Tax (CT600)** | `HMRC-CT-CT600` | `HMRC-CT-CT600-TIL` |
| **PAYE RTI FPS** | `HMRC-PAYE-RTI-FPS` | `HMRC-PAYE-RTI-FPS-TIL` |
| **PAYE RTI EPS** | `HMRC-PAYE-RTI-EPS` | `HMRC-PAYE-RTI-EPS-TIL` |
| **PAYE RTI EYU** | `HMRC-PAYE-RTI-EYU` | `HMRC-PAYE-RTI-EYU-TIL` |
| **Stamp Duty SDLT** | `HMRC-SDLT-RETURN` | `HMRC-SDLT-RETURN-TIL` |

> **TIL (Test in Live)**: 在 Class 后加 `-TIL` 后缀,可以发送测试消息到生产环境,验证用户凭据但不会实际提交到后台系统。

### 2.4 认证方式

**重要**: GovTalk XML API 的认证**不同于** REST MTD API 的 OAuth 2.0。

| 环境 | 认证方式 |
|------|---------|
| **开发测试 (ETS/TPVS)** | Vendor ID + Password (从 SDST 获得) |
| **生产** | 终端用户的 Government Gateway UserName + Password |

在 `<SenderDetails>` 中:
```xml
<SenderDetails>
  <IDAuthentication>
    <SenderID>MY_VENDOR_ID</SenderID>
    <Authentication>
      <Method>clear</Method>
      <Value>my_password</Value>
    </Authentication>
  </IDAuthentication>
</SenderDetails>
```

> **注意**: OAuth 2.0 仅用于 REST API (VAT、SA)。GovTalk XML API 使用传统的 UserName/Password 认证。

### 2.5 GatewayTest 元素

| 值 | 含义 |
|----|------|
| `1` (或省略) | 测试模式 — 发送到开发/测试环境 |
| `0` | 生产模式 — 发送真实数据 |

### 2.6 IRmark (完整性校验)

IRmark 是 **CRC32 散列**(非 MD5/SHA),对 Body 部分的 XML 内容计算校验和。HMRC 在收到消息后重新计算,比对一致才接受。

**计算步骤**:
1. 提取 `<Body>` 内的 XML 内容 (不含 `<Body>` 标签本身)
2. 对该内容计算 CRC32
3. 结果作为 `<IRmark>` 元素放入 envelope

### 2.7 提交 → 轮询 → 接受 (异步流程)

```
发起方                            Transaction Engine
  │                                      │
  ├── POST /submission ──────────────►   │
  │    (GovTalkMessage, Class=...)        │
  │                                      │
  │◄── 即时响应 ──────────────────────    │
  │    (Poll URL, Receipt ID)             │
  │                                      │
  │    (30s ~ 30min 等待后端处理)          │
  │                                      │
  ├── POST /poll ─────────────────────►   │
  │    (Poll Request, CorrelationID)      │
  │                                      │
  │◄── Pending ────────────────────────   │
  │    (继续等待)                          │
  │                                      │
  ├── POST /poll ─────────────────────►   │
  │                                      │
  │◄── Accepted / Rejected ────────────   │
  │    (完成,含数字签名回执)                │
```

**轮询间隔**: 建议从 1s 开始,指数退避到 30s,超时 30min。

---

## 三、完整示例

### 3.1 CT600 完整 GovTalkMessage

```xml
<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
  <EnvelopeVersion>1.0</EnvelopeVersion>
  <Header>
    <MessageDetails>
      <Class>HMRC-CT-CT600</Class>
      <Qualifier>request</Qualifier>
      <CorrelationID>a1b2c3d4-e5f6-7890-abcd-ef1234567890</CorrelationID>
      <SubmitTime>2026-06-14T10:00:00Z</SubmitTime>
      <GatewayTest>1</GatewayTest>
    </MessageDetails>
    <SenderDetails>
      <IDAuthentication>
        <SenderID>MY_VENDOR_ID</SenderID>
        <Authentication>
          <Method>clear</Method>
          <Value>my_password</Value>
        </Authentication>
      </IDAuthentication>
    </SenderDetails>
  </Header>
  <Body>
    <IRenvelope xmlns="http://www.govtalk.gov.uk/taxation/CT/5.0">
      <CT600>
        <CTREF>1234567890</CTREF>
        <CompanyName>Acme Ltd</CompanyName>
        <PeriodStart>2024-04-01</PeriodStart>
        <PeriodEnd>2025-03-31</PeriodEnd>
        <!-- ... CT600 各 box 值 ... -->
        <Turnover>1000000</Turnover>
        <ProfitChargeable>250000</ProfitChargeable>
        <TaxDue>47500</TaxDue>
      </CT600>
    </IRenvelope>
  </Body>
  <IRmark>ABCD1234</IRmark>  <!-- CRC32 校验 -->
</GovTalkMessage>
```

### 3.2 提交响应 (含 Poll URL)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
  <Header>
    <MessageDetails>
      <Class>HMRC-CT-CT600</Class>
      <Qualifier>response</Qualifier>
      <CorrelationID>a1b2c3d4-e5f6-7890-abcd-ef1234567890</CorrelationID>
    </MessageDetails>
  </Header>
  <Body>
    <SubmitResponse>
      <ReceiptID>REC-12345</ReceiptID>
      <PollURL>https://test-transaction-engine.tax.service.gov.uk/poll</PollURL>
      <Message>Your submission has been received and is being processed</Message>
    </SubmitResponse>
  </Body>
</GovTalkMessage>
```

### 3.3 Poll 请求

```xml
<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
  <EnvelopeVersion>1.0</EnvelopeVersion>
  <Header>
    <MessageDetails>
      <Class>HMRC-CT-CT600</Class>
      <Qualifier>poll</Qualifier>
      <CorrelationID>a1b2c3d4-e5f6-7890-abcd-ef1234567890</CorrelationID>
    </MessageDetails>
  </Header>
</GovTalkMessage>
```

### 3.4 Poll 响应 (Accepted)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
  <Header>
    <MessageDetails>
      <Class>HMRC-CT-CT600</Class>
      <Qualifier>acknowledgement</Qualifier>
      <CorrelationID>a1b2c3d4-e5f6-7890-abcd-ef1234567890</CorrelationID>
    </MessageDetails>
  </Header>
  <Body>
    <PollResponse>
      <Result>Accepted</Result>
      <Message>Your CT600 has been successfully submitted</Message>
      <Receipt>
        <ReceiptID>REC-12345</ReceiptID>
        <Signature>
          <!-- HMRC 的数字签名,用于法律证明 -->
        </Signature>
        <ServiceSpecificMessage>
          <FormBundleNumber>FB-987654</FormBundleNumber>
          <ProcessingDate>2026-06-14T10:05:00Z</ProcessingDate>
        </ServiceSpecificMessage>
      </Receipt>
    </PollResponse>
  </Body>
</GovTalkMessage>
```

---

## 四、代码骨架

### 4.1 通用 GovTalkClient

```python
# backend/channels/govtalk/client.py
"""GovTalk XML Client — HMRC Transaction Engine 网关客户端"""

import uuid
import zlib
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import httpx


class GovTalkError(Exception):
    """GovTalk 错误基类"""
    pass

class TransientError(GovTalkError):
    """临时错误 (可重试)"""
    pass

class PermanentError(GovTalkError):
    """永久错误 (不可重试)"""
    pass


class GovTalkClient:
    """GovTalk 消息客户端 — 通用,可供 CT/PAYE/SDLT 共用"""

    # Namespaces
    NS = {
        "gov": "http://www.govtalk.gov.uk/CM/envelope",
    }

    def __init__(
        self,
        vendor_id: str,
        vendor_password: str,
        base_url: str = "https://test-transaction-engine.tax.service.gov.uk",
        gateway_test: bool = True,
    ):
        self.vendor_id = vendor_id
        self.vendor_password = vendor_password
        self.submit_url = f"{base_url}/submission"
        self.poll_url = f"{base_url}/poll"
        self.gateway_test = "1" if gateway_test else "0"
        self._client = httpx.AsyncClient(timeout=60)

    def _build_envelope(
        self,
        class_name: str,
        body_xml: str,
        qualifier: str = "request",
        correlation_id: str | None = None,
    ) -> str:
        """构建完整的 GovTalkMessage XML envelope"""
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        # 计算 IRmark (Body 部分的 CRC32)
        irmark = format(zlib.crc32(body_xml.encode("utf-8")) & 0xFFFFFFFF, "08X")

        # 用 f-string 构建 XML (简单场景,复杂场景用 lxml)
        envelope = f"""<?xml version="1.0" encoding="UTF-8"?>
<GovTalkMessage xmlns="http://www.govtalk.gov.uk/CM/envelope">
  <EnvelopeVersion>1.0</EnvelopeVersion>
  <Header>
    <MessageDetails>
      <Class>{class_name}</Class>
      <Qualifier>{qualifier}</Qualifier>
      <CorrelationID>{correlation_id}</CorrelationID>
      <SubmitTime>{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}</SubmitTime>
      <GatewayTest>{self.gateway_test}</GatewayTest>
    </MessageDetails>
    <SenderDetails>
      <IDAuthentication>
        <SenderID>{self.vendor_id}</SenderID>
        <Authentication>
          <Method>clear</Method>
          <Value>{self.vendor_password}</Value>
        </Authentication>
      </IDAuthentication>
    </SenderDetails>
  </Header>
  <Body>
    {body_xml}
  </Body>
  <IRmark>{irmark}</IRmark>
</GovTalkMessage>"""
        return envelope

    async def submit(self, class_name: str, body_xml: str) -> dict:
        """提交 GovTalk 消息到 Transaction Engine

        Args:
            class_name: 消息类,如 "HMRC-CT-CT600"
            body_xml: 业务 XML (IRenvelope 内部的内容)

        Returns:
            {"receipt_id": str, "poll_url": str, "correlation_id": str}
        """
        envelope = self._build_envelope(class_name, body_xml)
        resp = await self._client.post(
            self.submit_url,
            content=envelope,
            headers={"Content-Type": "application/xml"},
        )
        resp.raise_for_status()

        # 解析响应,提取 Poll URL
        root = ET.fromstring(resp.text)
        ns = self.NS

        poll_url_el = root.find(".//gov:PollURL", ns)
        receipt_id_el = root.find(".//gov:ReceiptID", ns)

        if poll_url_el is None or receipt_id_el is None:
            # 检查是否有错误
            errors = root.findall(".//gov:Errors/gov:Error", ns)
            if errors:
                raise PermanentError(
                    "; ".join(e.text or "" for e in errors)
                )
            raise GovTalkError("Unexpected GovTalk response format")

        return {
            "receipt_id": receipt_id_el.text or "",
            "poll_url": poll_url_el.text or self.poll_url,
            "correlation_id": "",  # 从响应解析 (简化)
        }

    async def poll(self, class_name: str, correlation_id: str) -> str:
        """轮询提交结果

        Returns:
            "Pending" | "Accepted" | "Rejected"
        """
        poll_request = self._build_envelope(
            class_name=class_name,
            body_xml="",
            qualifier="poll",
            correlation_id=correlation_id,
        )
        resp = await self._client.post(
            self.poll_url,
            content=poll_request,
            headers={"Content-Type": "application/xml"},
        )
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        ns = self.NS

        result_el = root.find(".//gov:Result", ns)
        if result_el is not None:
            return result_el.text or "Pending"

        return "Pending"
```

### 4.2 CT600 body builder

```python
# backend/jurisdictions/uk/corporation_tax/govtalk_body.py
"""Build CT600 IRenvelope XML from the adapter's line items dict."""

import lxml.etree as ET


def build_ct600_body(ctref: str, company_name: str, period_start: str,
                     period_end: str, line_map: dict[str, float]) -> str:
    """构建 CT600 的 IRenvelope XML body.

    Args:
        line_map: CT adapter 的 to_filing_format() 输出的 line items

    Returns:
        CT600 业务 XML 字符串 (不含 GovTalk envelope)
    """
    NS = "http://www.govtalk.gov.uk/taxation/CT/5.0"

    ir = ET.Element(f"{{{NS}}}IRenvelope")
    ct600 = ET.SubElement(ir, f"{{{NS}}}CT600")

    ET.SubElement(ct600, f"{{{NS}}}CTREF").text = ctref
    ET.SubElement(ct600, f"{{{NS}}}CompanyName").text = company_name
    ET.SubElement(ct600, f"{{{NS}}}PeriodStart").text = period_start
    ET.SubElement(ct600, f"{{{NS}}}PeriodEnd").text = period_end

    # 映射到 CT600 各 box
    for key, value in line_map.items():
        box = ET.SubElement(ct600, f"{{{NS}}}{key}")
        box.text = str(value)
        if isinstance(value, float):
            box.set("decimals", "2")

    return ET.tostring(ir, encoding="unicode")
```

---

## 五、实现路线

### Phase 1: GovTalkClient 通用层 (3-4 周)

```
backend/channels/govtalk/
  ├── __init__.py         (导出)
  ├── client.py           (GovTalkClient: envelope 构建 + CRC32 + 异步 poll)
  ├── exceptions.py       (TransientError, PermanentError, AuthError)
  └── schema/             (可选,缓存 XSD 文件)
```

### Phase 2: 各税种 body builder (1-2 周/税种)

```
backend/jurisdictions/uk/corporation_tax/govtalk_body.py
backend/jurisdictions/uk/paye/govtalk_body.py
backend/jurisdictions/uk/stamp_duty/govtalk_body.py
```

### Phase 3: 替换现有 HMRCCTService / HMRCPAYEService (1 周/税种)

- 将 `submit_return` 从 JSON REST 改为 GovTalk XML
- 用 `GovTalkClient.submit(class, body_xml)` 替换 `httpx.post(url, json=body)`
- 在 Orchestrator 的 TRACK 阶段增加 GovTalk poll 逻辑

---

## 六、关键注意事项 (Pitfalls)

1. **IRmark CRC32 必须正确** — 不是 MD5/SHA,是 **CRC32** (0xFFFFFFFF 掩码后 8 位大写 HEX)
2. **Poll URL 来自响应**,不是硬编码 — 每次提交返回的 Poll URL 可能不同
3. **认证用 UserName/Password**,不是 OAuth — GovTalk 不使用 REST 的 OAuth 2.0
4. **Vendor ID 必须从 SDST 获得** — 需要注册为 HMRC 软件开发商
5. **XSD 验证** — 每个 technical pack 有对应的 XSD schema,body XML 必须严格符合
6. **XML 大小限制** — 某些服务有 payload 大小上限
7. **轮询超时** — 建议 30 分钟超时 (HMRC 最长处理时间)
8. **TIL 测试** — 在 Class 后加 `-TIL` 可发送测试到生产环境,验证真实用户凭据

---

## 七、HMRC 注册流程

1. 访问 [Register as a software developer](https://www.gov.uk/government/collections/register-as-a-software-developer)
2. 联系 SDST (sdsteam@hmrc.gov.uk) 申请 Vendor ID
3. 获取对应 technical pack (含 XSD schema、测试凭据、测试场景)
4. 开发完成后申请 HMRC recognition (10 个工作日内完成)

---

## 八、参考资料

- [Basic guide for XML software developers (gov.uk)](https://www.gov.uk/guidance/basic-guide-for-xml-software-developers)
- [Transaction Engine: Document Submission Protocol](https://www.gov.uk/government/collections/government-gateway-support-for-software-developers)
- [IRmark technical pack](https://www.gov.uk/government/collections/hmrcirmark-support-for-software-developers)
- [Software development for HMRC](https://www.gov.uk/topic/dealing-with-hmrc/software-development)
- [Register as a software developer](https://www.gov.uk/government/collections/register-as-a-software-developer)
