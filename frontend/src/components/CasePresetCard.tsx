import { FileText, Building2, Building, CircleDot, CheckCircle, Globe2, Table, Sparkles, ExternalLink } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { CasePreset } from '../data/casePresets';

interface CasePresetCardProps {
  preset: CasePreset;
  onLoad: (preset: CasePreset) => void;
  isSelected?: boolean;
}

const iconMap: Record<string, React.ElementType> = {
  FileText, Building2, Building, Globe2, Table, Sparkles,
};

export default function CasePresetCard({ preset, onLoad, isSelected = false }: CasePresetCardProps) {
  const Icon = iconMap[preset.icon] || CircleDot;
  const isJiahang = preset.kind === 'case-jiahang';
  const isDocLink = preset.kind === 'doc-link';

  // jiahang 走金色高亮,doc-link 走紫色高亮
  const accentBorder = isJiahang
    ? 'border-primary ring-2 ring-primary/30 shadow-md bg-gradient-to-br from-primary/5 to-transparent'
    : isDocLink
      ? 'border-accent ring-1 ring-accent/30 bg-gradient-to-br from-accent/5 to-transparent'
      : isSelected
        ? 'border-accent ring-2 ring-accent/30 shadow-md'
        : 'border-gray-200 hover:shadow-md';

  const iconBgClass = isJiahang
    ? 'bg-primary/15'
    : isDocLink
      ? 'bg-accent/15'
      : 'bg-blue-50';
  const iconColorClass = isJiahang
    ? 'text-primary'
    : isDocLink
      ? 'text-accent'
      : 'text-blue-600';

  return (
    <div
      className={`h-full bg-white rounded-xl border p-5 transition-all duration-200 flex flex-col gap-4 ${accentBorder}`}
    >
      <div className="flex-1 flex items-start gap-4">
        <div className={`w-11 h-11 rounded-lg ${iconBgClass} flex items-center justify-center shrink-0`}>
          <Icon className={`w-5 h-5 ${iconColorClass}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <h3 className="font-medium text-gray-900">{preset.title}</h3>
            <div className="flex items-center gap-1.5">
              {isJiahang && (
                <span className="inline-flex items-center gap-1 text-[10px] font-bold text-white bg-primary px-1.5 py-0.5 rounded">
                  嘉汉
                </span>
              )}
              {isDocLink && (
                <span className="inline-flex items-center gap-1 text-[10px] font-bold text-accent bg-accent-muted px-1.5 py-0.5 rounded">
                  DOC
                </span>
              )}
              {isSelected && !isDocLink && (
                <span className="inline-flex items-center gap-1 text-xs font-medium text-accent bg-accent-muted px-2 py-0.5 rounded-full">
                  <CheckCircle className="w-3 h-3" />
                  已加载
                </span>
              )}
            </div>
          </div>
          <p className="text-sm text-gray-500 mt-1">{preset.description}</p>
        </div>
      </div>

      {isDocLink && preset.entryRoute ? (
        <Link
          to={preset.entryRoute}
          className="mt-auto w-full min-h-[40px] py-2 px-4 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover active:bg-accent-hover transition-colors duration-200 flex items-center justify-center gap-2"
        >
          <ExternalLink className="w-4 h-4" />
          查看文档
        </Link>
      ) : (
        <button
          type="button"
          onClick={() => onLoad(preset)}
          className={`mt-auto w-full min-h-[40px] py-2 px-4 rounded-lg text-white text-sm font-medium transition-colors duration-200 ${
            isJiahang
              ? 'bg-primary hover:bg-primary-hover active:bg-primary-hover'
              : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800'
          }`}
        >
          {isSelected ? '重新加载此 Case' : '加载此 Case'}
        </button>
      )}
    </div>
  );
}
