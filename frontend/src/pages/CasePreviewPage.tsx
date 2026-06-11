import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  CpuChipIcon,
  ArrowRightIcon,
  DocumentTextIcon,
  ArrowLeftIcon,
} from '@heroicons/react/24/outline'
import { useDemoStore } from '../stores/demoStore'
import CaseHeaderCard from '../components/CaseHeaderCard'
import ErpInvoiceTable from '../components/ErpInvoiceTable'
import NineBoxEditor from '../components/NineBoxEditor'

export default function CasePreviewPage() {
  const navigate = useNavigate()
  const { presetId } = useParams<{ presetId: string }>()

  const buffer = useDemoStore((s) => s.buffer)
  const loadCase = useDemoStore((s) => s.loadCase)
  const setNineBoxValue = useDemoStore((s) => s.setNineBoxValue)
  const resetNineBox = useDemoStore((s) => s.resetNineBox)

  // Route guard:没有 buffer 或 URL 不匹配 → 回 dashboard
  useEffect(() => {
    if (!buffer || buffer.presetId !== presetId) {
      navigate('/dashboard', { replace: true })
    }
  }, [buffer, presetId, navigate])

  if (!buffer || buffer.presetId !== presetId) {
    return null
  }

  const handleGoToAgent = () => {
    navigate('/agent')
  }

  const handleGoToManual = () => {
    navigate('/filings/new', { state: { fromBuffer: true } })
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-8">
      {/* 顶部导航 + 标题 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/dashboard')}
            className="p-1.5 text-fg-dim hover:text-fg hover:bg-bg-elevated rounded-md transition-colors"
          >
            <ArrowLeftIcon className="w-4 h-4" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-fg tracking-tight">
              Case 数据预览
            </h1>
            <p className="text-sm text-fg-muted mt-0.5">
              检查原始数据、调整 9-Box 数值，然后让 AI 帮你完成申报
            </p>
          </div>
        </div>
      </div>

      {/* Case 头部信息 */}
      <CaseHeaderCard preset={buffer.preset} />

      {/* ERP 原始发票 */}
      <ErpInvoiceTable />

      {/* 9-Box 可编辑表单 */}
      <NineBoxEditor
        values={buffer.nineBox}
        onChange={setNineBoxValue}
        onReset={resetNineBox}
      />

      {/* 底部行动按钮 */}
      <div className="sticky bottom-0 bg-bg-surface/80 backdrop-blur-sm border-t border-border py-4 -mx-4 px-4 flex flex-col sm:flex-row items-center gap-3 sm:gap-4">
        <button
          onClick={handleGoToAgent}
          className="btn btn-primary flex-1 w-full sm:w-auto flex items-center justify-center gap-2"
        >
          <CpuChipIcon className="w-5 h-5" />
          让 AI 帮我报税
          <ArrowRightIcon className="w-4 h-4" />
        </button>

        <button
          onClick={handleGoToManual}
          className="btn btn-ghost flex items-center gap-2 text-fg-dim"
        >
          <DocumentTextIcon className="w-4 h-4" />
          手动填写申报
        </button>
      </div>
    </div>
  )
}
