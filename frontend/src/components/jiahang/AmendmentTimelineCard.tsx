// 5 大修订点 timeline
import { useState } from 'react'
import { ChevronDownIcon, ChevronUpIcon, PencilSquareIcon } from '@heroicons/react/24/outline'

export interface AmendEntry {
  order: number
  title: string
  impact: string
  reason: string
}

interface AmendmentTimelineCardProps {
  entries: AmendEntry[]
  title?: string
  defaultExpanded?: boolean
}

export default function AmendmentTimelineCard({
  entries,
  title = '5 大修订点',
  defaultExpanded = false,
}: AmendmentTimelineCardProps) {
  const [open, setOpen] = useState(defaultExpanded)

  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 bg-bg-elevated/50 hover:bg-bg-elevated transition-colors"
      >
        <div className="flex items-center gap-3">
          {open ? (
            <ChevronUpIcon className="w-4 h-4 text-fg-dim" />
          ) : (
            <ChevronDownIcon className="w-4 h-4 text-fg-dim" />
          )}
          <PencilSquareIcon className="w-4 h-4 text-info" />
          <span className="font-medium text-fg text-sm">{title}</span>
          <span className="text-xs text-fg-dim bg-bg-elevated px-2 py-0.5 rounded-full">
            {entries.length} 修订
          </span>
        </div>
        <span className="text-xs text-fg-dim">{open ? '收起' : '展开'}</span>
      </button>

      {open && (
        <div className="border-t border-border p-4 fade-in">
          <ol className="relative space-y-3 pl-6 border-l-2 border-primary/40">
            {entries.map((e) => (
              <li key={e.order} className="relative">
                {/* 圆点 */}
                <span className="absolute -left-[31px] top-1.5 w-4 h-4 rounded-full bg-primary text-white text-[10px] font-bold flex items-center justify-center shadow-glow-primary">
                  {e.order}
                </span>
                <div className="rounded border border-border bg-bg-elevated/30 p-3">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <h4 className="text-sm font-semibold text-fg">{e.title}</h4>
                    <span className="text-[11px] font-mono text-primary shrink-0">
                      {e.impact}
                    </span>
                  </div>
                  <p className="text-xs text-fg-muted">{e.reason}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
