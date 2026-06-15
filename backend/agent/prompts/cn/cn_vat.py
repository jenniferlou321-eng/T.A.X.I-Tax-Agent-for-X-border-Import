"""中国增值税(CN VAT)特定提示。

知识(多档税率 13/9/6/5/3% / 含税不含税换算 / 销项−进项 / workflow / 工具)
已迁至 `cn:cn-vat` skill。此处只保留:能力指针 + 常驻的提交前门禁。
工具名对齐实际 metadata(get_cn_vat_obligations / calculate_cn_vat_return /
validate_cn_vat_return / submit_cn_vat_return / get_cn_vat_return);命名空间
`mcp__tax_agent_cn_cn_vat__*`。
"""
from __future__ import annotations

from .._generic import pre_submit_gate

PROMPT = """
## CN VAT(中国增值税)
For the full China VAT procedure — the 13% / 9% / 6% / 5% / 3% rate bands,
tax-inclusive vs tax-exclusive conversion, output−input VAT, the
get→calculate→validate→submit workflow and the exact tool-call JSON — invoke
the `cn:cn-vat` skill (loads on demand) before you compute or file a China
VAT return. Tools are namespaced `mcp__tax_agent_cn_cn_vat__*`.
""" + pre_submit_gate(
    tool_name="submit_cn_vat_return",
    id_label="USCC 统一社会信用代码(18 位)",
    period_example="2026-05",
    tax_type="cn_vat",
    form_name="增值税纳税申报表",
    figures="""\
   - 销项税额合计 (output_tax): CNY
   - 进项税额合计 (input_tax): CNY
   - 应纳增值税 (vat_payable = 销项 − 进项): CNY
   - 期末留抵税额 (若进项 > 销项): CNY
   - 纳税人类型 (taxpayer_type: general / small): """,
    amendment_note="China VAT is filed monthly (by the 15th of the following month); corrections are made via a 更正申报 (amended return) for the period.",
    authority="国家税务总局 (China State Taxation Administration)",
)
