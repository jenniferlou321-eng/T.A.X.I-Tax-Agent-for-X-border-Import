"""UK Self Assessment 特定提示。

知识(所得税档 / CGT / workflow)已迁至 `uk:self-assessment` skill。
此处只保留:能力指针 + 常驻的提交前门禁。
"""
from __future__ import annotations

from .._generic import pre_submit_gate

PROMPT = """
## UK Self Assessment
For the full UK Self Assessment procedure — income tax bands, capital gains
rates, the workflow and the SA tool list — invoke the `uk:self-assessment`
skill (loads on demand) before you compute or file an SA return.
""" + pre_submit_gate(
    tool_name="submit_self_assessment",
    id_label="NINO",
    period_example="2024-25",
    tax_type="self_assessment",
    form_name="SA108 (Self Assessment tax return)",
    figures="""\
   - Total income (employment + self-employment + property + savings + dividends + pensions): GBP
   - Allowable deductions / reliefs: GBP
   - Taxable income: GBP
   - Income tax (PAYE deducted + balancing payment due): GBP
   - National Insurance (Class 2 + Class 4): GBP
   - Capital gains tax: GBP
   - Student loan repayment: GBP
   - High Income Child Benefit Charge: GBP
   - Total tax due: GBP
   - Tax overpaid / (underpaid): GBP
   - Payments on account (next year): GBP
   - Balancing payment: GBP""",
    amendment_note="subsequent amendments require a formal SA amend (within 12 months of original filing).",
)
