"""UK PAYE 特定提示。"""
from __future__ import annotations

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
"""
