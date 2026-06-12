import { useEffect, useRef } from 'react';
import { GlobeAltIcon, InformationCircleIcon, CheckCircleIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';
import { useDemoStore } from '../stores/demoStore';

const POLL_INTERVAL_MS = 5000;

function formatTime(iso: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return iso;
  }
}

export default function ErpConnectionToggle() {
  const erpOn = useDemoStore((s) => s.erpConnectionOn);
  const setErp = useDemoStore((s) => s.setErpConnection);
  const status = useDemoStore((s) => s.erpnextStatus);
  const lastPushAt = useDemoStore((s) => s.erpnextLastPushAt);
  const salesCount = useDemoStore((s) => s.erpnextSalesCount);
  const purchasesCount = useDemoStore((s) => s.erpnextPurchasesCount);
  const docnames = useDemoStore((s) => s.erpnextDocnames);
  const refresh = useDemoStore((s) => s.refreshErpnextStatus);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (erpOn) {
      // 立即拉一次,然后 5s 轮询
      refresh();
      pollRef.current = setInterval(() => {
        refresh();
      }, POLL_INTERVAL_MS);
    } else {
      // 关 toggle: 停轮询,清状态
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [erpOn, refresh]);

  const statusBadge = (() => {
    if (status === 'connected') {
      return (
        <span className="flex items-center gap-1 text-xs text-success">
          <CheckCircleIcon className="w-4 h-4" />
          <span>已连接</span>
        </span>
      );
    }
    if (status === 'error') {
      return (
        <span className="flex items-center gap-1 text-xs text-error">
          <ExclamationTriangleIcon className="w-4 h-4" />
          <span>连接异常</span>
        </span>
      );
    }
    if (status === 'disconnected') {
      return (
        <span className="flex items-center gap-1 text-xs text-warning">
          <InformationCircleIcon className="w-4 h-4" />
          <span>等待推送</span>
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1 text-xs text-fg-dim">
        <GlobeAltIcon className="w-4 h-4" />
        <span>空闲</span>
      </span>
    );
  })();

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <GlobeAltIcon className="w-5 h-5 text-fg-muted" />
          <div>
            <p className="text-sm font-medium text-fg">接入 ERP</p>
            <p className="text-xs text-fg-dim">
              {erpOn
                ? status === 'connected'
                  ? `已连接 · ${salesCount} 笔销售 / ${purchasesCount} 笔采购`
                  : '从 ERPNext 实时拉取 (等待推送)'
                : '当前走 Demo Case 数据'}
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
      </div>
      {erpOn && (
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
          {statusBadge}
          <span className="text-fg-dim">
            最近推送: <span className="text-fg">{formatTime(lastPushAt)}</span>
          </span>
          {docnames.length > 0 && (
            <span className="text-fg-dim truncate max-w-[20rem]" title={docnames.join(', ')}>
              单据: {docnames.slice(0, 3).join(', ')}{docnames.length > 3 ? ` 等 ${docnames.length} 笔` : ''}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
