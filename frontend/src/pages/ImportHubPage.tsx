import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ImportHubCardErpNext from '../components/ImportHubCardErpNext';
import ImportHubCardCsv from '../components/ImportHubCardCsv';

function currentPeriod(): { id: string; start: string; end: string } {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth(); // 0-11
  const q = Math.floor(month / 3) + 1;
  return {
    id: `Q${q}_${year}`,
    start: `${year}-${String((q - 1) * 3 + 1).padStart(2, '0')}-01`,
    end: `${year}-${String(q * 3).padStart(2, '0')}-${q === 1 || q === 4 ? '31' : '30'}`,
  };
}

export default function ImportHubPage() {
  const defaultPeriod = currentPeriod();
  const [period, setPeriod] = useState(defaultPeriod.id);
  const [start, setStart] = useState(defaultPeriod.start);
  const [end, setEnd] = useState(defaultPeriod.end);
  const navigate = useNavigate();

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-semibold mb-4">Import Hub</h1>

      <div className="card p-4 mb-6">
        <label className="text-sm text-fg-dim">本期</label>
        <select
          value={period}
          onChange={(e) => {
            setPeriod(e.target.value);
            // 简化: 实际可调一个 period→{start,end} 映射
          }}
          className="ml-2 input"
          data-testid="import-hub-period-select"
        >
          <option value="Q1_2026">Q1 2026</option>
          <option value="Q2_2026">Q2 2026</option>
          <option value="Q3_2026">Q3 2026</option>
          <option value="Q4_2026">Q4 2026</option>
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
          className="btn-primary"
          data-testid="import-hub-to-preview"
        >
          ✓ 准备报税,继续到 Preview
        </button>
      </div>
    </div>
  );
}
