"""UK VAT 特定提示。

知识(税率 / 9-box / 工具格式 / workflow)已迁至 `uk:vat` skill
(backend/agent/skill_plugins/uk/skills/vat/SKILL.md),按需加载。
此处只保留:能力指针 + 常驻的提交前门禁(pre_submit_gate)。
"""
from __future__ import annotations

from .._generic import pre_submit_gate

PROMPT = """
## UK VAT
For the full UK VAT filing procedure — VAT rates, EU / reverse-charge / import
rules, the 9-box structure, the calculate→validate→submit workflow and the
exact tool-call JSON — invoke the `uk:vat` skill (it loads on demand). Do this
before you compute or file a UK VAT return.
""" + pre_submit_gate(
    tool_name="submit_vat_return",
    id_label="VRN",
    period_example="26A1",
    tax_type="vat",
    form_name="VAT 9-Box (MTD)",
    figures="""\
   - Box 1 (VAT due on sales and outputs): GBP
   - Box 2 (VAT due on acquisitions from EU): GBP
   - Box 3 (Total VAT due): GBP
   - Box 4 (VAT reclaimed on inputs): GBP
   - Box 5 (Net VAT to pay / (reclaim)): GBP
   - Box 6 (Total sales excluding VAT): GBP
   - Box 7 (Total purchases excluding VAT): GBP
   - Box 8 (Total goods supplied to EU): GBP
   - Box 9 (Total acquisitions from EU): GBP""",
    amendment_note="subsequent amendments require a formal correction workflow (VAT Notice 700/45 — 30-day amendment window).",
)
