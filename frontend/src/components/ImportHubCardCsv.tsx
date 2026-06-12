import { useState } from 'react';
import { api } from '../api/client';
import { useDemoStore } from '../stores/demoStore';

interface Props { period: string; }

export default function ImportHubCardCsv({ period }: Props) {
  const setHubSummary = useDemoStore((s) => s.setHubDataForPeriod);
  const [uploading, setUploading] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setLastResult(null);
    try {
      const ir = await api.erp.importCsv(file, 'erpnext_export');
      setLastResult(`✓ ${file.name} · ${ir.sales.length} 销售 + ${ir.purchases.length} 采购`);
      setHubSummary(period, {
        salesCount: ir.sales.length,
        purchasesCount: ir.purchases.length,
        cancelledCount: 0,
        amendsCount: 0,
        lastPulledAt: new Date().toISOString(),
      });
    } catch (e: any) {
      setLastResult(`❌ ${e.message}`);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="card p-4" data-testid="import-hub-card-csv">
      <h3 className="font-medium mb-3">📤 上传 CSV</h3>
      <input
        type="file"
        accept=".csv"
        onChange={handleFile}
        disabled={uploading}
        data-testid="import-hub-csv-input"
      />
      {uploading && <p className="text-xs text-fg-dim mt-2">上传中...</p>}
      {lastResult && <p className="text-xs mt-2">{lastResult}</p>}
    </div>
  );
}
