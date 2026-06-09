import { useState } from 'react';
import { CloudArrowUpIcon, XMarkIcon, ExclamationCircleIcon } from '@heroicons/react/24/outline';
import { api } from '../api/client';
import type { ImportResult } from '../types';

interface CsvImportWizardProps {
  onImported: (result: ImportResult) => void;
  onClose: () => void;
}

export default function CsvImportWizard({ onImported, onClose }: CsvImportWizardProps) {
  const [file, setFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);

  const handleFile = (f: File) => {
    if (f.size > 10 * 1024 * 1024) {
      setError('文件超过 10MB 上限');
      return;
    }
    setFile(f);
    setError(null);
    setResult(null);
  };

  const handleImport = async () => {
    if (!file) return;
    setImporting(true);
    setError(null);
    try {
      const ir = await api.erp.importCsv(file);
      setResult(ir);
    } catch (err: any) {
      setError(err?.message || '导入失败');
    } finally {
      setImporting(false);
    }
  };

  const handleConfirm = () => {
    if (result) onImported(result);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <div className="bg-bg rounded-xl max-w-3xl w-full max-h-[80vh] overflow-y-auto">
        <div className="px-6 py-4 flex items-center justify-between border-b border-fg-dim/20">
          <h2 className="text-lg font-semibold text-fg">上传 CSV</h2>
          <button onClick={onClose} className="text-fg-dim hover:text-fg">
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {!file && (
            <label className="block border-2 border-dashed border-fg-dim/30 rounded-lg p-8 text-center cursor-pointer hover:border-accent">
              <CloudArrowUpIcon className="w-12 h-12 text-fg-dim mx-auto mb-2" />
              <p className="text-sm text-fg-muted">点击或拖拽 CSV 文件到此处</p>
              <p className="text-xs text-fg-dim mt-1">最大 10MB</p>
              <input
                type="file"
                accept=".csv"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              />
            </label>
          )}

          {file && !result && (
            <div>
              <p className="text-sm text-fg-muted mb-2">
                已选文件: <span className="font-mono text-fg">{file.name}</span> (
                {(file.size / 1024).toFixed(1)} KB)
              </p>
              <button
                onClick={handleImport}
                disabled={importing}
                className="btn btn-primary w-full"
              >
                {importing ? '解析中...' : '解析 CSV'}
              </button>
            </div>
          )}

          {error && (
            <div className="border border-error/30 bg-error-muted rounded-lg p-4 flex items-start gap-2">
              <ExclamationCircleIcon className="w-5 h-5 text-error shrink-0 mt-0.5" />
              <p className="text-sm text-error">{error}</p>
            </div>
          )}

          {result && (
            <div>
              <p className="text-sm text-fg-muted mb-2">
                ✅ 解析成功: {result.sales.length} 张销售 + {result.purchases.length} 张采购
              </p>
              {result.rejected_rows && result.rejected_rows.length > 0 && (
                <div className="border border-warning/30 bg-warning-muted rounded-lg p-3 mb-3">
                  <p className="text-sm text-warning">
                    ⚠️ {result.rejected_rows.length} 行被拒绝:
                  </p>
                  <ul className="text-xs text-fg-dim mt-1 space-y-1 max-h-32 overflow-y-auto">
                    {result.rejected_rows.slice(0, 10).map((r) => (
                      <li key={r.row_index}>Row {r.row_index}: {r.reason}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="flex gap-2">
                <button onClick={handleConfirm} className="btn btn-primary flex-1">
                  使用此数据继续
                </button>
                <button onClick={() => { setFile(null); setResult(null); }} className="btn btn-ghost">
                  重新选择
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
