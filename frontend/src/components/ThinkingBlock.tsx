/**
 * ThinkingBlock — 折叠展示模型的扩展思考（extended thinking）。
 *
 * 生命周期：
 *   - streaming 期间：默认展开（isStreaming=true），并显示"思考中…"脉冲。
 *   - 流结束后：默认折叠（defaultCollapsed=true），等用户点击展开。
 *   - 用户手动 toggle 后：override 一直生效，不随流状态翻转。
 *
 * 内容以 font-mono 纯文本渲染 — 思考段通常结构化、技术性、短，
 * 跑一遍 markdown 既慢又容易把代码块搞乱。如果未来需要支持，
 * 把内层 <pre> 换成 <Markdown content={content} /> 即可。
 */
import { useState } from 'react'
import { ChevronDownIcon, ChevronUpIcon, LightBulbIcon } from '@heroicons/react/24/outline'

interface ThinkingBlockProps {
  content: string
  /** 思考流是否还在进行（true 时默认展开 + 显示脉冲） */
  isStreaming: boolean
  /** 流结束后的默认折叠态 */
  defaultCollapsed: boolean
  /** 用户点击后回调（父组件可用于持久化偏好） */
  onUserToggle?: (collapsed: boolean) => void
}

export default function ThinkingBlock({
  content,
  isStreaming,
  defaultCollapsed,
  onUserToggle,
}: ThinkingBlockProps) {
  // null = 跟随 isStreaming/defaultCollapsed；true/false = 用户显式选择
  const [userOverride, setUserOverride] = useState<boolean | null>(null)

  const collapsed =
    userOverride !== null
      ? userOverride
      : isStreaming
        ? false
        : defaultCollapsed

  const toggle = () => {
    const next = !collapsed
    setUserOverride(next)
    onUserToggle?.(next)
  }

  return (
    <div
      className="mb-2 rounded-xl border border-border/60 bg-bg-elevated/40 px-3 py-2 text-xs text-fg-dim"
      data-thinking-collapsed={collapsed ? 'true' : 'false'}
      data-thinking-streaming={isStreaming ? 'true' : 'false'}
    >
      <button
        type="button"
        onClick={toggle}
        className="flex items-center gap-1.5 w-full text-left select-none rounded
                   hover:text-fg transition-colors"
        aria-expanded={!collapsed}
      >
        {collapsed ? (
          <ChevronDownIcon className="w-3 h-3 shrink-0" />
        ) : (
          <ChevronUpIcon className="w-3 h-3 shrink-0" />
        )}
        <LightBulbIcon className="w-3 h-3 text-secondary shrink-0" />
        <span className="font-medium text-fg-dim">思考</span>
        {isStreaming && (
          <span className="ml-1 text-fg-muted animate-pulse">思考中…</span>
        )}
      </button>
      {!collapsed && (
        <pre className="mt-1.5 font-mono text-[11px] leading-relaxed whitespace-pre-wrap break-words text-fg-dim">
          {content}
        </pre>
      )}
    </div>
  )
}
