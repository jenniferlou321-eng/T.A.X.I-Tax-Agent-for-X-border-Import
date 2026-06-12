import { FileText, Building2, Building, CircleDot, CheckCircle } from 'lucide-react';
import type { CasePreset } from '../data/casePresets';

interface CasePresetCardProps {
  preset: CasePreset;
  onLoad: (preset: CasePreset) => void;
  isSelected?: boolean;  // 新加
}

const iconMap: Record<string, React.ElementType> = {
  FileText, Building2, Building,
};

export default function CasePresetCard({ preset, onLoad, isSelected = false }: CasePresetCardProps) {
  const Icon = iconMap[preset.icon] || CircleDot;

  return (
    <div
      className={`bg-white rounded-xl border p-5 transition-all duration-200 flex flex-col gap-4 ${
        isSelected
          ? 'border-accent ring-2 ring-accent/30 shadow-md'
          : 'border-gray-200 hover:shadow-md'
      }`}
    >
      <div className="flex items-start gap-4">
        <div className="w-11 h-11 rounded-lg bg-blue-50 flex items-center justify-center shrink-0">
          <Icon className="w-5 h-5 text-blue-600" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-medium text-gray-900">{preset.title}</h3>
            {isSelected && (
              <span className="inline-flex items-center gap-1 text-xs font-medium text-accent bg-accent-muted px-2 py-0.5 rounded-full">
                <CheckCircle className="w-3 h-3" />
                已加载
              </span>
            )}
          </div>
          <p className="text-sm text-gray-500 mt-1">{preset.description}</p>
        </div>
      </div>
      <button
        type="button"
        onClick={() => onLoad(preset)}
        className="w-full py-2 px-4 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 active:bg-blue-800 transition-colors duration-200"
      >
        {isSelected ? '重新加载此 Case' : '加载此 Case'}
      </button>
    </div>
  );
}
