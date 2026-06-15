---
name: cn-vat
description: "China VAT (增值税) filing. Load this BEFORE computing or filing any China VAT return — it has the multi-tier rate bands (13% / 9% / 6% / 5% / 3%), tax-inclusive vs tax-exclusive conversion, the output−input VAT mechanism, the calculate→validate→submit workflow, and the exact tool-call JSON for every China VAT tool (namespace mcp__tax_agent_cn_cn_vat__*)."
---

# China VAT Filing (增值税)

This skill is the working procedure for China VAT. The safety gate (pre-submit
re-statement) and the never-invent-numbers discipline are in your always-on
system prompt — this skill is the *how*: rates, rules, tool formats, workflow.

## Your Capabilities (China VAT)
You have access to the following tools (namespace `mcp__tax_agent_cn_cn_vat__*`):

1. **get_cn_vat_obligations** — Query open China VAT filing obligations for a USCC (filed monthly, by the 15th of the following month)
2. **calculate_cn_vat_return** — Compute VAT payable = output VAT − input VAT from pre-aggregated line items
3. **validate_cn_vat_return** — Validate a VAT Return (amounts non-negative; flags a credit carry-forward when input > output)
4. **submit_cn_vat_return** — Submit a VAT Return to the 电子税务局 (simulated in demo) — irreversible, only after explicit user confirmation
5. **get_cn_vat_return** — Retrieve a previously submitted VAT Return

## China VAT Rate Bands (2024)
| Rate | Applies to |
|------|------------|
| **13%** | Sale of goods, processing/repair/assembly, leasing of tangible movables |
| **9%** | Transport, construction, real-estate leasing, basic telecom |
| **6%** | Modern services, financial services, lifestyle services, value-added telecom |
| **5%** | Real-estate leasing (简易计税, properties acquired before 2016-04-30) |
| **3%** | Small-scale taxpayers / 简易征收 (simplified levy) |

**Taxpayer types**: `general` (一般纳税人, full output−input credit) vs `small`
(小规模纳税人, typically 3% / 1% simplified, no input credit). Pass via metadata
`taxpayer_type` (default `general`).

## VAT Calculation Mechanism
```
应纳增值税 (VAT payable) = 销项税额 (output VAT) − 进项税额 (input VAT)
```
- **output VAT** = Σ (sales at each rate × that rate)
- **input VAT** = Σ (deductible purchases at each rate)
- If input VAT > output VAT → the excess is a **期末留抵税额** (end-of-period
  credit carried forward), NOT a refund in the general case.

### Tax-inclusive vs tax-exclusive (含税 / 不含税)
- `line_items` amounts are **tax-inclusive by default** (metadata
  `tax_inclusive: true`). The calculator extracts tax as
  `tax = amount × rate / (1 + rate)`.
- If you pass tax-exclusive (不含税) sales, set `tax_inclusive: false` →
  `tax = amount × rate`.

## Tool Calling Guide
The validate / submit values are passed as a `return_data` sub-object, NOT as
flat fields. `line_items` categories: per-rate sales `output_13 / output_9 /
output_6 / output_5 / output_3` and per-rate input `input_13 / input_9 /
input_6`, OR the aggregate `output_tax` (销项税额合计) / `input_tax`
(进项税额合计) directly.

### get_cn_vat_obligations
```json
{
  "taxpayer_id": "91110000XXXXXXXXXX",
  "status_filter": "O"
}
```
(`uscc` is also accepted and mapped to `taxpayer_id`. `status_filter`: `""` all / `"O"` open / `"F"` fulfilled.)

### calculate_cn_vat_return
```json
{
  "line_items_json": "[{\"category\":\"output_tax\",\"amount\":2732000},{\"category\":\"input_tax\",\"amount\":270500}]"
}
```
Or by per-rate sales:
```json
{
  "line_items_json": "[{\"category\":\"output_13\",\"amount\":21000000},{\"category\":\"input_13\",\"amount\":2080000}]"
}
```

### validate_cn_vat_return
```json
{
  "return_data": {
    "output_tax": "2732000.00",
    "input_tax": "270500.00",
    "vat_payable": "2461500.00"
  }
}
```

### submit_cn_vat_return
```json
{
  "taxpayer_id": "91110000XXXXXXXXXX",
  "period_key": "2026-05",
  "return_data": {
    "output_tax": "2732000.00",
    "input_tax": "270500.00",
    "vat_payable": "2461500.00"
  }
}
```

### get_cn_vat_return
```json
{
  "taxpayer_id": "91110000XXXXXXXXXX",
  "period_key": "2026-05"
}
```

## Workflow
When a user wants to file a China VAT Return:

1. Use **get_cn_vat_obligations** to find open filing periods (monthly; due by the 15th of the following month).
2. Use **calculate_cn_vat_return** to compute output VAT − input VAT from the line items (per-rate sales/input, or aggregate output_tax/input_tax).
3. Use **validate_cn_vat_return** to check compliance (non-negative amounts; note any 留抵 credit when input > output).
4. Present the 销项/进项/应纳/留抵 figures for confirmation.
5. Use **submit_cn_vat_return** to file (only after explicit user confirmation — see the pre-submit gate in your system prompt).
6. Return the (simulated) receipt.
