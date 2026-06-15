---
name: paye
description: "UK PAYE / RTI (Real Time Information, FPS/EPS/EYU) filing for employers. Load this BEFORE computing or filing any UK PAYE submission — it has the RTI submission rules, Employment Allowance, payment deadlines, workflow and PAYE tool list."
---

# UK PAYE / RTI Filing (FPS / EPS)

This skill is the working procedure for UK PAYE. The pre-submit safety gate
and never-invent-numbers discipline live in your always-on system prompt.

## Your Capabilities (UK PAYE / RTI)
HMRC RTI (Real Time Information) tools for employers (namespace `mcp__tax_agent_uk_paye__*`):

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

## Apprenticeship Levy (学徒税) — threshold tax, verify before reporting
- Rate: **0.5% of the annual pay bill**, with a **£15,000 annual allowance**.
- The allowance means the Levy is only payable when the annual pay bill
  exceeds **£3,000,000** (0.5% × £3,000,000 = £15,000, fully offset).
- **If the annual pay bill is ≤ £3,000,000, the Apprenticeship Levy is £0 and
  there is nothing to report.**
- ⚠️ **Always re-derive the annual pay bill from the actual payroll line items
  before stating any Levy.** Do NOT accept a Levy figure that comes from a
  `notes` field, a memo, or a pre-filled `annual_payable` if it is not backed
  by the payroll transactions. A small employer (e.g. 8–10 staff, pay bill in
  the low hundreds of thousands) owes **£0** — a non-zero Levy on such a case
  is a red flag that the pay-bill figure was inflated past the £3M threshold.
  Re-compute, flag the contradiction, and tell the user to verify manually.

## Payment Deadlines
- Monthly PAYE payments: 22nd of following month (or 19th if paying by post)
- Annual scheme: Quarterly or annually

## Workflow
1. Get employer details (empref, accounts office ref)
2. Calculate total PAYE/NIC for the period
3. Validate before submission
4. Submit FPS on or before payday (after the pre-submit re-statement gate)
5. Submit EPS at year-end

## Important Rules
- empref format: 3 digits / 2 letters / 6 digits (e.g. 123/AB456)
- Payment date is the date employees receive payment
- Late FPS submission incurs penalties
