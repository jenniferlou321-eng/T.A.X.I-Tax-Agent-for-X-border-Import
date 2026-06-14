---
name: stamp-duty
description: "UK SDLT (Stamp Duty Land Tax, SDLT1) filing for property purchases. Load this BEFORE computing or filing any UK SDLT return — it has the residential / non-residential rate bands, first-time-buyer relief, additional-dwellings & non-resident surcharges, and the SDLT tool list."
---

# UK Stamp Duty Land Tax Filing (SDLT1)

This skill is the working procedure for UK SDLT. The pre-submit safety gate
and never-invent-numbers discipline are in your always-on system prompt.

## Your Capabilities (UK SDLT)
UK Stamp Duty Land Tax calculation and filing tools (namespace `mcp__tax_agent_uk_stamp_duty__*`):

1. **calculate_sdlt** — Calculate SDLT with tiered rates and reliefs
2. **validate_sdlt** — Validate SDLT submission
3. **submit_sdlt** — Submit SDLT return
4. **get_sdlt** — Retrieve previously submitted SDLT

## SDLT Rates (Residential, rUK, 2024/25)
| Portion of Price | Rate |
|------------------|------|
| £0 - £250,000 | 0% |
| £250,001 - £925,000 | 5% |
| £925,001 - £1,500,000 | 10% |
| Over £1,500,000 | 12% |

## First-Time Buyer Relief
| Portion of Price | Rate |
|------------------|------|
| £0 - £425,000 | 0% |
| £425,001 - £625,000 | 5% |

## Additional Dwellings Surcharge
- 5% on top of standard rates
- Applies to second homes and buy-to-let
- Stamp duty surcharge for non-UK residents: 2%

## Non-Residential SDLT
| Portion of Price | Rate |
|------------------|------|
| £0 - £150,000 | 0% |
| £150,001 - £250,000 | 2% |
| Over £250,000 | 5% |

## Important Notes
- England & Northern Ireland: SDLT
- Scotland: LBTT (different rates)
- Wales: LTT (different rates)
- Must submit SDLT return within 14 days of completion (after the pre-submit re-statement gate)
