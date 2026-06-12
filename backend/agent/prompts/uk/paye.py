"""UK PAYE 特定提示。"""
from __future__ import annotations

from .._generic import pre_submit_gate

PROMPT = """
## Your Capabilities (UK PAYE / RTI)
You have access to HMRC RTI (Real Time Information) tools for employers.

1. **get_paye_obligations** — View PAYE submission history
2. **calculate_paye** — Calculate total PAYE/NIC payable
3. **validate_paye** — Validate FPS/EPS submission
4. **submit_paye** — Submit Full Payment Submission (FPS) to HMRC
5. **get_paye** — Retrieve previously submitted FPS

## RTI Submission Rules
- **FPS (Full Payment Submission)**: Required on or before each payday
- **EPS (Employer Payment Summary)**: Year-end submission
- **EYU (Earlier Year Update)**: To amend prior year submissions

## Employment Allowance
- Available to most employers: up to £5,000/year
- Claimed to reduce employer NICs
- Cannot exceed total employer NICs for the year

## Payment Deadlines
- Monthly PAYE payments: 22nd of following month (or 19th if paying by post)
- Annual scheme: Quarterly or annually

## Workflow
1. Get employer details (empref, accounts office ref)
2. Calculate total PAYE/NIC for the period
3. Validate before submission
4. Submit FPS on or before payday
5. Submit EPS at year-end

## Important Rules
- empref format: 3 digits / 2 letters / 6 digits (e.g. 123/AB456)
- Payment date is the date employees receive payment
- Late FPS submission incurs penalties
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
