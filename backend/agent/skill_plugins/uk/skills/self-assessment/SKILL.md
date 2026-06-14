---
name: self-assessment
description: "UK Self Assessment (SA, HMRC MTD for ITSA) filing for individuals. Load this BEFORE computing or filing any UK Self Assessment return — it has the income tax bands, capital gains rates, the workflow and the SA tool list."
---

# UK Self Assessment Filing (SA)

This skill is the working procedure for UK Self Assessment. The pre-submit
safety gate and never-invent-numbers discipline are in your always-on system
prompt.

## Your Capabilities (UK Self Assessment)
HMRC MTD for ITSA tools for individual taxpayers (namespace `mcp__tax_agent_uk_self_assessment__*`):

1. **get_self_assessment_obligations** — Query filing obligations for a given NINO
2. **calculate_self_assessment** — Calculate tax liability from income sources
3. **validate_self_assessment** — Validate SA submission
4. **submit_self_assessment** — Submit SA return to HMRC
5. **get_self_assessment** — Retrieve previously submitted SA

## UK Income Tax Rates (2024/25 rUK)
| Band | Rate | Range |
|------|------|-------|
| Personal Allowance | 0% | £0 - £12,570 |
| Basic Rate | 20% | £12,571 - £50,270 |
| Higher Rate | 40% | £50,271 - £125,140 |
| Additional Rate | 45% | > £125,140 |

* Personal Allowance reduced by £1 for every £2 over £100,000
* Scotland has different rates

## Capital Gains Tax (2024/25)
- Annual Exempt Amount: £3,000
- Basic rate taxpayers: 18%
- Higher/Additional rate: 24%

## Workflow
1. Ask for NINO if not provided
2. Use get_self_assessment_obligations to find open tax years
3. Collect income data (employment, self-employment, property, capital gains, etc.)
4. Use calculate_self_assessment to compute tax due
5. Use validate_self_assessment to check compliance
6. Present results for confirmation
7. Use submit_self_assessment to file (after the pre-submit re-statement gate)

## Important Rules
- UK tax year: 6 April to 5 April
- Online filing deadline: 31 January following tax year-end
- Confirm calculations before submission
- Tax already paid includes PAYE withheld by employer
