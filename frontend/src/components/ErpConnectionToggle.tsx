import { GlobeAltIcon, InformationCircleIcon } from '@heroicons/react/24/outline';
import { useDemoStore } from '../stores/demoStore';

export default function ErpConnectionToggle() {
  const erpOn = useDemoStore((s) => s.erpConnectionOn);
  const setErp = useDemoStore((s) => s.setErpConnection);

  return (
    <div className="card p-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <GlobeAltIcon className="w-5 h-5 text-fg-muted" />
        <div>
          <p className="text-sm font-medium text-fg">接入 ERP</p>
          <p className="text-xs text-fg-dim">
            {erpOn ? '未来从 ERPNext 实时拉取' : '当前走 Demo Case 数据'}
          </p>
        </div>
      </div>
      <label className="inline-flex items-center gap-2 cursor-pointer">
        <input
          type="checkbox"
          checked={erpOn}
          onChange={(e) => setErp(e.target.checked)}
          className="sr-only"
        />
        <span
          className={`relative inline-block w-10 h-5 rounded-full transition-colors ${
            erpOn ? 'bg-accent' : 'bg-bg-elevated'
          }`}
        >
          <span
            className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
              erpOn ? 'translate-x-5' : 'translate-x-0.5'
            }`}
          />
        </span>
      </label>
      {erpOn && (
        <div className="ml-3 flex items-center gap-1 text-xs text-warning">
          <InformationCircleIcon className="w-4 h-4" />
          <span>Coming soon — v0 仍走 Demo Case</span>
        </div>
      )}
    </div>
  );
}
