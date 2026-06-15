/**
 * AgentActivityPanel — 统一折叠面板，展示 Agent 的思考 + 工具调用活动。
 *
 * 设计目标：
 *   - 所有思考段和工具调用收拢到一个 <details> 面板
 *   - 默认只展开最新一条活动的详情
 *   - 其余条目折叠为单行摘要（icon + 名称）
 *   - summary 行实时显示 activeStep（正在执行的操作）
 *
 * 数据来源：
 *   - activities: ActivityEntry[]（按时间顺序排列）
 *   - thinkingData: 从 ChatMessage.thinking 累积的内容，按 messageId 查找
 *   - activeStep: 当前执行阶段（由后端 step_start/step_end 信号驱动）
 */
import {
  WrenchIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'

export interface ActivityEntry {
  id: string
  type: 'thinking' | 'tool_call'
  // thinking — 引用 ChatMessage.id
  messageId?: string
  // tool_call — 内联数据
  toolCallId?: string
  toolName?: string
  args?: string
  result?: string // undefined = 执行中
}

interface AgentActivityPanelProps {
  activities: ActivityEntry[]
  thinkingData: Record<string, { content: string; isFinished: boolean }>
  activeStep: string | null
  /**
   * embedded=true 时,渲染进 assistant 消息气泡内部:
   *   - 去掉外层 ml-11 / fade-in 包装(气泡自带 padding/alignment)
   *   - summary 文案简化为"思考与工具调用",不再显示总步数
   * 默认 false,保持原有的"消息列底部独立面板"形态(向后兼容)。
   */
  embedded?: boolean
}

/** 把后端 step_name 翻译成中文状态标签 */
function formatStepName(step: string): string {
  if (step === 'thinking') return '思考中...'
  if (step.startsWith('tool:')) {
    const raw = step.slice(5)
    const m = raw.match(/^mcp__tax_agent_(\w+)__(.+)$/)
    if (m) {
      const prefix = m[1].replace(/_/g, ' ').toUpperCase()
      const tool = m[2]
      return `正在调用 ${prefix}: ${tool}...`
    }
    return `正在调用 ${raw}...`
  }
  return step
}

/** 尝试美化 JSON；非 JSON 原样返回 */
function prettyJson(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2)
  } catch {
    return raw
  }
}

export default function AgentActivityPanel({
  activities,
  thinkingData,
  activeStep,
  embedded = false,
}: AgentActivityPanelProps) {
  if (activities.length === 0) return null

  // 过滤掉内容为空的 thinking 条目(LLM 可能开了 REASONING 但没输出内容,
  // 历史消息数据也可能缺失)— 避免面板里出现"空气泡"折叠块。
  // tool_call 条目始终保留(执行中/已结束都有意义)。
  const visibleEntries = activities.filter((entry) => {
    if (entry.type !== 'thinking') return true
    const data = entry.messageId ? thinkingData[entry.messageId] : undefined
    const content = (data?.content || '').trim()
    return content.length > 0
  })

  if (visibleEntries.length === 0) return null

  const latestIdx = visibleEntries.length - 1

  return (
    <div className={embedded ? 'space-y-1' : 'ml-11 fade-in'}>
      {/* 默认折叠:仅在流式执行(有 activeStep)时自动展开,完成/历史消息折叠。
          summary 行始终显示当前状态,用户随时可手动展开看详情。 */}
      <details open={!!activeStep}>
        <summary className="flex items-center gap-2 text-xs text-fg-dim cursor-pointer hover:text-fg select-none py-1.5">
          {activeStep ? (
            <>
              {activeStep.startsWith('tool:') ? (
                <WrenchIcon className="w-3.5 h-3.5 text-accent shrink-0 animate-spin" />
              ) : (
                <SparklesIcon className="w-3.5 h-3.5 text-secondary shrink-0 animate-pulse" />
              )}
              <span className="animate-pulse">{formatStepName(activeStep)}</span>
            </>
          ) : (
            <>
              <WrenchIcon className="w-3.5 h-3.5 text-accent shrink-0" />
              <span>
                {embedded ? '思考与工具调用' : `Agent 活动 (${visibleEntries.length} 步)`}
              </span>
            </>
          )}
        </summary>

        <div className="space-y-1 mt-1 border-l-2 border-border pl-3">
          {visibleEntries.map((entry, idx) => {
            const isLatest = idx === latestIdx

            if (entry.type === 'thinking') {
              const data = entry.messageId
                ? thinkingData[entry.messageId]
                : undefined
              const content = (data?.content || '').trim()
              const isFinished = data?.isFinished ?? true

              return (
                <details
                  key={entry.id}
                  open={isLatest && !isFinished}
                >
                  <summary className="flex items-center gap-1.5 cursor-pointer text-xs select-none py-0.5 text-fg-dim hover:text-fg">
                    <SparklesIcon className="w-3 h-3 text-secondary shrink-0" />
                    <span className="text-secondary">思考</span>
                    {!isFinished && (
                      <span className="animate-pulse text-fg-dim">...</span>
                    )}
                  </summary>                  <div className="mt-1 text-[11px] text-fg-dim bg-secondary/5 rounded-lg p-2 max-h-40 overflow-y-auto whitespace-pre-wrap leading-relaxed">
                    {content}
                  </div>
                </details>
              )
            }

            // tool_call
            const isRunning = entry.result === undefined

            return (
              <details key={entry.id} open={isLatest && isRunning}>
                <summary className="flex items-center gap-1.5 cursor-pointer text-xs select-none py-0.5 text-fg-dim hover:text-fg">
                  <WrenchIcon className="w-3 h-3 text-accent shrink-0" />
                  <span className="text-accent font-medium">
                    {entry.toolName}
                  </span>
                  {isRunning && (
                    <span className="animate-pulse text-fg-dim">执行中...</span>
                  )}
                  {entry.result !== undefined && (
                    <span className="text-success text-[10px]">✓</span>
                  )}
                </summary>

                <div className="mt-1 space-y-1 text-[11px]">
                  {entry.args && (
                    <details open={false}>
                      <summary className="cursor-pointer text-fg-muted hover:text-fg select-none">
                        参数
                      </summary>
                      <pre className="mt-1 p-1.5 bg-bg-elevated/60 rounded font-mono text-fg overflow-x-auto whitespace-pre-wrap break-all">
                        {prettyJson(entry.args)}
                      </pre>
                    </details>
                  )}

                  {entry.result !== undefined && (
                    <details open={false}>
                      <summary className="cursor-pointer text-fg-muted hover:text-fg select-none">
                        结果
                      </summary>
                      <pre className="mt-1 p-1.5 bg-bg-elevated/60 rounded font-mono text-fg overflow-x-auto whitespace-pre-wrap break-all max-h-40 overflow-y-auto">
                        {prettyJson(entry.result || '')}
                      </pre>
                    </details>
                  )}
                </div>
              </details>
            )
          })}
        </div>
      </details>
    </div>
  )
}
