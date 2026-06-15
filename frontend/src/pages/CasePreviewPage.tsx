import { useEffect, useState } from 'react'
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
import CnGroupSummaryCard from '../components/CnGroupSummaryCard'
import TaxRequirementAccordion from '../components/jiahang/TaxRequirementAccordion'
import MirrorLedgerTable, { type MirrorEvent } from '../components/jiahang/MirrorLedgerTable'
import TemporaryDiffCard, {
  type TempDiffEvent,
  type DtaBalance,
} from '../components/jiahang/TemporaryDiffCard'
import AmendmentTimelineCard, { type AmendEntry } from '../components/jiahang/AmendmentTimelineCard'
import type { TaxRequirement } from '../types/jiahang'

export default function CasePreviewPage() {
  const navigate = useNavigate()
  const { presetId } = useParams<{ presetId: string }>()

  const buffer = useDemoStore((s) => s.buffer)
  const loadCase = useDemoStore((s) => s.loadCase)
  const setNineBoxValue = useDemoStore((s) => s.setNineBoxValue)
  const resetNineBox = useDemoStore((s) => s.resetNineBox)

  // jiahang 案例附加数据(从静态 JSON 加载)
  const [taxRequirements, setTaxRequirements] = useState<TaxRequirement[]>([])
  const [mirrorEvents, setMirrorEvents] = useState<MirrorEvent[]>([])
  const [tempDiffEvents, setTempDiffEvents] = useState<TempDiffEvent[]>([])
  const [dtaBalance, setDtaBalance] = useState<DtaBalance | null>(null)
  const [amendments, setAmendments] = useState<AmendEntry[]>([])

  const isJiahang = !!buffer?.preset?.id?.startsWith('case-jiahang-')
  const isJiahangCN = buffer?.preset?.id === 'case-jiahang-cn-fy2023'

  // Route guard:没有 buffer 或 URL 不匹配 → 回 dashboard
  useEffect(() => {
    if (!buffer || buffer.presetId !== presetId) {
      navigate('/dashboard', { replace: true })
    }
  }, [buffer, presetId, navigate])

  // 加载 jiahang 案例的附加 JSON 数据
  useEffect(() => {
    if (!isJiahang) return
    let active = true
    // 1. tax_requirements.json — 按 case id 加载
    const reqLoader =
      buffer?.preset?.id === 'case-jiahang-uk-fy2023'
        ? import('../data/jiahang-uk-fy2023-tax-requirements.json')
        : buffer?.preset?.id === 'case-jiahang-uk-fy2023-al-error'
          ? import('../data/jiahang-uk-fy2023-al-error-tax-requirements.json')
          : buffer?.preset?.id === 'case-jiahang-cn-fy2023'
            ? import('../data/jiahang-cn-fy2023-tax-requirements.json')
            : Promise.resolve(null)
    reqLoader.then((mod: any) => {
      if (active && mod) {
        setTaxRequirements((mod.default || mod).filings || [])
      }
    })
    // 2. jiahangCnFiling 提供 mirror + dta + amendments(若 CN case)
    if (isJiahangCN) {
      import('../data/jiahangCnFiling.json').then((mod) => {
        if (!active) return
        const d = mod as any
        setMirrorEvents(d?.related_party?.events || [])
        setTempDiffEvents(d?.dta?.events || [])
        setDtaBalance({
          beginning_cny: d?.dta?.beginning_cny || 0,
          reversal_cny: d?.dta?.reversal_cny || 0,
          new_recognized_cny: d?.dta?.new_recognized_cny || 0,
          ending_cny: d?.dta?.ending_cny || 0,
        })
        setAmendments(d?.amendments || [])
      })
    }
    return () => {
      active = false
    }
  }, [isJiahang, isJiahangCN, buffer?.preset?.id])

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
              {isJiahang && (
                <span className="ml-2 inline-flex items-center gap-1 text-[10px] font-bold text-white bg-primary px-1.5 py-0.5 rounded align-middle">
                  嘉汉
                </span>
              )}
            </h1>
            <p className="text-sm text-fg-muted mt-0.5">
              {isJiahang
                ? '完整账套 + 报税要求 + 关联交易 + 暂性差异,案例驱动平台完善路线图'
                : '检查原始数据、调整 9-Box 数值,然后让 AI 帮你完成申报'}
            </p>
          </div>
        </div>
      </div>

      {/* Case 头部信息 */}
      <CaseHeaderCard preset={buffer.preset} />

      {/* ERP 原始发票(10 列升级版,多货币 + 4 新列) */}
      <ErpInvoiceTable />

      {/* Case B / Case J (CN) 专用:CN 集团数字汇总卡 */}
      {buffer.preset.groupDataRef && (
        <CnGroupSummaryCard dataRef={buffer.preset.groupDataRef} />
      )}

      {/* jiahang 专用 4 折叠区(默认首个展开) */}
      {isJiahang && taxRequirements.length > 0 && (
        <div className="space-y-3">
          <TaxRequirementAccordion
            title="报税要求清单(原始数字保留)"
            requirements={taxRequirements}
            defaultExpanded={true}
          />
          {isJiahangCN && mirrorEvents.length > 0 && (
            <MirrorLedgerTable events={mirrorEvents} defaultExpanded={false} />
          )}
          {isJiahangCN && tempDiffEvents.length > 0 && dtaBalance && (
            <TemporaryDiffCard
              events={tempDiffEvents}
              balance={dtaBalance}
              defaultExpanded={false}
            />
          )}
          {isJiahangCN && amendments.length > 0 && (
            <AmendmentTimelineCard entries={amendments} defaultExpanded={false} />
          )}
        </div>
      )}

      {/* 9-Box 可编辑表单(只对 UK 9-Box 案例有意义;jiahang / Case B 跳过) */}
      {!isJiahang && buffer.preset.lineItems.length > 0 && (
        <NineBoxEditor
          values={buffer.nineBox}
          onChange={setNineBoxValue}
          onReset={resetNineBox}
        />
      )}

      {/* 底部行动按钮 */}
      <div className="sticky bottom-0 bg-bg-surface/80 backdrop-blur-sm border-t border-border py-4 -mx-4 px-4 flex flex-col sm:flex-row items-center gap-3 sm:gap-4">
        <button
          onClick={handleGoToAgent}
          className="btn btn-primary flex-1 w-full sm:w-auto flex items-center justify-center gap-2"
        >
          <CpuChipIcon className="w-5 h-5" />
          {isJiahang ? '让 AI 解析案例' : '让 AI 帮我报税'}
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
