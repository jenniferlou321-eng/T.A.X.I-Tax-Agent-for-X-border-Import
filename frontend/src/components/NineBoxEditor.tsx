import { ArrowPathIcon } from '@heroicons/react/24/outline'

interface NineBoxEditorProps {
  values: Record<string, number>
  onChange: (key: string, value: number) => void
  onReset: () => void
}

const BOX_ORDER = [
  'vat_due_sales',
  'vat_due_acquisitions',
  'vat_reclaimed_purchases',
  'total_sales_ex_vat',
  'total_purchases_ex_vat',
  'total_goods_supplied_eu',
  'total_goods_acquired_eu',
]

const BOX_CONFIG: Record<
  string,
  { label: string; box: string; hint: string; wholePounds: boolean }
> = {
  vat_due_sales: {
    label: 'Box 1 — VAT due on sales',
    box: 'Box 1',
    hint: 'VAT due in this period on sales and other outputs',
    wholePounds: false,
  },
  vat_due_acquisitions: {
    label: 'Box 2 — VAT due on EC acquisitions',
    box: 'Box 2',
    hint: 'VAT due on acquisitions from EU member states',
    wholePounds: false,
  },
  vat_reclaimed_purchases: {
    label: 'Box 4 — VAT reclaimed on purchases',
    box: 'Box 4',
    hint: 'VAT reclaimed on purchases and other inputs',
    wholePounds: false,
  },
  total_sales_ex_vat: {
    label: 'Box 6 — Total sales (ex VAT)',
    box: 'Box 6',
    hint: 'Total value of sales and other supplies excluding VAT',
    wholePounds: true,
  },
  total_purchases_ex_vat: {
    label: 'Box 7 — Total purchases (ex VAT)',
    box: 'Box 7',
    hint: 'Total value of purchases and other inputs excluding VAT',
    wholePounds: true,
  },
  total_goods_supplied_eu: {
    label: 'Box 8 — Supplies to EU',
    box: 'Box 8',
    hint: 'Total value of goods supplied to EU (ex VAT)',
    wholePounds: true,
  },
  total_goods_acquired_eu: {
    label: 'Box 9 — Acquisitions from EU',
    box: 'Box 9',
    hint: 'Total value of goods acquired from EU (ex VAT)',
    wholePounds: true,
  },
}

export default function NineBoxEditor({
  values,
  onChange,
  onReset,
}: NineBoxEditorProps) {
  const isEdited = Object.entries(values).some(([k, v]) => {
    return v !== (values[k] ?? 0)
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold text-fg">9-Box VAT 汇总</h2>
          <span className="text-xs text-fg-dim bg-bg-elevated px-2 py-0.5 rounded-full">
            可编辑
          </span>
        </div>
        <button
          onClick={onReset}
          className="btn btn-sm btn-ghost text-fg-dim hover:text-fg flex items-center gap-1.5"
          title="恢复到 case 默认值"
        >
          <ArrowPathIcon className="w-3.5 h-3.5" />
          恢复默认值
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {BOX_ORDER.map((key) => {
          const cfg = BOX_CONFIG[key]
          if (!cfg) return null
          const val = values[key] ?? 0

          return (
            <div
              key={key}
              className="card p-4 space-y-2 hover:border-primary/30 transition-colors"
            >
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold text-primary bg-primary-muted px-1.5 py-0.5 rounded">
                  {cfg.box}
                </span>
                <span className="text-sm font-medium text-fg">{cfg.label}</span>
              </div>

              <input
                type="number"
                min="0"
                step={cfg.wholePounds ? '1' : '0.01'}
                value={val}
                onChange={(e) =>
                  onChange(key, Math.max(0, parseFloat(e.target.value) || 0))
                }
                className="input w-full"
                placeholder="0.00"
              />

              <p className="text-xs text-fg-dim">{cfg.hint}</p>

              {cfg.wholePounds && (
                <p className="text-xs text-accent">
                  💡 HMRC 要求此字段为整磅数（无小数位）
                </p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
