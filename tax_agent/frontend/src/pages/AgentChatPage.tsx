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
} from '@heroicons/react/24/outline'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'tool' | 'system'
  content: string
  timestamp: Date
  status?: 'sending' | 'streaming' | 'done' | 'error'
}

interface HistorySession {
  session_id: string
  created_at: string
  updated_at: string
  message_count: number
  preview: string
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8765'

function generateId() {
  return Math.random().toString(36).substring(2, 10)
}

function formatTime(iso: string) {
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function AgentChatPage() {
  const [searchParams] = useSearchParams()
  const initialMessage = searchParams.get('message') || ''

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content: '您好！我是 TaxAgent 智能报税助手。\n\n我可以帮您：\n• 查询 HMRC 待申报义务\n• 自动计算 VAT Return（9-Box）\n• 验证申报数据合规性\n• 提交 VAT Return 至 HMRC\n• 查询已提交的申报\n\n请告诉我您需要什么帮助？',
      timestamp: new Date(),
      status: 'done',
    },
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string>('')
  const [connectionMode, setConnectionMode] = useState<'sse' | 'ws'>('ws')
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const [sampleData, setSampleData] = useState<Record<string, unknown> | null>(null)
  const [sampleDataLoading, setSampleDataLoading] = useState(false)

  // ── History Sidebar State ──
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historySessions, setHistorySessions] = useState<HistorySession[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Probe the WebSocket on mount so the status dot reflects reality
  // (otherwise the UI says "未连接" until the user sends the first message).
  useEffect(() => {
    if (connectionMode !== 'ws') return
    let cancelled = false
    const ws = new WebSocket(`${API_BASE.replace('http', 'ws')}/api/agent/ws/chat`)
    wsRef.current = ws
    ws.onopen = () => { if (!cancelled) setIsConnected(true) }
    ws.onerror = () => { if (!cancelled) setIsConnected(false) }
    ws.onclose = () => {
      if (!cancelled) {
        setIsConnected(false)
        if (wsRef.current === ws) wsRef.current = null
      }
    }
    return () => {
      cancelled = true
      ws.close()
      if (wsRef.current === ws) wsRef.current = null
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectionMode])

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
        id: 'welcome',
        role: 'assistant',
        content: '对话已加载。继续输入以继续对话。',
        timestamp: new Date(),
        status: 'done',
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

  // ── SSE Mode ──
  const sendViaSSE = async (message: string) => {
    const sid = sessionId || generateId()
    if (!sessionId) setSessionId(sid)

    abortRef.current = new AbortController()

    try {
      const response = await fetch(
        `${API_BASE}/api/agent/chat?session_id=${sid}&message=${encodeURIComponent(message)}`,
        {
          method: 'POST',
          signal: abortRef.current.signal,
        }
      )

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let assistantMessageId = ''

      if (!reader) throw new Error('No response body')

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))

              if (data.done) {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMessageId ? { ...m, status: 'done' } : m
                  )
                )
                setIsLoading(false)
                continue
              }

              const text = data.chunk || ''

              if (!assistantMessageId) {
                assistantMessageId = generateId()
                setMessages((prev) => [
                  ...prev,
                  {
                    id: assistantMessageId,
                    role: 'assistant',
                    content: text,
                    timestamp: new Date(),
                    status: 'streaming',
                  },
                ])
              } else {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMessageId
                      ? { ...m, content: m.content + text }
                      : m
                  )
                )
              }

              scrollToBottom()
            } catch {
              // Ignore parse errors for incomplete chunks
            }
          }
        }
      }
    } catch (err) {
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
    }
  }

  // ── WebSocket Mode ──
  const sendViaWebSocket = (message: string) => {
    const sid = sessionId || generateId()
    if (!sessionId) setSessionId(sid)

    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      const ws = new WebSocket(
        `${API_BASE.replace('http', 'ws')}/api/agent/ws/chat`
      )
      wsRef.current = ws

      let assistantMessageId = ''

      ws.onopen = () => {
        setIsConnected(true)
        ws.send(
          JSON.stringify({
            session_id: sid,
            message,
          })
        )
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          if (data.type === 'session') {
            setSessionId(data.session_id)
          } else if (data.type === 'chunk') {
            const text = data.content || ''

            if (!assistantMessageId) {
              assistantMessageId = generateId()
              setMessages((prev) => [
                ...prev,
                {
                  id: assistantMessageId,
                  role: 'assistant',
                  content: text,
                  timestamp: new Date(),
                  status: 'streaming',
                },
              ])
            } else {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMessageId
                    ? { ...m, content: m.content + text }
                    : m
                )
              )
            }

            scrollToBottom()
          } else if (data.type === 'done') {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId ? { ...m, status: 'done' } : m
              )
            )
            setIsLoading(false)
          } else if (data.type === 'error') {
            setMessages((prev) => [
              ...prev,
              {
                id: generateId(),
                role: 'system',
                content: `❌ ${data.error || '未知错误'}`,
                timestamp: new Date(),
                status: 'error',
              },
            ])
            setIsLoading(false)
          }
        } catch {
          // Ignore parse errors
        }
      }

      ws.onerror = () => {
        setIsConnected(false)
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: 'system',
            content: '❌ WebSocket 连接失败，请检查后端服务是否运行',
            timestamp: new Date(),
            status: 'error',
          },
        ])
        setIsLoading(false)
      }

      ws.onclose = () => {
        setIsConnected(false)
        wsRef.current = null
      }
    } else {
      wsRef.current.send(
        JSON.stringify({
          session_id: sid,
          message,
        })
      )
    }
  }

  const handleSend = async (overrideMessage?: string) => {
    const text = overrideMessage || input.trim()
    if (!text || isLoading) return

    if (!overrideMessage) setInput('')
    setIsLoading(true)

    // Add user message
    const userMsgId = generateId()
    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        role: 'user',
        content: text,
        timestamp: new Date(),
        status: 'done',
      },
    ])

    if (connectionMode === 'sse') {
      await sendViaSSE(text)
    } else {
      sendViaWebSocket(text)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const clearChat = () => {
    wsRef.current?.close()
    wsRef.current = null
    abortRef.current?.abort()
    setMessages([
      {
        id: 'welcome',
        role: 'assistant',
        content: '您好！我是 TaxAgent 智能报税助手。\n\n我可以帮您：\n• 分析原始企业发票数据并自动计算 VAT Return\n• 查询 HMRC 待申报义务\n• 验证申报数据合规性\n• 提交 VAT Return 至 HMRC\n• 查询已提交的申报\n\n请告诉我您需要什么帮助？',
        timestamp: new Date(),
        status: 'done',
      },
    ])
    setSessionId('')
    setIsLoading(false)
    setIsConnected(false)
    setSampleData(null)
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

  // ── Send with Raw Business Data ──
  const sendWithRawData = (message: string, data: Record<string, unknown>) => {
    const text = message.trim()
    if (!text || isLoading) return

    setIsLoading(true)
    const sid = sessionId || generateId()
    if (!sessionId) setSessionId(sid)

    // Add user message
    const userMsgId = generateId()
    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        role: 'user',
        content: text + '\n[已附加 TechFlow Distribution Ltd Q1 原始业务数据]',
        timestamp: new Date(),
        status: 'done',
      },
    ])

    if (connectionMode === 'sse') {
      sendViaSSEWithData(text, data, sid)
    } else {
      sendViaWebSocketWithData(text, data, sid)
    }
  }

  // ── WebSocket with Raw Data ──
  const sendViaWebSocketWithData = (message: string, data: Record<string, unknown>, sid: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      const ws = new WebSocket(
        `${API_BASE.replace('http', 'ws')}/api/agent/ws/chat`
      )
      wsRef.current = ws

      let assistantMessageId = ''

      ws.onopen = () => {
        setIsConnected(true)
        ws.send(
          JSON.stringify({
            session_id: sid,
            message,
            data,
          })
        )
      }

      ws.onmessage = (event) => {
        try {
          const wsData = JSON.parse(event.data)

          if (wsData.type === 'session') {
            setSessionId(wsData.session_id)
          } else if (wsData.type === 'chunk') {
            const text = wsData.content || ''
            if (!assistantMessageId) {
              assistantMessageId = generateId()
              setMessages((prev) => [
                ...prev,
                {
                  id: assistantMessageId,
                  role: 'assistant',
                  content: text,
                  timestamp: new Date(),
                  status: 'streaming',
                },
              ])
            } else {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMessageId
                    ? { ...m, content: m.content + text }
                    : m
                )
              )
            }
            scrollToBottom()
          } else if (wsData.type === 'done') {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId ? { ...m, status: 'done' } : m
              )
            )
            setIsLoading(false)
          } else if (wsData.type === 'error') {
            setMessages((prev) => [
              ...prev,
              {
                id: generateId(),
                role: 'system',
                content: `❌ ${wsData.error || '未知错误'}`,
                timestamp: new Date(),
                status: 'error',
              },
            ])
            setIsLoading(false)
          }
        } catch {
          // ignore
        }
      }

      ws.onerror = () => {
        setIsConnected(false)
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: 'system',
            content: '❌ WebSocket 连接失败，请检查后端服务是否运行',
            timestamp: new Date(),
            status: 'error',
          },
        ])
        setIsLoading(false)
      }

      ws.onclose = () => {
        setIsConnected(false)
        wsRef.current = null
      }
    } else {
      wsRef.current.send(
        JSON.stringify({
          session_id: sid,
          message,
          data,
        })
      )
    }
  }

  // ── SSE with Raw Data ──
  const sendViaSSEWithData = async (message: string, data: Record<string, unknown>, sid: string) => {
    abortRef.current = new AbortController()

    try {
      const response = await fetch(
        `${API_BASE}/api/agent/chat?session_id=${sid}&message=${encodeURIComponent(message)}&raw_data=${encodeURIComponent(JSON.stringify(data))}`,
        {
          method: 'POST',
          signal: abortRef.current.signal,
        }
      )

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let assistantMessageId = ''

      if (!reader) throw new Error('No response body')

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const eventData = JSON.parse(line.slice(6))

              if (eventData.done) {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMessageId ? { ...m, status: 'done' } : m
                  )
                )
                setIsLoading(false)
                continue
              }

              const text = eventData.chunk || ''

              if (!assistantMessageId) {
                assistantMessageId = generateId()
                setMessages((prev) => [
                  ...prev,
                  {
                    id: assistantMessageId,
                    role: 'assistant',
                    content: text,
                    timestamp: new Date(),
                    status: 'streaming',
                  },
                ])
              } else {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantMessageId
                      ? { ...m, content: m.content + text }
                      : m
                  )
                )
              }

              scrollToBottom()
            } catch {
              // Ignore parse errors for incomplete chunks
            }
          }
        }
      }
    } catch (err) {
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
                <span
                  className={`inline-block w-2 h-2 rounded-full ${
                    isConnected || connectionMode === 'sse'
                      ? 'bg-success'
                      : 'bg-fg-dim'
                  }`}
                />
                <span className="text-xs text-fg-dim">
                  {connectionMode === 'ws'
                    ? isConnected
                      ? 'WebSocket 已连接'
                      : 'WebSocket 未连接'
                    : 'SSE 模式'}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Connection mode toggle */}
            <div className="flex items-center bg-bg-elevated rounded-md p-0.5">
              <button
                onClick={() => setConnectionMode('ws')}
                className={`px-2.5 py-1 text-xs rounded font-medium transition-colors ${
                  connectionMode === 'ws'
                    ? 'bg-bg-surface text-fg shadow-sm'
                    : 'text-fg-dim hover:text-fg'
                }`}
              >
                WebSocket
              </button>
              <button
                onClick={() => setConnectionMode('sse')}
                className={`px-2.5 py-1 text-xs rounded font-medium transition-colors ${
                  connectionMode === 'sse'
                    ? 'bg-bg-surface text-fg shadow-sm'
                    : 'text-fg-dim hover:text-fg'
                }`}
              >
                SSE
              </button>
            </div>

            <button
              onClick={clearChat}
              className="p-2 text-fg-dim hover:text-fg hover:bg-bg-elevated rounded-md transition-colors"
              title="重置对话"
            >
              <ArrowPathIcon className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">
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
                className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${getMessageStyle(
                  msg.role
                )}`}
              >
                {msg.content}
                {msg.status === 'streaming' && (
                  <span className="inline-block w-2 h-4 ml-1 bg-primary animate-pulse rounded-sm" />
                )}
              </div>
            </div>
          ))}

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
              onClick={loadSampleData}
              disabled={isLoading || sampleDataLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-accent/10 text-accent rounded-lg hover:bg-accent/20 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              title="加载 TechFlow Distribution Ltd 2026 Q1 真实数据"
            >
              {sampleDataLoading ? (
                <ArrowPathIcon className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <BuildingOfficeIcon className="w-3.5 h-3.5" />
              )}
              {sampleData ? '重新分析 TechFlow Q1 数据' : '加载 TechFlow Q1 真实数据'}
            </button>
            {sampleData && (
              <span className="text-[11px] text-fg-dim">
                ✅ 已加载: TechFlow Distribution Ltd 2026 Q1
              </span>
            )}
          </div>
          <div className="flex items-end gap-2 max-w-3xl mx-auto">
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
              onClick={() => handleSend()}
              disabled={isLoading || !input.trim()}
              className="shrink-0 w-11 h-11 bg-primary text-on-primary rounded-xl flex items-center justify-center hover:bg-primary-hover disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-sm hover:shadow-md active:scale-95"
            >
              {isLoading ? (
                <ArrowPathIcon className="w-5 h-5 animate-spin" />
              ) : (
                <PaperAirplaneIcon className="w-5 h-5" />
              )}
            </button>
          </div>
          <p className="text-center text-[11px] text-fg-dim mt-2">
            TaxAgent 使用 Claude Agent SDK 驱动 · 支持 HMRC MTD for VAT API
          </p>
        </div>
      </div>
    </div>
  )
}
