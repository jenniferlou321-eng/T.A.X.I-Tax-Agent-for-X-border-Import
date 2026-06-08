import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  GlobeAltIcon,
  CheckCircleIcon,
  LinkIcon,
  ArrowRightIcon,
  ShieldCheckIcon,
  DocumentTextIcon,
} from '@heroicons/react/24/outline'
import { api } from '../api/client'
import type { Jurisdiction } from '../types'

const channelConfig: Record<string, { label: string; style: string }> = {
  api: { label: 'API', style: 'bg-success-muted text-success border-success/20' },
  browser: { label: 'Browser', style: 'bg-accent-muted text-accent border-accent/20' },
}

function JurisdictionCard({ jurisdiction, index }: { jurisdiction: Jurisdiction; index: number }) {
  return (
    <div
      className="card card-interactive p-5 fade-in"
      style={{ animationDelay: `${index * 80}ms` }}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-accent-muted flex items-center justify-center glow-accent">
            <GlobeAltIcon className="w-5 h-5 text-accent" strokeWidth={1.5} />
          </div>
          <div>
            <h3 className="text-base font-semibold text-fg">{jurisdiction.country_name}</h3>
            <p className="text-xs text-fg-dim font-mono mt-0.5">{jurisdiction.country_code.toUpperCase()}</p>
          </div>
        </div>
        <div className="flex items-center gap-1 text-success">
          <ShieldCheckIcon className="w-4 h-4" />
          <span className="text-xs font-medium">已就绪</span>
        </div>
      </div>

      <div className="space-y-2">
        {jurisdiction.tax_types.map((tt) => (
          <div
            key={tt.value}
            className="flex items-center justify-between px-3 py-2.5 bg-bg rounded-lg border border-border/50 hover:border-border transition-colors"
          >
            <div className="flex items-center gap-2">
              <CheckCircleIcon className="w-4 h-4 text-success shrink-0" />
              <span className="text-sm text-fg">{tt.label}</span>
            </div>
            <span className="text-xs text-fg-dim">{tt.value.toUpperCase()}</span>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border">
        {jurisdiction.supported_channels.map((ch) => {
          const config = channelConfig[ch] || { label: ch, style: 'bg-fg-dim/10 text-fg-dim' }
          return (
            <span
              key={ch}
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${config.style}`}
            >
              <LinkIcon className="w-3 h-3" />
              {config.label}
            </span>
          )
        })}
      </div>

      <div className="flex gap-2 mt-4">
        <Link
          to="/filings/new"
          className="btn btn-primary flex-1 text-sm"
        >
          <DocumentTextIcon className="w-4 h-4" />
          新建申报
        </Link>
        <button className="btn btn-ghost px-3">
          <ArrowRightIcon className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center fade-in">
      <div className="w-16 h-16 rounded-2xl bg-bg-elevated flex items-center justify-center mb-4">
        <GlobeAltIcon className="w-8 h-8 text-fg-dim" strokeWidth={1.5} />
      </div>
      <h3 className="text-lg font-semibold text-fg mb-1">暂无已配置的管辖地</h3>
      <p className="text-sm text-fg-muted mb-6 max-w-sm">
        管辖地配置完成后，您可以在此管理各国税务申报通道。
      </p>
      <button className="btn btn-primary">
        <GlobeAltIcon className="w-4 h-4" />
        添加管辖地
      </button>
    </div>
  )
}

// Backend returns {jurisdictions: [...]} with tax_types as string[] (e.g. ["vat"]).
// The card UI expects a typed TaxType[] — adapt at the boundary.

const taxTypeLabels: Record<string, string> = {
  vat: '增值税',
  cit: '企业所得税',
  ptt: '消费税',
  gst: '商品及服务税',
}
const formatTaxType = (t: string) => taxTypeLabels[t] ?? t.toUpperCase()

function JurisdictionListPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['jurisdictions'],
    queryFn: api.jurisdictions.list,
  })

  // Unwrap the response and normalise tax_types strings to {value,label}.
  const jurisdictions: Jurisdiction[] | undefined = data?.jurisdictions.map((j) => ({
    ...j,
    tax_types: j.tax_types.map((t) => ({ value: t, label: formatTaxType(t) })),
  }))

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 fade-in">
        <div>
          <h1 className="text-2xl font-bold text-fg tracking-tight">管辖地管理</h1>
          <p className="text-sm text-fg-muted mt-1">管理已配置的国家/地区税务申报通道</p>
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="card p-5 space-y-4">
              <div className="flex items-center gap-3">
                <div className="skeleton w-11 h-11 rounded-xl" />
                <div className="space-y-2 flex-1">
                  <div className="skeleton h-4 w-24" />
                  <div className="skeleton h-3 w-12" />
                </div>
              </div>
              <div className="skeleton h-10 rounded-lg" />
              <div className="skeleton h-10 rounded-lg" />
            </div>
          ))}
        </div>
      ) : !jurisdictions || jurisdictions.length === 0 ? (
        <div className="card">
          <EmptyState />
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {jurisdictions.map((j, idx) => (
            <JurisdictionCard key={j.country_code} jurisdiction={j} index={idx} />
          ))}
        </div>
      )}
    </div>
  )
}

export default JurisdictionListPage
