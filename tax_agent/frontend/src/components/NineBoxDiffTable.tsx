import type { ERPNineBox, ReconciliationDelta } from '../types';
import { CheckCircleIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';

interface NineBoxDiffTableProps {
  erpBoxes: ERPNineBox;
  taxiBoxes: ERPNineBox;
  delta: ReconciliationDelta;
  tolerance?: number;
}

const BOX_LABELS: Array<[string, string, keyof ERPNineBox]> = [
  ['box1', 'Box 1 (销项 VAT)', 'box1_vat_due_sales'],
  ['box2', 'Box 2 (EC 进项 VAT)', 'box2_vat_due_acquisitions'],
  ['box3', 'Box 3 (VAT 合计)', 'box3_total_vat_due'],
  ['box4', 'Box 4 (进项抵扣)', 'box4_vat_reclaimed'],
  ['box5', 'Box 5 (净 VAT)', 'box5_net_vat_due'],
  ['box6', 'Box 6 (总销额 £)', 'box6_total_sales_ex_vat'],
  ['box7', 'Box 7 (总采额 £)', 'box7_total_purchases_ex_vat'],
  ['box8', 'Box 8 (对欧供货 £)', 'box8_total_goods_supplied_eu'],
  ['box9', 'Box 9 (欧进采购 £)', 'box9_total_goods_acquired_eu'],
];

function formatAmount(value: string | number, isInt: boolean): string {
  if (isInt) return String(value);
  return Number(value).toFixed(2);
}

function isIntBox(boxKey: string): boolean {
  return boxKey.startsWith('box6') || boxKey.startsWith('box7')
      || boxKey.startsWith('box8') || boxKey.startsWith('box9');
}

export default function NineBoxDiffTable({
  erpBoxes, taxiBoxes, delta, tolerance = 0.5,
}: NineBoxDiffTableProps) {
  return (
    <div className="my-2 border border-fg-dim/20 rounded-lg overflow-hidden">
      <div className="bg-bg-elevated px-4 py-2 flex items-center justify-between">
        <p className="font-medium text-fg">📊 9-Box 复核结果</p>
        <p className={`text-xs ${delta.within_tolerance ? 'text-success' : 'text-warning'}`}>
          tolerance £{tolerance.toFixed(2)} · 总差异 £{Number(delta.total_abs_diff).toFixed(2)}
          {delta.within_tolerance ? ' ✅' : ' ⚠️'}
        </p>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-bg-elevated/50 text-xs text-fg-dim">
            <th className="px-3 py-2 text-left">Box</th>
            <th className="px-3 py-2 text-right">ERP 算的</th>
            <th className="px-3 py-2 text-right">T.A.X.I. 算的</th>
            <th className="px-3 py-2 text-right">差异</th>
            <th className="px-3 py-2 text-center">状态</th>
          </tr>
        </thead>
        <tbody>
          {BOX_LABELS.map(([key, label, erpKey]) => {
            const isInt = isIntBox(key);
            const erpVal = erpBoxes[erpKey] as any;
            const taxiVal = taxiBoxes[erpKey] as any;
            const diff = Number(delta.box_diffs[key] || 0);
            const overTolerance = Math.abs(diff) > tolerance;
            return (
              <tr
                key={key}
                className={`border-t border-fg-dim/10 ${
                  overTolerance ? 'bg-error-muted animate-pulse' : ''
                }`}
              >
                <td className="px-3 py-2 text-fg-dim">{label}</td>
                <td className="px-3 py-2 text-right font-mono text-fg">
                  {formatAmount(erpVal, isInt)}
                </td>
                <td className="px-3 py-2 text-right font-mono text-fg">
                  {formatAmount(taxiVal, isInt)}
                </td>
                <td className={`px-3 py-2 text-right font-mono ${
                  overTolerance ? 'text-error font-semibold' : 'text-fg-dim'
                }`}>
                  {diff >= 0 ? '+' : ''}{diff.toFixed(isInt ? 0 : 2)}
                </td>
                <td className="px-3 py-2 text-center">
                  {overTolerance ? (
                    <ExclamationTriangleIcon className="w-4 h-4 text-error inline" />
                  ) : (
                    <CheckCircleIcon className="w-4 h-4 text-success inline" />
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {!delta.within_tolerance && (
        <div className="px-4 py-2 border-t border-error/20 bg-error-muted text-xs text-error">
          ⚠️ 差异超 tolerance: {delta.notes.join('; ')}
        </div>
      )}
    </div>
  );
}
