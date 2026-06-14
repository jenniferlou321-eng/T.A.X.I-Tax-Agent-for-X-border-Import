// Runtime export to prevent Vite/esbuild from compiling this file to `export {};`
// All other exports are type-only and stripped at compile time.
export const TYPES_VERSION = '1.0.0';

export type FilingStatus = 'pending' | 'in_progress' | 'submitted' | 'accepted' | 'rejected' | 'error';

export interface TaxType {
  value: string;
  label: string;
}

export interface Jurisdiction {
  country_code: string;
  country_name: string;
  tax_types: TaxType[];
  supported_channels: string[];
}

export interface TemplateField {
  key: string;
  label: string;
  field_type: 'number' | 'text' | 'select' | 'date' | 'file';
  required: boolean;
  hint?: string;
  example?: string;
  auto_calculated?: boolean;
  allow_manual_override?: boolean;
}

export interface TemplateSection {
  title: string;
  description?: string;
  fields: TemplateField[];
  is_optional?: boolean;
}

export interface DataTemplate {
  tax_type: string;
  jurisdiction: string;
  version: string;
  sections: TemplateSection[];
}

export type VATCategory =
  | 'vat_due_sales'
  | 'vat_due_acquisitions'
  | 'vat_reclaimed_purchases'
  | 'total_sales_ex_vat'
  | 'total_purchases_ex_vat'
  | 'total_goods_supplied_eu'
  | 'total_goods_acquired_eu';

export interface LineItem {
  category: VATCategory;
  amount: number;
  currency: string;
  description?: string;
}

export interface TaxData {
  tax_type: string;
  period: {
    year: number;
    period_type: string;
    period_key: string;
  };
  taxpayer: {
    name: string;
    tax_id: string;
    tax_id_type: string;
  };
  line_items: LineItem[];
}

export interface StageResult {
  stage: string;
  status: 'pending' | 'running' | 'success' | 'warning' | 'error';
  message: string;
  detail?: Record<string, any>;
  started_at?: string;
  completed_at?: string;
}

export interface FilingResult {
  filing_id: string;
  status: FilingStatus;
  receipt?: {
    receipt_id: string;
    submitted_at: string;
    raw_response?: Record<string, any>;
  };
  errors: Array<{
    code: string;
    message: string;
    stage: string;
  }>;
  stage_results: Record<string, StageResult>;
}

export interface CalculationResult {
  total_tax_due: number;
  breakdown: Array<{
    category: string;
    amount: number;
  }>;
  warnings: string[];
}

export interface ValidationResult {
  is_valid: boolean;
  errors: Array<{
    field: string;
    message: string;
  }>;
  warnings: Array<{
    field: string;
    message: string;
  }>;
}

export interface VATObligation {
  start: string;
  end: string;
  due: string;
  status: string;
  period_key: string;
  received: string | null;
}

// ERP integration types (v0)
export interface SalesTransaction {
  id: string;
  txn_date: string;
  counterparty: string;
  net_amount: string;
  vat_amount: string;
  gross_amount: string;
  vat_rate: string;
  tax_code: string;
  is_eu?: boolean;
  is_reverse_charge?: boolean;
}

export interface PurchaseTransaction {
  id: string;
  txn_date: string;
  counterparty: string;
  net_amount: string;
  vat_amount: string;
  gross_amount: string;
  vat_rate: string;
  tax_code: string;
  is_recoverable?: boolean;
  is_eu_acquisition?: boolean;
}

export interface ERPNineBox {
  box1_vat_due_sales: string;
  box2_vat_due_acquisitions: string;
  box3_total_vat_due: string;
  box4_vat_reclaimed: string;
  box5_net_vat_due: string;
  box6_total_sales_ex_vat: number;
  box7_total_purchases_ex_vat: number;
  box8_total_goods_supplied_eu: number;
  box9_total_goods_acquired_eu: number;
  scheme_flags?: string[];
}

export interface ImportResult {
  sales: SalesTransaction[];
  purchases: PurchaseTransaction[];
  erp_provided_boxes: ERPNineBox;
  source_profile: string;
  source_filename: string;
  source_hash: string;
  warnings?: string[];
  rejected_rows?: Array<{ row_index: number; reason: string; raw: Record<string, string> }>;
  /** Pydantic ImportResult 自由 dict 字段(嘉汉案例 metadata 在此) */
  metadata?: Record<string, unknown>;
}

export interface ReconciliationDelta {
  box_diffs: Record<string, string>;
  total_abs_diff: string;
  within_tolerance: boolean;
  erp_source: string;
  notes: string[];
}

export interface DemoCaseSummary {
  id: string;
  title: string;
  description: string;
}

export interface ImportSummary {
  source?: string;
  compute_mode: string;
  sales_count: number;
  purchases_count: number;
  import_warnings: string[];
  import_rejected_rows_count: number;
}
