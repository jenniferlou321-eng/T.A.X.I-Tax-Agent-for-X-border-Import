import { useMemo, useState } from 'react';
import { XMarkIcon, PaperAirplaneIcon } from '@heroicons/react/24/outline';
import type { SalesTransaction, PurchaseTransaction } from '../types';

interface InvoiceMultiSelectPanelProps {
  invoices: Array<SalesTransaction | PurchaseTransaction>;
  invoiceType: 'sale' | 'purchase';
  onSend: (selectedIds: string[]) => void;
  onClose: () => void;
}

export default function InvoiceMultiSelectPanel({
  invoices, invoiceType, onSend, onClose,
}: InvoiceMultiSelectPanelProps) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const toggle = (id: string) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };

  const toggleAll = () => {
    if (selected.size === invoices.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(invoices.map((i) => i.id)));
    }
  };

  const { totalNet, totalVat } = useMemo(() => {
    let net = 0;
    let vat = 0;
    for (const i of invoices) {
      if (selected.has(i.id)) {
        net += Number(i.net_amount);
        vat += Number(i.vat_amount);
      }
    }
    return { totalNet: net, totalVat: vat };
  }, [invoices, selected]);

  return (
    <div className="my-2 border border-fg-dim/30 rounded-lg overflow-hidden bg-bg-elevated">
      <div className="px-4 py-2 flex items-center justify-between border-b border-fg-dim/20">
        <p className="font-medium text-fg">
          选择{invoiceType === 'sale' ? '销售' : '采购'}发票 ({invoices.length} 张可选)
        </p>
        <button onClick={onClose} className="text-fg-dim hover:text-fg">
          <XMarkIcon className="w-5 h-5" />
        </button>
      </div>

      <div className="max-h-80 overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="bg-bg sticky top-0">
            <tr className="text-xs text-fg-dim">
              <th className="px-3 py-2 text-left w-10">
                <input
                  type="checkbox"
                  checked={selected.size === invoices.length && invoices.length > 0}
                  onChange={toggleAll}
                />
              </th>
              <th className="px-3 py-2 text-left">ID</th>
              <th className="px-3 py-2 text-left">日期</th>
              <th className="px-3 py-2 text-left">对方</th>
              <th className="px-3 py-2 text-right">净额</th>
              <th className="px-3 py-2 text-right">VAT</th>
              <th className="px-3 py-2 text-right">总额</th>
            </tr>
          </thead>
          <tbody>
            {invoices.map((inv) => (
              <tr
                key={inv.id}
                className={`border-t border-fg-dim/10 cursor-pointer hover:bg-bg-elevated/50 ${
                  selected.has(inv.id) ? 'bg-accent-muted' : ''
                }`}
                onClick={() => toggle(inv.id)}
              >
                <td className="px-3 py-2">
                  <input
                    type="checkbox"
                    checked={selected.has(inv.id)}
                    onChange={() => toggle(inv.id)}
                    onClick={(e) => e.stopPropagation()}
                  />
                </td>
                <td className="px-3 py-2 font-mono text-xs text-fg">{inv.id}</td>
                <td className="px-3 py-2 text-fg-dim">{inv.txn_date}</td>
                <td className="px-3 py-2 text-fg">{inv.counterparty}</td>
                <td className="px-3 py-2 text-right font-mono text-fg">
                  £{Number(inv.net_amount).toFixed(2)}
                </td>
                <td className="px-3 py-2 text-right font-mono text-fg">
                  £{Number(inv.vat_amount).toFixed(2)}
                </td>
                <td className="px-3 py-2 text-right font-mono text-fg">
                  £{Number(inv.gross_amount).toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="px-4 py-3 border-t border-fg-dim/20 flex items-center justify-between bg-bg">
        <p className="text-sm text-fg-muted">
          已选 <span className="font-medium text-fg">{selected.size}</span> 张 · 净额
          <span className="font-mono ml-1 text-fg">£{totalNet.toFixed(2)}</span> ·
          VAT <span className="font-mono ml-1 text-fg">£{totalVat.toFixed(2)}</span>
        </p>
        <button
          onClick={() => onSend(Array.from(selected))}
          disabled={selected.size === 0}
          className="btn btn-sm btn-primary disabled:opacity-50"
        >
          <PaperAirplaneIcon className="w-4 h-4" />
          发送选中的发票
        </button>
      </div>
    </div>
  );
}
