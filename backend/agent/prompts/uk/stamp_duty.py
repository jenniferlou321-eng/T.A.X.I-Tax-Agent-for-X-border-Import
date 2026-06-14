"""UK Stamp Duty 特定提示。

知识(SDLT 税率档 / 首购减免 / 附加住宅与非居民附加费 / 工具)已迁至
`uk:stamp-duty` skill。此处只保留:能力指针 + 常驻的提交前门禁。
"""
from __future__ import annotations

from .._generic import pre_submit_gate

PROMPT = """
## UK SDLT
For the full UK SDLT procedure — residential / non-residential rate bands,
first-time-buyer relief, the additional-dwellings & non-resident surcharges,
and the SDLT tool list — invoke the `uk:stamp-duty` skill (loads on demand)
before you compute or file an SDLT return.
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
