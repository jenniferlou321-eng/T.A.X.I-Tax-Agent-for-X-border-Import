---
name: corporation-tax
description: "UK Corporation Tax (CT600, HMRC MTD for CT) filing. Load this BEFORE computing or filing any UK Corporation Tax return — it has the CT rates, marginal relief formula, the calculate→validate→submit workflow, and the CT tool list."
---

# UK Corporation Tax Filing (CT600)

This skill is the working procedure for UK Corporation Tax. The pre-submit
safety gate and never-invent-numbers discipline are in your always-on system
prompt; this skill is the rates, formula, workflow and tools.

## Your Capabilities (UK Corporation Tax)
HMRC MTD for CT tools for limited companies (namespace `mcp__tax_agent_uk_corporation_tax__*`):

1. **get_corporation_tax_obligations** — Query filing obligations for a given CTREF
2. **calculate_corporation_tax** — Calculate CT with marginal rate relief
3. **validate_corporation_tax** — Validate CT600 submission
4. **submit_corporation_tax** — Submit CT return to HMRC
5. **get_corporation_tax** — Retrieve previously submitted CT

## UK Corporation Tax Rates (Financial Year 2024)
| Profit | Rate |
|--------|------|
| ≤ £50,000 | 19% |
| £50,000 - £250,000 | Marginal (between 19% and 25%) |
| ≥ £250,000 | 25% (main rate) |

## Marginal Relief Formula
For profits between £50,000 and £250,000, the rate is calculated to avoid abrupt jumps:
    Tax = Profits × 25% - (Standard Fraction × (Upper Limit - Profits))
where Standard Fraction = (250,000 × 25% - 50,000 × 19%) / (250,000 - 50,000)

## Workflow
1. Ask for CTREF and company details
2. Use get_corporation_tax_obligations to find open periods
3. Collect financial data (trading profits, non-trading income, capital allowances, losses)
4. Use calculate_corporation_tax to compute CT liability
5. Use validate_corporation_tax to check
6. Submit when confirmed (after the pre-submit re-statement gate)

## Important Rules
- Accounting period (typically 12 months) required
- Payment due 9 months and 1 day after period end
- Corporation Tax Reference (CTREF) is 10 digits
- Marginal relief only applies for associated companies
