# 报税提醒功能研究报告

> **状态**: 调研完成
> **日期**: 2026-06-14
> **关联文档**: `JIAHANG_TAX_ROADMAP.md`, `docs/architecture/pipeline.md`

## 1. 概述

跨境企业在多个国家运营时，面临不同国家、不同税种、不同申报频率的报税截止日管理难题。例如：

- 英国 VAT 季度申报，截止日为申报月次月 7 日
- 中国企业所得税需要季度预缴（4次/年）+ 年度汇算清缴（1次/年）
- 德国 VAT 月报，截止日为次月 10 日
- 新加坡 GST 季报，截止日为申报期结束后 1 个月

一个跨境企业每年可能需要应对 **20-40 个不同的报税截止日**，手动管理极易遗漏，导致滞纳金和罚款。

## 2. 各国报税频率与截止日

### 2.1 英国 (UK)

| 税种 | 频率 | 截止日规则 | 具体示例 |
|------|------|-----------|----------|
| **VAT** | 季度 | 申报期结束后 1 个月 + 7 天 | Q1 (1-3月) → 5月7日 |
| **Corporation Tax** | 年度 | 会计期结束后 12 个月 | FY2023 (4月) → 2025年4月 |
| **PAYE/RTI** | 每次发薪 | 发薪日当天或之前 (FPS on or before payday) | 每月25日发薪 → 每月25日前 |
| **Self Assessment** | 年度 | 纸质:10月31日, 在线:次年1月31日 | FY2023/24 → 2025年1月31日 |
| **CIS (Construction)** | 月度 | 次月19日 | 4月 → 5月19日 |

**UK VAT 关键日期（按月申报周期）：**

| 申报周期 | 截止日 |
|----------|--------|
| 1-3月 (Q1) | 5月7日 |
| 4-6月 (Q2) | 8月7日 |
| 7-9月 (Q3) | 11月7日 |
| 10-12月 (Q4) | 2月7日 |

### 2.2 德国 (DE)

| 税种 | 频率 | 截止日规则 |
|------|------|-----------|
| **VAT (Umsatzsteuer)** | 月度/季度 | 次月10日（可申请延期至次月15日） |
| **CIT (Körperschaftsteuer)** | 年度 | 会计年度结束后 7 个月 |
| **Trade Tax (Gewerbesteuer)** | 年度 | 与 CIT 同期 |
| **VAT 预申报** | 月度 | 上年税额 < €7,500 → 季度; €7,500-€100,000 → 月度 |
| **工资税 (Lohnsteuer)** | 月度/季度 | 次月10日 |

### 2.3 法国 (FR)

| 税种 | 频率 | 截止日规则 |
|------|------|-----------|
| **VAT (TVA)** | 月度/季度 | 次月15-24日（取决于地区） |
| **CIT (Impôt sur les sociétés)** | 年度 + 季度预缴 | 季度预缴: 3/6/9/12月15日; 年度申报: 5月 |
| **CVAE** | 年度 | 5月（电子申报） |
| **CFE** | 年度 | 12月 |

**法国 VAT 特殊规则：**
- 年 VAT < €15,000 → 年度申报
- €15,000 - €250,000 → 季度申报
- > €250,000 → 月度申报

### 2.4 中国 (CN)

| 税种 | 频率 | 截止日规则 |
|------|------|-----------|
| **增值税** | 月度/季度 | 次月15日 |
| **企业所得税 (CIT)** | 季度预缴 + 年度汇算 | 季度: 次月15日; 年度: 次年5月31日 |
| **个人所得税代扣** | 月度 | 次月15日 |
| **印花税** | 按次/按期 | 按次: 纳税义务发生后15日; 按期: 期后15日 |
| **房产税** | 季度 | 季度结束后15日 |
| **城建税+附加** | 与增值税同期 | 与增值税同截止日 |

**中国 CIT 申报节奏（一年 5 次申报）：**

| 申报 | 期间 | 截止日 |
|------|------|--------|
| Q1 预缴 | 1-3月 | 4月15日 |
| Q2 预缴 | 1-6月 | 7月15日 |
| Q3 预缴 | 1-9月 | 10月15日 |
| Q4 预缴 | 1-12月 | 1月15日 |
| 年度汇算清缴 | 全年 | 次年5月31日 |

### 2.5 新加坡 (SG)

| 税种 | 频率 | 截止日规则 |
|------|------|-----------|
| **GST** | 季度 | 申报期结束后 1 个月 |
| **CIT (ECI)** | 年度 | 财年结束后 3 个月 |
| **CIT (Form C/C-S)** | 年度 | 11月30日（纸质）/ 12月15日（电子） |
| **Withholding Tax** | 按次 | 付款日次月15日 |
| **Property Tax** | 年度 | 1月31日 |

**新加坡 GST 关键日期（按季度申报，财年 4月-次年3月）：**

| 申报周期 | 截止日 |
|----------|--------|
| 1-3月 | 4月30日 |
| 4-6月 | 7月31日 |
| 7-9月 | 10月31日 |
| 10-12月 | 1月31日 |

## 3. 嘉汉案例的报税日历

基于嘉汉案例（UK 子公司 + CN 母公司），一年至少需要应对以下截止日：

### UK 子公司（Jiahang UK Holdings Ltd.）

| 序号 | 税种 | 频率 | 申报次数/年 | 关键截止日 |
|------|------|------|-------------|-----------|
| 1 | VAT | 季度 | 4 | 5月7日, 8月7日, 11月7日, 2月7日 |
| 2 | Corporation Tax | 年度 | 1 | 会计期结束后12个月 |
| 3 | PAYE/RTI | 月度 | 12 | 每月发薪日 |
| 4 | Import Duty | 按次 | 不定 | 进口时 |

### CN 母公司（江苏嘉汉国际贸易有限公司）

| 序号 | 税种 | 频率 | 申报次数/年 | 关键截止日 |
|------|------|------|-------------|-----------|
| 5 | 增值税 | 月度 | 12 | 次月15日 |
| 6 | 企业所得税预缴 | 季度 | 4 | 4/7/10/1月15日 |
| 7 | 企业所得税汇算清缴 | 年度 | 1 | 次年5月31日 |
| 8 | 个人所得税代扣 | 月度 | 12 | 次月15日 |
| 9 | 城建税+附加 | 月度 | 12 | 与增值税同 |
| 10 | 印花税 | 按次 | 不定 | 义务发生后15日 |
| 11 | 房产税 | 季度 | 4 | 季度结束后15日 |

> **合计**：仅嘉汉案例一年就需要管理 **60+ 个报税时间节点**。

## 4. 竞品分析：现有税务软件的提醒机制

### 4.1 Xero

- **Tax Calendar**：Dashboard 中展示未来 3 个月的税务截止日
- **通知方式**：App 内提醒 + Email 通知
- **集成**：与 HMRC/ATO/IRD 等直接同步 obligation 数据
- **特色**：根据实际 obligation 自动计算截止日，非固定日历

### 4.2 QuickBooks

- **Tax Deadlines**：Tax Center 中列出所有即将到来的截止日
- **通知方式**：Dashboard 徽章 + Email
- **集成**：与 IRS/state tax agencies 对接
- **特色**：自动计算预估税额并提醒付款

### 4.3 Avalara

- **Returns Calendar**：按 jurisdiction 分组的日历视图
- **通知方式**：Email + SMS + Dashboard
- **集成**：与 50+ 国家的税务日历集成
- **特色**：支持 filing frequency 变更自动调整

### 4.4 TaxJar (Stripe Tax)

- **AutoFile Calendar**：自动申报状态日历
- **通知方式**：Email + Dashboard
- **特色**：仅覆盖 US sales tax，状态颜色编码

### 4.5 竞品功能对比

| 功能 | Xero | QuickBooks | Avalara | TaxJar | TAXI 目标 |
|------|------|------------|---------|--------|----------|
| 多国截止日 | ✅ | ✅ | ✅ | ❌ | ✅ |
| Email 提醒 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SMS 提醒 | ❌ | ❌ | ✅ | ❌ | ✅ |
| 日历导出 (ics) | ❌ | ❌ | ❌ | ❌ | ✅ |
| 提前N天可配置 | 🟡 | 🟡 | ✅ | ❌ | ✅ |
| 与 obligation 自动同步 | ✅ | 🟡 | ✅ | ✅ | ✅ |
| In-App 通知中心 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 多用户通知 | ✅ | ✅ | ✅ | ❌ | P1 |

## 5. TAXI 提醒系统架构设计

### 5.1 数据模型

```python
# backend/models/deadline.py

@dataclass
class FilingDeadline:
    """一个具体的报税截止日"""
    id: str
    jurisdiction: str               # "UK", "CN", "DE", "FR", "SG"
    tax_type: TaxType                # VAT, CORPORATION_TAX, PAYE, etc.
    taxpayer_id: str                 # 纳税人标识
    period: FiscalPeriod             # 申报期间
    filing_deadline: datetime        # 申报截止时间
    payment_deadline: datetime       # 缴款截止时间（可能与申报不同）
    status: str                      # "pending" | "filed" | "overdue"
    reminder_days_before: list[int]  # [30, 14, 7, 3, 1] — 提前N天提醒
    metadata: dict                   # 附加信息

@dataclass
class DeadlineRule:
    """截止日计算规则 — 按国家+税种+频率定义"""
    jurisdiction: str
    tax_type: TaxType
    period_type: PeriodType
    # "次月15日" → offset_month=1, day_of_month=15
    filing_offset_months: int
    filing_day_of_month: int
    # 缴款截止日可能与申报不同
    payment_offset_months: int | None = None
    payment_day_of_month: int | None = None
    # 特殊规则
    last_working_day: bool = False   # 如遇周末/假期顺延至下一工作日
    holiday_calendar: str = ""       # 假期日历 jurisdiction

@dataclass
class ReminderConfig:
    """提醒配置 — 可按纳税人/税种粒度"""
    id: str
    taxpayer_id: str
    jurisdiction: str | None = None  # None = 全局
    tax_type: TaxType | None = None  # None = 全部
    reminder_days_before: list[int]  # [30, 7, 1]
    channels: list[str]              # ["email", "sms", "in_app"]
    email: str = ""
    phone: str = ""
    enabled: bool = True

@dataclass
class ReminderLog:
    """提醒发送记录"""
    id: str
    deadline_id: str
    sent_at: datetime
    channel: str                     # "email" | "sms" | "in_app"
    recipient: str
    success: bool
    error: str | None = None
```

### 5.2 服务架构

```
backend/services/
├── deadline_calculator.py    # 基于 DeadlineRule 计算下次截止日
├── deadline_scheduler.py     # 定时检查 + 触发提醒（APScheduler）
├── notification.py           # 多渠道通知（Email/SMS/In-App）
└── calendar_export.py        # 导出 .ics 文件
```

#### deadline_calculator.py

```python
class DeadlineCalculator:
    """根据规则计算所有即将到来的截止日"""

    def __init__(self, registry: JurisdictionRegistry):
        self.registry = registry
        self.rules = self._load_rules()  # 内置规则 + DB 自定义

    def calculate_upcoming(
        self, taxpayer_id: str, months_ahead: int = 3
    ) -> list[FilingDeadline]:
        """计算未来 N 个月的所有截止日"""
        ...

    def calculate_next(
        self, jurisdiction: str, tax_type: TaxType, period: FiscalPeriod
    ) -> FilingDeadline:
        """计算下一个截止日"""
        ...

    def is_overdue(self, deadline: FilingDeadline) -> bool:
        """判断是否逾期"""
        ...
```

#### deadline_scheduler.py

```python
class DeadlineScheduler:
    """每天定时检查即将到来的截止日，触发提醒"""

    def __init__(self, calculator: DeadlineCalculator, notifier: NotificationService):
        self.calculator = calculator
        self.notifier = notifier

    async def daily_check(self):
        """每日检查（通过 APScheduler cron 触发）"""
        for taxpayer in self._list_taxpayers():
            deadlines = self.calculator.calculate_upcoming(taxpayer.id, months_ahead=1)
            for d in deadlines:
                days_left = (d.filing_deadline - now).days
                if days_left in d.reminder_days_before:
                    await self.notifier.send_deadline_reminder(d, days_left)
                if days_left < 0 and d.status != "filed":
                    await self.notifier.send_overdue_alert(d)
```

#### notification.py

```python
class NotificationService:
    """多渠道通知服务"""

    async def send_deadline_reminder(self, deadline: FilingDeadline, days_left: int):
        """发送截止日提醒"""
        ...

    async def send_overdue_alert(self, deadline: FilingDeadline):
        """发送逾期告警"""
        ...

    async def send(self, channel: str, recipient: str, subject: str, body: str):
        """通用发送方法"""
        if channel == "email":
            await self._send_email(recipient, subject, body)
        elif channel == "sms":
            await self._send_sms(recipient, body)
        elif channel == "in_app":
            await self._send_in_app(recipient, subject, body)
```

### 5.3 前端组件

```
frontend/src/
├── components/
│   ├── DeadlineCalendar.tsx       # 日历视图，展示本月/本季度截止日
│   ├── DeadlineList.tsx           # 列表视图，按紧迫程度排列
│   ├── DeadlineBadge.tsx          # 导航栏上的逾期数量角标
│   └── ReminderConfigPanel.tsx    # 提醒配置面板
└── pages/
    └── TaxCalendarPage.tsx        # 税务日历完整页
```

### 5.4 API 端点

```
GET    /api/deadlines/upcoming?taxpayer_id=X&months=3   # 即将到来的截止日
GET    /api/deadlines/calendar?year=2026&jurisdiction=UK # 年度日历
GET    /api/deadlines/{id}                               # 单个截止日详情
PUT    /api/deadlines/{id}/status                        # 标记已申报
GET    /api/deadlines/reminders/config                   # 提醒配置
PUT    /api/deadlines/reminders/config                   # 更新提醒配置
GET    /api/deadlines/export.ics                         # 导出日历文件
GET    /api/deadlines/overdue                            # 逾期列表
POST   /api/deadlines/snooze/{id}                        # 暂时推迟提醒
```

### 5.5 通知模板示例

**邮件提醒模板（截止日前 7 天）：**

```
Subject: [TAXI] UK VAT Q1 申报截止日还剩 7 天

您好，

您的 UK VAT Q1 (2026年1-3月) 申报截止日为 2026年5月7日，距现在还有 7 天。

申报信息：
- 主体：Jiahang UK Holdings Ltd.
- 税种：VAT
- 期间：2026 Q1 (1月-3月)
- 预计应缴税额：£20,000 (仅供参考)

请及时登录 TAXI 平台完成申报：
https://taxi.example.com/filings/new?type=vat&period=2026-Q1

---
TAXI — 多国税务，一键叫车
如需调整提醒频率，请访问：https://taxi.example.com/settings/reminders
```

**短信提醒模板（截止日前 1 天）：**

```
[TAXI] UK VAT Q1 申报明天截止！主体：Jiahang UK，截止：5月7日。请立即登录处理。
```

## 6. 假期日历与工作日调整

### 6.1 各国假期日历

需要维护每个 jurisdiction 的公共假期日历，用于：
- 遇周末/假期自动顺延截止日
- 提醒时间避开假期

### 6.2 实现方案

```python
# backend/services/holiday_calendar.py

HOLIDAY_CALENDARS = {
    "UK": {
        "2026-01-01": "New Year's Day",
        "2026-04-03": "Good Friday",
        "2026-04-06": "Easter Monday",
        "2026-05-04": "Early May Bank Holiday",
        "2026-05-25": "Spring Bank Holiday",
        "2026-08-31": "Summer Bank Holiday",
        "2026-12-25": "Christmas Day",
        "2026-12-28": "Boxing Day",
    },
    "CN": {
        "2026-02-17": "春节 (Spring Festival)",
        "2026-04-05": "清明节 (Qingming)",
        "2026-05-01": "劳动节 (Labour Day)",
        "2026-06-19": "端午节 (Dragon Boat)",
        "2026-09-25": "中秋节 (Mid-Autumn)",
        "2026-10-01": "国庆节 (National Day)",
    },
    # ... DE, FR, SG 等
}

def adjust_for_holiday(date: date, jurisdiction: str) -> date:
    """如果截止日遇假期/周末，顺延至下一工作日"""
    holidays = HOLIDAY_CALENDARS.get(jurisdiction, {})
    while date.weekday() >= 5 or date.isoformat() in holidays:
        date += timedelta(days=1)
    return date
```

## 7. 实施优先级

| 优先级 | 功能 | 说明 |
|--------|------|------|
| **P0** | 截止日计算引擎 | 基于内置规则计算所有 jurisdiction 的截止日 |
| **P0** | 截止日数据模型 | `FilingDeadline`, `DeadlineRule`, `ReminderConfig` |
| **P0** | Email 提醒 | 截止日前 30/14/7/3/1 天发送 |
| **P1** | 前端日历视图 | Dashboard 中展示即将到来的截止日 |
| **P1** | In-App 通知中心 | 站内提醒徽章 + 列表 |
| **P1** | 逾期告警 | 超过截止日未申报的红色告警 |
| **P2** | SMS 提醒 | 截止日前 1 天短信 |
| **P2** | 日历导出 (ics) | 可导入 Google Calendar / Outlook |
| **P2** | 与 HMRC Obligations API 同步 | 自动获取 UK VAT 实际 obligation |
| **P3** | 多用户通知配置 | 按用户角色配置不同提醒策略 |
| **P3** | 假期日历集成 | 自动调整截止日（遇周末/假期顺延） |

## 8. 参考资源

- UK VAT deadlines: https://www.gov.uk/vat-returns/deadlines
- UK Corporation Tax: https://www.gov.uk/corporation-tax
- HMRC Obligations API: https://developer.service.hmrc.gov.uk/api-documentation/docs/api/service/vat-api/1.0
- German Tax Calendar: https://www.bzst.de/
- Singapore IRAS Filing Due Dates: https://www.iras.gov.sg/taxes/
- China State Taxation Administration: https://www.chinatax.gov.cn/
- Xero Tax Calendar: https://central.xero.com/s/article/Tax-calendar
- Avalara: https://www.avalara.com/
- APScheduler: https://apscheduler.readthedocs.io/
