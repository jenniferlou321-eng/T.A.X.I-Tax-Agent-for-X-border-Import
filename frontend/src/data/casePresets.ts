import type { LineItem, VATCategory } from '../types';

/** 挂在 preset 上的 CN 视角集团数据(Case B 专用)。
 *  实际数据从 cnParentFiling.json 加载,这里只是 TypeScript 类型声明。 */
export interface CnParentFilingRef {
  vat_payable_cny: number;
  cit_payable_cny: number;
  total_wht_cny: number;
  intra_group_total_cny: number;
  tp_adjustment_cny: number;
  vat_outputs: Record<string, number>;
  cit_outputs: Record<string, number>;
  withholding_tax: Record<string, number>;
  transfer_pricing: Record<string, unknown>;
  dac6_disclosures: Record<string, unknown>;
}

export interface CasePreset {
  id: string;
  title: string;
  description: string;
  icon: string;
  lineItems: LineItem[];            // 9-Box 默认值,Case B 为空数组
  taxpayer: {
    name: string;
    tax_id: string;
    tax_id_type: string;
  };
  /** 后端 case 目录名(也是 erp_samples 下的子目录名) */
  erpCaseId: string;
  /** 多管辖地: 多个 case_id 列表(优先于 erpCaseId) */
  erpCaseIds?: string[];
  /** Case B 专用: 引用 frontend/src/data/cnParentFiling.json */
  groupDataRef?: 'cnParentFiling' | 'jiahangCnFiling';
  /** 案例分类(嘉汉案例 = 驱动平台完善路线图) */
  kind?: 'standard' | 'case-jiahang' | 'doc-link';
  /** doc-link 专用: 点击后跳转到文档 URL(相对 /docs/) */
  entryRoute?: string;
}

const DEFAULT_CURRENCY = 'GBP';
const DEFAULT_VRN = '960606228';

export const casePresets: CasePreset[] = [
  // ── Case X: 入门,UK 单国 ─────────────────────────────
  {
    id: 'case-x-uk-standard',
    title: '入门:UK VAT 标准应交',
    description: 'Anker UK Ltd 2026 Q1:£1,250 销售、£600 采购,正常应交 £180。9-Box 自洽教学案例,数字小、关系清晰。',
    icon: 'FileText',
    lineItems: [
      { category: 'vat_due_sales' as VATCategory, amount: 250, currency: DEFAULT_CURRENCY, description: 'Box 1: VAT due on sales (£1,250 × 20%)' },
      { category: 'vat_due_acquisitions' as VATCategory, amount: 50, currency: DEFAULT_CURRENCY, description: 'Box 2: VAT due on acquisitions (EU acq reverse charge)' },
      { category: 'vat_reclaimed_purchases' as VATCategory, amount: 120, currency: DEFAULT_CURRENCY, description: 'Box 4: VAT reclaimed on purchases' },
      { category: 'total_sales_ex_vat' as VATCategory, amount: 1250, currency: DEFAULT_CURRENCY, description: 'Box 6: Total value of sales ex VAT' },
      { category: 'total_purchases_ex_vat' as VATCategory, amount: 600, currency: DEFAULT_CURRENCY, description: 'Box 7: Total value of purchases ex VAT' },
      { category: 'total_goods_supplied_eu' as VATCategory, amount: 100, currency: DEFAULT_CURRENCY, description: 'Box 8: Total value of EU B2B supplies' },
      { category: 'total_goods_acquired_eu' as VATCategory, amount: 50, currency: DEFAULT_CURRENCY, description: 'Box 9: Total value of EU acquisitions' },
    ],
    taxpayer: {
      name: 'Anker UK Ltd',
      tax_id: DEFAULT_VRN,
      tax_id_type: 'vrn',
    },
    erpCaseId: 'case-x-uk-standard',
  },

  // ── Case A: 跨境 — UK 子公司申报 ────────────────────────
  {
    id: 'case-a-uk-subsidiary',
    title: '跨境集团 · UK 子公司申报',
    description: 'TechFlow Distribution Ltd 2026 Q1:£282,750 销售、£240,460 采购,4 国 EU B2B + 2 国 EU acq + 2 笔进口 C79。9-Box 数字与后端 case-a-uk-subsidiary/erp_import.json 严格一致。',
    icon: 'Building2',
    lineItems: [
      { category: 'vat_due_sales' as VATCategory, amount: 41523.50, currency: DEFAULT_CURRENCY, description: 'Box 1: Domestic sales VAT (£41,520 + £3.50 zero-rating adj.)' },
      { category: 'vat_due_acquisitions' as VATCategory, amount: 13700, currency: DEFAULT_CURRENCY, description: 'Box 2: EU acquisitions VAT (DE £10,000 + NL £3,700)' },
      { category: 'vat_reclaimed_purchases' as VATCategory, amount: 47612, currency: DEFAULT_CURRENCY, description: 'Box 4: Reclaimable input VAT (incl. EU acq reverse charge + 2× C79)' },
      { category: 'total_sales_ex_vat' as VATCategory, amount: 282750, currency: DEFAULT_CURRENCY, description: 'Box 6: All sales ex VAT (21 domestic + 4 EU B2B + 2 zero-rated)' },
      { category: 'total_purchases_ex_vat' as VATCategory, amount: 240460, currency: DEFAULT_CURRENCY, description: 'Box 7: All purchases ex VAT (21 UK + 2 EU acq + 1 exempt insurance)' },
      { category: 'total_goods_supplied_eu' as VATCategory, amount: 42450, currency: DEFAULT_CURRENCY, description: 'Box 8: EU B2B supplies (DE £12,500 + FR £15,000 + ES £8,750 + SE £6,200)' },
      { category: 'total_goods_acquired_eu' as VATCategory, amount: 68500, currency: DEFAULT_CURRENCY, description: 'Box 9: EU acquisitions (DE £50,000 + NL £18,500)' },
    ],
    taxpayer: {
      name: 'TechFlow Distribution Ltd',
      tax_id: DEFAULT_VRN,
      tax_id_type: 'vrn',
    },
    erpCaseId: 'case-a-uk-subsidiary',
  },

  // ── Case B: 跨境 — CN 母 + UK 子(多管辖地) ────────────────
  {
    id: 'case-b-cn-parent',
    title: '跨境集团 · CN 母 + UK 子',
    description: 'Shenzhen TechFlow 2026 Q1:¥8.6M 营收,报 CN VAT ¥551k + CIT ¥950k + WHT ¥115.5k + TP 调整 +¥320k。集团对 UK 子 ¥2.1M IT 服务(6% VAT),同期资料 / DAC6 C1(b) / BEPS 2.0。',
    icon: 'Building',
    // CN 不是 9-Box 体系,lineItems 为空;数字在 cnParentFiling.json 的 groupDataRef 指向里
    lineItems: [],
    taxpayer: {
      name: 'Shenzhen TechFlow Technology Co., Ltd.',
      tax_id: '91440300MA5DC9X',
      tax_id_type: 'uscc',
    },
    erpCaseId: 'case-b-cn-parent',
    erpCaseIds: ['case-b-cn-parent', 'case-a-uk-subsidiary'],  // CN + UK 双国
    groupDataRef: 'cnParentFiling',
  },

  // ── Case J: 嘉汉跨境集团 — UK 子公司 FY2023(主线) ─────────
  {
    id: 'case-jiahang-uk-fy2023',
    title: '嘉汉集团 · UK 子公司 FY2023',
    description: 'Jiahang UK Holdings Ltd FY2023:33 笔业务覆盖 9 个 UK 税种。UK CT £43,950(3/200 公式)+ WHT £6,278(利息+特许权 10% 中英协定)+ Q1-Q4 VAT 净应缴 £12,925。9 个税种中 1 支持 / 2 部分 / 5 待实现 / 1 不需申报,案例驱动平台完善路线图。',
    icon: 'Globe2',
    kind: 'case-jiahang',
    // 嘉汉不是 9-Box 体系,lineItems 为空(数字在 erp_import.json metadata 与 tax_requirements.json)
    lineItems: [],
    taxpayer: {
      name: 'Jiahang UK Holdings Ltd.',
      // Demo: 用已在 HMRC 沙箱注册的 VRN(960606228)替换占位号,保证 4d 真提交不失败;公司名仍显示嘉汉品牌。
      tax_id: '960606228',
      tax_id_type: 'vrn',
    },
    erpCaseId: 'case-jiahang-uk-fy2023',
  },

  // ── Case J: 嘉汉跨境集团 — CN 母公司 FY2023(主线) ─────────
  {
    id: 'case-jiahang-cn-fy2023',
    title: '嘉汉集团 · CN 母公司 FY2023',
    description: '江苏嘉汉国际贸易有限公司 FY2023:64 笔业务覆盖 9 个 CN 税种。CIT 应纳 ¥2,032,500(8,000k + 280k 调增 - 150k 调减)× 25% + 境外抵免 ¥43,679(足额)+ DTA 期末 ¥70,000(期初 37.5k - 转回 37.5k + 新增 70k)。VAT 全年应纳 ¥2,461,500(销 2,732k - 进 270.5k)。9 个 CN 税种 0 支持 / 全部待实现。',
    icon: 'Building2',
    kind: 'case-jiahang',
    lineItems: [],
    taxpayer: {
      name: '江苏嘉汉国际贸易有限公司',
      tax_id: '91320000MA1XXXXXX',
      tax_id_type: 'uscc',
    },
    erpCaseId: 'case-jiahang-cn-fy2023',
    groupDataRef: 'jiahangCnFiling',
  },

  // ── 能力差距卡(跳转到 doc,不入 demoStore) ─────────
  {
    id: 'case-jiahang-capability',
    title: '平台能力差距矩阵(18 税种 × TAXI 支持状态)',
    description: '基于嘉汉案例驱动分析的 18 税种能力矩阵:1/18 已支持 + 2/18 部分支持 + 15/18 待实现 = 11% 已支持。P0 优先:UK CT、CN VAT、CN CIT(金额大、频率高、跨境必经)。',
    icon: 'Table',
    kind: 'doc-link',
    entryRoute: '/docs/jiahang-capability-matrix',
    lineItems: [],
    taxpayer: {
      name: 'T.A.X.I. 平台路线图',
      tax_id: 'P0-P3',
      tax_id_type: 'doc',
    },
    erpCaseId: 'case-jiahang-capability', // 仅为 validIds 白名单
  },
];

export function getCasePresetById(id: string): CasePreset | undefined {
  return casePresets.find(p => p.id === id);
}
