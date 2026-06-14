// 关联交易镜像账目(母→子双向)
import { useState } from 'react'
import { ChevronDownIcon, ChevronUpIcon, ScaleIcon, ArrowRightIcon } from '@heroicons/react/24/outline'

export interface MirrorEvent {
  id: string
  type: string
  direction: 'CN→UK' | 'UK→CN'
  amount_cny?: number
  amount_gbp?: number
  principal_cny?: number
  interest_cny?: number
  wht_cny?: number
  net_cny?: number
  note: string
}

interface MirrorLedgerTableProps {
  events: MirrorEvent[]
  title?: string
  defaultExpanded?: boolean
}

const fmtCNY = (n: number | undefined) =>
  `¥${(n ?? 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`
const fmtGBP = (n: number | undefined) =>
  `£${(n ?? 0).toLocaleString('en-GB', { maximumFractionDigits: 0 })}`

export default function MirrorLedgerTable({
  events,
  title = '关联交易镜像账目',
  defaultExpanded = false,
}: MirrorLedgerTableProps) {
  const [open, setOpen] = useState(defaultExpanded)

  const totalCN = events.reduce((s, e) => s + (e.amount_cny || e.principal_cny || 0), 0)

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
          <ScaleIcon className="w-4 h-4 text-accent" />
          <span className="font-medium text-fg text-sm">{title}</span>
          <span className="text-xs text-fg-dim bg-bg-elevated px-2 py-0.5 rounded-full">
            {events.length} 条流
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-fg-dim">母端合计</span>
          <span className="font-mono text-fg font-medium">{fmtCNY(totalCN)}</span>
        </div>
      </button>

      {open && (
        <div className="border-t border-border max-h-96 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="bg-bg sticky top-0">
              <tr className="text-[10px] text-fg-dim uppercase tracking-wide">
                <th className="px-3 py-2 text-left">ID</th>
                <th className="px-3 py-2 text-left">类型</th>
                <th className="px-3 py-2 text-left">方向</th>
                <th className="px-3 py-2 text-right">金额(CNY)</th>
                <th className="px-3 py-2 text-right">WHT</th>
                <th className="px-3 py-2 text-left">备注</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr
                  key={e.id}
                  className="border-t border-border hover:bg-bg-elevated/40"
                >
                  <td className="px-3 py-2 font-mono text-fg">{e.id}</td>
                  <td className="px-3 py-2 text-fg">{e.type}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono ${
                        e.direction === 'CN→UK'
                          ? 'bg-primary/15 text-primary'
                          : 'bg-accent/15 text-accent'
                      }`}
                    >
                      {e.direction === 'CN→UK' ? 'CN' : 'UK'}
                      <ArrowRightIcon className="w-2.5 h-2.5" />
                      {e.direction === 'CN→UK' ? 'UK' : 'CN'}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-fg">
                    {fmtCNY(e.amount_cny || e.principal_cny)}
                  </td>
                  <td className="px-3 py-2 text-right font-mono text-warning">
                    {e.wht_cny ? fmtCNY(e.wht_cny) : '—'}
                  </td>
                  <td className="px-3 py-2 text-fg-dim">{e.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
