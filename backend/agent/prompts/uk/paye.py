"""UK PAYE 特定提示。

知识(RTI 规则 / Employment Allowance / 截止日 / workflow)已迁至 `uk:paye`
skill。此处只保留:能力指针 + 常驻的提交前门禁。
"""
from __future__ import annotations

from .._generic import pre_submit_gate

PROMPT = """
## UK PAYE / RTI
For the full UK PAYE procedure — RTI submission rules (FPS/EPS/EYU),
Employment Allowance, payment deadlines, the workflow and the PAYE tool list —
invoke the `uk:paye` skill (loads on demand) before you compute or file a PAYE
submission.
""" + pre_submit_gate(
    tool_name="submit_paye",
    id_label="EM PREF",
    period_example="2026-04",
    tax_type="paye",
    form_name="FPS (Full Payment Submission) / EPS (Employer Payment Summary)",
    figures="""\
   - Employer PAYE income tax withheld: GBP
   - Employer NIC (Class 1A, Class 1B): GBP
   - Employee NIC (Class 1): GBP
   - CIS deductions (Construction Industry Scheme): GBP
   - Statutory payments (SSP / SMP / SPP): GBP
   - Employment Allowance claimed: GBP
   - Total payable for this period: GBP
   - Payment date (date employees received payment): YYYY-MM-DD
   - Number of employees on payroll: N""",
    amendment_note="subsequent amendments require an EYU (Earlier Year Update) within the same tax year, or a formal correction thereafter.",
)
