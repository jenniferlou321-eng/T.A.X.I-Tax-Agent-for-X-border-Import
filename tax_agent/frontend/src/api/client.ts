import type {
  DataTemplate,
  FilingResult,
  CalculationResult,
  ValidationResult,
  VATObligation,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8765';

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    // FastAPI returns errors as {detail: "..."} or {detail: [{msg, loc, ...}, ...]} (validation 422).
    // Coerce whatever we get into a readable string — never leak "[object Object]".
    const message = formatErrorMessage(body, res.status, res.statusText);
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

function formatErrorMessage(body: unknown, status: number, fallback: string): string {
  if (body == null) return `${status} ${fallback}`;
  if (typeof body === 'string') return body;
  if (typeof body !== 'object') return String(body);
  const b = body as Record<string, unknown>;
  if (typeof b.message === 'string') return b.message;
  if (typeof b.detail === 'string') return b.detail;
  if (Array.isArray(b.detail)) {
    // FastAPI 422 validation: [{loc: [...], msg: "...", type: "..."}, ...]
    const parts = b.detail
      .map((d) => {
        if (d && typeof d === 'object') {
          const dd = d as Record<string, unknown>;
          const loc = Array.isArray(dd.loc) ? dd.loc.join('.') : '';
          return loc ? `${loc}: ${dd.msg ?? 'invalid'}` : String(dd.msg ?? 'invalid');
        }
        return String(d);
      })
      .filter(Boolean);
    if (parts.length) return parts.join('; ');
  }
  return `${status} ${fallback}`;
}

export const api = {
  jurisdictions: {
    // Backend wraps the list and returns tax_types as a string[] (e.g. ["vat"]).
    // Consumers should normalise tax_types to {value,label} objects as needed.
    list: () =>
      fetchApi<{
        jurisdictions: {
          country_code: string;
          country_name: string;
          tax_types: string[];
          supported_channels: string[];
        }[];
      }>('/api/jurisdictions/'),
    template: (country: string, taxType: string) =>
      fetchApi<DataTemplate>(`/api/jurisdictions/${country}/templates/${taxType}`),
  },
  filings: {
    list: () => fetchApi<{ filings: FilingResult[]; total: number }>('/api/filings/'),
    get: (id: string) => fetchApi<FilingResult>(`/api/filings/${id}`),
    preview: (body: unknown) =>
      fetchApi<{ calculation: CalculationResult; validation: ValidationResult; can_submit: boolean }>(
        '/api/filings/preview',
        { method: 'POST', body: JSON.stringify(body) }
      ),
    submit: (body: unknown) =>
      fetchApi<FilingResult>('/api/filings/submit', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    status: (id: string) =>
      fetchApi<{ status: string }>(`/api/filings/${id}/status`),
    // Backend 的 /api/filings/obligations/{country}/{tax_type} 端点使用
    // 统一的 `taxpayer_id` query 参数（不同国家/税种 ID 命名：vrn/nino/ctref/empref）。
    // 前端传入的 ID 字段名因税种而异（vrn/nino/ctref/empref），这里统一映射为 taxpayer_id。
    obligations: (country: string, taxType: string, taxpayerId: string, params?: Record<string, string>) => {
      const search = new URLSearchParams({ taxpayer_id: taxpayerId });
      if (params) {
        Object.entries(params).forEach(([k, v]) => search.set(k, v));
      }
      return fetchApi<{ obligations: VATObligation[] }>(
        `/api/filings/obligations/${country}/${taxType}?${search.toString()}`
      );
    },
  },
  channel: {
    health: (country: string, taxType: string) =>
      fetchApi<{ healthy: boolean }>(`/api/channel/${country}/${taxType}/health`),
    authUrl: (country: string, taxType: string, redirectUri?: string) =>
      fetchApi<{ auth_url: string }>(
        `/api/channel/${country}/${taxType}/auth-url${redirectUri ? `?redirect_uri=${encodeURIComponent(redirectUri)}` : ''}`
      ),
    callback: (country: string, taxType: string, code: string, state?: string) =>
      fetchApi<{ success: boolean; token?: string; expires_at?: string; error?: string }>(
        `/api/channel/${country}/${taxType}/callback`,
        {
          method: 'POST',
          body: JSON.stringify({ code, state: state || '' }),
        }
      ),
    authStatus: (country: string, taxType: string) =>
      fetchApi<{ authenticated: boolean; expires_at?: number }>(
        `/api/channel/${country}/${taxType}/auth-status`
      ),
  },
};
