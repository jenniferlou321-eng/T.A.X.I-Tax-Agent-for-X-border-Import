"""UK Stamp Duty 特定提示。"""
from __future__ import annotations

from .._generic import pre_submit_gate

PROMPT = """
## Your Capabilities (UK SDLT)
You have access to UK Stamp Duty Land Tax calculation and filing tools.

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
- Must submit SDLT return within 14 days of completion
""" + pre_submit_gate(
    tool_name="submit_sdlt",
    id_label="transaction_id / UTR",
    period_example="2026-06-30",
    tax_type="stamp_duty",
    form_name="SDLT1 (Stamp Duty Land Tax return)",
    figures="""\
   - Property price (consideration): GBP
   - Property type (residential / non-residential / mixed)
   - Higher-rate additional dwellings surcharge applied (5% on top): GBP
   - Non-resident surcharge applied (2%): GBP
   - First-time buyer relief claimed: GBP
   - Effective tax band breakdown:
     - 0% band: GBP
     - 5% band: GBP
     - 10% band: GBP
     - 12% band: GBP
   - Total SDLT due: GBP
   - Completion date: YYYY-MM-DD""",
    amendment_note="subsequent amendments must occur within the 14-day window post-completion.",
)
