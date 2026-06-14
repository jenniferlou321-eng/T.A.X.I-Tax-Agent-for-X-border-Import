// 暂时性差异 → DTA 变动表(4 笔事件)
import { useState } from 'react'
import { ChevronDownIcon, ChevronUpIcon, ClockIcon } from '@heroicons/react/24/outline'

export interface TempDiffEvent {
  id: string
  date: string
  type: 'reversal' | 'new'
  amount_cny: number
  dta_impact_cny: number
  desc: string
}

export interface DtaBalance {
  beginning_cny: number
  reversal_cny: number
  new_recognized_cny: number
  ending_cny: number
}

interface TemporaryDiffCardProps {
  events: TempDiffEvent[]
  balance: DtaBalance
  title?: string
  defaultExpanded?: boolean
}

const fmtCNY = (n: number | undefined) =>
  `¥${(n ?? 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`

export default function TemporaryDiffCard({
  events,
  balance,
  title = '暂时性差异 → 递延所得税资产',
  defaultExpanded = false,
}: TemporaryDiffCardProps) {
  const [open, setOpen] = useState(defaultExpanded)
  const totalEventDTA = events.reduce((s, e) => s + e.dta_impact_cny, 0)

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
          <ClockIcon className="w-4 h-4 text-warning" />
          <span className="font-medium text-fg text-sm">{title}</span>
          <span className="text-xs text-fg-dim bg-bg-elevated px-2 py-0.5 rounded-full">
            {events.length} 事件
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <span className="text-fg-dim">DTA 期末</span>
          <span className="font-mono text-fg font-medium">{fmtCNY(balance.ending_cny)}</span>
        </div>
      </button>

      {open && (
        <div className="border-t border-border p-4 space-y-3 fade-in">
          {/* DTA 变动条形图(简化) */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <div className="rounded border border-border p-3 bg-bg-elevated/40">
              <div className="text-[10px] text-fg-dim uppercase tracking-wide">期初余额</div>
              <div className="text-lg font-bold font-mono text-fg mt-0.5">
                {fmtCNY(balance.beginning_cny)}
              </div>
              <div className="text-[10px] text-fg-dim">来自 FY2022 末</div>
            </div>
            <div className="rounded border border-warning/30 p-3 bg-warning-muted/30">
              <div className="text-[10px] text-warning uppercase tracking-wide">本期转回</div>
              <div className="text-lg font-bold font-mono text-warning mt-0.5">
                {fmtCNY(balance.reversal_cny)}
              </div>
              <div className="text-[10px] text-fg-dim">C1-000a 支付</div>
            </div>
            <div className="rounded border border-success/30 p-3 bg-success-muted/30">
              <div className="text-[10px] text-success uppercase tracking-wide">本期确认</div>
              <div className="text-lg font-bold font-mono text-success mt-0.5">
                +{fmtCNY(balance.new_recognized_cny)}
              </div>
              <div className="text-[10px] text-fg-dim">C1-040c/d/e</div>
            </div>
            <div className="rounded border border-primary/30 p-3 bg-primary-muted/30">
              <div className="text-[10px] text-primary uppercase tracking-wide">期末余额</div>
              <div className="text-lg font-bold font-mono text-primary mt-0.5">
                {fmtCNY(balance.ending_cny)}
              </div>
              <div className="text-[10px] text-fg-dim">净增 {fmtCNY(totalEventDTA)}</div>
            </div>
          </div>

          {/* 事件列表 */}
          <div>
            <div className="text-[10px] text-fg-dim uppercase tracking-wide mb-1.5">
              事件明细
            </div>
            <div className="space-y-1">
              {events.map((e) => (
                <div
                  key={e.id}
                  className="flex items-center gap-3 px-3 py-2 rounded border border-border bg-bg-elevated/20 text-xs"
                >
                  <span className="font-mono text-fg-dim shrink-0">{e.id}</span>
                  <span className="text-fg-dim shrink-0">{e.date}</span>
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-medium shrink-0 ${
                      e.type === 'reversal'
                        ? 'bg-warning-muted text-warning'
                        : 'bg-success-muted text-success'
                    }`}
                  >
                    {e.type === 'reversal' ? '转回' : '新增'}
                  </span>
                  <span className="text-fg-muted flex-1 truncate">{e.desc}</span>
                  <span className="font-mono text-fg shrink-0">
                    {fmtCNY(e.amount_cny)}
                  </span>
                  <span
                    className={`font-mono font-medium shrink-0 ${
                      e.dta_impact_cny < 0 ? 'text-warning' : 'text-success'
                    }`}
                  >
                    {e.dta_impact_cny >= 0 ? '+' : ''}
                    {fmtCNY(e.dta_impact_cny)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <p className="text-[11px] text-fg-dim italic">
            适用税率 25%;4 笔分录:当期所得税 + DTA 确认 + DTA 转回 + 境外税收抵免(详见 C1-041 汇算清缴)
          </p>
        </div>
      )}
    </div>
  )
}
