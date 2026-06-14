// 嘉汉案例专用类型定义
import type { SalesTransaction, PurchaseTransaction } from './index'

// 扩展 transaction 类型,加入 jiahang 案例自定义字段(Pydantic 默认忽略)
export interface JiahangTransactionExtension {
  txn_type?: string
  currency?: string
  fx_rate?: number | null
  related_party_id?: string | null
  tax_filing_tag?: string | null
  filable?: boolean
  platform_status?: string
  notes?: string
  tax_code?: string
}

export type JiahangSalesTx = SalesTransaction & JiahangTransactionExtension
export type JiahangPurchaseTx = PurchaseTransaction & JiahangTransactionExtension

// Capability 状态枚举
export type CapabilityStatus =
  | 'supported'
  | 'partial'
  | 'not_supported'
  | 'no_action_required'

// 报税要求(单税种)
export interface TaxRequirement {
  tax_type: string
  tax_name: string
  period: string
  period_key?: string
  deadline: string
  [key: string]: unknown
  platform_support: CapabilityStatus | string
  action: string
  missing?: string[]
  evidence?: string
}

// case metadata 关键字段(从 erp_import.json metadata 抽出)
export interface CaseMetadata {
  case_id: string
  title: string
  company: string
  company_type: 'uk_subsidiary' | 'cn_parent'
  currency: 'GBP' | 'CNY'
  fiscal_year: string
  scenario?: string
  related_case_ids?: string[]
  transaction_count?: number
  tax_types_involved?: string[]
  [key: string]: unknown
}
