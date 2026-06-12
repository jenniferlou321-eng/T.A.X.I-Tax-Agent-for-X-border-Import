import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import ImportPreviewTable, { type RawInvoice } from '../components/ImportPreviewTable';
import type { SalesTransaction, PurchaseTransaction } from '../types';

export default function ImportPreviewPage() {
  const [params] = useSearchParams();
  const period = params.get('period') ?? 'Q1_2026';
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [sales, setSales] = useState<SalesTransaction[]>([]);
  const [purchases, setPurchases] = useState<PurchaseTransaction[]>([]);
  const [raw, setRaw] = useState<RawInvoice[]>([]);
  const [count, setCount] = useState<{ sales: number; purchases: number; cancelled: number; amends: number; total: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api.erp.erpnextHubSummary(period)
      .then((data) => {
        if (cancelled) return;
        setSales(data.sales);
        setPurchases(data.purchases);
        setRaw(data.raw);
        setCount(data.count);
      })
      .catch((e) => {
        if (cancelled) return;
        console.error('Failed to load hub summary:', e);
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, [period]);

  if (loading) return <div className="p-6">加载中...</div>;
  if (!count || count.total === 0) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <h1 className="text-2xl font-semibold mb-4">Preview · {period}</h1>
        <div className="card p-6 text-center">
          <p className="text-fg-dim">本期内还没有导入数据。</p>
          <button onClick={() => navigate('/import')} className="btn-secondary mt-4">
            ← 回 Import Hub
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-semibold mb-2">Preview · {period}</h1>
      <p className="text-sm text-fg-dim mb-4">
        销售 {count.sales} 笔 · 采购 {count.purchases} 笔 · {count.cancelled > 0 && `${count.cancelled} 已冲红 · `}{count.amends > 0 && `${count.amends} 冲红 Credit Note`}
      </p>

      <div className="card p-4 mb-6">
        <details>
          <summary className="cursor-pointer text-sm font-medium">▼ 明细表 ({count.total} 行)</summary>
          <div className="mt-3">
            <ImportPreviewTable sales={sales} purchases={purchases} raw={raw} />
          </div>
        </details>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <button onClick={() => navigate('/agent')} className="btn-primary py-4">
          🤖 与 Agent 对话
        </button>
        <button onClick={() => navigate('/filings/new')} className="btn-secondary py-4">
          📝 手动报税
        </button>
      </div>

      <div className="mt-4 text-center">
        <button onClick={() => navigate('/import')} className="text-xs text-fg-dim">
          ← 回 Import Hub 重拉数据
        </button>
      </div>
    </div>
  );
}
