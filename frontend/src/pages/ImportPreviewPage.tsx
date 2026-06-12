import { useSearchParams } from 'react-router-dom';

export default function ImportPreviewPage() {
  const [params] = useSearchParams();
  const period = params.get('period') ?? 'Q1_2026';
  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-semibold mb-2">Preview · {period}</h1>
      <p className="text-fg-dim">Coming soon — full Preview UI in Task 11.</p>
    </div>
  );
}
