import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  CalendarIcon,
  DocumentCheckIcon,
  ExclamationTriangleIcon,
  ArrowLeftIcon,
} from '@heroicons/react/24/outline'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import PipelineVisualizer from '../components/PipelineVisualizer'

const statusConfig: Record<string, { style: string; label: string; icon: React.ElementType }
> = {
  pending: { style: 'bg-warning-muted text-warning border-warning/20', label: '待处理', icon: ClockIcon },
  in_progress: { style: 'bg-info-muted text-info border-info/20', label: '进行中', icon: ArrowPathIcon },
  submitted: { style: 'bg-accent-muted text-accent border-accent/20', label: '已提交', icon: CheckCircleIcon },
  accepted: { style: 'bg-success-muted text-success border-success/20', label: '已受理', icon: CheckCircleIcon },
  rejected: { style: 'bg-error-muted text-error border-error/20', label: '已驳回', icon: XCircleIcon },
  error: { style: 'bg-error-muted text-error border-error/20', label: '错误', icon: XCircleIcon },
}

const stageOrder = ['PRECHECK', 'PREPARE', 'CALCULATE', 'VALIDATE', 'SUBMIT', 'TRACK']
const stageLabels: Record<string, string> = {
  PRECHECK: '前置检查',
  PREPARE: '数据准备',
  CALCULATE: '税额计算',
  VALIDATE: '规则校验',
  SUBMIT: '提交申报',
  TRACK: '状态追踪',
}

function StatusBadge({ status }: { status: string }) {
  const config = statusConfig[status] || { style: 'bg-fg-dim/10 text-fg-dim border-fg-dim/20', label: status, icon: ClockIcon }
  const Icon = config.icon
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium border ${config.style}`}>
      <Icon className="w-4 h-4" />
      {config.label}
    </span>
  )
}

function TimelineItem({ stage, index, total }: {
  stage: { stage: string; status: string; message: string }
  index: number
  total: number
}) {
  const isPassed = stage.status === 'success'
  const isFailed = stage.status === 'error'
  const isWarning = stage.status === 'warning'
  const isLast = index === total - 1

  return (
    <div className="flex gap-4">
      {/* Timeline connector */}
      <div className="flex flex-col items-center shrink-0">
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 transition-all duration-300 ${
            isPassed
              ? 'bg-success text-white glow-success-sm'
              : isFailed
              ? 'bg-error text-white glow-error-sm'
              : isWarning
              ? 'bg-warning text-white glow-warning-sm'
              : 'bg-bg-elevated text-fg-dim border border-border'
          }`}
        >
          {isPassed ? (
            <CheckCircleIcon className="w-4 h-4" strokeWidth={2.5} />
          ) : isFailed ? (
            <XCircleIcon className="w-4 h-4" strokeWidth={2.5} />
          ) : isWarning ? (
            <ExclamationTriangleIcon className="w-4 h-4" strokeWidth={2.5} />
          ) : (
            <ClockIcon className="w-4 h-4" strokeWidth={2} />
          )}
        </div>
        {!isLast && (
          <div
            className={`w-px flex-1 min-h-[24px] mt-1 transition-colors duration-500 ${
              isPassed ? 'bg-success/40' : isWarning ? 'bg-warning/40' : 'bg-border'
            }`}
          />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 pb-5">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-semibold text-fg">
            {stageLabels[stage.stage] || stage.stage}
          </span>
          <span
            className={`text-xs font-medium px-2 py-0.5 rounded-full ${
              isPassed
                ? 'bg-success-muted text-success'
                : isFailed
                ? 'bg-error-muted text-error'
                : isWarning
                ? 'bg-warning-muted text-warning'
                : 'bg-bg-elevated text-fg-dim'
            }`}
          >
            {isPassed ? '通过' : isFailed ? '失败' : isWarning ? '警告' : '待处理'}
          </span>
        </div>
        <p className="text-sm text-fg-muted mt-1">{stage.message}</p>
      </div>
    </div>
  )
}

function FilingDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: filing, isLoading } = useQuery({
    queryKey: ['filing', id],
    queryFn: () => api.filings.get(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const terminal = ['accepted', 'rejected', 'error', 'submitted'];
      const filingData = query.state.data;
      return filingData && terminal.includes(filingData.status) ? false : 500;
    },
  })

  if (isLoading) {
    return (
      <div className="max-w-3xl mx-auto flex flex-col items-center justify-center py-24 fade-in">
        <ArrowPathIcon className="w-10 h-10 text-fg-dim animate-spin mb-4" />
        <p className="text-sm text-fg-muted">加载申报详情...</p>
      </div>
    )
  }

  if (!filing) {
    return (
      <div className="max-w-3xl mx-auto text-center py-24 fade-in">
        <div className="w-16 h-16 rounded-2xl bg-bg-elevated flex items-center justify-center mx-auto mb-4">
          <DocumentTextIcon className="w-8 h-8 text-fg-dim" strokeWidth={1.5} />
        </div>
        <h3 className="text-lg font-semibold text-fg mb-1">未找到申报记录</h3>
        <p className="text-sm text-fg-muted mb-6">该申报 ID 不存在或已被删除</p>
        <Link to="/dashboard" className="btn btn-secondary">
          <ArrowLeftIcon className="w-4 h-4" />
          返回仪表盘
        </Link>
      </div>
    )
  }

  const stages = stageOrder
    .map((key) => filing.stage_results?.[key])
    .filter(Boolean)

  return (
    <div className="max-w-3xl mx-auto space-y-5 fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link
              to="/dashboard"
              className="p-1.5 -ml-1.5 text-fg-dim hover:text-fg hover:bg-bg-elevated rounded-md transition-colors"
            >
              <ArrowLeftIcon className="w-4 h-4" />
            </Link>
            <h1 className="text-xl font-bold text-fg tracking-tight">申报详情</h1>
          </div>
          <p className="text-xs text-fg-dim font-mono ml-5">{filing.filing_id}</p>
        </div>
        <StatusBadge status={filing.status} />
      </div>

      {/* Pipeline Timeline */}
      <div className="card p-5">
        <div className="flex items-center gap-2 mb-5">
          <ArrowPathIcon className="w-4 h-4 text-fg-muted" />
          <h2 className="text-base font-semibold text-fg">申报流程</h2>
        </div>
        <div>
          {stages.map((stage, idx) => (
            <TimelineItem key={stage.stage} stage={stage} index={idx} total={stages.length} />
          ))}
        </div>
      </div>

      {/* Receipt */}
      {filing.receipt && (
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-4">
            <DocumentCheckIcon className="w-4 h-4 text-fg-muted" />
            <h2 className="text-base font-semibold text-fg">税局回执</h2>
          </div>
          <div className="space-y-3">
            <div className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-bg-elevated/30 transition-colors">
              <div className="flex items-center gap-2 text-sm text-fg-muted">
                <DocumentTextIcon className="w-4 h-4" />
                回执编号
              </div>
              <span className="text-sm font-mono text-fg font-medium">{filing.receipt.receipt_id}</span>
            </div>
            <div className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-bg-elevated/30 transition-colors">
              <div className="flex items-center gap-2 text-sm text-fg-muted">
                <CalendarIcon className="w-4 h-4" />
                提交时间
              </div>
              <span className="text-sm text-fg">
                {new Date(filing.receipt.submitted_at).toLocaleString('zh-CN')}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Pipeline Visualizer */}
      <div className="mt-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-3">管线执行记录</h3>
        <PipelineVisualizer stages={filing?.stage_results || {}} interactive={true} />
      </div>

      {/* Errors */}
      {filing.errors.length > 0 && (
        <div className="card p-5 border-error/30">
          <div className="flex items-center gap-2 mb-4">
            <ExclamationTriangleIcon className="w-4 h-4 text-error" />
            <h2 className="text-base font-semibold text-error">错误信息</h2>
          </div>
          <div className="space-y-3">
            {filing.errors.map((err, idx) => (
              <div
                key={idx}
                className="flex items-start gap-3 p-3 bg-error-muted rounded-lg border border-error/10"
              >
                <XCircleIcon className="w-4 h-4 text-error mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-semibold text-fg">{err.code}</p>
                  <p className="text-sm text-fg-muted mt-0.5">{err.message}</p>
                  <p className="text-xs text-fg-dim mt-1">阶段: {stageLabels[err.stage] || err.stage}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default FilingDetailPage