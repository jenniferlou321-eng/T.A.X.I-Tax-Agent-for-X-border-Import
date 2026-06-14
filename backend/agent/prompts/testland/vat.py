"""Testland VAT 占位 prompt。

知识(税率 / workflow / 工具名)已迁至 `testland:vat` skill。
此处只保留:能力指针 + 常驻的提交前门禁(与 UK 税种一致,防"样板缺门")。
工具名对齐实际 metadata(get_vat_obligations / calculate_vat_return /
validate_vat_return / submit_vat_return)。
"""
from __future__ import annotations

from .._generic import pre_submit_gate

PROMPT = """
## Testland VAT
For the Testland VAT procedure — illustrative rates (21% / 9% / 0%), the
get→calculate→validate→submit workflow and the tool list — invoke the
`testland:vat` skill (loads on demand) before you compute or file a Testland
VAT return.
""" + pre_submit_gate(
    tool_name="submit_vat_return",
    id_label="Testland TIN",
    period_example="2026-Q1",
    tax_type="vat",
    form_name="Testland VAT Return",
    figures="""\
   - Standard-rated VAT due (21%): TLD
   - Reduced-rated VAT due (9%): TLD
   - Zero-rated sales (0%): TLD
   - VAT reclaimed on purchases: TLD
   - Net VAT payable / (reclaim): TLD""",
    amendment_note="this is a demo jurisdiction — the submission is simulated; corrections are made by re-filing the period.",
)
