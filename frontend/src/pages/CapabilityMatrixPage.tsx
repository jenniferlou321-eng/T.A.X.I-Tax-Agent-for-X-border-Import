// 平台能力差距矩阵展示页 — 18 税种 × TAXI 支持状态
import { useNavigate } from 'react-router-dom'
import {
  ArrowLeftIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
  TableCellsIcon,
  ArrowTopRightOnSquareIcon,
} from '@heroicons/react/24/outline'
import jiahangShowcase from '../data/jiahangShowcase.json'
import CapabilityBadge from '../components/jiahang/CapabilityBadge'

interface TaxRow {
  id: number
  jurisdiction: 'UK' | 'CN'
  tax_code: string
  tax_name: string
  rate: string
  platform_support: string
}

export default function CapabilityMatrixPage() {
  const navigate = useNavigate()
  const matrix: TaxRow[] = (jiahangShowcase.tax_matrix as unknown as TaxRow[]) || []
  const stats = jiahangShowcase.summary_stats || {}
  const p0Priority = jiahangShowcase.p0_priority || []

  // 按 jurisdiction 分组
  const ukRows = matrix.filter((r) => r.jurisdiction === 'UK')
  const cnRows = matrix.filter((r) => r.jurisdiction === 'CN')

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-8">
      {/* 顶部导航 */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => navigate('/dashboard')}
          className="p-1.5 text-fg-dim hover:text-fg hover:bg-bg-elevated rounded-md transition-colors"
        >
          <ArrowLeftIcon className="w-4 h-4" />
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-fg tracking-tight flex items-center gap-2">
            <TableCellsIcon className="w-6 h-6 text-primary" />
            T.A.X.I. 平台能力差距矩阵
          </h1>
          <p className="text-sm text-fg-muted mt-0.5">
            基于嘉汉跨境税务案例的 18 税种 × 平台支持状态分析,平台未来路线图
          </p>
        </div>
      </div>

      {/* 统计 4 卡 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card p-4 fade-in" style={{ animationDelay: '0ms' }}>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-fg-dim">已支持</p>
              <p className="text-3xl font-bold text-success tracking-tight mt-1">
                {stats.supported}
              </p>
              <p className="text-[11px] text-fg-dim mt-1">/ {stats.total_tax_types} 税种</p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-success flex items-center justify-center glow-success">
              <CheckCircleIcon className="w-5 h-5 text-white" strokeWidth={2} />
            </div>
          </div>
        </div>
        <div className="card p-4 fade-in" style={{ animationDelay: '80ms' }}>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-fg-dim">部分支持</p>
              <p className="text-3xl font-bold text-warning tracking-tight mt-1">
                {stats.partial}
              </p>
              <p className="text-[11px] text-fg-dim mt-1">/ {stats.total_tax_types} 税种</p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-warning flex items-center justify-center glow-warning">
              <ExclamationTriangleIcon className="w-5 h-5 text-white" strokeWidth={2} />
            </div>
          </div>
        </div>
        <div className="card p-4 fade-in" style={{ animationDelay: '160ms' }}>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-fg-dim">待实现</p>
              <p className="text-3xl font-bold text-error tracking-tight mt-1">
                {stats.not_supported}
              </p>
              <p className="text-[11px] text-fg-dim mt-1">/ {stats.total_tax_types} 税种</p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-error flex items-center justify-center glow-error">
              <XCircleIcon className="w-5 h-5 text-white" strokeWidth={2} />
            </div>
          </div>
        </div>
        <div className="card p-4 fade-in" style={{ animationDelay: '240ms' }}>
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs text-fg-dim">完成度</p>
              <p className="text-3xl font-bold text-primary tracking-tight mt-1">
                {stats.completion_pct}%
              </p>
              <p className="text-[11px] text-fg-dim mt-1">长期目标 100%</p>
            </div>
            <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center shadow-glow-primary">
              <TableCellsIcon className="w-5 h-5 text-white" strokeWidth={2} />
            </div>
          </div>
        </div>
      </div>

      {/* P0 优先 */}
      <div className="card p-5 border-primary/30 bg-primary-muted/30 fade-in">
        <div className="flex items-center gap-2 mb-2">
          <span className="px-2 py-0.5 rounded bg-primary text-white text-[10px] font-bold">
            P0
          </span>
          <h2 className="text-base font-semibold text-fg">优先实现的核心税种</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          {p0Priority.map((p, i) => (
            <span
              key={i}
              className="px-3 py-1 rounded-full bg-primary text-white text-xs font-medium"
            >
              {p}
            </span>
          ))}
        </div>
        <p className="text-xs text-fg-muted mt-3">
          这 3 个税种的特点:**金额大、频率高、跨境必经**。先做完这 3 个,平台对中资跨境集团的覆盖率从 11% 提升到 38%。
        </p>
      </div>

      {/* UK 8 税种 + 1 不需申报 = 9 行 */}
      <div className="card overflow-hidden fade-in">
        <div className="px-4 py-3 bg-bg-elevated/50 border-b border-border flex items-center gap-2">
          <span className="px-2 py-0.5 rounded bg-primary/20 text-primary text-[10px] font-bold">UK</span>
          <h2 className="text-base font-semibold text-fg">英国税种(9 个)</h2>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px] text-fg-dim uppercase tracking-wide bg-bg/40">
              <th className="px-3 py-2 text-left w-12">#</th>
              <th className="px-3 py-2 text-left">税种</th>
              <th className="px-3 py-2 text-left">税率</th>
              <th className="px-3 py-2 text-left">平台状态</th>
            </tr>
          </thead>
          <tbody>
            {ukRows.map((r) => (
              <tr key={r.id} className="border-t border-border hover:bg-bg-elevated/40">
                <td className="px-3 py-2 font-mono text-xs text-fg-dim">{r.id}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px] text-primary bg-primary-muted/50 px-1.5 py-0.5 rounded shrink-0">
                      {r.tax_code}
                    </span>
                    <span className="font-medium text-fg">{r.tax_name}</span>
                  </div>
                </td>
                <td className="px-3 py-2 text-fg-dim text-xs">{r.rate}</td>
                <td className="px-3 py-2"><CapabilityBadge status={r.platform_support} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* CN 9 税种 */}
      <div className="card overflow-hidden fade-in">
        <div className="px-4 py-3 bg-bg-elevated/50 border-b border-border flex items-center gap-2">
          <span className="px-2 py-0.5 rounded bg-accent/20 text-accent text-[10px] font-bold">CN</span>
          <h2 className="text-base font-semibold text-fg">中国税种(9 个)</h2>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px] text-fg-dim uppercase tracking-wide bg-bg/40">
              <th className="px-3 py-2 text-left w-12">#</th>
              <th className="px-3 py-2 text-left">税种</th>
              <th className="px-3 py-2 text-left">税率</th>
              <th className="px-3 py-2 text-left">平台状态</th>
            </tr>
          </thead>
          <tbody>
            {cnRows.map((r) => (
              <tr key={r.id} className="border-t border-border hover:bg-bg-elevated/40">
                <td className="px-3 py-2 font-mono text-xs text-fg-dim">{r.id}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[11px] text-accent bg-accent/10 px-1.5 py-0.5 rounded shrink-0">
                      {r.tax_code}
                    </span>
                    <span className="font-medium text-fg">{r.tax_name}</span>
                  </div>
                </td>
                <td className="px-3 py-2 text-fg-dim text-xs">{r.rate}</td>
                <td className="px-3 py-2"><CapabilityBadge status={r.platform_support} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 完整 markdown 文档链接 */}
      <div className="card p-5 fade-in">
        <h2 className="text-base font-semibold text-fg mb-2">完整能力差距分析文档</h2>
        <p className="text-sm text-fg-muted mb-3">
          含每个税种的缺失项明细、工作量估算、3 步走路径图(Foundation / Coverage / Long Tail)、跨平台架构缺口分析。
        </p>
        <div className="flex flex-wrap gap-2">
          <a
            href="/docs/cases/jiahang-capability-matrix.md"
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-primary"
          >
            <ArrowTopRightOnSquareIcon className="w-4 h-4" />
            查看完整文档
          </a>
          <a
            href="/docs/cases/jiahang-data-model.md"
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn-ghost"
          >
            数据模型说明
          </a>
        </div>
      </div>

      {/* 案例驱动平台完善 — 价值主张 */}
      <div className="card p-5 fade-in">
        <h2 className="text-base font-semibold text-fg mb-2">为什么用嘉汉案例驱动平台完善?</h2>
        <ul className="text-sm text-fg-muted space-y-1 list-disc list-inside">
          <li><span className="text-fg font-medium">真实业务密度</span>:嘉汉案例 98 笔业务覆盖 18 个税种,远超单一国家场景</li>
          <li><span className="text-fg font-medium">关联交易完整</span>:5 类配对(贷款/利息/特许权/股息/服务费),母→子双向镜像</li>
          <li><span className="text-fg font-medium">税务复杂度</span>:暂性差异 4 笔事件 + 跨年度业务 + 汇算清缴 4 笔分录,DTA 完整滚动</li>
          <li><span className="text-fg font-medium">中英协定应用</span>:WHT 10% / 股息 0% / 抵免 ¥43,679(足额),消除双重征税完整链路</li>
          <li><span className="text-fg font-medium">P0 信号清晰</span>:UK CT、CN VAT、CN CIT 三个最大税种,优先级一目了然</li>
        </ul>
      </div>
    </div>
  )
}
