import { useSearchParams, useNavigate } from 'react-router-dom';

export default function ImportPreviewPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const period = params.get('period') ?? 'Q1_2026';
  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-semibold mb-4">Preview · {period}</h1>
      <div className="card p-6 text-center">
        <p className="text-fg-dim">本期内还没有导入数据。</p>
        <button
          onClick={() => navigate('/import')}
          className="btn-secondary mt-4"
          data-testid="import-preview-back"
        >
          ← 回 Import Hub
        </button>
      </div>
    </div>
  );
}
