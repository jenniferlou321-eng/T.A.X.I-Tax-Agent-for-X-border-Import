import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { initTheme } from './hooks/useTheme'
import './index.css'
import App from './App.tsx'

// Initialize theme before React renders to prevent flash
initTheme()

/**
 * 全局异步错误兜底。
 *
 * React 的 ErrorBoundary 只能捕获子组件 **渲染期间** 抛出的同步错误。
 * 下列场景需要 window 级别兜底，否则会变白屏：
 *   - 事件处理器里的 throw（onClick / onChange）
 *   - setTimeout / requestAnimationFrame / Promise 链里的 throw
 *   - 第三方库顶层 try/catch 漏掉的 throw
 *
 * 策略：抓到错误时往 <body> 末尾注入一个最小错误遮罩，提示用户并提供
 * 「刷新」+「复制日志」按钮，并把原始错误 console.error 留痕。
 */
function installGlobalErrorHandlers(): void {
  const showFallback = (
    title: string,
    detail: string,
    extra?: { stack?: string; source?: string },
  ): void => {
    // 去重：同一错误不重复弹出
    const existing = document.getElementById('__global_error_overlay__')
    if (existing) return

    const overlay = document.createElement('div')
    overlay.id = '__global_error_overlay__'
    overlay.setAttribute('role', 'alert')
    overlay.style.cssText = `
      position: fixed; inset: 0; z-index: 9999;
      background: rgba(0,0,0,0.6);
      display: flex; align-items: center; justify-content: center;
      font-family: ui-sans-serif, system-ui, sans-serif;
    `
    overlay.innerHTML = `
      <div style="
        background: #111827; color: #f3f4f6;
        border: 1px solid #ef4444; border-radius: 12px;
        padding: 24px; max-width: 560px; width: calc(100% - 32px);
        box-shadow: 0 20px 60px rgba(0,0,0,0.5);
      ">
        <div style="display:flex; align-items:flex-start; gap:12px; margin-bottom:12px;">
          <div style="
            width: 36px; height: 36px; border-radius: 50%;
            background: rgba(239,68,68,0.15);
            display:flex; align-items:center; justify-content:center;
            font-size: 20px; flex-shrink: 0;
          ">⚠</div>
          <div style="flex:1; min-width:0;">
            <h2 style="margin:0 0 4px; font-size:16px; font-weight:600;">${title}</h2>
            <p style="margin:0; color:#9ca3af; font-size:13px; word-break:break-word;">${detail}</p>
          </div>
        </div>
        <details style="margin: 8px 0 16px;">
          <summary style="cursor:pointer; color:#9ca3af; font-size:12px;">查看错误日志</summary>
          <pre style="
            margin-top: 8px; padding: 10px; font-size: 11px;
            background: #0b0f19; border-radius: 6px;
            max-height: 220px; overflow: auto;
            white-space: pre-wrap; word-break: break-all;
            border: 1px solid #1f2937;
          ">${(extra?.stack ?? '(无 stack)').replace(/</g, '&lt;')}</pre>
        </details>
        <div style="display:flex; gap:8px; justify-content:flex-end;">
          <button id="__global_err_copy__" style="
            padding: 6px 12px; border-radius: 6px; font-size: 13px;
            background: transparent; color: #d1d5db; border: 1px solid #374151;
            cursor: pointer;
          ">复制错误日志</button>
          <button id="__global_err_reload__" style="
            padding: 6px 12px; border-radius: 6px; font-size: 13px;
            background: #f59e0b; color: #0f172a; border: none;
            cursor: pointer; font-weight: 500;
          ">刷新整页</button>
        </div>
        <p style="margin: 12px 0 0; color: #6b7280; font-size: 11px;">
          源：${extra?.source ?? 'unknown'} · ${new Date().toISOString()}
        </p>
      </div>
    `

    document.body.appendChild(overlay)

    overlay.querySelector('#__global_err_reload__')?.addEventListener('click', () => {
      window.location.reload()
    })
    overlay.querySelector('#__global_err_copy__')?.addEventListener('click', async () => {
      const text = [
        `[window error] ${title}`,
        `url: ${location.href}`,
        `userAgent: ${navigator.userAgent}`,
        '',
        detail,
        '',
        extra?.stack ?? '(no stack)',
      ].join('\n')
      try {
        await navigator.clipboard.writeText(text)
        const btn = overlay.querySelector('#__global_err_copy__') as HTMLButtonElement | null
        if (btn) btn.textContent = '已复制 ✓'
      } catch {
        // 忽略：clipboard API 在非安全上下文可能不可用
      }
    })
  }

  // 1. 同步未捕获错误
  window.addEventListener('error', (event) => {
    // 忽略资源加载失败（图片/CDN）——这些不影响功能
    if (event.target && event.target !== window) return
    // eslint-disable-next-line no-console
    console.error('[window.error]', event.error ?? event.message)
    showFallback(
      '发生未捕获的错误',
      event.message || String(event.error || 'Unknown error'),
      { stack: event.error?.stack, source: 'window.error' },
    )
  })

  // 2. Promise 拒绝未处理
  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason
    const message = reason instanceof Error ? reason.message : String(reason)
    const stack = reason instanceof Error ? reason.stack : undefined
    // eslint-disable-next-line no-console
    console.error('[unhandledrejection]', reason)
    showFallback('未处理的 Promise 拒绝', message, {
      stack,
      source: 'unhandledrejection',
    })
  })
}

installGlobalErrorHandlers()

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

const rootEl = document.getElementById('root')!
if (!rootEl) {
  throw new Error('Root element not found')
}

const root = createRoot(rootEl)
root.render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
