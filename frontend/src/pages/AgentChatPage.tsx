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
  ChatBubbleOvalLeftIcon,
  BuildingOfficeIcon,
  MagnifyingGlassIcon,
  ChartBarIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline'
import QuickActionButton from '../components/QuickActionButton'
import InvoiceMultiSelectPanel from '../components/InvoiceMultiSelectPanel'
import NineBoxDiffTable from '../components/NineBoxDiffTable'
import ThinkingBlock from '../components/ThinkingBlock'
import Markdown from '../components/Markdown'
import { useDemoStore } from '../stores/demoStore'
import { casePresets } from '../data/casePresets'
import { api } from '../api/client'
import type { ImportResult, ReconciliationDelta, ERPNineBox } from '../types'
import { consumeAguiStream, type BaseEvent } from '../api/agentStream'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
  timestamp: Date
  status?: 'sending' | 'streaming' | 'done' | 'error'
  /** 扩展思考（extended thinking）流式累积。 */
  thinking?: string
}

/**
 * AG-UI 工具调用卡片：渲染 TOOL_CALL_START/ARGS/END/RESULT 序列。
 * 折叠显示 args + result（可能较大 JSON）。
 */
interface ToolCallCard {
  toolCallId: string
  toolName: string
  args: string
  result?: string
  argsOpen: boolean
  resultOpen: boolean
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

function buildWelcomeMessage(caseTitle?: string, hasErpData?: boolean): ChatMessage {
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
      ? 'ERP 数据已就绪 — 使用下方 Quick Action 一键开始。'
      : 'ERP 数据正在加载中…稍候即可使用 Quick Action。'
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
    buildWelcomeMessage(currentCase?.title, !!buffer?.erpData),
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string>('')
  const [sampleData, setSampleData] = useState<Record<string, unknown> | null>(null)
  const [sampleDataLoading, setSampleDataLoading] = useState(false)
  const [showInvoicePanel, setShowInvoicePanel] = useState<{ type: 'sale' | 'purchase' } | null>(null)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [lastDiff, _setLastDiff] = useState<{ erp: ERPNineBox; taxi: ERPNineBox; delta: ReconciliationDelta } | null>(null)
  // AG-UI tool call 卡片（per-run），UI 在每条 assistant 消息下方渲染
  const [toolCalls, setToolCalls] = useState<ToolCallCard[]>([])
  // 思考段（extended thinking）状态：
  //   - thinkingFinishedIds: 哪些 messageId 的 REASONING_END 已经到达
  //   - thinkingCollapsedByUser: 用户手动 toggle 的覆盖（session 内有效）
  const [thinkingFinishedIds, setThinkingFinishedIds] = useState<Set<string>>(new Set())
  const [thinkingCollapsedByUser, setThinkingCollapsedByUser] = useState<Record<string, boolean>>({})

  // 当前活跃的 assistant 消息 id（用 ref 避免 stale closure，
  // 不依赖 messages 数组查找）
  const assistantIdRef = useRef<string>('')
  // AbortController 引用，组件卸载或重置时取消正在进行的流
  const abortRef = useRef<AbortController | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

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

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

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

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
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
  //   - toolCalls 数组存放 TOOL_CALL_START 起的卡片（直到 RUN_FINISHED 重置）
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
    setToolCalls([])
    // 清掉上一轮的 thinkingFinishedIds（每轮 run 重新计算）；
    // thinkingCollapsedByUser 保留 — 那是"用户偏好"级别的 session 记忆。
    setThinkingFinishedIds(new Set())
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
          // 思考可能在 text 之前到达：先建一个空的 assistant 占位，
          // 后续 TEXT_MESSAGE_START 若用同 id，会复用此条。
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
            prev.map((m) =>
              m.id === mid ? { ...m, thinking: (m.thinking || '') + delta } : m
            )
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
          setThinkingFinishedIds((prev) => {
            const s = new Set(prev)
            s.add(mid)
            return s
          })
          break
        }
        case 'RUN_STARTED': {
          const tid = String(event.threadId || '')
          const rid = String(event.runId || '')
          if (tid) setSessionId(tid)
          // 重置本 run 的 tool call 卡片（新一轮 run 开始时清掉上一轮）
          setToolCalls([])
          // 用一个空 assistant 消息占位，让 user 看到"正在思考"动画
          if (!assistantIdRef.current) {
            const id = generateId()
            assistantIdRef.current = id
            setMessages((prev) => [
              ...prev,
              {
                id,
                role: 'assistant',
                content: '',
                timestamp: new Date(),
                status: 'streaming',
              },
            ])
          }
          // log 一下 run id（dev 用）
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
          if (!assistantIdRef.current || assistantIdRef.current !== mid) {
            assistantIdRef.current = mid
            setMessages((prev) => [
              ...prev,
              {
                id: mid,
                role: 'assistant',
                content: '',
                timestamp: new Date(),
                status: 'streaming',
              },
            ])
          }
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
          setToolCalls((prev) => [
            ...prev,
            {
              toolCallId: tcid,
              toolName: name,
              args: '',
              argsOpen: true,
              resultOpen: false,
            },
          ])
          scrollToBottom()
          break
        }
        case 'TOOL_CALL_ARGS': {
          const tcid = String(event.toolCallId || '')
          const delta = String(event.delta || '')
          if (!tcid) break
          setToolCalls((prev) =>
            prev.map((c) =>
              c.toolCallId === tcid ? { ...c, args: c.args + delta } : c
            )
          )
          break
        }
        case 'TOOL_CALL_END': {
          // 工具参数收尾：args 默认折叠，让 result 突出
          const tcid = String(event.toolCallId || '')
          if (!tcid) break
          setToolCalls((prev) =>
            prev.map((c) =>
              c.toolCallId === tcid ? { ...c, argsOpen: false } : c
            )
          )
          break
        }
        case 'TOOL_CALL_RESULT': {
          const tcid = String(event.toolCallId || '')
          const content = String(event.content || '')
          if (!tcid) break
          setToolCalls((prev) =>
            prev.map((c) =>
              c.toolCallId === tcid
                ? { ...c, result: content, resultOpen: true }
                : c
            )
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
          // tool call 卡片保留在 UI 上供用户查看；下次 RUN_STARTED 会清
          break
        }
        case 'RUN_ERROR': {
          const msg = String(event.message || 'Agent 错误')
          setMessages((prev) => [
            ...prev,
            {
              id: generateId(),
              role: 'system',
              content: `❌ ${msg}`,
              timestamp: new Date(),
              status: 'error',
            },
          ])
          setIsLoading(false)
          assistantIdRef.current = ''
          break
        }
        // STEP_STARTED / STEP_FINISHED / STATE_SNAPSHOT / 等暂不渲染
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

    try {
      const response = await fetch(
        `${API_BASE}/api/agent/chat?session_id=${sid}&message=${encodeURIComponent(text)}`,
        { method: 'POST', signal: controller.signal }
      )
      await consumeAguiStream(response, handleAguiEvent, { signal: controller.signal })
    } catch (err) {
      if ((err as Error).name === 'AbortError') return
      const errorMsg = err instanceof Error ? err.message : '连接失败'
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: 'system',
          content: `❌ ${errorMsg}`,
          timestamp: new Date(),
          status: 'error',
        },
      ])
      setIsLoading(false)
      resetRunState()
    }
  }

  // ── 发送带原始业务数据的消息 ──
  const sendWithRawData = useCallback(async (message: string, data: Record<string, unknown>) => {
    const text = message.trim()
    if (!text || isLoading) return

    setIsLoading(true)
    resetRunState()

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
        content: text + '\n[已附加 TechFlow Distribution Ltd Q1 原始业务数据]',
        timestamp: new Date(),
        status: 'done',
      },
    ])

    try {
      const response = await fetch(
        `${API_BASE}/api/agent/chat?session_id=${sid}&message=${encodeURIComponent(text)}&raw_data=${encodeURIComponent(JSON.stringify(data))}`,
        { method: 'POST', signal: controller.signal }
      )
      await consumeAguiStream(response, handleAguiEvent, { signal: controller.signal })
    } catch (err) {
      if ((err as Error).name === 'AbortError') return
      const errorMsg = err instanceof Error ? err.message : '连接失败'
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: 'system',
          content: `❌ ${errorMsg}`,
          timestamp: new Date(),
          status: 'error',
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
    setMessages([buildWelcomeMessage(currentCase?.title, !!buffer?.erpData)])
    setSessionId('')
    setIsLoading(false)
    setSampleData(null)
  }

  // 优先用 buffer 里已经准备好的 case 数据,没有 case 时回退到 loadSampleData
  const handleAnalyzeCurrentCase = async () => {
    const data = (importResult as unknown as Record<string, unknown> | null) ?? (buffer?.erpData as unknown as Record<string, unknown> | null) ?? null
    if (data) {
      // eslint-disable-next-line react-hooks/exhaustive-deps
      sendWithRawData('请分析这些数据并帮我报税', data)
      return
    }
    await loadSampleData()
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
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: 'system',
            content: '❌ 加载示例数据失败，请检查网络连接',
            timestamp: new Date(),
            status: 'error',
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
      <div className="flex-1 flex flex-col min-w-0">
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
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
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

          {messages.map((msg) => (
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
                {/* Assistant 消息：上方挂载折叠的思考段（如果存在）。
                    注意：放在 bubble 内（而不是外层）— 这样 wrap 不会让
                    thinking 与 user 的回复区隔开。 */}
                {msg.role === 'assistant' && (msg.thinking || '').length > 0 && (
                  <ThinkingBlock
                    content={msg.thinking || ''}
                    isStreaming={msg.status === 'streaming' && !thinkingFinishedIds.has(msg.id)}
                    defaultCollapsed={thinkingFinishedIds.has(msg.id)}
                    onUserToggle={(c) =>
                      setThinkingCollapsedByUser((p) => ({ ...p, [msg.id]: c }))
                    }
                  />
                )}

                {msg.role === 'assistant' ? (
                  msg.content ? (
                    <Markdown content={msg.content} streaming={msg.status === 'streaming'} />
                  ) : (
                    <span className="text-fg-muted">…</span>
                  )
                ) : (
                  <span className="whitespace-pre-wrap">{msg.content}</span>
                )}
                {msg.status === 'streaming' && msg.content && (
                  <span className="inline-block w-2 h-4 ml-1 bg-primary animate-pulse rounded-sm" />
                )}
              </div>
            </div>
          ))}

          {/* ── AG-UI tool call 卡片：本轮 run 期间的 TOOL_CALL_* 序列 ── */}
          {toolCalls.length > 0 && (
            <div className="space-y-2 fade-in">
              {toolCalls.map((tc) => (
                <div
                  key={tc.toolCallId}
                  className="ml-11 bg-accent-muted border border-accent/20 rounded-xl p-3 text-xs"
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <WrenchIcon className="w-3.5 h-3.5 text-accent shrink-0" />
                    <span className="font-semibold text-accent">{tc.toolName}</span>
                    {!tc.result && (
                      <span className="text-fg-dim animate-pulse">执行中...</span>
                    )}
                  </div>

                  {tc.args && (
                    <details
                      open={tc.argsOpen}
                      onToggle={(e) => {
                        const open = (e.target as HTMLDetailsElement).open
                        setToolCalls((prev) =>
                          prev.map((c) =>
                            c.toolCallId === tc.toolCallId ? { ...c, argsOpen: open } : c
                          )
                        )
                      }}
                      className="mb-1"
                    >
                      <summary className="cursor-pointer text-fg-muted hover:text-fg select-none flex items-center gap-1">
                        {(tc.argsOpen ? <ChevronUpIcon className="w-3 h-3" /> : <ChevronDownIcon className="w-3 h-3" />)}
                        参数
                      </summary>
                      <pre className="mt-1.5 p-2 bg-bg-elevated/60 rounded text-[11px] font-mono text-fg overflow-x-auto whitespace-pre-wrap break-all">
                        {(() => {
                          // 尝试把 JSON 美化；非 JSON 也直接显示
                          try { return JSON.stringify(JSON.parse(tc.args), null, 2) }
                          catch { return tc.args }
                        })()}
                      </pre>
                    </details>
                  )}

                  {tc.result !== undefined && (
                    <details
                      open={tc.resultOpen}
                      onToggle={(e) => {
                        const open = (e.target as HTMLDetailsElement).open
                        setToolCalls((prev) =>
                          prev.map((c) =>
                            c.toolCallId === tc.toolCallId ? { ...c, resultOpen: open } : c
                          )
                        )
                      }}
                    >
                      <summary className="cursor-pointer text-fg-muted hover:text-fg select-none flex items-center gap-1">
                        {(tc.resultOpen ? <ChevronUpIcon className="w-3 h-3" /> : <ChevronDownIcon className="w-3 h-3" />)}
                        结果
                      </summary>
                      <pre className="mt-1.5 p-2 bg-bg-elevated/60 rounded text-[11px] font-mono text-fg overflow-x-auto whitespace-pre-wrap break-all max-h-60 overflow-y-auto">
                        {(() => {
                          try { return JSON.stringify(JSON.parse(tc.result || ''), null, 2) }
                          catch { return tc.result || '' }
                        })()}
                      </pre>
                    </details>
                  )}
                </div>
              ))}
            </div>
          )}

          {isLoading && messages[messages.length - 1]?.role !== 'assistant' && (
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

        {/* Input */}
        <div className="border-t border-border bg-bg-surface px-4 py-3">
          {/* Quick Actions */}
          <div className="flex items-center gap-2 max-w-3xl mx-auto mb-2">
            <button
              onClick={handleAnalyzeCurrentCase}
              disabled={isLoading || sampleDataLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-accent/10 text-accent rounded-lg hover:bg-accent/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title={currentCase ? `分析 ${currentCase.title} 的 ERP 数据` : '加载示例数据(未选择 Case)'}
            >
              {sampleDataLoading ? (
                <ArrowPathIcon className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <BuildingOfficeIcon className="w-3.5 h-3.5" />
              )}
              {currentCase ? '分析当前帐套数据' : '加载示例数据'}
            </button>
            {currentCase ? (
              <span className="text-[11px] text-fg-dim">
                ✅ 已加载: {currentCase.title}
              </span>
            ) : (
              <span className="text-[11px] text-fg-dim">
                ⚠️ 未加载 Case,示例数据可能与预期不一致
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
