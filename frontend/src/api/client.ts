import type {
  DataTemplate,
  FilingResult,
  CalculationResult,
  ValidationResult,
  VATObligation,
  ImportResult, ReconciliationDelta,
  SalesTransaction, PurchaseTransaction,
} from '../types';

// Default to a same-origin empty string so the request hits Vite's dev-server
// proxy (which forwards /api → http://127.0.0.1:8765) and the static preview
// server's same-origin /api path. Override with VITE_API_BASE_URL when the
// frontend and backend are on different hosts (e.g. direct cloudfront → ALB).
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '';

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const isFormData = options?.body instanceof FormData;
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      // Let the browser set multipart Content-Type (with boundary) for FormData.
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...options?.headers,
    },
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
  agent: {
    mountWorkspaceCase: (caseId: string) =>
      fetchApi<{ workspace_path: string; manifest: Record<string, unknown> }>(
        `/api/agent/workspace/cases/${encodeURIComponent(caseId)}`,
        { method: 'POST' }
      ),
    clearWorkspace: () =>
      fetchApi<{ workspace_path: string; cleared: boolean }>(
        '/api/agent/workspace',
        { method: 'DELETE' }
      ),
  },
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
    clear: () =>
      fetchApi<{ status: string; cleared_filings: number; cleared_audit_entries: number; removed_log_files: number }>(
        '/api/filings/clear',
        { method: 'POST' }
      ),
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
  erp: {
    listCases: () =>
      fetchApi<{ cases: string[] }>('/api/erp/cases'),
    getCase: (caseId: string) =>
      fetchApi<ImportResult>(`/api/erp/cases/${encodeURIComponent(caseId)}`),
    importCsv: (file: File, profile?: string) => {
      const form = new FormData();
      form.append('file', file);
      if (profile) form.append('profile', profile);
      return fetchApi<ImportResult>('/api/erp/import', { method: 'POST', body: form });
    },
    reconcile: (importResult: ImportResult, erpSource: string) =>
      fetchApi<ReconciliationDelta>('/api/erp/reconcile', {
        method: 'POST',
        body: JSON.stringify({ import_result: importResult, erp_source: erpSource }),
      }),
    erpnextStatus: () =>
      fetchApi<{
        connected: boolean;
        last_push_at: string | null;
        sales_count: number;
        purchases_count: number;
        docnames: string[];
        company?: string | null;
        source?: string | null;
      }>('/api/erp/erpnext/status'),
    erpnextPull: (body: {
      url: string;
      api_key: string;
      api_secret: string;
      period: string;
      period_start: string;
      period_end: string;
      since?: string;
    }) =>
      fetchApi<{
        status: 'ok';
        period: string;
        sales: number;
        purchases: number;
        cancelled: number;
        amends: number;
        count: { sales: number; purchases: number; cancelled: number; amends: number; total: number };
      }>('/api/erp/erpnext/pull', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    erpnextHubSummary: (period: string) =>
      fetchApi<{
        period: string;
        sales: SalesTransaction[];
        purchases: PurchaseTransaction[];
        count: { sales: number; purchases: number; cancelled: number; amends: number; total: number };
        raw: Array<{ id: string; cancelled: boolean; is_amend: boolean; parent?: string | null }>;
      }>(`/api/erp/hub/summary?period=${encodeURIComponent(period)}`),
  },
  corpus: {
    // 知识库同步:对比镜像库与本地库,返回新增/修改的 source 列表
    checkUpdates: () =>
      fetchApi<{
        status: 'ok' | 'no_mirror' | 'error';
        message?: string;
        report: null | {
          summary: { new_count: number; modified_count: number };
          new: Array<{
            source_id: string;
            title: string;
            url: string;
            source_authority: string;
            tax_tags: string[];
            chunk_count: number;
            status: string;
          }>;
          modified: Array<{
            source_id: string;
            title: string;
            url: string;
            source_authority: string;
            tax_tags: string[];
            chunk_count: number;
            status: string;
          }>;
        };
      }>('/api/corpus/check-updates'),
    // 一键应用:把镜像的差异合并进本地 JSONL,自动重载 in-memory 知识库
    applyUpdates: () =>
      fetchApi<{
        status: 'ok' | 'partial' | 'error';
        message?: string;
        result?: {
          new_count: number;
          modified_count: number;
          total_chunks: number;
        };
      }>('/api/corpus/apply-updates', { method: 'POST' }),
  },
};
