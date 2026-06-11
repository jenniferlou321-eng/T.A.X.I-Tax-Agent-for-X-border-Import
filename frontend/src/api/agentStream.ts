/**
 * AG-UI 事件流 SSE consumer。
 *
 * 后端通过 `text/event-stream` 推送 AG-UI 事件，每个事件格式为
 *   `data: {<ag_ui.core.BaseEvent JSON>}\n\n`
 * 我们按行解析出 BaseEvent 对象，回调 `onEvent`，由调用方按 `type`
 * 派发到 React state。
 */

export interface BaseEvent {
  type: string
  timestamp?: number
  // 任何其它字段：messageId / delta / toolCallId / threadId / runId / ...
  [k: string]: unknown
}

export type AguiEventHandler = (event: BaseEvent) => void

export interface ConsumeOptions {
  signal?: AbortSignal
}

/**
 * 消费一个 `Response` body 里的 AG-UI SSE 流，逐事件回调 `onEvent`。
 * 正常结束时 resolve；HTTP 非 2xx 时 reject 带 `Error("HTTP <status>")`。
 */
export async function consumeAguiStream(
  response: Response,
  onEvent: AguiEventHandler,
  options: ConsumeOptions = {},
): Promise<void> {
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }
  if (!response.body) {
    throw new Error('No response body')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      // 支持外部 AbortSignal：用户点"重置"或卸载组件时立即退出
      if (options.signal?.aborted) {
        try {
          await reader.cancel()
        } catch {
          /* ignore */
        }
        return
      }

      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // SSE 事件以 \n\n 分隔，逐个切出处理
      let idx
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const rawEvent = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)

        for (const line of rawEvent.split('\n')) {
          if (!line.startsWith('data:')) continue
          // 兼容 "data:" / "data: " / "data: <json>" 各种 SSE 写法
          const payload = line.slice(5).replace(/^ /, '').trim()
          if (!payload) continue
          try {
            const event = JSON.parse(payload) as BaseEvent
            onEvent(event)
          } catch {
            // 忽略解析失败的 chunk（heartbeat / 注释 / 非 JSON 帧）
          }
        }
      }
    }
  } catch (err) {
    // 网络断开 / reader.cancel() / AbortError
    if ((err as Error).name === 'AbortError') return
    throw err
  } finally {
    try {
      reader.releaseLock()
    } catch {
      /* already released */
    }
  }
}
