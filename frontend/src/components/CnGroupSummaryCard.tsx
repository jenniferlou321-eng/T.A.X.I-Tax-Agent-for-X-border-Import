import { useEffect, useState } from 'react';
import { BanknotesIcon, BuildingLibraryIcon, DocumentChartBarIcon, ScaleIcon } from '@heroicons/react/24/outline';
import type { CnParentFilingRef } from '../data/casePresets';

interface CnGroupSummaryCardProps {
  dataRef: 'cnParentFiling' | 'jiahangCnFiling';
}

interface CnParentFiling {
  cn_parent?: { name_zh: string; name_en: string; uscc: string };
  vat_outputs?: { vat_payable_cny: number; output_vat_13_cny: number; output_vat_6_cny: number; input_vat_cny: number; intra_group_service_revenue_cny: number };
  cit_outputs?: { cit_payable_cny: number; pretax_income_cny: number; revenue_total_cny: number; effective_rate: number };
  withholding_tax?: { total_wht_cny: number; royalty_tax_cny: number; mgmt_fee_tax_cny: number; dividend_from_uk_sub_cny: number };
  transfer_pricing?: { intra_group_total_cny: number; tp_adjustment_cny: number; tp_method: string; documentation_status: string; beps2_pillar: string };
  dac6_disclosures?: { hallmark_C1b_cross_border: boolean; cross_border_rod_cny: number };
  expected_filings?: { vat_filing_deadline: string; tp_documentation_deadline: string };
}

const fmtCNY = (n: number | undefined) => `¥${(n ?? 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}`;

export default function CnGroupSummaryCard(props: CnGroupSummaryCardProps) {
  const [data, setData] = useState<CnParentFiling | null>(null);

  useEffect(() => {
    let active = true;
    const loader = props.dataRef === 'jiahangCnFiling'
      ? import('../data/jiahangCnFiling.json')
      : import('../data/cnParentFiling.json');
    loader.then((mod) => {
      if (active) setData(mod as unknown as CnParentFiling);
    });
    return () => {
      active = false;
    };
  }, []);

  if (!data) {
    return (
      <div className="card p-5 text-sm text-fg-dim">加载 CN 集团数据中...</div>
    );
  }

  return (
    <div className="card p-5 space-y-4">
      <div className="flex items-center gap-2">
        <BuildingLibraryIcon className="w-5 h-5 text-primary" />
        <h2 className="text-base font-semibold text-fg">CN 主场 · 集团视角申报数字</h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* VAT */}
        <div className="rounded-lg border border-border p-3 bg-bg-elevated">
          <div className="flex items-center gap-2 text-sm text-fg-muted">
            <BanknotesIcon className="w-4 h-4" />
            CN VAT 应缴
          </div>
          <div className="text-2xl font-bold text-fg mt-1">
            {fmtCNY(data.vat_outputs?.vat_payable_cny)}
          </div>
          <div className="text-[11px] text-fg-dim mt-1 leading-relaxed">
            销项 13%: {fmtCNY(data.vat_outputs?.output_vat_13_cny)}<br />
            销项 6%: {fmtCNY(data.vat_outputs?.output_vat_6_cny)}<br />
            进项抵扣: {fmtCNY(data.vat_outputs?.input_vat_cny)}<br />
            集团内服务收入: {fmtCNY(data.vat_outputs?.intra_group_service_revenue_cny)}
          </div>
        </div>

        {/* CIT */}
        <div className="rounded-lg border border-border p-3 bg-bg-elevated">
          <div className="flex items-center gap-2 text-sm text-fg-muted">
            <DocumentChartBarIcon className="w-4 h-4" />
            CN CIT 应缴
          </div>
          <div className="text-2xl font-bold text-fg mt-1">
            {fmtCNY(data.cit_outputs?.cit_payable_cny)}
          </div>
          <div className="text-[11px] text-fg-dim mt-1 leading-relaxed">
            应纳税所得额: {fmtCNY(data.cit_outputs?.pretax_income_cny)}<br />
            营业收入: {fmtCNY(data.cit_outputs?.revenue_total_cny)}<br />
            有效税率: {((data.cit_outputs?.effective_rate ?? 0.25) * 100).toFixed(0)}%(Q1 预缴)
          </div>
        </div>

        {/* WHT */}
        <div className="rounded-lg border border-border p-3 bg-bg-elevated">
          <div className="flex items-center gap-2 text-sm text-fg-muted">
            <ScaleIcon className="w-4 h-4" />
            预提税 WHT(中港税收安排)
          </div>
          <div className="text-2xl font-bold text-fg mt-1">
            {fmtCNY(data.withholding_tax?.total_wht_cny)}
          </div>
          <div className="text-[11px] text-fg-dim mt-1 leading-relaxed">
            特许权 7%: {fmtCNY(data.withholding_tax?.royalty_tax_cny)}<br />
            管理费 5%: {fmtCNY(data.withholding_tax?.mgmt_fee_tax_cny)}<br />
            股息 Q1: {fmtCNY(data.withholding_tax?.dividend_from_uk_sub_cny)}
          </div>
        </div>
      </div>

      {/* TP / DAC6 / BEPS 2.0 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-border">
        <div className="rounded-lg border border-border p-3 bg-bg-elevated">
          <div className="text-sm text-fg-muted">转让定价(TP)</div>
          <div className="mt-1 text-sm">
            <div>
              集团内部往来: <span className="font-mono text-fg">{fmtCNY(data.transfer_pricing?.intra_group_total_cny)}</span>
            </div>
            <div>
              TP 调整额: <span className="font-mono text-fg">+{fmtCNY(data.transfer_pricing?.tp_adjustment_cny)}</span>
            </div>
            <div className="text-[11px] text-fg-dim mt-1">
              方法: {data.transfer_pricing?.tp_method} | 文档: {data.transfer_pricing?.documentation_status}
            </div>
            <div className="text-[11px] text-fg-dim">
              BEPS 2.0 Pillar Two: {data.transfer_pricing?.beps2_pillar === 'not_in_scope' ? '不在范围内(<€750M)' : data.transfer_pricing?.beps2_pillar}
            </div>
          </div>
        </div>
        <div className="rounded-lg border border-border p-3 bg-bg-elevated">
          <div className="text-sm text-fg-muted">DAC6 强制披露(UK 侧)</div>
          <div className="mt-1 text-sm">
            <div>
              Hallmark C1(b) 跨境关联方 TP 安排:{' '}
              <span className={data.dac6_disclosures?.hallmark_C1b_cross_border ? 'text-amber-600 font-semibold' : 'text-fg-dim'}>
                {data.dac6_disclosures?.hallmark_C1b_cross_border ? '已触发' : '未触发'}
              </span>
            </div>
            <div>
              跨境 RoD 金额: <span className="font-mono text-fg">{fmtCNY(data.dac6_disclosures?.cross_border_rod_cny)}</span>
            </div>
            <div className="text-[11px] text-fg-dim mt-1">
              VAT 申报截止: {data.expected_filings?.vat_filing_deadline}<br />
              TP 文档截止: {data.expected_filings?.tp_documentation_deadline}
            </div>
          </div>
        </div>
      </div>

      <div className="text-[11px] text-fg-dim italic">
        注:CN 视角数据源:frontend/src/data/cnParentFiling.json(挂在 preset.groupDataRef='cnParentFiling' 上)。
        完整集团数据另见 frontend/src/data/realCaseData.json(Agent 兜底链)。
      </div>
    </div>
  );
}
