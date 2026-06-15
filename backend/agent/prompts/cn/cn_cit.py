"""中国企业所得税(CN CIT)特定提示。

知识(税率 25/15/5% / 应纳税所得额公式 / 境外税收抵免限额 / DTA-DTL /
季度预缴 vs 年度汇算 / workflow / 工具)已迁至 `cn:cn-cit` skill。此处只保留:
能力指针 + 常驻的提交前门禁。工具名对齐实际 metadata(get_cn_cit_obligations /
calculate_cn_cit_return / validate_cn_cit_return / submit_cn_cit_return /
get_cn_cit_return);命名空间 `mcp__tax_agent_cn_cn_cit__*`。
"""
from __future__ import annotations

from .._generic import pre_submit_gate

PROMPT = """
## CN CIT(中国企业所得税)
For the full China CIT procedure — the 25% standard / 15% high-tech / 5%
small-and-low-profit effective rates, taxable-income = accounting profit +
adjustments-up − adjustments-down, the foreign-tax-credit limit, DTA/DTL,
quarterly prepayment vs annual settlement (汇算清缴), and the exact tool-call
JSON — invoke the `cn:cn-cit` skill (loads on demand) before you compute or
file a China CIT return. Tools are namespaced `mcp__tax_agent_cn_cn_cit__*`.
""" + pre_submit_gate(
    tool_name="submit_cn_cit_return",
    id_label="USCC 统一社会信用代码(18 位)",
    period_example="2026-Q1(季度预缴)或 FY2025(年度汇算)",
    tax_type="cn_cit",
    form_name="企业所得税申报表(季度预缴 / 年度汇算清缴)",
    figures="""\
   - 应纳税所得额 (taxable_income = 会计利润 + 调增 − 调减): CNY
   - 适用税率 (tax_rate: standard 25% / high_tech 15% / small 5%): %
   - 应纳所得税额 (cit_tax): CNY
   - 境外税收抵免 (foreign_tax_credit, 限额 = 境外所得 × 税率): CNY
   - 已预缴税额 (quarterly_prepaid): CNY
   - 应补 / 退税额 (tax_payable): CNY""",
    amendment_note="quarterly returns are prepayments; the final liability is trued up in the annual 汇算清缴 (settlement, due by 31 May of the following year).",
    authority="国家税务总局 (China State Taxation Administration)",
)
