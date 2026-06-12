import { useEffect, useId, useRef, useState } from 'react';

interface Props {
  initial?: { url: string; apiKey: string; apiSecret: string };
  onSave: (creds: { url: string; apiKey: string; apiSecret: string }) => void;
  onClose: () => void;
}

export default function ErpCredentialsModal({ initial, onSave, onClose }: Props) {
  const [url, setUrl] = useState(initial?.url ?? 'http://my.local:9001');
  const [apiKey, setApiKey] = useState(initial?.apiKey ?? '');
  const [apiSecret, setApiSecret] = useState(initial?.apiSecret ?? '');

  const urlId = useId();
  const apiKeyId = useId();
  const apiSecretId = useId();
  const urlInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    urlInputRef.current?.focus();
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div
        className="card p-6 w-full max-w-md"
        role="dialog"
        aria-modal="true"
        aria-labelledby="erp-creds-title"
        data-testid="erp-credentials-modal"
      >
        <h2 id="erp-creds-title" className="text-lg font-semibold mb-4">ERPNext 凭证</h2>
        <div className="space-y-3">
          <div>
            <label htmlFor={urlId} className="text-xs text-fg-dim">ERPNext URL</label>
            <input
              id={urlId}
              ref={urlInputRef}
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="w-full input"
              placeholder="http://my.local:9001"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              data-testid="erp-creds-url"
            />
          </div>
          <div>
            <label htmlFor={apiKeyId} className="text-xs text-fg-dim">API Key</label>
            <input
              id={apiKeyId}
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full input"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              data-testid="erp-creds-key"
            />
          </div>
          <div>
            <label htmlFor={apiSecretId} className="text-xs text-fg-dim">API Secret</label>
            <input
              id={apiSecretId}
              type="password"
              value={apiSecret}
              onChange={(e) => setApiSecret(e.target.value)}
              className="w-full input"
              autoComplete="off"
              autoCapitalize="off"
              spellCheck={false}
              data-testid="erp-creds-secret"
            />
          </div>
          <p className="text-xs text-warning">
            ⚠️ 凭证不加密,仅存浏览器 localStorage(v0 demo 限制)。
          </p>
        </div>
        <div className="mt-6 flex justify-end gap-2">
          <button onClick={onClose} className="btn-secondary" data-testid="erp-creds-cancel">取消</button>
          <button
            onClick={() => onSave({ url, apiKey, apiSecret })}
            disabled={!url || !apiKey || !apiSecret}
            className="btn-primary"
            data-testid="erp-creds-save"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
