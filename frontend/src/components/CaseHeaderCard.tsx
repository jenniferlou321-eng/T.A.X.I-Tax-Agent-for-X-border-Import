import { FileText, Building2, Building } from 'lucide-react'
import type { CasePreset } from '../data/casePresets'

const iconMap: Record<string, React.ElementType> = {
  FileText,
  Building2,
  Building,
}

interface CaseHeaderCardProps {
  preset: CasePreset
}

export default function CaseHeaderCard({ preset }: CaseHeaderCardProps) {
  const Icon = iconMap[preset.icon] || Building2
  const isCn = preset.taxpayer.tax_id_type === 'uscc'

  return (
    <div className="card p-5 flex items-start gap-4">
      <div className="w-12 h-12 rounded-xl bg-primary-muted flex items-center justify-center shrink-0">
        <Icon className="w-6 h-6 text-primary" />
      </div>
      <div className="flex-1 min-w-0">
        <h1 className="text-xl font-bold text-fg">{preset.title}</h1>
        <p className="text-sm text-fg-muted mt-1">{preset.description}</p>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-3 text-sm text-fg-dim">
          <span>
            企业: <span className="text-fg font-medium">{preset.taxpayer.name}</span>
          </span>
          <span>
            {isCn ? '统一社会信用代码' : 'VRN'}: <span className="font-mono text-fg">{preset.taxpayer.tax_id}</span>
          </span>
        </div>
      </div>
    </div>
  )
}
