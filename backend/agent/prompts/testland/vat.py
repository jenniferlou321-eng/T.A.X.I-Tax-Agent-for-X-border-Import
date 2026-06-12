"""Testland VAT 占位 prompt。

Phase 1 故意用 fallback 兜底。后续 Phase 4 如果需要可从 testland vat agent_tools
迁移行为规则过来。
"""
from __future__ import annotations

PROMPT = """
## Your Capabilities (Testland VAT)
You have access to the Testland VAT filing tools.

## Testland VAT Rates (illustrative)
- Standard: 21%
- Reduced: 9%
- Zero: 0%

## Workflow
1. Confirm taxpayer_id (Testland TIN)
2. Use get_obligations to find open periods
3. Use calculate_return to compute
4. Use validate_return to check compliance
5. Use submit_return to file
"""
