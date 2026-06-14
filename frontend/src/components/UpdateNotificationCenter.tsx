import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  BellIcon,
  ArrowPathIcon,
  XMarkIcon,
  CheckCircleIcon,
  SparklesIcon,
  PencilSquareIcon,
  TrashIcon,
} from '@heroicons/react/24/outline'
import { api } from '../api/client'

// ── 类型 ──────────────────────────────────────────────────────
// 与 api.corpus.checkUpdates() 的 report.new[] / report.modified[] 同构
type SourceEntry = {
  source_id: string
  title: string
  url: string
  source_authority: string
  tax_tags: string[]
  chunk_count: number
  status: string
}

type ChangeKind = 'new' | 'modified'

type UpdateItem = SourceEntry & { kind: ChangeKind }

// 一次「收到上游更新」的批次,落进历史列表
type UpdateBatch = {
  id: string
  received_at: string // ISO 字符串(前端 new Date() 取)
  items: UpdateItem[]
}

const STORAGE_KEY = 'taxi_kb_update_history'

// ── localStorage 读写 ────────────────────────────────────────
function loadHistory(): UpdateBatch[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveHistory(batches: UpdateBatch[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(batches))
  } catch {
    // localStorage 不可用时静默降级:历史只存内存
  }
}

// ── 组件 ──────────────────────────────────────────────────────
export default function UpdateNotificationCenter() {
  const [checking, setChecking] = useState(false)
  const [applying, setApplying] = useState(false)
  const [pendingBatch, setPendingBatch] = useState<UpdateBatch | null>(null) // 弹窗里待确认的本批更新
  const [applied, setApplied] = useState(false) // 本批是否已「应用到知识库」
  const [noMirror, setNoMirror] = useState(false)
  const [error, setError] = useState('')

  const [history, setHistory] = useState<UpdateBatch[]>(() => loadHistory())
  const [historyOpen, setHistoryOpen] = useState(false)
  const [unread, setUnread] = useState(false) // 铃铛红点:有未读弹窗时亮
  const [expandedBatch, setExpandedBatch] = useState<string | null>(null)
  const [detailItem, setDetailItem] = useState<UpdateItem | null>(null) // 历史条目详情弹窗

  const dropdownRef = useRef<HTMLDivElement>(null)

  // 点击外部关闭历史下拉
  useEffect(() => {
    if (!historyOpen) return
    const onClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setHistoryOpen(false)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [historyOpen])

  // 「模拟收到上游更新」:调 check-updates,有变化则弹窗
  const handleSimulate = async () => {
    setChecking(true)
    setError('')
    setNoMirror(false)
    setApplied(false)
    try {
      const res = await api.corpus.checkUpdates()
      if (res.status === 'no_mirror') {
        setNoMirror(true)
      } else if (res.status === 'ok' && res.report) {
        const items: UpdateItem[] = [
          ...res.report.new.map((s) => ({ ...s, kind: 'new' as const })),
          ...res.report.modified.map((s) => ({ ...s, kind: 'modified' as const })),
        ]
        if (items.length === 0) {
          // 没有变化:弹一个「已是最新」轻提示(用 noMirror=false + pendingBatch=null + 临时 error 框承载)
          setError('知识库已是最新,没有检测到上游更新。')
        } else {
          setPendingBatch({
            id: `batch-${new Date().getTime()}`,
            received_at: new Date().toISOString(),
            items,
          })
          setUnread(true)
        }
      } else {
        setError(res.message || '检查更新失败')
      }
    } catch (e: any) {
      setError(e?.message || '检查更新失败')
    } finally {
      setChecking(false)
    }
  }

  // 「应用到知识库」:真合并 + 后端 reload
  const handleApply = async () => {
    setApplying(true)
    setError('')
    try {
      const res = await api.corpus.applyUpdates()
      if (res.status === 'ok' || res.status === 'partial') {
        setApplied(true)
      } else {
        setError(res.message || '应用更新失败')
      }
    } catch (e: any) {
      setError(e?.message || '应用更新失败')
    } finally {
      setApplying(false)
    }
  }

  // 「已阅读」:关弹窗 + 本批落进历史 + 灭红点
  const handleAcknowledge = () => {
    if (pendingBatch) {
      const next = [pendingBatch, ...history]
      setHistory(next)
      saveHistory(next)
    }
    setPendingBatch(null)
    setApplied(false)
    setUnread(false)
  }

  const handleClearHistory = () => {
    setHistory([])
    saveHistory([])
    setExpandedBatch(null)
  }

  const renderKindTag = (kind: ChangeKind) =>
    kind === 'new' ? (
      <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded bg-success/15 text-success">
        <SparklesIcon className="w-3 h-3" /> 新增
      </span>
    ) : (
      <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded bg-warning/15 text-warning">
        <PencilSquareIcon className="w-3 h-3" /> 修改
      </span>
    )

  return (
    <>
      {/* 头部:模拟更新按钮 + 铃铛 */}
      <button
        onClick={handleSimulate}
        disabled={checking}
        className="hidden sm:inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-md text-fg-muted hover:text-fg hover:bg-bg-elevated transition-colors disabled:opacity-60"
        title="演示用:模拟从 HMRC / GOV.UK 上游收到知识库更新"
      >
        {checking ? (
          <ArrowPathIcon className="w-4 h-4 animate-spin" />
        ) : (
          <ArrowPathIcon className="w-4 h-4" />
        )}
        模拟收到上游更新
      </button>

      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setHistoryOpen((v) => !v)}
          className="relative p-2 text-fg-muted hover:text-fg hover:bg-bg-elevated rounded-md transition-colors duration-200"
          aria-label="知识库更新记录"
        >
          <BellIcon className="w-5 h-5" />
          {unread && (
            <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-primary rounded-full ring-2 ring-bg" />
          )}
        </button>

        {/* 历史下拉 */}
        {historyOpen && (
          <div className="absolute right-0 mt-2 w-80 max-h-[28rem] overflow-y-auto bg-bg-surface border border-border rounded-lg shadow-xl z-50 fade-in">
            <div className="flex items-center justify-between px-3 py-2.5 border-b border-border sticky top-0 bg-bg-surface">
              <h3 className="text-sm font-semibold text-fg">知识库更新记录</h3>
              {history.length > 0 && (
                <button
                  onClick={handleClearHistory}
                  className="inline-flex items-center gap-1 text-xs text-fg-dim hover:text-error transition-colors"
                  title="清空记录(便于重跑演示)"
                >
                  <TrashIcon className="w-3.5 h-3.5" /> 清空
                </button>
              )}
            </div>

            {history.length === 0 ? (
              <p className="px-3 py-8 text-center text-sm text-fg-dim">暂无更新记录</p>
            ) : (
              <div className="divide-y divide-border">
                {history.map((batch) => (
                  <div key={batch.id} className="px-3 py-2.5">
                    <button
                      onClick={() =>
                        setExpandedBatch((cur) => (cur === batch.id ? null : batch.id))
                      }
                      className="w-full text-left"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-fg">
                          {batch.items.length} 条更新
                        </span>
                        <span className="text-[10px] text-fg-dim">
                          {new Date(batch.received_at).toLocaleString('zh-CN', {
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                      </div>
                    </button>

                    {expandedBatch === batch.id && (
                      <div className="mt-2 space-y-1.5">
                        {batch.items.map((it) => (
                          <button
                            key={it.source_id}
                            onClick={() => setDetailItem(it)}
                            className="w-full text-left text-xs bg-bg-elevated hover:bg-bg-elevated/70 rounded px-2 py-1.5 transition-colors"
                          >
                            <div className="flex items-center gap-1.5 mb-1">
                              {renderKindTag(it.kind)}
                              <span className="text-fg-dim text-[10px]">
                                {it.source_authority}
                              </span>
                            </div>
                            <p className="text-fg leading-snug">{it.title}</p>
                            {it.tax_tags?.length > 0 && (
                              <p className="text-fg-dim text-[10px] mt-0.5">
                                {it.tax_tags.join(' · ')}
                              </p>
                            )}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 轻提示:无 mirror / 无更新 / 错误 — Portal 到 body,避开 header 的 backdrop-blur containing block */}
      {(noMirror || error) && !pendingBatch &&
        createPortal(
          <div className="fixed bottom-4 right-4 z-50 max-w-sm bg-bg-surface border border-border rounded-lg shadow-xl px-4 py-3 fade-in">
            <div className="flex items-start gap-2">
              <p className="text-sm text-fg-muted flex-1">
                {noMirror
                  ? '未找到镜像文件。请先运行 scripts/build_demo_mirror.py 生成演示数据。'
                  : error}
              </p>
              <button
                onClick={() => {
                  setNoMirror(false)
                  setError('')
                }}
                className="text-fg-dim hover:text-fg"
              >
                <XMarkIcon className="w-4 h-4" />
              </button>
            </div>
          </div>,
          document.body
        )}

      {/* 弹窗:本批更新确认 — Portal 到 body,使 fixed inset-0 相对视口居中(否则被 header 的 backdrop-blur 困住,顶到屏幕最上方) */}
      {pendingBatch &&
        createPortal(
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 fade-in">
            <div className="w-full max-w-lg bg-bg-surface border border-border rounded-xl shadow-2xl max-h-[85vh] flex flex-col">
              <div className="flex items-center justify-between px-5 py-4 border-b border-border">
                <div className="flex items-center gap-2">
                  <BellIcon className="w-5 h-5 text-primary" />
                  <h2 className="text-base font-semibold text-fg">检测到知识库更新</h2>
                </div>
                <button
                  onClick={handleAcknowledge}
                  className="text-fg-dim hover:text-fg"
                  aria-label="关闭"
                >
                  <XMarkIcon className="w-5 h-5" />
                </button>
              </div>

              <div className="px-5 py-4 overflow-y-auto">
                <p className="text-sm text-fg-muted mb-4">
                  平台监测到上游官网(HMRC / GOV.UK)有{' '}
                  <span className="font-semibold text-fg">{pendingBatch.items.length}</span>{' '}
                  处税法内容变化:
                </p>

                <div className="space-y-2">
                  {pendingBatch.items.map((it) => (
                    <div
                      key={it.source_id}
                      className="bg-bg-elevated rounded-lg px-3 py-2.5"
                    >
                      <div className="flex items-center gap-2 mb-1">
                        {renderKindTag(it.kind)}
                        <span className="text-[11px] text-fg-dim">
                          {it.source_authority}
                        </span>
                      </div>
                      <p className="text-sm text-fg font-medium leading-snug">{it.title}</p>
                      {it.tax_tags?.length > 0 && (
                        <p className="text-xs text-fg-dim mt-1">{it.tax_tags.join(' · ')}</p>
                      )}
                      {it.url && (
                        <a
                          href={it.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-primary hover:underline mt-1 inline-block break-all"
                        >
                          {it.url}
                        </a>
                      )}
                    </div>
                  ))}
                </div>

                {applied && (
                  <div className="mt-4 flex items-center gap-2 text-sm text-success">
                    <CheckCircleIcon className="w-5 h-5" />
                    已应用到知识库,智能助手即刻可引用最新内容。
                  </div>
                )}
                {error && (
                  <p className="mt-4 text-sm text-error">{error}</p>
                )}
              </div>

              <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-border">
                <button
                  onClick={handleApply}
                  disabled={applying || applied}
                  className="btn btn-primary"
                >
                  {applying ? (
                    <>
                      <ArrowPathIcon className="w-4 h-4 animate-spin" />
                      应用中…
                    </>
                  ) : applied ? (
                    '已应用'
                  ) : (
                    '应用到知识库'
                  )}
                </button>
                <button onClick={handleAcknowledge} className="btn btn-ghost">
                  已阅读
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}

      {/* 历史条目详情弹窗 — Portal 到 body,避开 header 的 backdrop-blur containing block */}
      {detailItem &&
        createPortal(
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 fade-in"
            onClick={() => setDetailItem(null)}
          >
            <div
              className="w-full max-w-lg bg-bg-surface border border-border rounded-xl shadow-2xl max-h-[85vh] flex flex-col"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between px-5 py-4 border-b border-border">
                <div className="flex items-center gap-2">
                  {renderKindTag(detailItem.kind)}
                  <h2 className="text-base font-semibold text-fg">更新详情</h2>
                </div>
                <button
                  onClick={() => setDetailItem(null)}
                  className="text-fg-dim hover:text-fg"
                  aria-label="关闭"
                >
                  <XMarkIcon className="w-5 h-5" />
                </button>
              </div>

              <div className="px-5 py-4 overflow-y-auto space-y-4">
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-fg-dim mb-1">
                    来源标题
                  </p>
                  <p className="text-sm text-fg font-medium leading-snug">
                    {detailItem.title}
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <p className="text-fg-dim mb-0.5">来源机构</p>
                    <p className="text-fg">{detailItem.source_authority}</p>
                  </div>
                  <div>
                    <p className="text-fg-dim mb-0.5">状态</p>
                    <p className="text-fg">{detailItem.status}</p>
                  </div>
                  <div>
                    <p className="text-fg-dim mb-0.5">分段数</p>
                    <p className="text-fg">{detailItem.chunk_count}</p>
                  </div>
                  <div>
                    <p className="text-fg-dim mb-0.5">来源 ID</p>
                    <p className="text-fg break-all">{detailItem.source_id}</p>
                  </div>
                </div>

                {detailItem.tax_tags?.length > 0 && (
                  <div>
                    <p className="text-[11px] uppercase tracking-wide text-fg-dim mb-1">
                      税种标签
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {detailItem.tax_tags.map((t) => (
                        <span
                          key={t}
                          className="inline-flex items-center text-[11px] px-2 py-0.5 rounded bg-bg-elevated text-fg-muted"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {detailItem.url && (
                  <div>
                    <p className="text-[11px] uppercase tracking-wide text-fg-dim mb-1">
                      上游链接
                    </p>
                    <a
                      href={detailItem.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm text-primary hover:underline break-all"
                    >
                      {detailItem.url}
                    </a>
                  </div>
                )}

                {detailItem.kind === 'modified' && (
                  <div className="text-xs text-fg-muted bg-warning/10 border border-warning/20 rounded-md px-3 py-2">
                    该来源是平台已收录的 source,本次只是正文有更新
                    (diff 在 source_id 级别做文本哈希比对),其它元数据沿用旧值。
                  </div>
                )}
                {detailItem.kind === 'new' && (
                  <div className="text-xs text-fg-muted bg-success/10 border border-success/20 rounded-md px-3 py-2">
                    该来源为平台此前未收录的全新文档,首次纳入知识库。
                  </div>
                )}
              </div>

              <div className="flex items-center justify-end px-5 py-4 border-t border-border">
                <button
                  onClick={() => setDetailItem(null)}
                  className="btn btn-ghost"
                >
                  关闭
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}
    </>
  )
}
