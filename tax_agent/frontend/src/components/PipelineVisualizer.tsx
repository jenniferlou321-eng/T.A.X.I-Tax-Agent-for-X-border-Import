import { useState, useCallback } from 'react'
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  Circle,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import type { StageResult } from '../types'

interface PipelineVisualizerProps {
  stages: Record<string, StageResult>
  interactive?: boolean
  compact?: boolean
}

const STAGE_CONFIG = [
  { key: 'PRECHECK', label: '前置检查', icon: 'shield' },
  { key: 'PREPARE', label: '数据准备', icon: 'database' },
  { key: 'CALCULATE', label: '税务计算', icon: 'calculator' },
  { key: 'VALIDATE', label: '合规校验', icon: 'check' },
  { key: 'SUBMIT', label: '提交申报', icon: 'send' },
  { key: 'TRACK', label: '状态追踪', icon: 'activity' },
] as const

type StageStatus = 'pending' | 'running' | 'success' | 'warning' | 'error'

const STATUS_COLORS: Record<StageStatus, { text: string; bg: string; border: string; glow?: string }> = {
  pending: {
    text: 'text-fg-dim',
    bg: 'bg-bg-elevated/50',
    border: 'border-border',
  },
  running: {
    text: 'text-info',
    bg: 'bg-info-muted',
    border: 'border-info/30',
    glow: 'shadow-[0_0_12px_-2px_rgba(59,130,246,0.3)]',
  },
  success: {
    text: 'text-success',
    bg: 'bg-success-muted',
    border: 'border-success/30',
  },
  warning: {
    text: 'text-warning',
    bg: 'bg-warning-muted',
    border: 'border-warning/30',
  },
  error: {
    text: 'text-error',
    bg: 'bg-error-muted',
    border: 'border-error/30',
  },
}

function StatusIcon({ status, compact }: { status: StageStatus; compact?: boolean }) {
  const size = compact ? 'w-4 h-4' : 'w-5 h-5'

  switch (status) {
    case 'success':
      return <CheckCircle2 className={`${size} text-success`} />
    case 'error':
      return <XCircle className={`${size} text-error`} />
    case 'warning':
      return <AlertTriangle className={`${size} text-warning`} />
    case 'running':
      return <Loader2 className={`${size} text-info animate-spin`} />
    case 'pending':
    default:
      return <Circle className={`${size} text-fg-dim`} />
  }
}

function StageCard({
  config,
  result,
  interactive,
  compact,
}: {
  config: (typeof STAGE_CONFIG)[number]
  result?: StageResult
  interactive?: boolean
  compact?: boolean
}) {
  const [expanded, setExpanded] = useState(false)

  const status: StageStatus = result?.status ?? 'pending'
  const message = result?.message ?? '等待中...'
  const colors = STATUS_COLORS[status]

  const toggleExpand = useCallback(() => {
    if (interactive && result?.detail && Object.keys(result.detail).length > 0) {
      setExpanded((prev) => !prev)
    }
  }, [interactive, result])

  const hasDetail = !!result?.detail && Object.keys(result.detail).length > 0
  const isClickable = interactive && hasDetail

  if (compact) {
    return (
      <div
        className={`
          relative rounded-lg border p-3 transition-all duration-200
          ${colors.bg} ${colors.border}
          ${isClickable ? 'cursor-pointer hover:border-fg-muted' : ''}
          ${colors.glow ?? ''}
        `}
        onClick={isClickable ? toggleExpand : undefined}
        role={isClickable ? 'button' : undefined}
        tabIndex={isClickable ? 0 : undefined}
        onKeyDown={
          isClickable
            ? (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  toggleExpand()
                }
              }
            : undefined
        }
      >
        <div className="flex items-center gap-2.5">
          <StatusIcon status={status} compact />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-fg truncate">{config.label}</p>
            <p className={`text-[10px] truncate ${colors.text}`}>{message}</p>
          </div>
          {isClickable && (
            <div className="shrink-0">
              {expanded ? (
                <ChevronUp className="w-3 h-3 text-fg-dim" />
              ) : (
                <ChevronDown className="w-3 h-3 text-fg-dim" />
              )}
            </div>
          )}
        </div>

        {expanded && hasDetail && (
          <div className="mt-2 pt-2 border-t border-border/50">
            <pre className="text-[10px] text-fg-muted overflow-x-auto whitespace-pre-wrap break-all font-mono leading-relaxed">
              {JSON.stringify(result.detail, null, 2)}
            </pre>
          </div>
        )}
      </div>
    )
  }

  return (
    <div
      className={`
        relative rounded-xl border p-4 transition-all duration-200
        ${colors.bg} ${colors.border}
        ${isClickable ? 'cursor-pointer hover:border-fg-muted card-interactive' : ''}
        ${colors.glow ?? ''}
      `}
      onClick={isClickable ? toggleExpand : undefined}
      role={isClickable ? 'button' : undefined}
      tabIndex={isClickable ? 0 : undefined}
      onKeyDown={
        isClickable
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                toggleExpand()
              }
            }
          : undefined
      }
    >
      <div className="flex items-start gap-3">
        <div className="shrink-0 mt-0.5">
          <StatusIcon status={status} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-semibold text-fg">{config.label}</p>
            {isClickable && (
              <div className="shrink-0">
                {expanded ? (
                  <ChevronUp className="w-4 h-4 text-fg-dim" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-fg-dim" />
                )}
              </div>
            )}
          </div>
          <p className={`text-xs mt-1 ${colors.text}`}>{message}</p>

          {result?.started_at && (
            <p className="text-[10px] text-fg-dim mt-1.5">
              {result.completed_at
                ? `耗时: ${Math.round((new Date(result.completed_at).getTime() - new Date(result.started_at).getTime()) / 1000)}s`
                : `开始于: ${new Date(result.started_at).toLocaleTimeString('zh-CN')}`}
            </p>
          )}
        </div>
      </div>

      {expanded && hasDetail && (
        <div className="mt-3 pt-3 border-t border-border/50">
          <pre className="text-xs text-fg-muted overflow-x-auto whitespace-pre-wrap break-all font-mono leading-relaxed bg-bg/50 rounded-lg p-3">
            {JSON.stringify(result.detail, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

export default function PipelineVisualizer({
  stages,
  interactive = false,
  compact = false,
}: PipelineVisualizerProps) {
  return (
    <div className={`grid grid-cols-2 md:grid-cols-3 ${compact ? 'gap-2' : 'gap-3'}`}>
      {STAGE_CONFIG.map((config) => (
        <StageCard
          key={config.key}
          config={config}
          result={stages[config.key]}
          interactive={interactive}
          compact={compact}
        />
      ))}
    </div>
  )
}
