import { FileText, TrendingDown, CircleDashed, AlertTriangle, CircleDot, Building2 } from 'lucide-react';
import type { CasePreset } from '../data/casePresets';

interface CasePresetCardProps {
  preset: CasePreset;
  onLoad: (preset: CasePreset) => void;
}

const iconMap: Record<string, React.ElementType> = {
  FileText,
  TrendingDown,
  CircleDashed,
  AlertTriangle,
  Building2,
};

export default function CasePresetCard({ preset, onLoad }: CasePresetCardProps) {
  const Icon = iconMap[preset.icon] || CircleDot;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow duration-200 flex flex-col gap-4">
      <div className="flex items-start gap-4">
        <div className="w-11 h-11 rounded-lg bg-blue-50 flex items-center justify-center shrink-0">
          <Icon className="w-5 h-5 text-blue-600" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-900">{preset.title}</h3>
          <p className="text-sm text-gray-500 mt-1">{preset.description}</p>
        </div>
      </div>
      <button
        type="button"
        onClick={() => onLoad(preset)}
        className="w-full py-2 px-4 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 active:bg-blue-800 transition-colors duration-200"
      >
        加载此 Case
      </button>
    </div>
  );
}
