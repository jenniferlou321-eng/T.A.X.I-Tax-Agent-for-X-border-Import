import type { SalesTransaction, PurchaseTransaction } from '../types';

interface Props {
  sales: SalesTransaction[];
  purchases: PurchaseTransaction[];
  raw?: Array<{ id: string; cancelled: boolean; is_amend: boolean; parent?: string }>;
}

export default function ImportPreviewTable({ sales, purchases, raw = [] }: Props) {
  const rows = [
    ...sales.map((s) => ({ ...s, kind: 'sale' as const })),
    ...purchases.map((p) => ({ ...p, kind: 'purchase' as const })),
  ];
  const rawMap = new Map(raw.map((r) => [r.id, r]));

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-fg-dim">
          <th>ID</th><th>日期</th><th>对手方</th>
          <th>净额</th><th>税额</th><th>含税</th><th>状态</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const rRaw = rawMap.get(r.id);
          const cancelled = rRaw?.cancelled ?? false;
          const isAmend = rRaw?.is_amend ?? false;
          return (
            <tr key={r.id} className={cancelled ? 'opacity-50 line-through' : ''}>
              <td>
                {r.id}
                {isAmend && rRaw?.parent && (
                  <span className="text-xs text-fg-dim ml-1">↳ {rRaw.parent}</span>
                )}
              </td>
              <td>{r.txn_date}</td>
              <td>{r.counterparty}</td>
              <td>£{r.net_amount}</td>
              <td>£{r.vat_amount}</td>
              <td>£{r.gross_amount}</td>
              <td>
                {cancelled && <span className="text-error text-xs">已冲红</span>}
                {isAmend && !cancelled && <span className="text-warning text-xs">冲红</span>}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
