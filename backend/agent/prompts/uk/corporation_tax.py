"""UK Corporation Tax 特定提示。

知识(税率 / marginal relief / workflow)已迁至 `uk:corporation-tax` skill。
此处只保留:能力指针 + 常驻的提交前门禁。
"""
from __future__ import annotations

from .._generic import pre_submit_gate

PROMPT = """
## UK Corporation Tax
For the full UK Corporation Tax procedure — CT rates, the marginal relief
formula, the calculate→validate→submit workflow and the CT600 tool list —
invoke the `uk:corporation-tax` skill (loads on demand) before you compute or
file a CT return.
""" + pre_submit_gate(
    tool_name="submit_corporation_tax",
    id_label="CTREF",
    period_example="FY ending 2025-03-31",
    tax_type="corporation_tax",
    form_name="CT600 (Corporation Tax return)",
    figures="""\
   - Turnover (total trading income): GBP
   - Trading profits (after expenses & capital allowances): GBP
   - Non-trading income (loan relationships, intangible fixed assets, etc.): GBP
   - Total profits (chargeable to CT): GBP
   - Marginal relief applied (if profits £50k-£250k): GBP
   - R&D enhanced expenditure (R&D tax credit): GBP
   - Franked investment income: GBP
   - Corporation Tax chargeable: GBP
   - CT payable: GBP""",
    amendment_note="subsequent amendments require a formal CT600 amend (within 12 months of filing deadline).",
)
