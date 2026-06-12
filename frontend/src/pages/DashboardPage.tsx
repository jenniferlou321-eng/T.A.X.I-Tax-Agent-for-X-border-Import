import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import {
  ClockIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  ArrowRightIcon,
  DocumentTextIcon,
  GlobeAltIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline'
import { api } from '../api/client'
import type { FilingResult } from '../types'
import CasePresetCard from '../components/CasePresetCard'
import ErpConnectionToggle from '../components/ErpConnectionToggle'
import ClearDataButton from '../components/ClearDataButton'
import { casePresets, type CasePreset } from '../data/casePresets'
import { useDemoStore } from '../stores/demoStore'

const statusConfig: Record<string, { style: string; label: string; dot: string }> = {
  pending: { style: 'bg-warning-muted text-warning border-warning/20', label: '待处理', dot: 'bg-warning' },
  in_progress: { style: 'bg-info-muted text-info border-info/20', label: '进行中', dot: 'bg-info' },
  submitted: { style: 'bg-accent-muted text-accent border-accent/20', label: '已提交', dot: 'bg-accent' },
  accepted: { style: 'bg-success-muted text-success border-success/20', label: '已受理', dot: 'bg-success' },
  rejected: { style: 'bg-error-muted text-error border-error/20', label: '已驳回', dot: 'bg-error' },
  error: { style: 'bg-error-muted text-error border-error/20', label: '错误', dot: 'bg-error' },
}

function StatusBadge({ status }: { status: string }) {
  const config = statusConfig[status] || { style: 'bg-fg-dim/10 text-fg-dim border-fg-dim/20', label: status, dot: 'bg-fg-dim' }
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${config.style}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      {config.label}
    </span>
  )
}

function StatCard({ title, value, icon: Icon, colorClass, glowClass, delay }: {
  title: string
  value: string
  icon: React.ElementType
  colorClass: string
  glowClass: string
  delay: number
}) {
  return (
    <div
      className="card card-interactive p-5 fade-in"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <p className="text-sm text-fg-dim">{title}</p>
          <p className="text-3xl font-bold text-fg tracking-tight">{value}</p>
        </div>
        <div className={`w-10 h-10 rounded-lg ${colorClass} flex items-center justify-center shrink-0 ${glowClass}`}>
          <Icon className="w-5 h-5 text-white" strokeWidth={2} />
        </div>
      </div>
    </div>
  )
}

function SkeletonRow() {
  return (
    <div className="flex items-center justify-between px-6 py-4">
      <div className="space-y-2 flex-1">
        <div className="skeleton h-4 w-32" />
        <div className="skeleton h-3 w-48" />
      </div>
      <div className="skeleton h-6 w-16 rounded-full" />
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center fade-in">
      <div className="w-16 h-16 rounded-2xl bg-bg-elevated flex items-center justify-center mb-4">
        <DocumentTextIcon className="w-8 h-8 text-fg-dim" strokeWidth={1.5} />
      </div>
      <h3 className="text-lg font-semibold text-fg mb-1">暂无申报记录</h3>
      <p className="text-sm text-fg-muted mb-6 max-w-sm">
        您还没有提交过任何税务申报。点击下方按钮开始您的第一个申报。
      </p>
      <Link
        to="/filings/new"
        className="btn btn-primary"
      >
        <DocumentTextIcon className="w-4 h-4" />
        创建第一个申报
      </Link>
    </div>
  )
}

function DashboardPage() {
  const navigate = useNavigate()
  const loadCase = useDemoStore((s) => s.loadCase)
  const buffer = useDemoStore((s) => s.buffer)
  const selectedPreset = useDemoStore((s) => s.selectedPreset)  // PR 5 才删

  const handleLoadCase = (preset: CasePreset) => {
    loadCase(preset)
    navigate('/cases/' + preset.id)
  }

  const handleSwitchCase = (preset: CasePreset) => {
    if (window.confirm(`切换到 "${preset.title}"？当前数据将被清空。`)) {
      loadCase(preset)
    }
  }

  const { data: filingsRes, isLoading } = useQuery({
    queryKey: ['filings'],
    queryFn: api.filings.list,
  })

  const filings = filingsRes?.filings || []

  const stats = {
    pending: filings.filter((f: FilingResult) => f.status === 'pending' || f.status === 'in_progress').length || 0,
    submitted: filings.filter((f: FilingResult) => f.status === 'submitted').length || 0,
    accepted: filings.filter((f: FilingResult) => f.status === 'accepted').length || 0,
    errors: filings.filter((f: FilingResult) => f.status === 'error' || f.status === 'rejected').length || 0,
  }

  const hasFilings = filings.length > 0

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Dashboard 控件三件套 (v0 修订) */}
      <div className="flex items-center justify-between gap-4 fade-in">
        <div className="flex-1">
          <ErpConnectionToggle />
        </div>
        <ClearDataButton />
      </div>

      {buffer?.presetId && (
        <div className="card p-4 flex items-center justify-between fade-in">
          <p className="text-sm text-fg-muted">
            已加载 Case: <span className="font-medium text-fg">
              {casePresets.find(p => p.id === buffer.presetId)?.title}
            </span>
          </p>
          <button
            onClick={() => {
              const cur = casePresets.find(p => p.id === buffer.presetId)
              if (cur) handleSwitchCase(cur)
            }}
            className="btn btn-sm btn-ghost"
          >
            切换 Case
          </button>
        </div>
      )}

      {/* Import Hub entry — 外部数据流入口(在 case grid 上方,作为独立入口) */}
      <div className="fade-in flex justify-end">
        <button
          onClick={() => navigate('/import')}
          className="btn btn-primary"
          data-testid="dashboard-import-entry"
        >
          ⬇ 导入外部数据
        </button>
      </div>

      {/* Quick Demo Scenarios */}
      <div className="fade-in">
        <h2 className="text-lg font-semibold text-fg mb-3">快速演示场景</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {casePresets.map((preset) => (
            <CasePresetCard
              key={preset.id}
              preset={preset}
              onLoad={preset.id === buffer?.presetId ? handleSwitchCase : handleLoadCase}
              isSelected={preset.id === buffer?.presetId}
            />
          ))}
        </div>
      </div>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 fade-in">
        <div>
          <h1 className="text-2xl font-bold text-fg tracking-tight">仪表盘</h1>
          <p className="text-sm text-fg-muted mt-1">概览您的税务申报状态和近期活动</p>
        </div>
        <Link
          to="/filings/new"
          className="btn btn-primary self-start"
        >
          新建申报
          <ArrowRightIcon className="w-4 h-4" />
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="待处理"
          value={String(stats.pending)}
          icon={ClockIcon}
          colorClass="bg-warning"
          glowClass="glow-warning"
          delay={0}
        />
        <StatCard
          title="已提交"
          value={String(stats.submitted)}
          icon={ArrowRightIcon}
          colorClass="bg-accent"
          glowClass="glow-accent"
          delay={80}
        />
        <StatCard
          title="已受理"
          value={String(stats.accepted)}
          icon={CheckCircleIcon}
          colorClass="bg-success"
          glowClass="glow-success"
          delay={160}
        />
        <StatCard
          title="异常"
          value={String(stats.errors)}
          icon={ExclamationTriangleIcon}
          colorClass="bg-error"
          glowClass="glow-error"
          delay={240}
        />
      </div>

      {/* Recent Filings */}
      <div className="card overflow-hidden fade-in" style={{ animationDelay: '300ms' }}>
        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <DocumentTextIcon className="w-4 h-4 text-fg-muted" />
            <h2 className="text-base font-semibold text-fg">近期申报</h2>
          </div>
          {hasFilings && (
            <Link to="/filings" className="text-sm text-primary hover:text-primary-hover transition-colors flex items-center gap-1">
              查看全部
              <ChevronRightIcon className="w-4 h-4" />
            </Link>
          )}
        </div>

        {isLoading ? (
          <div className="divide-y divide-border">
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
          </div>
        ) : !hasFilings ? (
          <EmptyState />
        ) : (
          <div className="divide-y divide-border">
            {filings.slice(0, 5).map((filing: FilingResult) => (
              <Link
                key={filing.filing_id}
                to={`/filings/${filing.filing_id}`}
                className="flex items-center justify-between px-5 py-4 hover:bg-bg-elevated/40 transition-colors duration-200 group"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-8 h-8 rounded-md bg-bg-elevated flex items-center justify-center shrink-0 group-hover:bg-primary-muted transition-colors duration-200">
                    <GlobeAltIcon className="w-4 h-4 text-fg-dim group-hover:text-primary transition-colors duration-200" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-fg truncate">{filing.filing_id}</p>
                    <p className="text-xs text-fg-dim mt-0.5">
                      {filing.receipt ? `回执: ${filing.receipt.receipt_id}` : '等待提交'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <StatusBadge status={filing.status} />
                  <ChevronRightIcon className="w-4 h-4 text-fg-dim opacity-0 group-hover:opacity-100 transition-opacity duration-200" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default DashboardPage
