/**
 * ErrorBoundary — 全局错误兜底，防止单页崩溃导致整树白屏。
 *
 * 关键设计：
 *   - React 18 仍只有 class 组件能写 getDerivedStateFromError，这是 React 官方限制。
 *   - 渲染失败时把 children 替换为一个模态错误弹窗（而非整页占位），让用户
 *     可以关闭弹窗后继续浏览其他页面。
 *   - 错误信息默认折叠，展开后展示完整 stack 并支持一键复制。
 *   - 不上报到后端（用户当前选择），仅 console.error 留痕。
 *   - 提供 withErrorBoundary HOC，方便在路由层直接 <Component /> 包起来。
 */
import { Component, type ErrorInfo, type ReactNode } from 'react'
import {
  ExclamationTriangleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  XMarkIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline'

interface Props {
  children: ReactNode
  /** 弹窗标题后缀，便于定位是哪个边界抓到错误。 */
  scope?: string
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
  detailsOpen: boolean
  copied: boolean
}

const initialState: State = {
  hasError: false,
  error: null,
  errorInfo: null,
  detailsOpen: false,
  copied: false,
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = initialState

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // 留痕：DevTools 可见
    // eslint-disable-next-line no-console
    console.error('[ErrorBoundary]', this.props.scope ?? 'global', error, errorInfo)
    this.setState({ errorInfo })
  }

  handleReset = (): void => {
    this.setState(initialState)
  }

  handleReload = (): void => {
    window.location.reload()
  }

  handleCopy = async (): Promise<void> => {
    const text = this.formatErrorLog()
    try {
      await navigator.clipboard.writeText(text)
      this.setState({ copied: true })
      setTimeout(() => this.setState({ copied: false }), 1500)
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('[ErrorBoundary] clipboard write failed', e)
    }
  }

  formatErrorLog = (): string => {
    const { error, errorInfo, scope } = this.state
    const { location } = window
    return [
      `[ErrorBoundary] scope=${scope ?? 'global'}`,
      `url: ${location.href}`,
      `userAgent: ${navigator.userAgent}`,
      `timestamp: ${new Date().toISOString()}`,
      '',
      '--- error.message ---',
      error?.message ?? '(none)',
      '',
      '--- error.stack ---',
      error?.stack ?? '(none)',
      '',
      '--- componentStack ---',
      errorInfo?.componentStack ?? '(none)',
    ].join('\n')
  }

  render(): ReactNode {
    if (!this.state.hasError) {
      return this.props.children
    }

    const { error, errorInfo, scope, detailsOpen, copied } = this.state
    const title = scope ? `${scope} 出错了` : '页面出错了'

    return (
      <div
        className="fixed inset-0 z-[100] flex items-center justify-center bg-bg-overlay p-4 fade-in"
        role="dialog"
        aria-modal="true"
        aria-labelledby="err-boundary-title"
        data-testid="error-boundary-modal"
      >
        <div className="card p-6 w-full max-w-2xl max-h-[90vh] flex flex-col">
          {/* 头部 */}
          <div className="flex items-start gap-3 mb-4">
            <div className="shrink-0 w-10 h-10 rounded-full bg-error-muted flex items-center justify-center">
              <ExclamationTriangleIcon className="w-6 h-6 text-error" />
            </div>
            <div className="flex-1 min-w-0">
              <h2
                id="err-boundary-title"
                className="text-lg font-semibold text-fg"
              >
                {title}
              </h2>
              <p className="text-sm text-fg-dim mt-1 break-words">
                {error?.message || '发生了未知错误，已阻止整个页面崩溃。'}
              </p>
            </div>
            <button
              onClick={this.handleReset}
              className="shrink-0 p-1 rounded hover:bg-bg-elevated text-fg-dim hover:text-fg transition"
              aria-label="关闭错误弹窗"
              title="关闭弹窗（错误组件仍会保留在该位置）"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>

          {/* 操作区 */}
          <div className="flex flex-wrap gap-2 mb-4">
            <button
              onClick={this.handleReset}
              className="btn-secondary text-sm flex items-center gap-1.5"
            >
              <ArrowPathIcon className="w-4 h-4" />
              尝试恢复
            </button>
            <button
              onClick={this.handleReload}
              className="btn-secondary text-sm"
            >
              刷新整页
            </button>
            <button
              onClick={() =>
                this.setState((s) => ({ detailsOpen: !s.detailsOpen }))
              }
              className="btn-ghost text-sm flex items-center gap-1.5"
            >
              {detailsOpen ? (
                <ChevronUpIcon className="w-4 h-4" />
              ) : (
                <ChevronDownIcon className="w-4 h-4" />
              )}
              {detailsOpen ? '收起详情' : '查看错误日志'}
            </button>
            <button
              onClick={this.handleCopy}
              className="btn-ghost text-sm ml-auto"
            >
              {copied ? '已复制 ✓' : '复制错误日志'}
            </button>
          </div>

          {/* 详情 */}
          {detailsOpen && (
            <div className="flex-1 min-h-0 flex flex-col gap-3 overflow-y-auto">
              <DetailBlock label="错误消息" body={error?.message} />
              <DetailBlock
                label="调用栈 (stack)"
                body={error?.stack}
                mono
              />
              <DetailBlock
                label="组件栈 (componentStack)"
                body={errorInfo?.componentStack}
                mono
              />
            </div>
          )}

          <p className="text-xs text-fg-muted mt-4">
            提示：关闭弹窗会重置该错误边界。如果问题持续，请刷新整页或联系开发。
          </p>
        </div>
      </div>
    )
  }
}

interface DetailBlockProps {
  label: string
  body?: string | null
  mono?: boolean
}

function DetailBlock({ label, body, mono }: DetailBlockProps) {
  return (
    <div>
      <div className="text-xs font-medium text-fg-dim mb-1">{label}</div>
      <pre
        className={
          'p-2.5 bg-bg-elevated/60 rounded text-xs overflow-x-auto whitespace-pre-wrap break-all max-h-60 overflow-y-auto border border-border ' +
          (mono ? 'font-mono' : '')
        }
      >
        {body || '(无)'}
      </pre>
    </div>
  )
}

/**
 * withErrorBoundary — HOC 形式的便捷包裹。
 * 用法：export default withErrorBoundary(MyPage, 'Dashboard')
 */
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  scope?: string,
): React.ComponentType<P> {
  const displayName = Component.displayName || Component.name || 'Component'
  const Wrapped: React.FC<P> = (props) => (
    <ErrorBoundary scope={scope ?? displayName}>
      <Component {...props} />
    </ErrorBoundary>
  )
  Wrapped.displayName = `withErrorBoundary(${displayName})`
  return Wrapped
}
