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
    id: 'error-recovery',
    title: '错误修复',
    description: 'Contains a deliberate decimal error in Box 6 to test validation.',
    icon: 'AlertTriangle',
    lineItems: [
      { category: 'vat_due_sales' as VATCategory, amount: 200, currency: DEFAULT_CURRENCY, description: 'Box 1: VAT due on sales' },
      { category: 'vat_due_acquisitions' as VATCategory, amount: 0, currency: DEFAULT_CURRENCY, description: 'Box 2: VAT due on acquisitions' },
      { category: 'vat_reclaimed_purchases' as VATCategory, amount: 100, currency: DEFAULT_CURRENCY, description: 'Box 4: VAT reclaimed on purchases' },
      { category: 'total_sales_ex_vat' as VATCategory, amount: 500.99, currency: DEFAULT_CURRENCY, description: 'Box 6: Total value of sales ex VAT (deliberate decimal)' },
      { category: 'total_purchases_ex_vat' as VATCategory, amount: 250, currency: DEFAULT_CURRENCY, description: 'Box 7: Total value of purchases ex VAT' },
      { category: 'total_goods_supplied_eu' as VATCategory, amount: 100, currency: DEFAULT_CURRENCY, description: 'Box 8: Total value of goods supplied ex VAT' },
      { category: 'total_goods_acquired_eu' as VATCategory, amount: 50, currency: DEFAULT_CURRENCY, description: 'Box 9: Total value of acquisitions ex VAT' },
    ],
    taxpayer: {
      name: 'Test Company Ltd',
      tax_id: DEFAULT_VRN,
      tax_id_type: 'vrn',
    },
  },
  {
    id: 'real-business-q1',
    title: '真实企业季度申报',
    description: 'TechFlow Distribution Ltd 2026 Q1 完整季度数据：£245k 销售、£42k EU 贸易、进口 VAT。',
    icon: 'Building2',
    lineItems: [
      { category: 'vat_due_sales' as VATCategory, amount: 42520, currency: DEFAULT_CURRENCY, description: 'Box 1: Domestic sales VAT + reverse charge (£41,520 + £1,000)' },
      { category: 'vat_due_acquisitions' as VATCategory, amount: 13700, currency: DEFAULT_CURRENCY, description: 'Box 2: EU acquisitions VAT (DE £10,000 + NL £3,700)' },
      { category: 'vat_reclaimed_purchases' as VATCategory, amount: 51183, currency: DEFAULT_CURRENCY, description: 'Box 4: Total reclaimable VAT incl imports, adjustments' },
      { category: 'total_sales_ex_vat' as VATCategory, amount: 245300, currency: DEFAULT_CURRENCY, description: 'Box 6: All sales ex VAT incl zero-rated + exports' },
      { category: 'total_purchases_ex_vat' as VATCategory, amount: 240465, currency: DEFAULT_CURRENCY, description: 'Box 7: All purchases ex VAT incl imports + expenses' },
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
