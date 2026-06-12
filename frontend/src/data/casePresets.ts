import type { LineItem, VATCategory } from '../types';

export interface CasePreset {
  id: string;
  title: string;
  description: string;
  icon: string;
  lineItems: LineItem[];
  taxpayer: {
    name: string;
    tax_id: string;
    tax_id_type: string;
  };
}

const DEFAULT_CURRENCY = 'GBP';
const DEFAULT_VRN = '960606228';

export const casePresets: CasePreset[] = [
  {
    id: 'standard-taxable',
    title: '标准应税申报',
    description: 'A typical VAT return with standard UK VAT boxes filled.',
    icon: 'FileText',
    lineItems: [
      { category: 'vat_due_sales' as VATCategory, amount: 250, currency: DEFAULT_CURRENCY, description: 'Box 1: VAT due on sales' },
      { category: 'vat_due_acquisitions' as VATCategory, amount: 50, currency: DEFAULT_CURRENCY, description: 'Box 2: VAT due on acquisitions' },
      { category: 'vat_reclaimed_purchases' as VATCategory, amount: 120, currency: DEFAULT_CURRENCY, description: 'Box 4: VAT reclaimed on purchases' },
      { category: 'total_sales_ex_vat' as VATCategory, amount: 1250, currency: DEFAULT_CURRENCY, description: 'Box 6: Total value of sales ex VAT' },
      { category: 'total_purchases_ex_vat' as VATCategory, amount: 600, currency: DEFAULT_CURRENCY, description: 'Box 7: Total value of purchases ex VAT' },
      { category: 'total_goods_supplied_eu' as VATCategory, amount: 100, currency: DEFAULT_CURRENCY, description: 'Box 8: Total value of goods supplied ex VAT' },
      { category: 'total_goods_acquired_eu' as VATCategory, amount: 50, currency: DEFAULT_CURRENCY, description: 'Box 9: Total value of acquisitions ex VAT' },
    ],
    taxpayer: {
      name: 'Anker UK Ltd',
      tax_id: DEFAULT_VRN,
      tax_id_type: 'vrn',
    },
  },
  {
    id: 'net-refund',
    title: '净退税申报',
    description: 'A filing where reclaimable VAT exceeds VAT due, resulting in a refund.',
    icon: 'TrendingDown',
    lineItems: [
      { category: 'vat_due_sales' as VATCategory, amount: 100, currency: DEFAULT_CURRENCY, description: 'Box 1: VAT due on sales' },
      { category: 'vat_due_acquisitions' as VATCategory, amount: 0, currency: DEFAULT_CURRENCY, description: 'Box 2: VAT due on acquisitions' },
      { category: 'vat_reclaimed_purchases' as VATCategory, amount: 300, currency: DEFAULT_CURRENCY, description: 'Box 4: VAT reclaimed on purchases' },
      { category: 'total_sales_ex_vat' as VATCategory, amount: 500, currency: DEFAULT_CURRENCY, description: 'Box 6: Total value of sales ex VAT' },
      { category: 'total_purchases_ex_vat' as VATCategory, amount: 1500, currency: DEFAULT_CURRENCY, description: 'Box 7: Total value of purchases ex VAT' },
      { category: 'total_goods_supplied_eu' as VATCategory, amount: 0, currency: DEFAULT_CURRENCY, description: 'Box 8: Total value of goods supplied ex VAT' },
      { category: 'total_goods_acquired_eu' as VATCategory, amount: 0, currency: DEFAULT_CURRENCY, description: 'Box 9: Total value of acquisitions ex VAT' },
    ],
    taxpayer: {
      name: 'British Manufacturing Ltd',
      tax_id: DEFAULT_VRN,
      tax_id_type: 'vrn',
    },
  },
  {
    id: 'zero-filing',
    title: '零值申报',
    description: 'All boxes are zero — a nil return for a quiet period.',
    icon: 'CircleDashed',
    lineItems: [
      { category: 'vat_due_sales' as VATCategory, amount: 0, currency: DEFAULT_CURRENCY, description: 'Box 1: VAT due on sales' },
      { category: 'vat_due_acquisitions' as VATCategory, amount: 0, currency: DEFAULT_CURRENCY, description: 'Box 2: VAT due on acquisitions' },
      { category: 'vat_reclaimed_purchases' as VATCategory, amount: 0, currency: DEFAULT_CURRENCY, description: 'Box 4: VAT reclaimed on purchases' },
      { category: 'total_sales_ex_vat' as VATCategory, amount: 0, currency: DEFAULT_CURRENCY, description: 'Box 6: Total value of sales ex VAT' },
      { category: 'total_purchases_ex_vat' as VATCategory, amount: 0, currency: DEFAULT_CURRENCY, description: 'Box 7: Total value of purchases ex VAT' },
      { category: 'total_goods_supplied_eu' as VATCategory, amount: 0, currency: DEFAULT_CURRENCY, description: 'Box 8: Total value of goods supplied ex VAT' },
      { category: 'total_goods_acquired_eu' as VATCategory, amount: 0, currency: DEFAULT_CURRENCY, description: 'Box 9: Total value of acquisitions ex VAT' },
    ],
    taxpayer: {
      name: 'NewCo Consulting Ltd',
      tax_id: DEFAULT_VRN,
      tax_id_type: 'vrn',
    },
  },
  {
    id: 'real-business-q1',
    title: '真实企业季度申报',
    description: 'TechFlow Distribution Ltd 2026 Q1：£282k 销售、£240k 采购、4 国 EU B2B、进口 C79。数字与后端 techflow_q1_2026.json erp_provided_boxes 严格一致。',
    icon: 'Building2',
    lineItems: [
      { category: 'vat_due_sales' as VATCategory, amount: 41523.50, currency: DEFAULT_CURRENCY, description: 'Box 1: Domestic sales VAT (£41,520 domestic + £3.50 zero-rated adj.)' },
      { category: 'vat_due_acquisitions' as VATCategory, amount: 13700, currency: DEFAULT_CURRENCY, description: 'Box 2: EU acquisitions VAT (DE £10,000 + NL £3,700)' },
      { category: 'vat_reclaimed_purchases' as VATCategory, amount: 47612, currency: DEFAULT_CURRENCY, description: 'Box 4: Reclaimable input VAT (incl. EU acquisition reverse charge)' },
      { category: 'total_sales_ex_vat' as VATCategory, amount: 282750, currency: DEFAULT_CURRENCY, description: 'Box 6: All sales ex VAT (27 invoices: 21 domestic + 4 EU B2B + 2 zero-rated)' },
      { category: 'total_purchases_ex_vat' as VATCategory, amount: 240460, currency: DEFAULT_CURRENCY, description: 'Box 7: All purchases ex VAT (24 invoices: 21 UK + 2 EU acq. + 1 exempt insurance)' },
      { category: 'total_goods_supplied_eu' as VATCategory, amount: 42450, currency: DEFAULT_CURRENCY, description: 'Box 8: EU B2B supplies (DE £12,500 + FR £15,000 + ES £8,750 + SE £6,200)' },
      { category: 'total_goods_acquired_eu' as VATCategory, amount: 68500, currency: DEFAULT_CURRENCY, description: 'Box 9: EU acquisitions (DE £50,000 + NL £18,500)' },
    ],
    taxpayer: {
      name: 'TechFlow Distribution Ltd',
      tax_id: DEFAULT_VRN,
      tax_id_type: 'vrn',
    },
  },
];

export function getCasePresetById(id: string): CasePreset | undefined {
  return casePresets.find(p => p.id === id);
}
