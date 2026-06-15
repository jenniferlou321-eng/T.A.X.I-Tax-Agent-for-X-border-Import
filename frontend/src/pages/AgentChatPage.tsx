import { useState, useRef, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  ChatBubbleLeftRightIcon,
  PaperAirplaneIcon,
  UserIcon,
  CpuChipIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  WrenchIcon,
  SparklesIcon,
  ClockIcon,
  TrashIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  ChatBubbleOvalLeftIcon,
  BuildingOfficeIcon,
  MagnifyingGlassIcon,
  ChartBarIcon,
} from '@heroicons/react/24/outline'
import QuickActionButton from '../components/QuickActionButton'
import InvoiceMultiSelectPanel from '../components/InvoiceMultiSelectPanel'
import NineBoxDiffTable from '../components/NineBoxDiffTable'
import AgentActivityPanel, { type ActivityEntry } from '../components/AgentActivityPanel'
import Markdown from '../components/Markdown'
import { useDemoStore } from '../stores/demoStore'
import { casePresets } from '../data/casePresets'
import { api } from '../api/client'
import type { ImportResult, ReconciliationDelta, ERPNineBox } from '../types'
import { consumeAguiStream, type BaseEvent } from '../api/agentStream'
import ErrorCard, { type ErrorPayload } from '../components/ErrorCard'

/** 从 fetch() 异常或 SSE 异常里抽出 ErrorPayload。
 *  - 网络层(浏览器断网 / 后端 8765 没起):kind=network
 *  - HTTP 非 2xx 且 body 形如 {detail, kind, hint, request_id}:直接转发
 *  - HTTP 非 2xx 且 body 是其它:用 status + statusText 兜底
 *  - 流中途崩(ECONNRESET / AbortError 之外):kind=internal,带 requestId
 */
async function buildErrorFromFetchError(
  err: unknown,
  response: Response | undefined,
): Promise<ErrorPayload> {
  // 1) 网络层失败 — fetch 抛 TypeError("Failed to fetch" / "Load failed")
  if (err instanceof TypeError) {
    return {
      kind: 'network',
      hint: '后端 8765 不可达。检查 `./start_backend.sh` 是否在跑,或网络代理是否断了。',
      message: err.message,
    }
  }
  // 2) HTTP 非 2xx — 拿 body
  if (response && !response.ok) {
    const requestId = response.headers.get('X-Request-Id') || undefined
    let body: any = null
    try {
      body = await response.clone().json()
    } catch {
      try {
        body = await response.clone().text()
      } catch {
        /* ignore */
      }
    }
    if (body && typeof body === 'object' && (body.detail || body.kind)) {
      return {
        kind: typeof body.kind === 'string' ? body.kind : 'unknown',
        hint: typeof body.hint === 'string' ? body.hint : undefined,
        message: typeof body.detail === 'string' ? body.detail : `HTTP ${response.status}`,
        requestId: typeof body.request_id === 'string' ? body.request_id : requestId,
        raw: body,
      }
    }
    return {
      kind: response.status >= 500 ? 'internal' : 'validation',
      hint: `后端返回 ${response.status}。检查请求参数,或查 logs/backend.log。`,
      message: typeof body === 'string' ? body : `HTTP ${response.status} ${response.statusText}`,
      requestId,
      raw: body,
    }
  }
  // 3) 流中途崩
  return {
    kind: 'internal',
    hint: '流式响应中途断开。复制详情贴给开发,或重试一次。',
    message: err instanceof Error ? err.message : String(err),
  }
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
  timestamp: Date
  status?: 'sending' | 'streaming' | 'done' | 'error'
  /** 扩展思考（extended thinking）流式累积。 */
  thinking?: string
  /** REASONING_END 是否已到；仅当 thinking 非空时使用。 */
  thinkingFinished?: boolean
  /** 思考 + 工具调用活动，按到达时间顺序；per-message。
   *  在 TEXT_MESSAGE_START 时把上一条 reasoning 消息的 activities 合并进来。 */
  activities?: ActivityEntry[]
  /** 结构化错误(RUN_ERROR 事件 / 启动期 chat 失败 / 流中断)。存在时,系统消息
   *  气泡会渲染 ErrorCard 而不是纯文本。 */
  error?: ErrorPayload
}

interface HistorySession {
  session_id: string
  created_at: string
  updated_at: string
  message_count: number
  preview: string
}

// Same-origin by default (Vite dev-server proxy / static preview). Override
// with VITE_API_BASE_URL when the API lives on a different host.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

function generateId() {
  return Math.random().toString(36).substring(2, 10)
}

function formatTime(iso: string) {
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function buildWelcomeMessage(
  caseTitle?: string,
  hasErpData?: boolean,
  concurrentAgent?: boolean,
): ChatMessage {
  let content =
    '您好！我是 TaxAgent 智能报税助手。\n\n' +
    '我可以帮您：\n' +
    '• 分析原始企业发票数据并自动计算 VAT Return\n' +
    '• 查询 HMRC 待申报义务\n' +
    '• 验证申报数据合规性\n' +
    '• 提交 VAT Return 至 HMRC\n' +
    '• 查询已提交的申报'
  if (caseTitle) {
    content += `\n\n当前已加载 Case: "${caseTitle}"。`
    content += hasErpData
      ? 'ERP 数据已就绪,VRN 和期间信息已在 workspace 中 — 点击下方「分析当前帐套数据」一键开始,无需重复提供 VRN。'
      : 'ERP 数据正在加载中…稍候即可使用 Quick Action。'
    if (concurrentAgent) {
      content +=
        '\n\n⚠️ **并发占用提示**:此 case 已被另一 agent 锁定/正在申报中。' +
        '请先与用户确认策略 — 是等待对方完成、取消对方、还是改用「补申报 / 修正」路径。' +
        '**不要**直接调用 submit_* 系列工具,以免与对方的提交冲突。'
    }
  } else {
    content += '\n\n请先在 Dashboard 选择一个 Demo Case,或直接输入您的问题。'
  }
  return {
    id: 'welcome',
    role: 'assistant',
    content,
    timestamp: new Date(),
    status: 'done',
  }
}

export default function AgentChatPage() {
  const [searchParams] = useSearchParams()
  const initialMessage = searchParams.get('message') || ''

  const buffer = useDemoStore((s) => s.buffer)
  const currentCase = buffer?.preset ?? null

  const [messages, setMessages] = useState<ChatMessage[]>([
    buildWelcomeMessage(
      currentCase?.title,
      !!buffer?.erpData,
      currentCase?.concurrentAgent,
    ),
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string>('')
  const [sampleData, setSampleData] = useState<Record<string, unknown> | null>(null)
  const [sampleDataLoading, setSampleDataLoading] = useState(false)
  const [showInvoicePanel, setShowInvoicePanel] = useState<{ type: 'sale' | 'purchase' } | null>(null)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [lastDiff, _setLastDiff] = useState<{ erp: ERPNineBox; taxi: ERPNineBox; delta: ReconciliationDelta } | null>(null)
  // 当前 agent 执行阶段（由后端 step_start/step_end 信号驱动）
  const [activeStep, setActiveStep] = useState<string | null>(null)
  // 注意:思考 + 工具调用活动从全局 state 改为 per-message,存在 ChatMessage.activities / thinkingFinished 上。

  // 当前活跃的 assistant 消息 id（用 ref 避免 stale closure，
  // 不依赖 messages 数组查找）
  const assistantIdRef = useRef<string>('')
  // AbortController 引用，组件卸载或重置时取消正在进行的流
  const abortRef = useRef<AbortController | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  // 消息滚动容器 + 「是否贴底」状态:用户上滑离开底部 → 暂停自动下滑;
  // 再滑回底部 → 恢复自动下滑。stickToBottom 用 ref 存(滚动回调里读最新值,
  // 不触发重渲染);atBottomUi 仅用于「跳到底部」按钮的显隐。
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const stickToBottomRef = useRef(true)
  const [atBottomUi, setAtBottomUi] = useState(true)

  // ── Demo Case selection (from Dashboard / Preview) ──
  // buffer 已在组件顶部读取；currentCase = buffer?.preset

  const handleAnalyzeData = () => {
    if (!currentCase) {
      alert('请先在 Dashboard 选择一个 Demo Case')
      return
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    handleSend('帮我分析目前的财务数据')
  }

  const handleCalculateAndFile = () => {
    if (!currentCase) {
      alert('请先在 Dashboard 选择一个 Demo Case')
      return
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    handleSend('帮我计算本年增值税并申报')
  }

  // ── History Sidebar State ──
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historySessions, setHistorySessions] = useState<HistorySession[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)

  // Auto-scroll to bottom — 仅当用户仍贴底时(stickToBottomRef)才自动下滑
  useEffect(() => {
    if (stickToBottomRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  // 监听滚动容器:判断用户是否贴底(留 80px 容差)。
  // 上滑离底 → stickToBottom=false(暂停自动下滑);滑回底 → 恢复。
  useEffect(() => {
    const el = scrollContainerRef.current
    if (!el) return
    const onScroll = () => {
      const dist = el.scrollHeight - el.scrollTop - el.clientHeight
      const atBottom = dist < 80
      stickToBottomRef.current = atBottom
      setAtBottomUi(atBottom)
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  // Handle initial message from URL
  useEffect(() => {
    if (initialMessage && messages.length === 1) {
      handleSend(initialMessage)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialMessage])

  // ── Load History Sessions ──
  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/agent/sessions`)
      const data = await res.json()
      setHistorySessions(data.sessions || [])
    } catch {
      // ignore
    } finally {
      setHistoryLoading(false)
    }
  }, [])

  useEffect(() => {
    if (historyOpen) {
      loadHistory()
    }
  }, [historyOpen, loadHistory])

  // ── Load Case Data when buffer has a case but no ERP data yet ──
  useEffect(() => {
    if (buffer?.presetId && !importResult) {
      // 优先用 buffer 里已缓存的 erpData
      if (buffer.erpData) {
        setImportResult(buffer.erpData)
        return
      }
      api.erp.getCase(buffer.presetId)
        .then(setImportResult)
        .catch((err) => console.error('Failed to load case:', err))
    }
  }, [buffer, importResult])

  // ── Load Session Messages ──
  const loadSession = async (sid: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/agent/sessions/${sid}/messages`)
      const data = await res.json()
      const loaded: ChatMessage[] = (data.messages || []).map((m: { role: string; content: string; timestamp: string }, idx: number) => ({
        id: `hist-${idx}`,
        role: m.role as ChatMessage['role'],
        content: m.content,
        timestamp: new Date(m.timestamp || Date.now()),
        status: 'done',
      }))
      setMessages(loaded.length > 0 ? loaded : [{
        ...WELCOME_MESSAGE,
        content: '对话已加载。继续输入以继续对话。',
      }])
      setSessionId(sid)
      setHistoryOpen(false)
    } catch {
      // ignore
    }
  }

  const deleteSession = async (sid: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await fetch(`${API_BASE}/api/agent/sessions/${sid}`, { method: 'DELETE' })
      setHistorySessions((prev) => prev.filter((s) => s.session_id !== sid))
    } catch {
      // ignore
    }
  }

  const scrollToBottom = useCallback((force = false) => {
    // 流式过程中,只有用户仍贴底才自动下滑;force=true(如用户主动发消息)
    // 强制拉到底并重新「贴底」。
    if (force) {
      stickToBottomRef.current = true
      setAtBottomUi(true)
    }
    if (force || stickToBottomRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [])

  // ── AG-UI 事件流式接收：按 type 派发 ──
  //
  // 后端通过 SSE 推送 AG-UI 事件序列：
  //   RUN_STARTED → TEXT_MESSAGE_START → (TEXT_MESSAGE_CONTENT)* → TEXT_MESSAGE_END
  //                → (TOOL_CALL_START → TOOL_CALL_ARGS → TOOL_CALL_END → TOOL_CALL_RESULT)*
  //                → RUN_FINISHED | RUN_ERROR
  //
  // 状态机：
  //   - assistantIdRef 跟踪当前 active text message（首次 TEXT_MESSAGE_START 设置）
  //   - activities 数组存放 thinking + TOOL_CALL 序列（直到 RUN_FINISHED 重置）
  //   - sessionId 从 RUN_STARTED 的 threadId 取
  // 多个工具调用 / 多段文本都会被正确切片（每个 TOOL_CALL_START 之前先关闭前一段 TEXT）

  const ensureAssistantMessage = useCallback((initialText: string) => {
    if (assistantIdRef.current) {
      const id = assistantIdRef.current
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, content: m.content + initialText } : m))
      )
      return id
    }
    const id = generateId()
    assistantIdRef.current = id
    setMessages((prev) => [
      ...prev,
      {
        id,
        role: 'assistant',
        content: initialText,
        timestamp: new Date(),
        status: 'streaming',
      },
    ])
    return id
  }, [])

  const finishAssistantMessage = useCallback(() => {
    const id = assistantIdRef.current
    if (id) {
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, status: 'done' } : m))
      )
      assistantIdRef.current = ''
    }
    setIsLoading(false)
  }, [])

  const closeTextMessage = useCallback(() => {
    const id = assistantIdRef.current
    if (id) {
      setMessages((prev) =>
        prev.map((m) => (m.id === id ? { ...m, status: 'done' } : m))
      )
      // 不清空 ref：下一段 TEXT_MESSAGE_START 才会给新 id
      // 实际上 adapter 每次发 START 时会用新 messageId 重新 set，
      // 但 ref 留旧值在 closeTextMessage 后无影响。
    }
  }, [])

  const resetRunState = useCallback(() => {
    assistantIdRef.current = ''
    setActiveStep(null)
    // activities / thinkingFinished 改为 per-message,无需全局重置
  }, [])

  // AG-UI 事件派发器
  const handleAguiEvent = useCallback(
    (event: BaseEvent) => {
      const t = event.type
      switch (t) {
        // ── 扩展思考（REASONING_*） — 早于 TEXT_MESSAGE_* 到达 ──
        case 'REASONING_START': {
          const mid = String(event.messageId || '')
          if (!mid) break
          // 让后续 TOOL_CALL_* 路由到这条 reasoning 消息
          assistantIdRef.current = mid
          // 先建一个空的 assistant 占位；activities 不预创建 thinking 条目,
          // 等第一条 REASONING_MESSAGE_CONTENT 有内容时才加(避免空 thinking
          // 折叠块在面板里显示成"空气泡")。TEXT_MESSAGE_START 时再把 thinking
          // + activities 合并到 text 消息。
          setMessages((prev) => {
            if (prev.some((m) => m.id === mid)) return prev
            return [
              ...prev,
              {
                id: mid,
                role: 'assistant',
                content: '',
                timestamp: new Date(),
                status: 'streaming',
                thinking: '',
                thinkingFinished: false,
                activities: [],
              },
            ]
          })
          scrollToBottom()
          break
        }
        case 'REASONING_MESSAGE_START': {
          // no-op — REASONING_START 已建好占位；这里只是协议必发的事件。
          break
        }
        case 'REASONING_MESSAGE_CONTENT': {
          const mid = String(event.messageId || '')
          const delta = String(event.delta || '')
          if (!mid || !delta) break
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== mid) return m
              const newThinking = (m.thinking || '') + delta
              // 第一次收到非空 thinking 时,把 thinking 条目追加到 activities(若还没有)
              const acts = m.activities ?? []
              const hasThinkingEntry = acts.some(
                (a) => a.type === 'thinking' && a.messageId === mid
              )
              const newActs = hasThinkingEntry
                ? acts
                : [...acts, { id: mid, type: 'thinking' as const, messageId: mid }]
              return {
                ...m,
                thinking: newThinking,
                activities: newActs,
              }
            })
          )
          scrollToBottom()
          break
        }
        case 'REASONING_MESSAGE_END': {
          // no-op — 等 REASONING_END 才把"finished"标记挂上
          break
        }
        case 'REASONING_END': {
          const mid = String(event.messageId || '')
          if (!mid) break
          setMessages((prev) =>
            prev.map((m) => (m.id === mid ? { ...m, thinkingFinished: true } : m))
          )
          break
        }
        case 'RUN_STARTED': {
          const tid = String(event.threadId || '')
          const rid = String(event.runId || '')
          if (tid) setSessionId(tid)
          // 不再创建空占位消息。第一个 REASONING_START 或 TEXT_MESSAGE_START
          // 才会创建第一条 assistant 气泡（避免历史回归的"用户→空气泡→文本"）。
          if (rid && typeof window !== 'undefined') {
            // eslint-disable-next-line no-console
            console.debug('[agui] RUN_STARTED', { threadId: tid, runId: rid })
          }
          scrollToBottom()
          break
        }
        case 'TEXT_MESSAGE_START': {
          const mid = String(event.messageId || '')
          if (!mid) break
          if (assistantIdRef.current && assistantIdRef.current !== mid) {
            // 上一段 text 还没 END，先关掉
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantIdRef.current ? { ...m, status: 'done' } : m
              )
            )
          }
          // ★ 核心合并逻辑:若前一条 assistant 消息是同段的 reasoning 消息
          //   (id 与 assistantIdRef.current 相同,content 为空),把它持有的
          //   thinking + activities 搬过来,然后删掉 reasoning 消息。
          //   后端 agui_adapter.py 初始化时 reasoning_msg_id 与 text_msg_id
          //   是两个不同的 UUID,所以这里不能用 id 相等去合并 — 而是用"前一条
          //   assistant 消息"作为合并源(它要么是上一段 text,要么是本段 reasoning)。
          setMessages((prev) => {
            const prevId = assistantIdRef.current
            const prevIdx = prev.findIndex((m) => m.id === prevId)
            const textMsgExists = prev.some((m) => m.id === mid)
            if (prevIdx >= 0 && prev[prevIdx].id !== mid && prev[prevIdx].content === '') {
              const reasonMsg = prev[prevIdx]
              const newMsg: ChatMessage = {
                id: mid,
                role: 'assistant',
                content: '',
                timestamp: new Date(),
                status: 'streaming',
                thinking: reasonMsg.thinking,
                thinkingFinished: reasonMsg.thinkingFinished,
                activities: reasonMsg.activities ?? [],
              }
              const filtered = prev.filter((m) => m.id !== reasonMsg.id)
              if (textMsgExists) {
                return filtered.map((m) => (m.id === mid ? { ...m, ...newMsg } : m))
              }
              return [...filtered, newMsg]
            }
            if (textMsgExists) return prev
            return [
              ...prev,
              {
                id: mid,
                role: 'assistant',
                content: '',
                timestamp: new Date(),
                status: 'streaming',
                activities: [],
              },
            ]
          })
          assistantIdRef.current = mid
          break
        }
        case 'TEXT_MESSAGE_CONTENT': {
          const mid = String(event.messageId || '')
          const delta = String(event.delta || '')
          if (!mid || !delta) break
          // 若这条 message 还没建（先来 content 后来 start 的异常），补建
          if (assistantIdRef.current !== mid) {
            assistantIdRef.current = mid
            setMessages((prev) => {
              const exists = prev.some((m) => m.id === mid)
              if (exists) return prev
              return [
                ...prev,
                {
                  id: mid,
                  role: 'assistant',
                  content: delta,
                  timestamp: new Date(),
                  status: 'streaming',
                },
              ]
            })
          } else {
            setMessages((prev) =>
              prev.map((m) => (m.id === mid ? { ...m, content: m.content + delta } : m))
            )
          }
          scrollToBottom()
          break
        }
        case 'TEXT_MESSAGE_END': {
          const mid = String(event.messageId || '')
          if (mid) {
            setMessages((prev) =>
              prev.map((m) => (m.id === mid ? { ...m, status: 'done' } : m))
            )
          }
          break
        }
        case 'TOOL_CALL_START': {
          const tcid = String(event.toolCallId || '')
          const name = String(event.toolCallName || '(unnamed)')
          if (!tcid) break
          // 路由到当前 active assistant 消息(reasoning 阶段也允许出现 tool call)
          const targetId = assistantIdRef.current
          if (!targetId) break
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== targetId) return m
              const acts = m.activities ?? []
              if (acts.some((a) => a.toolCallId === tcid)) return m
              return {
                ...m,
                activities: [
                  ...acts,
                  {
                    id: tcid,
                    type: 'tool_call',
                    toolCallId: tcid,
                    toolName: name,
                    args: '',
                    result: undefined,
                  },
                ],
              }
            })
          )
          scrollToBottom()
          break
        }
        case 'TOOL_CALL_ARGS': {
          const tcid = String(event.toolCallId || '')
          const delta = String(event.delta || '')
          if (!tcid) break
          const targetId = assistantIdRef.current
          if (!targetId) break
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== targetId) return m
              const acts = m.activities ?? []
              return {
                ...m,
                activities: acts.map((a) =>
                  a.toolCallId === tcid ? { ...a, args: (a.args || '') + delta } : a
                ),
              }
            })
          )
          break
        }
        case 'TOOL_CALL_END': {
          // 工具参数收尾（无需额外数据变更，args 已完整）
          break
        }
        case 'TOOL_CALL_RESULT': {
          const tcid = String(event.toolCallId || '')
          const content = String(event.content || '')
          if (!tcid) break
          const targetId = assistantIdRef.current
          if (!targetId) break
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== targetId) return m
              const acts = m.activities ?? []
              return {
                ...m,
                activities: acts.map((a) =>
                  a.toolCallId === tcid ? { ...a, result: content } : a
                ),
              }
            })
          )
          scrollToBottom()
          break
        }
        case 'RUN_FINISHED': {
          // 关掉所有还 streaming 的 assistant 消息（多消息 run 的兜底）
          setMessages((prev) =>
            prev.map((m) =>
              m.role === 'assistant' && m.status === 'streaming'
                ? { ...m, status: 'done' }
                : m
            )
          )
          finishAssistantMessage()
          // 活动面板保留在 UI 上供用户查看；下次 RUN_STARTED 会清
          break
        }
        case 'RUN_ERROR': {
          // 后端 agui_adapter._classify_error 已经把 kind/hint/requestId 一起塞进
          // event 的 extra 字段(ConfiguredBaseModel extra="allow")。这里组装成
          // ErrorPayload 交给 ErrorCard 渲染。
          const errPayload: ErrorPayload = {
            kind: typeof event.errorKind === 'string' ? event.errorKind : undefined,
            hint: typeof event.errorHint === 'string' ? event.errorHint : undefined,
            message: typeof event.message === 'string' ? event.message : undefined,
            requestId: typeof event.requestId === 'string' ? event.requestId : undefined,
            stage: typeof event.errorStage === 'string' ? event.errorStage : undefined,
          }
          setMessages((prev) => [
            ...prev,
            {
              id: generateId(),
              role: 'system',
              content: errPayload.message || 'Agent 错误',
              timestamp: new Date(),
              status: 'error',
              error: errPayload,
            },
          ])
          setIsLoading(false)
          assistantIdRef.current = ''
          break
        }
        case 'STEP_STARTED': {
          setActiveStep(String(event.stepName || ''))
          break
        }
        case 'STEP_FINISHED': {
          setActiveStep(null)
          break
        }
        // STATE_SNAPSHOT / 等暂不渲染
        default:
          break
      }
    },
    [finishAssistantMessage, scrollToBottom]
  )

  // ── 发送普通消息（纯文本） ──
  const handleSend = async (overrideMessage?: string) => {
    const text = overrideMessage || input.trim()
    if (!text || isLoading) return

    if (!overrideMessage) setInput('')
    setIsLoading(true)
    resetRunState()  // 清掉旧 assistantIdRef + tool calls

    // 取消上一次未完成的流（防止 chunk 串入新一轮消息）
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    const sid = sessionId || generateId()
    if (!sessionId) setSessionId(sid)

    setMessages((prev) => [
      ...prev,
      {
        id: generateId(),
        role: 'user',
        content: text,
        timestamp: new Date(),
        status: 'done',
      },
    ])
    // 用户主动发消息 → 强制拉到底并恢复「贴底」自动下滑
    scrollToBottom(true)

    try {
      const response = await fetch(
        `${API_BASE}/api/agent/chat?session_id=${sid}&message=${encodeURIComponent(text)}`,
        { method: 'POST', signal: controller.signal }
      )
      await consumeAguiStream(response, handleAguiEvent, { signal: controller.signal })
    } catch (err) {
      if ((err as Error).name === 'AbortError') return
      // consumeAguiStream 抛 err 时我们拿不到 response(它在内部读 body 后就丢了)。
      // 改用 err 自身结构(TypeError → network;其它 → internal) + err.message。
      const errPayload = await buildErrorFromFetchError(
        err,
        err instanceof Error && (err as any).response as Response | undefined,
      )
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: 'system',
          content: errPayload.message || '连接失败',
          timestamp: new Date(),
          status: 'error',
          error: errPayload,
        },
      ])
      setIsLoading(false)
      resetRunState()
    }
  }

  // ── 发送带 workspace 上下文的消息（case_ids 多管辖地优先;caseId/rawData 兼容） ──
  const sendWithRawData = useCallback(async (
    message: string,
    opts?: { caseId?: string; caseIds?: string[]; rawData?: Record<string, unknown> }
  ) => {
    const text = message.trim()
    if (!text || isLoading) return

    setIsLoading(true)
    resetRunState()

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    const sid = sessionId || generateId()
    if (!sessionId) setSessionId(sid)

    // 构造 query string:case_ids 优先(多管辖地),caseId 兼容(单国)
    const params = new URLSearchParams({ session_id: sid, message: text })
    if (opts?.caseIds && opts.caseIds.length > 0) {
      params.set('case_ids', opts.caseIds.join(','))
    } else if (opts?.caseId) {
      params.set('case_id', opts.caseId)
    }
    if (opts?.rawData) params.set('raw_data', JSON.stringify(opts.rawData))

    setMessages((prev) => [
      ...prev,
      {
        id: generateId(),
        role: 'user',
        content: (opts?.caseIds || opts?.caseId)
          ? text + '\n[Case 已加载 — VRN/期间/发票数据在 workspace 中,agent 将自动读取]'
          : text + '\n[已附加 TechFlow Distribution Ltd Q1 原始业务数据]',
        timestamp: new Date(),
        status: 'done',
      },
    ])

    try {
      const response = await fetch(
        `${API_BASE}/api/agent/chat?${params.toString()}`,
        { method: 'POST', signal: controller.signal }
      )
      await consumeAguiStream(response, handleAguiEvent, { signal: controller.signal })
    } catch (err) {
      if ((err as Error).name === 'AbortError') return
      const errPayload = await buildErrorFromFetchError(
        err,
        err instanceof Error && (err as any).response as Response | undefined,
      )
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: 'system',
          content: errPayload.message || '连接失败',
          timestamp: new Date(),
          status: 'error',
          error: errPayload,
        },
      ])
      setIsLoading(false)
      resetRunState()
    }
  }, [sessionId, isLoading, handleAguiEvent, resetRunState])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const clearChat = () => {
    if (!window.confirm('确定要清空当前对话吗?Case 数据不会被删除。')) return
    abortRef.current?.abort()
    abortRef.current = null
    resetRunState()
    setMessages([
      buildWelcomeMessage(
        currentCase?.title,
        !!buffer?.erpData,
        currentCase?.concurrentAgent,
      ),
    ])
    setSessionId('')
    setIsLoading(false)
    setSampleData(null)
  }

  // 强制要求已选 Case(无 case 时按钮 disabled 拦截,此处兜底 alert)
  // 走 case_ids 路径(多管辖地),后端落盘 workspace + LLM 用 Read 工具按需读取
  const handleAnalyzeCurrentCase = async () => {
    if (!currentCase) {
      alert('请先在 Dashboard 选择一个 Demo Case')
      return
    }
    const ids = currentCase.erpCaseIds || [currentCase.erpCaseId]
    // eslint-disable-next-line react-hooks/exhaustive-deps
    sendWithRawData('请分析这些数据并帮我报税', { caseIds: ids })
  }

  // ── Load Sample Business Data ──
  const loadSampleData = async () => {
    if (sampleData) {
      // 已加载，直接发送
      sendWithRawData('请分析这些原始数据并帮我报税', sampleData)
      return
    }
    setSampleDataLoading(true)
    try {
      // 从后端获取示例数据（避免前端打包过大）
      const res = await fetch(`${API_BASE}/api/agent/sample-data`)
      if (!res.ok) throw new Error(`Failed to load sample data: HTTP ${res.status}`)
      const data = await res.json()
      setSampleData(data)
      sendWithRawData('请分析这些原始数据并帮我报税', data)
    } catch {
      // 回退：从前端本地加载
      try {
        const res = await fetch('/data/realCaseData.json')
        const data = await res.json()
        setSampleData(data)
        sendWithRawData('请分析这些原始数据并帮我报税', data)
      } catch (err) {
        const errPayload = await buildErrorFromFetchError(
          err,
          err instanceof Error && (err as any).response as Response | undefined,
        )
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: 'system',
            content: '加载示例数据失败',
            timestamp: new Date(),
            status: 'error',
            error: errPayload,
          },
        ])
      }
    } finally {
      setSampleDataLoading(false)
    }
  }

  const getMessageIcon = (role: ChatMessage['role']) => {
    switch (role) {
      case 'user':
        return <UserIcon className="w-4 h-4" />
      case 'assistant':
        return <SparklesIcon className="w-4 h-4" />
      case 'tool':
        return <WrenchIcon className="w-4 h-4" />
      case 'system':
        return <ExclamationTriangleIcon className="w-4 h-4" />
      default:
        return <ChatBubbleLeftRightIcon className="w-4 h-4" />
    }
  }

  const getMessageStyle = (role: ChatMessage['role']) => {
    switch (role) {
      case 'user':
        return 'bg-primary-muted text-primary-foreground ml-auto'
      case 'assistant':
        return 'bg-bg-elevated text-fg border border-border'
      case 'tool':
        return 'bg-accent-muted text-accent border border-accent/20'
      case 'system':
        return 'bg-error/10 text-error border border-error/20'
      default:
        return 'bg-bg-elevated text-fg'
    }
  }

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* ── History Sidebar ── */}
      <aside
        className={`bg-bg-surface border-r border-border flex flex-col transition-all duration-300 ${
          historyOpen ? 'w-72' : 'w-0 overflow-hidden'
        }`}
      >
        <div className="p-4 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-semibold text-fg">历史会话</h2>
          <button
            onClick={() => setHistoryOpen(false)}
            className="p-1 text-fg-dim hover:text-fg rounded"
          >
            <ChevronLeftIcon className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {historyLoading ? (
            <div className="flex items-center justify-center py-8">
              <ArrowPathIcon className="w-5 h-5 text-fg-dim animate-spin" />
            </div>
          ) : historySessions.length === 0 ? (
            <div className="text-center py-8 text-fg-dim text-sm">
              <ChatBubbleOvalLeftIcon className="w-8 h-8 mx-auto mb-2 opacity-40" />
              暂无历史会话
            </div>
          ) : (
            historySessions.map((s) => (
              <button
                key={s.session_id}
                onClick={() => loadSession(s.session_id)}
                className={`w-full text-left p-3 rounded-lg text-sm transition-colors group ${
                  sessionId === s.session_id
                    ? 'bg-primary-muted text-primary'
                    : 'hover:bg-bg-elevated text-fg'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="truncate font-medium">
                      {typeof s.preview === 'string' ? s.preview : JSON.stringify(s.preview).slice(0, 40)}
                    </p>
                    <div className="flex items-center gap-2 mt-1 text-xs text-fg-dim">
                      <ClockIcon className="w-3 h-3" />
                      <span>{formatTime(s.updated_at)}</span>
                      <span>·</span>
                      <span>{s.message_count} 条消息</span>
                    </div>
                  </div>
                  <button
                    onClick={(e) => deleteSession(s.session_id, e)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-fg-dim hover:text-error transition-opacity"
                  >
                    <TrashIcon className="w-3.5 h-3.5" />
                  </button>
                </div>
              </button>
            ))
          )}
        </div>
      </aside>

      {/* ── Main Chat Area ── */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-bg-surface">
          <div className="flex items-center gap-3">
            {!historyOpen && (
              <button
                onClick={() => setHistoryOpen(true)}
                className="p-2 text-fg-dim hover:text-fg hover:bg-bg-elevated rounded-md transition-colors"
                title="打开历史会话"
              >
                <ChevronRightIcon className="w-4 h-4" />
              </button>
            )}
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
              <CpuChipIcon className="w-5 h-5 text-on-primary" />
            </div>
            <div>
              <h1 className="text-sm font-semibold text-fg">TaxAgent 智能助手</h1>
              <div className="flex items-center gap-2">
                <span className="inline-block w-2 h-2 rounded-full bg-success" />
                <span className="text-xs text-fg-dim">SSE 流式连接</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={clearChat}
              className="p-2 text-fg-dim hover:text-fg hover:bg-bg-elevated rounded-md transition-colors"
              title="清空对话(不删除 Case 数据)"
            >
              <TrashIcon className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div ref={scrollContainerRef} className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
          {/* Case summary banner */}
          {currentCase && (
            <div className="card p-3 flex items-center gap-2 fade-in">
              <BuildingOfficeIcon className="w-5 h-5 text-fg-muted" />
              <p className="text-sm text-fg-muted">
                当前 Case: <span className="font-medium text-fg">{currentCase.title}</span>
              </p>
            </div>
          )}

          {/* Quick action buttons */}
          {currentCase && (
            <div className="flex gap-2 fade-in">
              <QuickActionButton
                icon={<MagnifyingGlassIcon className="w-4 h-4" />}
                label={`🔍 分析 ${currentCase?.title ?? '当前数据'}`}
                onClick={handleAnalyzeData}
              />
              <QuickActionButton
                icon={<ChartBarIcon className="w-4 h-4" />}
                label="📊 算 9-Box 并准备申报"
                onClick={handleCalculateAndFile}
                variant="primary"
              />
            </div>
          )}

          {/* ERP Panel + Diff rendering (Task 16) */}
          {showInvoicePanel && importResult && (
            <InvoiceMultiSelectPanel
              invoices={showInvoicePanel.type === 'sale' ? importResult.sales : importResult.purchases}
              invoiceType={showInvoicePanel.type}
              onSend={(ids) => {
                setShowInvoicePanel(null)
                const idList = ids.join(', ')
                setInput(`我选了这些发票: ${idList}`)
              }}
              onClose={() => setShowInvoicePanel(null)}
            />
          )}

          {lastDiff && <NineBoxDiffTable erpBoxes={lastDiff.erp} taxiBoxes={lastDiff.taxi} delta={lastDiff.delta} />}

          {messages.map((msg, idx) => {
            // 仅最后一个 assistant 气泡显示 activeStep 指示器(避免旧气泡继续"spinning")
            const isLastAssistant =
              msg.role === 'assistant' &&
              idx === messages.findLastIndex((m) => m.role === 'assistant')
            return (
              <div
                key={msg.id}
                className={`flex gap-3 ${
                  msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'
                }`}
              >
                {/* Avatar */}
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                    msg.role === 'user'
                      ? 'bg-primary/20 text-primary'
                      : msg.role === 'assistant'
                      ? 'bg-secondary/20 text-secondary'
                      : 'bg-bg-elevated text-fg-dim'
                  }`}
                >
                  {getMessageIcon(msg.role)}
                </div>

                {/* Content */}
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${getMessageStyle(
                    msg.role
                  )}`}
                >
                  {msg.role === 'assistant' ? (
                    <div className="space-y-2">
                      {/* 1. 思考 + 工具调用,内嵌在气泡里(在文本之上) */}
                      {msg.activities && msg.activities.length > 0 && (
                        <AgentActivityPanel
                          embedded
                          activities={msg.activities}
                          thinkingData={
                            msg.thinking
                              ? {
                                  [msg.id]: {
                                    content: msg.thinking,
                                    isFinished: !!msg.thinkingFinished,
                                  },
                                }
                              : {}
                          }
                          activeStep={isLastAssistant ? activeStep : null}
                        />
                      )}
                      {/* 2. 文本内容(光标在 streaming 时显示) */}
                      {msg.content ? (
                        <Markdown content={msg.content} streaming={msg.status === 'streaming'} />
                      ) : msg.status === 'streaming' ? (
                        /* 无文本但仍在 streaming:显示光标(通常发生在 REASONING 阶段或刚到 TEXT 还没收到 content) */
                        <span className="inline-block w-2 h-4 bg-primary animate-pulse rounded-sm" />
                      ) : null}
                      {msg.status === 'streaming' && msg.content && (
                        <span className="inline-block w-2 h-4 ml-1 bg-primary animate-pulse rounded-sm" />
                      )}
                    </div>
                  ) : msg.error ? (
                    // 结构化错误(RUN_ERROR 事件 / 流中断) → ErrorCard 渲染
                    <ErrorCard error={msg.error} fallbackText={msg.content} />
                  ) : (
                    <span className="whitespace-pre-wrap">{msg.content}</span>
                  )}
                </div>
              </div>
            )
          })}

          {isLoading && (
            messages[messages.length - 1]?.role !== 'assistant' ||
            (messages[messages.length - 1]?.role === 'assistant' &&
             !messages[messages.length - 1]?.content)
          ) && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-secondary/20 text-secondary flex items-center justify-center shrink-0">
                <SparklesIcon className="w-4 h-4 animate-pulse" />
              </div>
              <div className="bg-bg-elevated border border-border rounded-2xl px-4 py-3">
                <div className="flex gap-1.5">
                  <div className="w-2 h-2 bg-fg-dim rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <div className="w-2 h-2 bg-fg-dim rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <div className="w-2 h-2 bg-fg-dim rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* 跳到底部:用户上滑离底时浮现,点击恢复贴底自动下滑 */}
        {!atBottomUi && (
          <button
            onClick={() => scrollToBottom(true)}
            className="absolute bottom-24 left-1/2 -translate-x-1/2 z-10 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-bg-surface border border-border shadow-lg text-xs text-fg-muted hover:text-fg hover:bg-bg-elevated transition-colors fade-in"
            aria-label="跳到最新消息"
          >
            <ChevronDownIcon className="w-4 h-4" />
            最新消息
          </button>
        )}

        {/* Input */}
        <div className="border-t border-border bg-bg-surface px-4 py-3">
          {/* Quick Actions */}
          <div className="flex items-center gap-2 max-w-3xl mx-auto mb-2">
            <button
              onClick={handleAnalyzeCurrentCase}
              disabled={!currentCase || isLoading || sampleDataLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-accent/10 text-accent rounded-lg hover:bg-accent/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title={currentCase ? `分析 ${currentCase.title} 的 ERP 数据` : '请先在 Dashboard 选择 Case'}
            >
              {sampleDataLoading ? (
                <ArrowPathIcon className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <BuildingOfficeIcon className="w-3.5 h-3.5" />
              )}
              {currentCase ? '分析当前帐套数据' : '请先选择 Case'}
            </button>
            {currentCase ? (
              <span className="text-[11px] text-fg-dim">
                ✅ 已加载: {currentCase.title}
              </span>
            ) : (
              <span className="text-[11px] text-fg-dim">
                ⚠️ 未加载 Case — 请先在 Dashboard 选择一个 Demo Case
              </span>
            )}
            {import.meta.env.DEV && (
              <button
                onClick={() => setShowInvoicePanel({ type: 'sale' })}
                className="btn btn-sm btn-ghost"
                disabled={!importResult}
                title="开发演示用: 打开发票多选面板"
              >
                📋 选择发票 (dev)
              </button>
            )}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              handleSend()
            }}
            className="flex items-end gap-2 max-w-3xl mx-auto"
          >
            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入消息，按 Enter 发送..."
                rows={1}
                className="w-full bg-bg-elevated border border-border rounded-xl px-4 py-3 pr-12 text-sm text-fg placeholder:text-fg-dim resize-none focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-all"
                style={{ minHeight: '44px', maxHeight: '120px' }}
                disabled={isLoading}
              />
              {sessionId && (
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] text-fg-dim bg-bg-surface px-1.5 py-0.5 rounded">
                  {sessionId.slice(0, 6)}...
                </span>
              )}
            </div>
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="shrink-0 w-11 h-11 bg-primary text-on-primary rounded-xl flex items-center justify-center hover:bg-primary-hover disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm hover:shadow-md active:scale-95"
            >
              {isLoading ? (
                <ArrowPathIcon className="w-5 h-5 animate-spin" />
              ) : (
                <PaperAirplaneIcon className="w-5 h-5" />
              )}
            </button>
          </form>
          <p className="text-center text-[11px] text-fg-dim mt-2">
            TaxAgent 使用 Claude Agent SDK 驱动 · 支持 HMRC MTD for VAT API
          </p>
        </div>
      </div>
    </div>
  )
}
