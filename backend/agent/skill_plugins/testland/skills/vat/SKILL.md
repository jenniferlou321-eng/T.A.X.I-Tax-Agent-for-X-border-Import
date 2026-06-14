---
name: vat
description: "Testland VAT filing (illustrative demo jurisdiction). Load this BEFORE computing or filing any Testland VAT return — it has the Testland VAT rates and the get→calculate→validate→submit workflow."
---

# Testland VAT Filing (Demo)

Testland is an illustrative demo jurisdiction. The pre-submit safety gate and
never-invent-numbers discipline are in your always-on system prompt.

## Your Capabilities (Testland VAT)
You have access to the Testland VAT filing tools (namespace `mcp__tax_agent_testland_vat__*`).

## Testland VAT Rates (illustrative)
- Standard: 21%
- Reduced: 9%
- Zero: 0%

## Workflow
1. Confirm taxpayer_id (Testland TIN)
2. Use get_vat_obligations to find open periods
3. Use calculate_vat_return to compute
4. Use validate_vat_return to check compliance
5. Use submit_vat_return to file (after the pre-submit re-statement gate)
