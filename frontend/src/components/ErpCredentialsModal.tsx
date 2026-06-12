import { useState } from 'react';

interface Props {
  initial?: { url: string; apiKey: string; apiSecret: string };
  onSave: (creds: { url: string; apiKey: string; apiSecret: string }) => void;
  onClose: () => void;
}

export default function ErpCredentialsModal({ initial, onSave, onClose }: Props) {
  const [url, setUrl] = useState(initial?.url ?? 'http://my.local:8000');
  const [apiKey, setApiKey] = useState(initial?.apiKey ?? '');
  const [apiSecret, setApiSecret] = useState(initial?.apiSecret ?? '');

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="card p-6 w-full max-w-md">
        <h2 className="text-lg font-semibold mb-4">ERPNext 凭证</h2>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-fg-dim">ERPNext URL</label>
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="w-full input"
              placeholder="http://my.local:8000"
            />
          </div>
          <div>
            <label className="text-xs text-fg-dim">API Key</label>
            <input
              type="text"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full input"
            />
          </div>
          <div>
            <label className="text-xs text-fg-dim">API Secret</label>
            <input
              type="password"
              value={apiSecret}
              onChange={(e) => setApiSecret(e.target.value)}
              className="w-full input"
            />
          </div>
          <p className="text-xs text-warning">
            ⚠️ 凭证不加密,仅存浏览器 localStorage(v0 demo 限制)。
          </p>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onClose} className="btn-secondary">取消</button>
          <button
            onClick={() => onSave({ url, apiKey, apiSecret })}
            disabled={!url || !apiKey || !apiSecret}
            className="btn-primary"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
