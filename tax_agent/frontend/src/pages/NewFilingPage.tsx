import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  CheckIcon,
  GlobeAltIcon,
  CalculatorIcon,
  ShieldCheckIcon,
  ChevronRightIcon,
  ArrowLeftIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  DocumentCheckIcon,
  BanknotesIcon,
  CalendarDaysIcon,
  IdentificationIcon,
} from '@heroicons/react/24/outline'
import { api } from '../api/client'
import type { DataTemplate, LineItem, CalculationResult, VATObligation, ValidationResult, FilingResult, StageResult } from '../types'
import PipelineVisualizer from '../components/PipelineVisualizer'
import { HMRCReceiptCard } from '../components/HMRCReceiptCard'
import { casePresets } from '../data/casePresets'
import { useDemoStore } from '../stores/demoStore'
import { useUserProfile } from '../stores/userProfile'

const STEPS = [
  { id: 1, label: '选择管辖地', icon: GlobeAltIcon },
  { id: 2, label: '申报义务', icon: CalendarDaysIcon },
  { id: 3, label: '数据录入', icon: BanknotesIcon },
  { id: 4, label: '预览计算', icon: CalculatorIcon },
  { id: 5, label: '确认提交', icon: ShieldCheckIcon },
]

function StepIndicator({ currentStep }: { currentStep: number }) {
  return (
    <div className="mb-8">
      <div className="flex items-center justify-between">
        {STEPS.map((step, idx) => {
          const isCompleted = step.id < currentStep
          const isCurrent = step.id === currentStep

          return (
            <div key={step.id} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center gap-2"
                style={{ minWidth: isCurrent ? 'auto' : undefined }}
              >
                {/* Step circle */}
                <div
                  className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 transition-all duration-300 ${
                    isCompleted
                      ? 'bg-success text-white glow-success'
                      : isCurrent
                      ? 'bg-primary text-on-primary ring-4 ring-primary/15 shadow-glow-primary'
                      : 'bg-bg-elevated text-fg-dim border border-border'
                  }`}
                >
                  {isCompleted ? (
                    <CheckIcon className="w-4 h-4" strokeWidth={2.5} />
                  ) : (
                    <step.icon className="w-4 h-4" strokeWidth={2} />
                  )}
                </div>
                {/* Label */}
                <span
                  className={`text-xs font-medium whitespace-nowrap transition-colors duration-200 ${
                    isCurrent ? 'text-fg' : isCompleted ? 'text-success' : 'text-fg-dim'
                  }`}
                >
                  {step.label}
                </span>
              </div>
              {/* Connector */}
              {idx < STEPS.length - 1 && (
                <div className="flex-1 h-px mx-3 mb-5 relative">
                  <div
                    className={`absolute inset-0 transition-colors duration-500 ${
                      isCompleted ? 'bg-success/60' : 'bg-border'
                    }`}
                  />
                  {isCompleted && (
                    <div className="absolute inset-0 bg-success/30 animate-pulse" />
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function JurisdictionSelector({
  onSelect,
  initialVrn = '',
}: {
  onSelect: (country: string, taxType: string, vrn: string) => void
  initialVrn?: string
}) {
  const [country, setCountry] = useState('uk')
  const [taxType, setTaxType] = useState('vat')
  const [vrn, setVrn] = useState(initialVrn)

  return (
    <div className="max-w-lg mx-auto space-y-6 fade-in">
      <div className="text-center mb-8">
        <div className="w-14 h-14 rounded-2xl bg-primary-muted flex items-center justify-center mx-auto mb-4">
          <GlobeAltIcon className="w-7 h-7 text-primary" strokeWidth={1.5} />
        </div>
        <h2 className="text-xl font-bold text-fg">选择申报管辖地</h2>
        <p className="text-sm text-fg-muted mt-1">选择您需要提交税务申报的国家/地区和税种</p>
      </div>

      <div className="card p-5 space-y-5">
        <div>
          <label className="block text-sm font-medium text-fg mb-2">国家 / 地区</label>
          <div className="relative">
            <select
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              className="input appearance-none pr-10"
            >
              <option value="uk">🇬🇧 英国 (United Kingdom)</option>
            </select>
            <ChevronRightIcon className="w-4 h-4 text-fg-dim absolute right-3 top-1/2 -translate-y-1/2 rotate-90 pointer-events-none" />
          </div>
          <p className="text-xs text-fg-dim mt-1.5">更多国家/地区即将支持</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-fg mb-2">税种</label>
          <div className="relative">
            <select
              value={taxType}
              onChange={(e) => setTaxType(e.target.value)}
              className="input appearance-none pr-10"
            >
              <option value="vat">增值税 (VAT)</option>
            </select>
            <ChevronRightIcon className="w-4 h-4 text-fg-dim absolute right-3 top-1/2 -translate-y-1/2 rotate-90 pointer-events-none" />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-fg mb-2">
            VAT 注册号 (VRN)
          </label>
          <div className="relative">
            <IdentificationIcon className="w-4 h-4 text-fg-dim absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={vrn}
              onChange={(e) => setVrn(e.target.value)}
              placeholder="例如: 123456789"
              className="input pl-10"
            />
          </div>
          <p className="text-xs text-fg-dim mt-1.5">
            您的 VAT Registration Number，用于从 HMRC 获取申报义务
          </p>
        </div>

        <button
          onClick={() => onSelect(country, taxType, vrn)}
          disabled={!vrn.trim()}
          className="btn btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
        >
          下一步
          <ChevronRightIcon className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}

function ObligationSelector({
  vrn,
  onSelect,
  onBack,
}: {
  vrn: string
  onSelect: (obligation: VATObligation) => void
  onBack: () => void
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['obligations', vrn],
    queryFn: () => api.filings.obligations('uk', 'vat', vrn, { status: 'O' }),
  })

  const obligations = data?.obligations || []

  return (
    <div className="max-w-lg mx-auto space-y-6 fade-in">
      <div className="text-center mb-8">
        <div className="w-14 h-14 rounded-2xl bg-primary-muted flex items-center justify-center mx-auto mb-4">
          <CalendarDaysIcon className="w-7 h-7 text-primary" strokeWidth={1.5} />
        </div>
        <h2 className="text-xl font-bold text-fg">选择申报期间</h2>
        <p className="text-sm text-fg-muted mt-1">
          从 HMRC 获取的开放申报义务中选择要申报的期间
        </p>
      </div>

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-12">
          <ArrowPathIcon className="w-8 h-8 text-fg-dim animate-spin mb-4" />
          <p className="text-sm text-fg-muted">正在从 HMRC 获取申报义务...</p>
        </div>
      ) : error ? (
        <div className="card p-5 border-error/30">
          <div className="flex items-center gap-2 mb-2">
            <ExclamationTriangleIcon className="w-5 h-5 text-error" />
            <p className="text-sm font-semibold text-error">获取失败</p>
          </div>
          <p className="text-sm text-fg-muted">
            {(error as Error).message || '无法从 HMRC 获取申报义务。请确保已完成 HMRC OAuth 授权。'}
          </p>
          <button onClick={onBack} className="btn btn-secondary mt-4">
            <ArrowLeftIcon className="w-4 h-4" />
            返回
          </button>
        </div>
      ) : obligations.length === 0 ? (
        <div className="card p-8 text-center">
          <CalendarDaysIcon className="w-12 h-12 text-fg-dim mx-auto mb-3" strokeWidth={1.5} />
          <h3 className="text-base font-semibold text-fg mb-1">暂无开放申报义务</h3>
          <p className="text-sm text-fg-muted mb-4">
            HMRC 当前没有待申报的开放期间。所有申报义务已完成或尚未生成。
          </p>
          <button onClick={onBack} className="btn btn-secondary">
            <ArrowLeftIcon className="w-4 h-4" />
            返回
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-fg-muted">
            找到 {obligations.length} 个开放申报义务，请选择要申报的期间：
          </p>
          {obligations.map((ob) => (
            <button
              key={ob.period_key}
              onClick={() => onSelect(ob)}
              className="w-full card p-4 text-left hover:border-primary/50 hover:bg-primary-muted/20 transition-all duration-200 group"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-fg group-hover:text-primary transition-colors">
                    {ob.start} — {ob.end}
                  </p>
                  <p className="text-xs text-fg-muted mt-1">
                    截止日期: {ob.due}
                  </p>
                </div>
                <ChevronRightIcon className="w-4 h-4 text-fg-dim group-hover:text-primary transition-colors" />
              </div>
            </button>
          ))}
          <button onClick={onBack} className="btn btn-secondary w-full">
            <ArrowLeftIcon className="w-4 h-4" />
            返回
          </button>
        </div>
      )}
    </div>
  )
}

function DataEntryForm({ template, onSubmit, initialValues }: { template: DataTemplate; onSubmit: (data: LineItem[]) => void; initialValues?: Record<string, string> }) {
  const [values, setValues] = useState<Record<string, string>>(initialValues || {})

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const lineItems: LineItem[] = []
    template.sections.forEach((section) => {
      section.fields.forEach((field) => {
        if (!field.auto_calculated && values[field.key]) {
          lineItems.push({
            category: field.key as LineItem['category'],
            amount: parseFloat(values[field.key]) || 0,
            currency: 'GBP',
          })
        }
      })
    })
    onSubmit(lineItems)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5 fade-in">
      {template.sections.map((section, sIdx) => (
        <div
          key={section.title}
          className="card p-5 slide-in"
          style={{ animationDelay: `${sIdx * 80}ms` }}
        >
          <div className="flex items-center gap-2 mb-1">
            <div className="w-6 h-6 rounded bg-primary-muted flex items-center justify-center text-xs font-bold text-primary">
              {sIdx + 1}
            </div>
            <h3 className="text-base font-semibold text-fg">{section.title}</h3>
          </div>
          {section.description && (
            <p className="text-sm text-fg-muted ml-8 mb-4">{section.description}</p>
          )}
          <div className="space-y-4">
            {section.fields.map((field) => (
              <div key={field.key}>
                <label className="block text-sm font-medium text-fg mb-1.5">
                  {field.label}
                  {field.required && !field.auto_calculated && (
                    <span className="text-error ml-1">*</span>
                  )}
                  {field.auto_calculated && (
                    <span className="text-accent text-xs font-medium ml-2 px-1.5 py-0.5 bg-accent-muted rounded">
                      自动计算
                    </span>
                  )}
                </label>
                <input
                  type={field.field_type === 'number' ? 'number' : 'text'}
                  step={field.key.startsWith('total_') && field.key !== 'total_vat_due' ? '1' : '0.01'}
                  disabled={field.auto_calculated}
                  placeholder={field.example || field.hint || '请输入数值'}
                  value={values[field.key] || ''}
                  onChange={(e) => setValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                  className={`input ${field.auto_calculated ? 'opacity-50 cursor-not-allowed bg-bg-elevated/50' : ''}`}
                />
                {field.hint && !field.auto_calculated && (
                  <p className="text-xs text-fg-dim mt-1.5 ml-0.5">{field.hint}</p>
                )}
                {field.key.startsWith('total_sales') || field.key.startsWith('total_purchases') || field.key.startsWith('total_goods') ? (
                  <p className="text-xs text-accent mt-1 ml-0.5">
                    💡 HMRC 要求此字段为整磅数（无小数位）
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ))}

      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          className="btn btn-primary"
        >
          <CalculatorIcon className="w-4 h-4" />
          预览计算
        </button>
      </div>
    </form>
  )
}

function PreviewPanel({
  calculation,
  validation,
  onConfirm,
  onBack,
}: {
  calculation: CalculationResult
  validation?: ValidationResult
  onConfirm: () => void
  onBack: () => void
}) {
  return (
    <div className="space-y-5 fade-in">
      <div className="card p-5">
        <div className="flex items-center gap-2 mb-5">
          <DocumentCheckIcon className="w-5 h-5 text-primary" />
          <h3 className="text-base font-semibold text-fg">计算结果预览</h3>
        </div>

        <div className="space-y-3">
          {calculation.breakdown.map((item) => (
            <div
              key={item.category}
              className="flex items-center justify-between py-2.5 px-3 rounded-lg hover:bg-bg-elevated/40 transition-colors"
            >
              <span className="text-sm text-fg-muted">{item.category}</span>
              <span className="text-sm font-semibold text-fg font-mono">£{item.amount.toFixed(2)}</span>
            </div>
          ))}

          <div className="border-t border-border pt-4 mt-2">
            <div className="flex items-center justify-between py-2 px-3 bg-primary-muted rounded-lg">
              <span className="text-sm font-semibold text-fg">应缴税额 (Box 5)</span>
              <span className="text-xl font-bold text-primary font-mono">£{calculation.total_tax_due.toFixed(2)}</span>
            </div>
          </div>
        </div>

        {validation && !validation.is_valid && (
          <div className="mt-5 p-4 bg-error-muted border border-error/20 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <ExclamationTriangleIcon className="w-4 h-4 text-error shrink-0" />
              <p className="text-sm font-semibold text-error">验证错误</p>
            </div>
            <ul className="space-y-1.5">
              {validation.errors.map((e, i) => (
                <li key={i} className="text-sm text-error/80 flex items-start gap-2">
                  <span className="w-1 h-1 rounded-full bg-error mt-2 shrink-0" />
                  {e.field}: {e.message}
                </li>
              ))}
            </ul>
          </div>
        )}

        {calculation.warnings.length > 0 && (
          <div className="mt-5 p-4 bg-warning-muted border border-warning/20 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <ExclamationTriangleIcon className="w-4 h-4 text-warning shrink-0" />
              <p className="text-sm font-semibold text-warning">警告提示</p>
            </div>
            <ul className="space-y-1.5">
              {calculation.warnings.map((w, i) => (
                <li key={i} className="text-sm text-warning/80 flex items-start gap-2">
                  <span className="w-1 h-1 rounded-full bg-warning mt-2 shrink-0" />
                  {w}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="flex gap-3">
        <button
          onClick={onBack}
          className="btn btn-secondary"
        >
          <ArrowLeftIcon className="w-4 h-4" />
          返回修改
        </button>
        <button
          onClick={onConfirm}
          disabled={validation && !validation.is_valid}
          className="btn btn-primary flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <ShieldCheckIcon className="w-4 h-4" />
          确认并提交
        </button>
      </div>
    </div>
  )
}

const MOCK_PENDING_STAGES: Record<string, StageResult> = {
  PRECHECK: { stage: 'PRECHECK', status: 'pending', message: '等待中...' },
  PREPARE: { stage: 'PREPARE', status: 'pending', message: '等待中...' },
  CALCULATE: { stage: 'CALCULATE', status: 'pending', message: '等待中...' },
  VALIDATE: { stage: 'VALIDATE', status: 'pending', message: '等待中...' },
  SUBMIT: { stage: 'SUBMIT', status: 'pending', message: '等待中...' },
  TRACK: { stage: 'TRACK', status: 'pending', message: '等待中...' },
}

function DeclarationPanel({
  calculation,
  onSubmit,
  onBack,
  isSubmitting,
}: {
  calculation: CalculationResult
  onSubmit: () => void
  onBack: () => void
  isSubmitting: boolean
}) {
  const [agreed, setAgreed] = useState(false)

  return (
    <div className="space-y-5 fade-in">
      <div className="card p-5">
        <div className="flex items-center gap-2 mb-5">
          <ShieldCheckIcon className="w-5 h-5 text-primary" />
          <h3 className="text-base font-semibold text-fg">法定声明</h3>
        </div>

        <details className="mb-5 group">
          <summary className="cursor-pointer list-none">
            <div className="flex items-center justify-between p-3 bg-bg-elevated/50 rounded-lg border border-border hover:border-primary/30 transition-colors">
              <span className="text-sm font-medium text-fg">管线预览（点击展开）</span>
              <ChevronRightIcon className="w-4 h-4 text-fg-dim group-open:rotate-90 transition-transform" />
            </div>
          </summary>
          <div className="mt-3 p-3 bg-bg-elevated/30 rounded-lg border border-border/50">
            <PipelineVisualizer stages={MOCK_PENDING_STAGES} interactive={false} compact={true} />
          </div>
        </details>

        <div className="p-4 bg-warning-muted/50 border border-warning/20 rounded-lg mb-5">
          <p className="text-sm text-warning font-medium mb-2">
            根据 HMRC 法律要求，您必须在提交前确认以下声明：
          </p>
          <p className="text-sm text-fg leading-relaxed">
            "When you submit this VAT information you are making a legal declaration that the information is true and complete. A false declaration can result in prosecution."
          </p>
          <p className="text-xs text-fg-muted mt-2">
            （提交此 VAT 信息即表示您作出法律声明，确认信息真实完整。虚假声明可能导致起诉。）
          </p>
        </div>

        <div className="space-y-3 mb-5">
          <div className="flex items-center justify-between py-2 px-3 rounded-lg bg-bg-elevated/30">
            <span className="text-sm text-fg-muted">应缴税额 (Box 5)</span>
            <span className="text-lg font-bold text-primary font-mono">£{calculation.total_tax_due.toFixed(2)}</span>
          </div>
        </div>

        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={agreed}
            onChange={(e) => setAgreed(e.target.checked)}
            className="mt-0.5 w-4 h-4 rounded border-border text-primary focus:ring-primary"
          />
          <span className="text-sm text-fg">
            我已阅读并理解上述法律声明，确认所填写的 VAT 申报信息真实、准确、完整。
          </span>
        </label>
      </div>

      <div className="flex gap-3">
        <button
          onClick={onBack}
          disabled={isSubmitting}
          className="btn btn-secondary"
        >
          <ArrowLeftIcon className="w-4 h-4" />
          返回
        </button>
        <button
          onClick={onSubmit}
          disabled={!agreed || isSubmitting}
          className="btn btn-primary flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSubmitting ? (
            <>
              <ArrowPathIcon className="w-4 h-4 animate-spin" />
              提交中...
            </>
          ) : (
            <>
              <ShieldCheckIcon className="w-4 h-4" />
              提交至 HMRC
            </>
          )}
        </button>
      </div>
    </div>
  )
}

function NewFilingPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const selectedPreset = useDemoStore((s) => s.selectedPreset)
  const profileVrn = useUserProfile((s) => s.taxpayer.vrn)

  const [step, setStep] = useState(1)
  const [country, setCountry] = useState('')
  const [taxType, setTaxType] = useState('')
  const [vrn, setVrn] = useState('')
  const [selectedObligation, setSelectedObligation] = useState<VATObligation | null>(null)
  const [lineItems, setLineItems] = useState<LineItem[]>([])
  const [calculation, setCalculation] = useState<CalculationResult | null>(null)
  const [validation, setValidation] = useState<ValidationResult | null>(null)
  const [filingResult, setFilingResult] = useState<FilingResult | null>(null)
  const [prefilledValues, setPrefilledValues] = useState<Record<string, string> | undefined>(undefined)

  // Preset prefill effect
  useEffect(() => {
    const presetId = (location.state as { presetId?: string } | null)?.presetId || selectedPreset
    if (presetId) {
      const preset = casePresets.find((p) => p.id === presetId)
      if (preset) {
        // Pre-fill lineItems into values map for DataEntryForm
        const values: Record<string, string> = {}
        preset.lineItems.forEach((item) => {
          values[item.category] = String(item.amount)
        })
        setPrefilledValues(values)
        // Pre-fill taxpayer info into VRN if applicable
        if (preset.taxpayer.tax_id) {
          setVrn(preset.taxpayer.tax_id)
        }
        // Clear preset state to avoid re-applying
        useDemoStore.getState().setSelectedPreset(null)
      }
    }
  }, [location.state, selectedPreset])

  const { data: template, isLoading: templateLoading } = useQuery({
    queryKey: ['template', country, taxType],
    queryFn: () => api.jurisdictions.template(country, taxType),
    enabled: step >= 3 && !!country && !!taxType,
  })

  // Poll for latest filing status after submission
  const { data: polledFiling } = useQuery({
    queryKey: ['filing', filingResult?.filing_id],
    queryFn: () => api.filings.get(filingResult!.filing_id),
    enabled: !!filingResult?.filing_id && step === 6,
    refetchInterval: 2000,
  })

  const displayFilingResult = polledFiling || filingResult

  const previewMutation = useMutation({
    mutationFn: api.filings.preview,
    onSuccess: (data) => {
      setCalculation(data.calculation)
      setValidation(data.validation)
      setStep(4)
    },
  })

  const submitMutation = useMutation({
    mutationFn: api.filings.submit,
    onSuccess: (data) => {
      setFilingResult(data)
      setStep(6)
    },
  })

  const handleJurisdictionSelect = (c: string, t: string, v: string) => {
    setCountry(c)
    setTaxType(t)
    setVrn(v)
    setStep(2)
  }

  const handleObligationSelect = (ob: VATObligation) => {
    setSelectedObligation(ob)
    setStep(3)
  }

  const handleDataSubmit = (items: LineItem[]) => {
    setLineItems(items)
    previewMutation.mutate({
      jurisdiction: country,
      tax_type: taxType,
      period: {
        year: new Date(selectedObligation!.start).getFullYear(),
        period_type: 'QUARTERLY',
        period_key: selectedObligation!.period_key,
        start_date: selectedObligation!.start,
        end_date: selectedObligation!.end,
      },
      taxpayer: {
        name: 'Demo Business',
        tax_id: vrn,
        tax_id_type: 'vrn',
      },
      data: items,
    })
  }

  const handleConfirmSubmit = () => {
    submitMutation.mutate({
      jurisdiction: country,
      tax_type: taxType,
      period: {
        year: new Date(selectedObligation!.start).getFullYear(),
        period_type: 'QUARTERLY',
        period_key: selectedObligation!.period_key,
        start_date: selectedObligation!.start,
        end_date: selectedObligation!.end,
      },
      taxpayer: {
        name: 'Demo Business',
        tax_id: vrn,
        tax_id_type: 'vrn',
      },
      data: lineItems,
    })
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-fg tracking-tight">新建申报</h1>
        <p className="text-sm text-fg-muted mt-1">填写数据并提交至 HMRC</p>
      </div>

      <StepIndicator currentStep={step} />

      {step === 1 && <JurisdictionSelector onSelect={handleJurisdictionSelect} initialVrn={profileVrn} />}

      {step === 2 && (
        <ObligationSelector
          vrn={vrn}
          onSelect={handleObligationSelect}
          onBack={() => setStep(1)}
        />
      )}

      {step === 3 && templateLoading && (
        <div className="flex flex-col items-center justify-center py-20">
          <ArrowPathIcon className="w-8 h-8 text-fg-dim animate-spin mb-4" />
          <p className="text-sm text-fg-muted">加载申报模板中...</p>
        </div>
      )}

      {step === 3 && template && (
        <DataEntryForm template={template} onSubmit={handleDataSubmit} initialValues={prefilledValues} />
      )}

      {step === 4 && calculation && (
        <PreviewPanel
          calculation={calculation}
          validation={validation || undefined}
          onConfirm={() => setStep(5)}
          onBack={() => setStep(3)}
        />
      )}

      {step === 5 && calculation && (
        <DeclarationPanel
          calculation={calculation}
          onSubmit={handleConfirmSubmit}
          onBack={() => setStep(4)}
          isSubmitting={submitMutation.isPending}
        />
      )}

      {step === 6 && displayFilingResult && (
        <div className="space-y-6 fade-in">
          <div className="flex flex-col items-center justify-center py-10">
            <div className="w-20 h-20 bg-success-muted rounded-full flex items-center justify-center mb-6 glow-success-lg">
              <CheckIcon className="w-10 h-10 text-success" strokeWidth={2.5} />
            </div>
            <h3 className="text-xl font-bold text-fg mb-2">提交成功</h3>
            <p className="text-sm text-fg-muted">申报已提交至 HMRC，以下是处理管线状态</p>
          </div>

          <div className="card p-5">
            <h4 className="text-sm font-semibold text-fg mb-4">处理管线</h4>
            <PipelineVisualizer stages={displayFilingResult.stage_results} interactive={true} />
          </div>

          {displayFilingResult.receipt?.raw_response && (
            <HMRCReceiptCard receipt={displayFilingResult.receipt.raw_response as Record<string, string>} />
          )}

          <div className="flex justify-center">
            <button
              onClick={() => navigate(`/filings/${displayFilingResult.filing_id}`)}
              className="btn btn-primary"
            >
              查看申报详情
              <ChevronRightIcon className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {step === 6 && !displayFilingResult && (
        <div className="flex flex-col items-center justify-center py-20 fade-in">
          <div className="w-20 h-20 bg-success-muted rounded-full flex items-center justify-center mb-6 glow-success-lg">
            <CheckIcon className="w-10 h-10 text-success" strokeWidth={2.5} />
          </div>
          <h3 className="text-xl font-bold text-fg mb-2">提交成功</h3>
          <p className="text-sm text-fg-muted">正在跳转至申报详情页面...</p>
        </div>
      )}
    </div>
  )
}

export default NewFilingPage
