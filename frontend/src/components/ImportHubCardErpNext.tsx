import { useState } from 'react';
import { useDemoStore } from '../stores/demoStore';
import { api } from '../api/client';
import ErpCredentialsModal from './ErpCredentialsModal';

interface Props {
  period: string;
  periodStart: string;
  periodEnd: string;
}

export default function ImportHubCardErpNext({ period, periodStart, periodEnd }: Props) {
  const credentials = useDemoStore((s) => s.erpnextCredentials);
  const setCredentials = useDemoStore((s) => s.setErpnextCredentials);
  const setHubSummary = useDemoStore((s) => s.setHubDataForPeriod);
  const hubData = useDemoStore((s) => s.hubDataByPeriod[period]);

  const [showCreds, setShowCreds] = useState(false);
  const [pulling, setPulling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingPull, setPendingPull] = useState(false);

  const handlePull = async () => {
    if (!credentials) {
      setPendingPull(true);
      setShowCreds(true);
      return;
    }
    setPulling(true);
    setError(null);
    try {
      const result = await api.erp.erpnextPull({
        url: credentials.url,
        api_key: credentials.apiKey,
        api_secret: credentials.apiSecret,
        period,
        period_start: periodStart,
        period_end: periodEnd,
      });
      // 先用 pull 响应里的 count 立刻更新 UI(快路径)。
      setHubSummary(period, {
        salesCount: result.sales,
        purchasesCount: result.purchases,
        cancelledCount: result.cancelled,
        amendsCount: result.amends,
        lastPulledAt: new Date().toISOString(),
      });
      // 再从后端 ImportHubStore 拉一次 canonical count(按 docname dedup),
      // 避免前端累加导致重复 — 这是 source of truth,覆盖上面的快路径值。
      try {
        const summary = await api.erp.erpnextHubSummary(period);
        setHubSummary(period, {
          salesCount: summary.count.sales,
          purchasesCount: summary.count.purchases,
          cancelledCount: summary.count.cancelled,
          amendsCount: summary.count.amends,
          lastPulledAt: new Date().toISOString(),
        });
      } catch {
        // canonical count 拉不到,保留快路径的值
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setPulling(false);
    }
  };

  return (
    <div className="card p-4" data-testid="import-hub-card-erpnext">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-medium">📥 从 ERPNext 导入</h3>
        <button
          onClick={() => {
            setPendingPull(false);
            setShowCreds(true);
          }}
          className="text-xs text-fg-dim hover:text-fg"
          data-testid="import-hub-config-credentials"
        >
          {credentials ? '✏️ 修改凭证' : '⚙️ 配置凭证'}
        </button>
      </div>

      <div className="text-sm space-y-2">
        <p className="text-fg-dim">
          凭证: {credentials ? '✓ 已配置' : '⚠️ 未配置'} ({credentials?.url ?? '—'})
        </p>
        {hubData && (
          <p className="text-fg-dim">
            上次拉取: {hubData.lastPulledAt ? new Date(hubData.lastPulledAt).toLocaleString() : '—'}
            {' · '}{hubData.salesCount} 销售 / {hubData.purchasesCount} 采购
            {hubData.cancelledCount > 0 && ` · ${hubData.cancelledCount} 已冲红`}
          </p>
        )}
      </div>

      <button
        onClick={handlePull}
        disabled={pulling}
        className="btn-primary mt-3 w-full"
        data-testid="import-hub-pull"
      >
        {pulling ? '拉取中...' : '🔄 拉取本季度'}
      </button>

      {error && (
        <p className="text-xs text-error mt-2">❌ {error}</p>
      )}

      {showCreds && (
        <ErpCredentialsModal
          initial={credentials ?? undefined}
          onSave={(creds) => {
            setCredentials(creds);
            setShowCreds(false);
            if (pendingPull) {
              setPendingPull(false);
              handlePull();
            }
          }}
          onClose={() => setShowCreds(false)}
        />
      )}
    </div>
  );
}
