/**
 * ErrorCard — 替代聊天流里那个干瘪的 "❌ network error" 字符串。
 *
 * 设计:
 *  - 顶部红条:kind 图标 + 短标题(给人立刻看的)
 *  - hint(mono 字体的建议行)
 *  - "Details ▾" 折叠:message 全文 / requestId / raw detail
 *  - "Copy" 按钮:一键把全部内容贴到剪贴板,方便贴到工单 / Slack
 *
 * 优先消费结构化 payload(后端 RUN_ERROR 事件或 /api/agent/chat 启动期错误):
 *   { kind, hint, message, requestId, stage? }
 * 旧文本("❌ ...")也会被吸进来,只是没法展示 hint。
 */
import { useState } from 'react'
import {
  ExclamationTriangleIcon,
  WifiIcon,
  KeyIcon,
  ClockIcon,
  CheckBadgeIcon,
  ServerStackIcon,
  XCircleIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ClipboardDocumentIcon,
  ClipboardDocumentCheckIcon,
} from '@heroicons/react/24/outline'

export interface ErrorPayload {
  /** 'network' | 'auth' | 'timeout' | 'validation' | 'rate_limit' | 'internal' | 'unknown' */
  kind?: string
  /** 一行"人话"指引 */
  hint?: string
  /** 异常全文(如 "AuthenticationError: 401 ...") */
  message?: string
  /** 后端 request_id,贴工单时一起带 */
  requestId?: string
  /** 哪一步崩了(如 "calculate_vat" / "submit_vat_return") */
  stage?: string
  /** 任何额外 JSON,折叠区域里展开 */
  raw?: unknown
}

interface ErrorCardProps {
  error: ErrorPayload
  /** 退化路径:旧的 "❌ xxx" 字符串也能传进来 */
  fallbackText?: string
}

const KIND_META: Record<string, { icon: React.ElementType; label: string; tone: string }> = {
  network:     { icon: WifiIcon,            label: '网络错误',   tone: 'text-amber-600' },
  auth:        { icon: KeyIcon,             label: '鉴权失败',   tone: 'text-red-600' },
  timeout:     { icon: ClockIcon,           label: '请求超时',   tone: 'text-amber-600' },
  validation:  { icon: CheckBadgeIcon,      label: '参数校验',   tone: 'text-orange-600' },
  rate_limit:  { icon: ClockIcon,           label: '频率限制',   tone: 'text-amber-600' },
  internal:    { icon: ServerStackIcon,     label: '内部错误',   tone: 'text-red-600' },
  unknown:     { icon: XCircleIcon,         label: '错误',       tone: 'text-red-600' },
}

export default function ErrorCard({ error, fallbackText }: ErrorCardProps) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  const kind = error.kind && KIND_META[error.kind] ? error.kind : 'unknown'
  const meta = KIND_META[kind]
  const Icon = meta.icon

  const message = error.message || fallbackText || '未知错误'
  const title = error.hint ? error.hint : message

  const copyText = JSON.stringify(
    {
      kind: error.kind,
      hint: error.hint,
      message: error.message,
      requestId: error.requestId,
      stage: error.stage,
      raw: error.raw,
      fallbackText,
    },
    null,
    2,
  )

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(copyText)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* 旧浏览器 / 非安全上下文,放弃 */
    }
  }

  return (
    <div className="space-y-1.5">
      {/* 红条:图标 + 标题 + Copy */}
      <div className="flex items-start gap-2">
        <Icon className={`w-4 h-4 mt-0.5 shrink-0 ${meta.tone}`} />
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-medium ${meta.tone}`}>{meta.label}</p>
          <p className="text-xs text-fg-muted mt-0.5 break-words">{title}</p>
        </div>
        <button
          onClick={handleCopy}
          className="shrink-0 p-1 rounded text-fg-dim hover:text-fg hover:bg-error/10 transition-colors"
          title="复制错误详情"
          aria-label="复制错误详情"
        >
          {copied ? (
            <ClipboardDocumentCheckIcon className="w-4 h-4 text-green-600" />
          ) : (
            <ClipboardDocumentIcon className="w-4 h-4" />
          )}
        </button>
      </div>

      {/* 折叠 details */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1 text-[11px] text-fg-dim hover:text-fg"
      >
        {open ? <ChevronDownIcon className="w-3 h-3" /> : <ChevronRightIcon className="w-3 h-3" />}
        {open ? '收起' : '详情'}
      </button>

      {open && (
        <div className="mt-1 space-y-1.5 text-[11px] font-mono leading-relaxed">
          {error.requestId && (
            <div className="flex gap-2">
              <span className="text-fg-dim shrink-0">request_id</span>
              <span className="text-fg break-all">{error.requestId}</span>
            </div>
          )}
          {error.stage && (
            <div className="flex gap-2">
              <span className="text-fg-dim shrink-0">stage</span>
              <span className="text-fg break-all">{error.stage}</span>
            </div>
          )}
          {message && message !== title && (
            <div className="flex gap-2">
              <span className="text-fg-dim shrink-0">message</span>
              <span className="text-fg break-all whitespace-pre-wrap">{message}</span>
            </div>
          )}
          {error.raw != null && (
            <pre className="mt-1 p-2 bg-error/5 rounded text-fg-muted overflow-x-auto">
              {typeof error.raw === 'string' ? error.raw : JSON.stringify(error.raw, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}
