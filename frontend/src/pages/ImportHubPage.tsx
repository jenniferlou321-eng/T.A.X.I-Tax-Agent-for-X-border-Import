import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ImportHubCardErpNext from '../components/ImportHubCardErpNext';
import ImportHubCardCsv from '../components/ImportHubCardCsv';
import { useDemoStore } from '../stores/demoStore';

/**
 * Period id → {start, end, label}.
 * UK HMRC 允许 back-filing 最多 4 年,这里覆盖 2025 + 2026 共 8 个季度。
 */
const PERIODS: Record<string, { start: string; end: string; label: string }> = {
  Q1_2026: { start: '2026-01-01', end: '2026-03-31', label: 'Q1 2026' },
  Q2_2026: { start: '2026-04-01', end: '2026-06-30', label: 'Q2 2026' },
  Q3_2026: { start: '2026-07-01', end: '2026-09-30', label: 'Q3 2026' },
  Q4_2026: { start: '2026-10-01', end: '2026-12-31', label: 'Q4 2026' },
  Q1_2025: { start: '2025-01-01', end: '2025-03-31', label: 'Q1 2025' },
  Q2_2025: { start: '2025-04-01', end: '2025-06-30', label: 'Q2 2025' },
  Q3_2025: { start: '2025-07-01', end: '2025-09-30', label: 'Q3 2025' },
  Q4_2025: { start: '2025-10-01', end: '2025-12-31', label: 'Q4 2025' },
};

function defaultPeriodId(): string {
  // 默认挑一个在 PERIODS 里、又尽量接近"现在"的季度(Q1 2026)
  // — 不要每次 render 都用 currentPeriod(),否则跨年会跟着走,
  //   且 2025 老季度的 demo 用户第一次进来会被跳过。
  if (PERIODS['Q1_2026']) return 'Q1_2026';
  return Object.keys(PERIODS)[0];
}

export default function ImportHubPage() {
  const defaultId = defaultPeriodId();
  const defaultEntry = PERIODS[defaultId];
  const [period, setPeriod] = useState(defaultId);
  const [start, setStart] = useState(defaultEntry.start);
  const [end, setEnd] = useState(defaultEntry.end);
  const navigate = useNavigate();

  // 本期是否已有数据 — 控制 "准备报税" 按钮的可用状态
  const hubData = useDemoStore((s) => s.hubDataByPeriod[period]);
  const hasData = !!hubData && (hubData.salesCount + hubData.purchasesCount) > 0;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-semibold mb-4">Import Hub</h1>

      <div className="card p-4 mb-6">
        <label className="text-sm text-fg-dim">本期</label>
        <select
          value={period}
          onChange={(e) => {
            const id = e.target.value;
            setPeriod(id);
            const p = PERIODS[id];
            if (p) {
              setStart(p.start);
              setEnd(p.end);
            }
          }}
          className="ml-2 input"
          data-testid="import-hub-period-select"
        >
          {Object.entries(PERIODS).map(([id, p]) => (
            <option key={id} value={id}>
              {p.label}
            </option>
          ))}
        </select>
        <span className="ml-4 text-xs text-fg-dim">
          {start} ~ {end}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ImportHubCardErpNext period={period} periodStart={start} periodEnd={end} />
        <ImportHubCardCsv period={period} />
      </div>

      <div className="mt-6 text-right">
        <button
          onClick={() => navigate(`/import/preview?period=${period}`)}
          disabled={!hasData}
          className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          title={hasData ? '' : '请先导入数据'}
          data-testid="import-hub-to-preview"
        >
          ✓ 准备报税,继续到 Preview
        </button>
      </div>
    </div>
  );
}
