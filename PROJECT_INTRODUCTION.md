# T.A.X.I. 项目介绍

> **Tax Agent for X-border & Import**  
> **多国税务，一键叫车** — 面向跨境企业的 AI 税务申报 Copilot。  
> **最后更新**:2026-06-14(已对齐代码与 `Case_Roadmap.md` 真实状态,A1/A2/A3 收尾)

---

## 1. 项目定位:不只是报税表单,而是跨境税务智能体

**T.A.X.I.** 是一个面向跨境企业的多国家 AI 税务申报平台。它希望解决的不是"如何在线填写一张税表",而是更复杂的问题:

> 当一家企业同时面对多个国家、多个税种、多个申报入口、不同认证方式和持续变化的税法规则时,如何让 AI 成为可靠、可审计、可扩展的税务副驾?

传统税务软件通常以表单为中心:用户需要知道该进哪个菜单、填哪个字段、套用哪条规则。T.A.X.I. 的思路则是以企业真实业务为起点:用户可以通过对话、ERP 数据、案例账套或表单入口触发税务分析,再由平台完成数据转换、税额计算、合规校验、申报提交和回执追踪。

T.A.X.I. 把以下能力串联成一个智能税务操作系统雏形:


- **AI Agent 对话式操作** — 用自然语言触发税务分析和申报流程。
- **Agent 自动报税** — AI 可以调用专业工具、跑申报管线、生成申报结果。
- **确定性申报管线** — 关键报税动作不依赖 LLM 自由发挥,而由可验证的 6 阶段流程执行。
- **多国家可拓展架构** — 通过插件化设计支持不同国家、税种和提交渠道。
- **ERP 数据接入** — 把企业经营数据自动转译为税务申报数据。
- **自建结构化税务知识库** — 8,301 条已分块语料 + 按国家/税种组织的可查询 KB 段落。
- **自动更新与提醒** — 截止日自动计算、申报义务、授权状态、合规风险提示。
- **人类最终确认** — AI 是副驾,正式申报仍保留人工确认与审计记录。

---

## 2. 为什么跨境税务需要被重新设计

跨境企业的税务复杂性来自多个层面。

**不同国家的税制和申报方式完全不同。** 英国 VAT 通过 HMRC Making Tax Digital REST API 申报;英国 CT、PAYE/RTI、SDLT 走 GovTalk XML 网关(已实现);中国税务场景更多面向电子税务局网页流程(浏览器通道骨架已就位);欧洲不同国家还可能混合 API、EDI、门户网站和本地软件。

**税务申报不是普通问答任务。** AI 可以解释规则、整理资料、辅助判断,但正式申报必须满足确定性、可复核、可追踪和责任边界清晰的要求。税额计算、字段校验、提交回执、异常重试、审计日志,都不能只靠模型"猜"。

**企业原始数据不是天然的税务数据。** ERP、CSV、发票、销售记录、采购记录、工资数据、关联交易、汇率、暂时性差异等,都需要被转换成税务系统能理解的申报事项。

**跨境税务不是单点流程,而是连续义务。** VAT 季度/月度申报,PAYE 实时申报,公司税年度申报,中国增值税月度 + 汇算清缴年度,每个国家都有周期性义务。企业需要的不只是"一次填表",而是持续合规提醒和风险监控。

T.A.X.I. 的核心创新,正是围绕这些问题重新设计税务软件:让 AI 负责理解和协助,让确定性系统负责执行和审计,让插件化架构负责多国家扩展。

---

## 3. 核心特色总览

| 特色 | 当前真实状态 |
|---|---|
| **Agent 对话式操作** | 已上线。Agent 通过 `claude-agent-sdk` 接入 UK 6 个 + testland 1 个税种工具,带会话状态、上下文、工具调用。 |
| **Agent 自动报税** | 已上线。Agent 调 MCP 工具 → 走 6 阶段管线 → 提交至 HMRC。Copilot 哲学:LLM 不直接拍板,所有正式动作走 `StateMachine` + `AuditLog`。 |
| **AI + 确定性管线** | 已上线。`PRECHECK → PREPARE → CALCULATE → VALIDATE → SUBMIT → TRACK` 在所有国家/税种间共享。 |
| **多国家可拓展** | 已上线。Registry → Adapter → Channel 插件架构;UK / Testland 已注册;CN 8 个税种计算器 + DE/FR 有 KB 锚点(2026-06-14 更新)。 |
| **ERP 接入** | 已上线。CSV 解析、ERP 案例账套、多币种(`currency`/`fx_rate`)、`LineItem` 标准化、**关联交易镜像对账**(`backend/erp/reconciliation/mirror.py`,2026-06-14)。 |
| **支付网关接入** | PoC 已实现。PayPal Channel 走 OAuth2 Client Credentials,从 `.env` 优雅降级。 |
| **电商平台接入** | PoC 已实现。Shopify Channel 走 Admin API Access Token,`from_env()` 工厂。 |
| **多国截止日计算** | **已上线**。`/api/deadlines/upcoming` 端到端,5 国 × 2 税种 × 季度/月度/年度,带紧急度。 |
| **自建结构化税务知识库** | 已上线。UK 6 个 KB + CN/DE/FR/testland 各 1 个 VAT KB + 8,301 条分块语料 + `tax_knowledge_store.get_section()` 可被 Agent 直接读。 |
| **数据库自动更新** | 部分上线。`corpus_sync.py` 服务存在;定期调度 + 规则 diff 提醒待补。 |
| **自动提醒** | 部分上线。`DeadlineCalculator` 已上线,基于截止日/申报义务的提醒闭环待补。 |
| **人工确认与审计** | 已上线。`StateMachine` 拒绝非法跳转,`AuditLog` 记录每阶段,SDK 工具标注 `destructiveHint`。 |

---

## 4. 创新一:Agent 对话,不只是聊天机器人

T.A.X.I. 的 Agent 不是一个只会回答税务常识的聊天窗口,而是一个可以理解上下文、调用工具、读取会话状态并触发申报流程的税务操作入口。

用户可以用接近自然业务语言的方式与系统交互,例如:

- "帮我看一下 Q1 VAT 该报多少。"
- "这批 ERP 数据有没有 VAT 风险?"
- "帮我准备这个季度的英国 VAT 申报。"
- "这个客户案例里 UK 子公司和中国母公司的关联交易有哪些税务影响?"

Agent 会在会话中维护关键上下文:国家、税种、纳税人编号、申报期间、ERP 数据、历史消息、已调用工具结果。最新一次重构(`8ba1adc`)让它支持**多国家 namespace 路由** — 一个 Agent 进程,多个国家/税种工具空间,无需重启即可切换。`1-click auto-login flow` + 工作区数据自加载(workspace 在 `~/.taxi/workspace/`)让 Agent 第一次就能读到 manifest,不被 LLM 注意力衰减欺骗。

相比传统税务软件要求用户在菜单和表单之间寻找路径,T.A.X.I. 的交互逻辑更接近"把需求告诉税务副驾,由副驾帮你组织下一步"。

---

## 5. 创新二:Agent 自动报税,但不让 LLM 自由提交

"自动报税"很容易被误解为让大模型直接代替人提交申报。T.A.X.I. 的设计并不是这样。

Agent 可以自动完成大量繁琐步骤:

1. 获取申报义务和期间信息。
2. 读取或分析 ERP/CSV/案例账套数据。
3. 调用税种计算器生成应纳税额。
4. 调用合规校验器发现缺失字段或异常金额。
5. 生成目标税局所需的申报 payload(UK 走 GovTalk XML,UK VAT 走 JSON)。
6. 查询提交状态和回执。
7. 向用户解释计算逻辑和风险提示。

但正式申报动作不会由 LLM 随意决定。项目坚持 Copilot 哲学:**AI 是副驾,最终决定权在人**。

工程上具体做到三件事:

1. **预提交二次陈述提示**(`193e469`)— Agent 在调 `submit_*` 工具前必须重述本期关键金额,等用户确认。
2. **`destructiveHint: true` 工具标注** — 提交类工具在 SDK 层被识别为不可逆操作,需要更严格的 permission。
3. **`StateMachine` 拒绝非法跳转** — `PENDING → IN_PROGRESS → SUBMITTED → ACCEPTED/REJECTED` 之外的状态变更全部抛错,审计日志全程记录。

这使 T.A.X.I. 与普通 LLM demo 拉开差距:它不是让模型"看起来会报税",而是让模型在受控工具体系内协助完成可验证的税务工作。

---

## 6. 创新三:AI Agent + 6 阶段确定性管线

T.A.X.I. 的核心架构是"双引擎":

```text
自然语言 / ERP 数据 / 表单输入
        ↓
AI Agent 理解意图、分析数据、调用工具
        ↓
PRECHECK → PREPARE → CALCULATE → VALIDATE → SUBMIT → TRACK
        ↓
HMRC REST / GovTalk XML / BrowserChannel / PayPal/Shopify 数据回执
```

其中,Agent 解决"人如何更自然地使用系统"的问题;6 阶段管线解决"申报如何可靠执行"的问题。

| 阶段 | 作用 |
|---|---|
| **PRECHECK** | 在网络请求前检查基础字段和模板要求,尽早发现数据缺口。 |
| **PREPARE** | 完成认证准备和目标申报格式转换(REST JSON / GovTalk XML / 表单 DOM)。 |
| **CALCULATE** | 执行确定性税务计算,例如 VAT 9-Box 派生字段、CT 3/200 边际救济。 |
| **VALIDATE** | 根据业务规则进行合规校验,区分错误与警告。 |
| **SUBMIT** | 调用税局通道提交申报,处理重试、错误和回执。 |
| **TRACK** | 追踪受理状态,保存审计记录和后续状态。 |

这种设计的关键价值在于:AI 可以很灵活,但税务申报必须很严谨。Agent 负责"理解和协助",管线负责"执行和留痕"。

---

## 7. 创新四:多国家可拓展架构

跨境税务平台最大的挑战之一,是不同国家的税种、表单、认证、提交渠道都不同。如果每新增一个国家就重写一套系统,平台很快会变得不可维护。

T.A.X.I. 采用三层插件架构:

```text
Registry  →  Adapter  →  Channel
```

### Registry:国家和税种注册中心

Registry 负责管理当前平台支持哪些国家、哪些税种、对应哪个 Adapter。`backend/main.py` 中:

```python
registry = JurisdictionRegistry()
registry.register(UKJurisdictionAdapter())          # 已上线
registry.register(TestlandJurisdictionAdapter())    # 已上线(示例国家)
```

### Adapter:国家/税种适配器

Adapter 负责某个国家、某个税种的业务逻辑:

- 需要什么申报模板
- 如何计算税额
- 如何校验业务规则
- 如何转换成税局要求的格式
- 向 Agent 暴露哪些工具(MCP 命名空间)

UK 的 Adapter 下已有 6 个 tax_type 落地:`vat / corporation_tax / paye / self_assessment / stamp_duty / withholding_tax`。CN 的 Adapter 也有 `vat / cit / surcharges / property_tax / stamp_duty / iit` 6 个 tax_type 注册,核心计算器就绪。

### Channel:提交渠道

Channel 负责"怎么把申报送出去":

- **UK VAT**:HMRC MTD REST API(`APIChannel`)。
- **UK CT / PAYE / SDLT / Levy**:**GovTalk XML 客户端**(`backend/channels/govtalk/client.py`,399 行),POST 到 HMRC Transaction Engine,带 correlation_id 轮询。
- **CN VAT / CN CIT / CN 附加**:`BrowserChannel` 骨架已实现(291 行),通过 `create_browser_channel()` 工厂分发到 `CNVATBrowserChannel` / `CNCITBrowserChannel`,Playwright 自动化电子税务局。
- **PayPal / Shopify**:通过 `PaymentChannel` / `EcommerceChannel` 抽象,把外部数据源(订单、收款)拉入同一条 `LineItem` 标准化管线,用于三方对账。
- **DE / FR**:占位中,已有 README + VAT KB 锚点,等计算器和通道补全。

这个架构让 T.A.X.I. 从一开始就不是"英国 VAT 单点项目",而是一个可以逐步扩展成多国家、多税种、多渠道平台的底座。

---

## 8. 创新五:MCP 工具体系,让 AI 调用专业税务能力

T.A.X.I. 的 Agent 能力不是直接写死在提示词里,而是通过 MCP(Model Context Protocol)工具体系暴露给 LLM。每个国家/税种可以有独立工具集,例如:

- 获取申报义务
- 计算税额
- 校验申报数据
- 提交申报
- 查询已提交申报
- 分析业务数据

工具命名遵循 MCP 命名空间约定:`mcp__tax_agent_uk_vat__get_vat_obligations`、`mcp__tax_agent_uk_ct__submit_ct600` 等。`tax_agent_*` 前缀是 MCP server 命名方案,与 Python package 路径无关。

**关键点**:工具按国家和税种隔离,避免不同国家规则混在一起。对 AI 来说,它不是依赖"模型记忆"硬回答,而是在需要时调用专业工具获得结果。

例如,UK PAYE 工具集与 UK CT 工具集完全独立,即便两者都走 GovTalk XML,也不会出现 LLM 误把 PAYE 消息发到 CT endpoint 的问题。

这种工具化设计也为未来扩展打下基础。新增一个国家或税种时,不需要重新训练模型,而是增加新的工具、知识库和适配器,让 Agent 自动获得新的可操作能力。`claude-agent-sdk` 内置了 MCP server 的运行时,`create_mcp_servers(registry)` 在 backend 启动时一次性注册所有国家/税种工具。

---

## 9. 创新六:ERP 接入,把业务数据转成税务语言

企业的税务申报不是从空白表单开始的,而是来自真实经营数据:销售、采购、进口、工资、贷款、利息、特许权、股息、固定资产、租赁、发票和银行流水。

T.A.X.I. 设计了 ERP/CSV/样本账套接入能力,将原始业务数据逐步转换为税务系统能处理的结构:

```text
ERP / CSV / 发票 / 案例账套
        ↓
标准化交易行 LineItem(currency / fx_rate / metadata)
        ↓
tax_code / txn_type
        ↓
VAT 9-Box / CT600 / FPS-EPS-EYU / WHT supplementary / CIT 调增调减
        ↓
申报计算、校验、提交或提醒
```

嘉汉案例是这一能力的最佳验证场。它包含 18 个税种/事项,涉及 UK 子公司 + CN 母公司双账套,GBP/CNY 双币种,母子公司关联交易(贷款/利息/特许权/股息)镜像,WHT 与 FTC 联动,以及 4 个暂时性差异事件驱动 DTA 计算。

**当前 ERP 接入已实现的增强**:

- `data/erp_samples/case-jiahang-uk-fy2023/` + `case-jiahang-cn-fy2023/` 双账套
- `ErpInvoiceTable` 支持多币种显示
- `related_party_id` 字段支持关联交易镜像
- `MirrorLedgerTable` + `TemporaryDiffCard` 前端展示组件
- `erp_import.json` 多币种 schema

这说明 T.A.X.I. 的价值不只是"把数字填进 VAT Box",而是构建一层从**业务事实**到**税务事实**再到**申报动作**的自动转译系统。

#### 扩展数据源:电商平台与跨境支付网关

除 ERP 之外,跨境企业的业务数据还来自电商平台(Shopify、WooCommerce、Amazon 等)和跨境支付网关(PayPal、Stripe 等)。T.A.X.I. 在 `backend/channels/` 下新增了与 `FilingChannel` 平行的两条渠道抽象,让这些外部平台也能进入同一套数据转译管线:

| 渠道类型 | 文件位置 | 对应平台 | 主要数据 |
|---|---|---|---|
| **PaymentChannel** | `backend/channels/payment/` | PayPal(已实现)、Stripe(未来) | 跨境收款、退款、手续费、争议 |
| **EcommerceChannel** | `backend/channels/ecommerce/` | Shopify(已实现)、WooCommerce / Amazon(未来) | 订单、客户、交易、退款 |
| **FilingChannel**(既有) | `backend/channels/` | HMRC 等税局 | 申报 payload、回执 |

两条渠道的设计目标:

1. **数据进得来**:通过 OAuth2 / Access Token 接入外部平台,复用现有的 `OAuth2Manager` 工具。
2. **数据能对账**:把电商订单和支付网关的收款数据,统一标准化为 TAXI 的 `LineItem` 抽象,进而进入 9-Box 计算和申报流程。
3. **凭证缺失不崩溃**:每条渠道都通过 `from_env()` 工厂方法读取 `.env` 中的凭证;凭证不存在时,渠道在 `app.state` 上为 `None`,不中断主服务。

```text
Shopify (订单) ──┐
                 ├→ 标准化 LineItem → VAT 9-Box
PayPal (收款) ──┘                    ↑
                 ↑ 三方对账:销售 = 收款 - 退款
```

T.A.X.I. 不仅能从**内部账务**(ERP)进入税务管线,也能从**外部交易平台**直接进入 — 对跨境电商客户尤其有价值。

---

## 10. 创新七:自建结构化税务知识库

税务 Agent 不能只依赖大模型训练时的知识。税率会变化,申报表会更新,API 会改版,税局口径也可能调整。对于税务系统来说,可维护、可审查、可更新的知识资产非常关键。

T.A.X.I. 的税务知识库由两层组成:

### 10.1 显式 KB 文档(`data/tax_knowledge/`)

按国家/税种组织,每个 H2 段落是一个可被 `get_section(jurisdiction, tax_type, title)` 检索的独立章节:

| 国家 | KB 文件 | 状态 |
|---|---|---|
| **UK** | `vat.md` / `corporation_tax.md` / `paye.md` / `self_assessment.md` / `stamp_duty.md` / `withholding_tax.md` | 6 个全部就绪 |
| **CN** | `vat.md` | 1 个,后续扩展 |
| **DE** | `vat.md` | 1 个,锚点 |
| **FR** | `vat.md` | 1 个,锚点 |
| **testland** | `vat.md` | 1 个,示例国家 |
| **taxonomy/** | `concepts.yaml` / `jurisdictions.yaml` / `tax_types.yaml` | 跨国家税务概念本体 |

每个 KB 文件:

- 用 `## Topic` 段落承载一个独立知识点,保持每段 < 300 token
- `<!-- source: URL -->` 注释标注每个段落的税局/法规来源,方便审计
- `## Rates` 段落是当前国家/税种的税率权威源 — Agent 通过 `kb-tools.get_tax_rates` 读取,不再硬编码

### 10.2 大规模分块语料(`data/tax_corpus/`)

`data/tax_corpus/` 包含 8,301 条带标签的 chunk,可通过 `corpus_sync.py` 服务同步、检索、向量化:

```
data/tax_corpus/
├── chunks_with_tags.jsonl    (8,301 条带语义标签的分块)
├── rendered.jsonl            (渲染后的版本)
└── tag_index.json            (按主题/国家/税种组织的标签索引)
```

这种双层设计带来四个好处:

1. **可审查**:KB 段落以文档和数据形式存在,可被人工复核,所有数字带源链接。
2. **可更新**:法规、税率、表单或 API 改变时,可更新 KB 而不是依赖模型重新训练。
3. **可分国家隔离**:UK、CN、DE、FR 规则放在各自命名空间,`tax_knowledge_store.get_section(jurisdiction, tax_type, title)` 严格按国家返回。
4. **可服务 Agent**:Agent 调 `kb-tools.get_tax_rates` 时拿到的是结构化结果,而不是让 LLM 自由发挥。

未来方向:让 `corpus_sync.py` 周期性拉取税局公告 → 触发 KB 段落 diff → 提醒相关用户/客户。

---

## 11. 创新八:截止日自动计算 + 自动提醒

税务合规不是一次性任务。企业需要持续知道:什么时候该申报、哪些数据还缺、授权是否过期、税率是否变化、某项规则更新是否影响当前申报。

### 11.1 多国截止日计算引擎(`backend/services/deadline_calculator.py`)

已上线,端到端打通:`GET /api/deadlines/upcoming` + `GET /api/deadlines/rules`,按 jurisdiction / tax_type 过滤返回未来若干条截止日,每条带 `days_remaining` 和紧急度(OVERDUE / URGENT / SOON)。

| 国家 | 税种 | 频率 | 截止日规则 |
|---|---|---|---|
| UK | VAT | 季度 | 期间结束后次月 7 日 |
| UK | CIT | 年度 | 财年结束后 9 个月(CT600) |
| DE | VAT | 月度 | 次月 10 日 |
| DE | CIT | 年度 | 财年结束后 7 个月 |
| FR | VAT | 月度 | 次月 19 日 |
| FR | CIT | 年度 | 财年结束后次年 4 月 15 日 |
| CN | VAT | 月度 | 次月 15 日 |
| CN | CIT | 季度预缴 | 季度结束后当月 15 日 |
| SG | GST | 季度 | 期间结束后次月 30 日 |
| SG | CIT | 年度 | 财年结束后次年 10 月 30 日 |

### 11.2 提醒机制的多源输入

截止日只是"骨架"。T.A.X.I. 的提醒引擎可以围绕以下信号构建:

- 税局返回的申报义务,例如 VAT obligations
- 历史申报状态(pending / submitted / accepted / rejected)
- OAuth 授权状态(token 是否需要更新)
- ERP 数据完整性(本期是否缺少发票或工资数据)
- 法规和税率变化(KB 段落 diff 触发)
- 人工确认节点(申报已准备好但尚未确认提交)

当前实现的**是截止日计算**,**待补**的是"把截止日 + 其他信号 → 邮件/IM/日历导出"的完整通知闭环。这是 Phase 2 重点。

---

## 12. 当前真实能力:18 税种 × 平台矩阵

为了避免把路线图包装成已完成能力,这里给出嘉汉案例 18 税种在当前平台上的真实状态(2026-06-14):

| 状态 | 数量 | 占比 | 含义 |
|:--:|:--:|:--:|---|
| ✅ 端到端(计算+通道) | **8 / 18** | **44%** | 计算器+提交通道完整,UK 侧 6 个税种 + 2 个 CN 长尾 VAT |
| 🟡 计算器就绪(通道待补) | **8 / 18** | **44%** | 算得对、提不出;CN 6 个 + UK 2 个长尾税种 |
| ❌ 仍需新增 | **2 / 18** | **11%** | 仅剩 DE/FR VAT adapter 缺失(无计算器) |

### 12.1 ✅ 已端到端(UK 侧)

| 税种 | 嘉汉金额 | 实现路径 |
|---|---|---|
| **UK VAT** | Q1-Q4 VAT Return,Q1 Box 5 = -£6,875 | HMRC MTD REST + OAuth 2.0(沙箱 E2E 已通) |
| **UK CT** | £180,000 利润 → £43,950(3/200 公式) | GovTalk XML → HMRC Transaction Engine,CT600 body builder |
| **UK PAYE & NIC** | £336,000 工资,FPS/EPS/EYU | GovTalk XML 三种消息类型全部连通 TE |
| **UK Apprenticeship Levy** | £30 / 年(£336k < £3M 门槛) | EPS body 内集成,与 PAYE 同通道 |
| **UK WHT(利息/特许权)** | £2,778 + £3,500(10% 中英协定) | WHT 计算器 + DTA 条约库(UK→CN/HK/US/DE/FR) |
| **UK 股息 WHT** | 100% 控股 0% / no action required | 平台识别为不需申报,而非提交 0 申报 |
| **CN 不动产租赁 VAT** | 5% 简易 vs 9% 一般决策树 | `cn/real_estate_rental_vat/calculator.py`,17 个单测,差额征税支持 |
| **CN 物业管理 VAT** | 6% 现代服务业 vs 3% 征收率 | `cn/property_management_vat/calculator.py`,12 个单测,含 2023-2027 阶段性 1% 减按 |

### 12.2 🟡 计算器就绪、通道待补

| 税种 | 嘉汉金额 | 计算器状态 | 缺什么 |
|---|---|---|---|
| **UK Import Duty** | CIF £157,500 × 5% = £7,875 | ✅ 已算对 | CDS/Tariff API 真实提交、HS Code 自动识别 |
| **UK Business Rates** | RV £187,500 × 0.546 = £102,375 | ✅ 已算对 | VOA Rateable Value API、Council bill |
| **CN VAT** | 销项 ¥2,732,000 / 应纳 ¥2,461,500 | ✅ 已算对 | BrowserChannel 真实提交电子税务局 |
| **CN CIT** | 调增/调减后 ¥2,032,500 / 费用 ¥1,918,821 | ✅ 已算对 | 季度预缴+汇算清缴表单、BrowserChannel 提交 |
| **CN 城建税/附加** | VAT × 12% = ¥295,380 | ✅ 已算对 | 与 CN VAT 联动、BrowserChannel |
| **CN 境外税收抵免(FTC)** | 抵免 ¥43,679,限额 ¥390,343 | ✅ 已算对 | 与 UK WHT 自动配对、BrowserChannel 提交 |
| **CN 个人所得税代扣** | 50 员工累进 + 年终奖 | ✅ 已算对 | 扣缴客户端自动化 |
| **CN 印花税** | 购销合同 0.03%,¥2,100 | ✅ 已算对 | 合同类型识别,电子税务局申报入口 |

### 12.3 ❌ 仍需新增

| 税种 | 优先级 | 备注 |
|---|:--:|---|
| **CN 房产税** | P2 | 从价/从租模型 + 季度申报 |
| **(DE / FR VAT 通道)** | P3 | 当前只有 KB 锚点 |

### 12.4 当前最关键的两条风险

1. **BrowserChannel 运行环境**:`chromium.launch()` 在 CentOS 7(glibc 2.17)上跑不起来,影响 CN 8 个税种从计算到真实提交的最后一步(已全有计算器,等通道)。
2. **HMRC Vendor ID**:GovTalk XML 已连通测试 Transaction Engine,但生产仍需注册软件商。

---

## 13. 嘉汉案例:不是 demo,而是路线图总账

T.A.X.I. 项目中最有特色的数据资产之一,是 **嘉汉跨境税务案例**。

嘉汉案例不是一组随手编的演示数据,而是一个覆盖英国子公司与中国母公司的综合跨境业务场景。它包含 18 个税种或税务事项,涉及:

- UK VAT / CT / PAYE / NIC / Import Duty / Business Rates / Levy / WHT
- CN VAT / CIT / 附加 / FTC / 个税 / 印花税 / 房产税 / 不动产租赁 / 物业
- 关联交易、股息、利息、特许权、贷款和汇率折算
- 4 个暂时性差异事件驱动 DTA 计算

这个案例对项目有三重意义。

**第一,它是能力矩阵**。当前平台支持什么、部分支持什么、完全缺什么,都可以在嘉汉案例中被清楚标记 — 这就是 `Case_Roadmap.md` 的存在意义。

**第二,它是路线图牵引**。短期最关键的下一批能力不是凭空规划出来的,而是由真实案例压力测试暴露出来的:UK CT、CN VAT、CN CIT、BrowserChannel、多币种、关联交易镜像、WHT 与境外税收抵免联动。

**第三,它是跨境智能体的验证场**。单个税种可以做成一个工具,但跨境税务真正难的是链条:英国子公司的利息和特许权支付,会影响中国母公司的境外所得和税收抵免;母子公司的同一笔交易,在两边账套中需要镜像匹配;不同币种和汇率会影响最终税务结果。

因此,嘉汉案例让 T.A.X.I. 的路线图更接近真实企业,而不是停留在孤立功能列表。

---

## 14. 技术路线图:从单税种闭环到跨境税务智能体

T.A.X.I. 的长期演进分为三个阶段。

### Phase 1:Foundation(0-3 月) — ✅ 大部分完成

目标:让平台从 UK VAT demo 扩展为**中英核心税种平台**。

| 事项 | 状态 |
|---|---|
| UK CT GovTalk XML 客户端 + CT600 | ✅ 已完成(连通 HMRC TE) |
| UK PAYE RTI XML(FPS/EPS/EYU) | ✅ 已完成 |
| CN VAT 计算器(多档税率) | ✅ 计算器完成;BrowserChannel 待补 |
| CN CIT 汇算清缴计算器 | ✅ 计算器完成;BrowserChannel 待补 |
| ErpInvoiceTable 多币种 | ✅ 已完成 |
| 嘉汉案例全链路预览 | ✅ 已完成 |
| UK Apprenticeship Levy 通道 | ✅ 已完成(EPS body 内集成) |

**验收标准完成度**:UK 侧 100% 完成,CN 侧计算器 100% 完成,通道 0% 完成(等 BrowserChannel 运行环境)。

### Phase 2:Coverage(3-6 月) — 🟡 进行中

目标:补齐跨境高频税种与抵免链路。

| 事项 | 状态 |
|---|---|
| UK WHT 利息/特许权 supplementary | ✅ 计算器 + 条约库 + CT600 supplementary 自动嵌入完成 |
| CN 境外税收抵免(FTC) | ✅ 计算器完成;与 UK WHT 自动配对待补 |
| CN 城建税/附加 | ✅ 计算器完成;CN VAT 联动待补 |
| 关联交易镜像自动对账 | ✅ **`backend/erp/reconciliation/mirror.py` 已上线**,22 个单测;嘉汉案例 10/11 对配对,7 对差异可识别 |
| 知识库自动同步调度 | 🟡 `corpus_sync.py` 服务已存在,scheduler 待补 |
| 提醒闭环(邮件/IM/日历) | 🟡 截止日计算已上线,通知通道待补 |

### Phase 3:Long Tail(6-12 月) — ⏳ 待启动

目标:补齐长尾税种,让平台覆盖更完整企业账套。

| 事项 | 状态 |
|---|---|
| UK Import Duty 真实通道(CDS/Tariff API) | ⏳ 待启动 |
| UK Business Rates 真实通道(VOA API) | ⏳ 待启动 |
| CN 房产税 | ⏳ 计算器待新增 |
| DE/FR VAT 通道 | ⏳ 待启动(KB 锚点已有) |
| BEPS 2.0 / Pillar Two GloBE 规则 | ⏳ 仅集团收入 >€750M 才触发 |
| 测试覆盖率补全 | 🟡 持续补;CN VAT/IIT/印花税/房产税/不动产/物业 5 个新计算器已各有 12-17 单测 |
| ~~CN 印花税 / 个税代扣 / 不动产租赁 VAT / 物业管理 VAT~~ | ✅ **已上线**(2026-06-14) |

**当前最紧迫的下一步**:

1. 解决 BrowserChannel 运行环境(CentOS 7 glibc 兼容)→ 解锁 CN 8 税种真实提交(全有计算器,等通道)
2. 申请 HMRC Vendor ID → 解锁 UK CT/PAYE/SDLT 生产通道
3. ~~关联交易镜像对账服务~~ ✅ **已上线**(`backend/erp/reconciliation/mirror.py`)

---

## 15. 架构层的"看不见的创新"

T.A.X.I. 的创新还体现在一些对用户透明、对工程关键的设计选择上。

### 15.1 SDK 合规性

最近一次 SDK 审计(`docs/superpowers/audit/2026-06-12-sdk-audit.md`,19 项 finding,2 critical / 5 high / 6 medium / 6 nit)已经落地了 3 个 PR:

- **PR-1**:`ToolAnnotations` 标 `destructiveHint: true`(覆盖 `submit_*` 工具)
- **PR-2**:`session_store` 改用 SDK 公开 API(`list_sessions` / `get_session_messages`)
- **PR-3**:OTEL pass-through + `AuditLog` 仪器化 SDK chat

剩余 5 项未决 finding 留在 Phase 3 重构时处理。

### 15.2 多国家 namespace 路由

`8ba1adc` 让一个 Agent 进程可同时承载 UK + Testland + 未来的 CN/DE/FR 工具空间,无需重启即可切换。`from_env()` 工厂模式让外部凭证缺失时不阻塞主服务。

### 15.3 工作区数据自加载

`~/.taxi/workspace/` 存放用户的 case 账套和 manifest,Agent 在每次启动时自动读取,避免 LLM 注意力衰减导致忘记关键上下文。

### 15.4 1-click auto-login

最近的提交让 Agent 在 dev 模式下可一键用本地凭证登录,代价是浏览器 localStorage 中暂存 OAuth refresh token — 该 trade-off 在 `01a8298` 文档中详细说明,并附带禁用指南。

---

## 16. 项目的新意在哪里

T.A.X.I. 的创新不在于单独某一个页面、某一个 API 或某一个计算公式,而在于它把 AI、税务规则、企业数据和申报通道组合成了一套新的系统设计。

可以用七个关键词概括:

1. **对话式税务操作** — 让用户用业务语言而不是表单路径操作税务系统。
2. **Agent 自动报税** — 让 AI 能调用工具、分析数据、准备申报,但不直接拍板。
3. **确定性申报管线** — 把关键报税动作放入可验证、可审计、可恢复的 6 阶段流程。
4. **多国家插件架构** — 用 Registry → Adapter → Channel 支撑不同国家、税种和提交方式。
5. **ERP 到税表自动转译** — 从企业经营事实自动生成税务事实和申报数据。
6. **结构化可更新税务知识库** — 显式 KB 段落 + 8,301 条分块语料,让税务规则成为可维护资产。
7. **截止日 + 持续合规副驾** — 从一次性申报扩展到周期性义务管理与自动提醒。

最终,T.A.X.I. 的目标不是替代税务专业判断,而是把跨境税务中重复、繁琐、容易出错的资料整理、规则匹配、税额计算、申报流转和状态追踪自动化,让人类专家保留最终判断权,把更多精力放在真正需要专业判断的地方。

> **T.A.X.I. 希望成为跨境企业的税务副驾:懂业务、懂规则、会调用工具、能执行流程,但始终尊重人的最终决策。**

---

## 附录 A:与本介绍文档配套的真实数据

- **能力总账**:`Case_Roadmap.md` — 18 税种 × 平台状态,每季度更新
- **能力矩阵细节**:`docs/cases/jiahang-capability-matrix.md`
- **数据模型**:`docs/cases/jiahang-data-model.md`
- **架构概览**:`docs/architecture/overview.md`
- **管线细节**:`docs/architecture/pipeline.md`
- **可拓展性**:`docs/architecture/extensibility.md`
- **加新国家**:`docs/architecture/adding-new-jurisdiction.md`
- **GovTalk XML 协议**:`docs/architecture/govtalk_client.md`
- **UK 国家说明**:`docs/jurisdictions/uk/README.md`
- **SDK 合规性审计**:`docs/superpowers/audit/2026-06-12-sdk-audit.md`

## 附录 B:本介绍文档的诚实边界

为了让读者正确理解 T.A.X.I. 的真实进度,以下内容必须明确:

1. **UK 侧**:VAT/CT/PAYE/Levy/WHT 端到端,生产通道等 Vendor ID;Import Duty / Business Rates 计算器就绪,通道待补。
2. **CN 侧**(2026-06-14 更新):VAT/CIT/附加/FTC/印花税/个税/不动产租赁 VAT/物业 VAT 8 个**计算器全部就绪**(算得与嘉汉案例一致),仅房产税缺计算器;**真实提交**需要 BrowserChannel 在更高 glibc 节点运行 Playwright,目前 CentOS 7 不行。
3. **DE / FR / SG**:仅有 README + VAT KB 锚点,无 adapter。
4. **数据库自动更新 / 完整通知闭环**:`corpus_sync.py` 服务存在,`/api/deadlines/upcoming` 已上线,但**自动同步调度**和**通知投递**仍未闭环。
5. **关联交易镜像对账**:`backend/erp/reconciliation/mirror.py` 已上线,支持 5 维度对账(金额/汇率/日期/WHT/方向),嘉汉案例 10/11 对成功配对。
6. **测试覆盖率**:UK VAT 端到端覆盖;CN 不动产租赁 VAT(17)+ 物业 VAT(12)+ 镜像对账(22)+ WHT supplementary(28)= 共 79 个新单测,UK VAT/CT/PAYE 覆盖率仍最厚。
