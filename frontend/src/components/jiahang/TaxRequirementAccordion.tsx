// 报税要求折叠面板
import { useState } from 'react'
import { ChevronDownIcon, ChevronUpIcon, DocumentChartBarIcon } from '@heroicons/react/24/outline'
import CapabilityBadge from './CapabilityBadge'
import type { TaxRequirement } from '../../types/jiahang'

interface TaxRequirementAccordionProps {
  title?: string
  requirements: TaxRequirement[]
  defaultExpanded?: boolean
}

const fmtCNY = (n: number | undefined) =>
  `¥${(n ?? 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`
const fmtGBP = (n: number | undefined) =>
  `£${(n ?? 0).toLocaleString('en-GB', { maximumFractionDigits: 0 })}`

const fmtAmount = (n: number | undefined, currency: 'GBP' | 'CNY' = 'CNY') =>
  currency === 'CNY' ? fmtCNY(n) : fmtGBP(n)

export default function TaxRequirementAccordion({
  title = '报税要求',
  requirements,
  defaultExpanded = true,
}: TaxRequirementAccordionProps) {
  const [open, setOpen] = useState(defaultExpanded)
  const [expandedIdx, setExpandedIdx] = useState<number | null>(0)

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
          <DocumentChartBarIcon className="w-4 h-4 text-primary" />
          <span className="font-medium text-fg text-sm">{title}</span>
          <span className="text-xs text-fg-dim bg-bg-elevated px-2 py-0.5 rounded-full">
            {requirements.length} 个税种
          </span>
        </div>
        <span className="text-xs text-fg-dim">
          {open ? '收起' : '展开'}
        </span>
      </button>

      {open && (
        <div className="border-t border-border">
          {requirements.map((req, i) => {
            const isExpanded = expandedIdx === i
            const currency = (req as any).currency === 'GBP' ? 'GBP' : 'CNY'
            return (
              <div
                key={i}
                className="border-b border-border last:border-b-0"
              >
                <button
                  onClick={() => setExpandedIdx(isExpanded ? null : i)}
                  className="w-full flex items-center justify-between px-4 py-3 hover:bg-bg-elevated/40 transition-colors text-left"
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <span className="text-[11px] font-mono text-fg-dim w-12 shrink-0">
                      {(i + 1).toString().padStart(2, '0')}
                    </span>
                    <span className="font-medium text-fg text-sm">
                      {req.tax_name || req.tax_type}
                    </span>
                    <span className="text-xs text-fg-dim">
                      {req.period}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <CapabilityBadge status={req.platform_support} />
                    {isExpanded ? (
                      <ChevronUpIcon className="w-4 h-4 text-fg-dim" />
                    ) : (
                      <ChevronDownIcon className="w-4 h-4 text-fg-dim" />
                    )}
                  </div>
                </button>

                {isExpanded && (
                  <div className="px-4 pb-4 pl-16 space-y-2 fade-in">
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                      {req.deadline && (
                        <div className="rounded border border-border p-2 bg-bg-elevated/40">
                          <div className="text-fg-dim text-[10px]">申报截止</div>
                          <div className="text-fg font-mono">{req.deadline}</div>
                        </div>
                      )}
                      {req.tax_due !== undefined && (
                        <div className="rounded border border-border p-2 bg-bg-elevated/40">
                          <div className="text-fg-dim text-[10px]">应纳税额</div>
                          <div className="text-fg font-mono font-medium">
                            {fmtAmount(req.tax_due, currency)}
                          </div>
                        </div>
                      )}
                      {req.taxable_profit !== undefined && (
                        <div className="rounded border border-border p-2 bg-bg-elevated/40">
                          <div className="text-fg-dim text-[10px]">应税利润</div>
                          <div className="text-fg font-mono">
                            {fmtAmount(req.taxable_profit, currency)}
                          </div>
                        </div>
                      )}
                      {req.box5_net_vat !== undefined && (
                        <div className="rounded border border-border p-2 bg-bg-elevated/40">
                          <div className="text-fg-dim text-[10px]">Box 5 净 VAT</div>
                          <div className="text-fg font-mono">
                            £{(req.box5_net_vat as number).toLocaleString('en-GB', { maximumFractionDigits: 0 })}
                          </div>
                        </div>
                      )}
                      {req.credit_limit !== undefined && (
                        <div className="rounded border border-border p-2 bg-bg-elevated/40">
                          <div className="text-fg-dim text-[10px]">抵免限额</div>
                          <div className="text-fg font-mono">
                            {fmtCNY(req.credit_limit)}
                          </div>
                        </div>
                      )}
                      {req.credit_taken !== undefined && (
                        <div className="rounded border border-border p-2 bg-bg-elevated/40">
                          <div className="text-fg-dim text-[10px]">实际抵免</div>
                          <div className="text-fg font-mono font-medium text-success">
                            {fmtCNY(req.credit_taken)}
                          </div>
                        </div>
                      )}
                    </div>

                    {req.missing && req.missing.length > 0 && (
                      <div className="rounded border border-warning/30 bg-warning-muted/30 p-2">
                        <div className="text-[10px] text-warning font-semibold uppercase tracking-wide mb-1">
                          平台缺失项
                        </div>
                        <ul className="text-xs text-fg-muted space-y-0.5 list-disc list-inside">
                          {req.missing.map((m, j) => (
                            <li key={j}>{m}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {req.evidence && (
                      <p className="text-[11px] text-fg-dim italic">
                        📎 {req.evidence}
                      </p>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
