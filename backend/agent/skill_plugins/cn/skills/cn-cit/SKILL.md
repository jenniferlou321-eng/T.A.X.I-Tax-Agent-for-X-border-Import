---
name: cn-cit
description: "China Corporate Income Tax (企业所得税, CIT) filing. Load this BEFORE computing or filing any China CIT return — it has the rates (25% standard / 15% high-tech / 5% small-and-low-profit), the taxable-income formula, the foreign-tax-credit limit, DTA/DTL recognition, quarterly prepayment vs annual settlement (汇算清缴), and the exact tool-call JSON for every China CIT tool (namespace mcp__tax_agent_cn_cn_cit__*)."
---

# China Corporate Income Tax Filing (企业所得税, CIT)

This skill is the working procedure for China CIT. The safety gate (pre-submit
re-statement) and the never-invent-numbers discipline are in your always-on
system prompt — this skill is the *how*: rates, rules, tool formats, workflow.

## Your Capabilities (China CIT)
You have access to the following tools (namespace `mcp__tax_agent_cn_cn_cit__*`):

1. **get_cn_cit_obligations** — Query open China CIT obligations for a USCC (quarterly prepayments + annual settlement 汇算清缴, due by 31 May of the following year)
2. **calculate_cn_cit_return** — Compute taxable income, CIT payable, foreign-tax-credit and amount-to-top-up from line items
3. **validate_cn_cit_return** — Validate a CIT Return (amounts non-negative; flags foreign-tax-credit over the limit)
4. **submit_cn_cit_return** — Submit the annual CIT settlement (simulated in demo) — irreversible, only after explicit user confirmation
5. **get_cn_cit_return** — Retrieve a previously submitted CIT Return

## China CIT Rates
| Rate | Applies to |
|------|------------|
| **25%** | Standard rate (一般企业) |
| **15%** | High-tech enterprises (高新技术企业) |
| **5% effective** | Small-and-low-profit enterprises (小型微利企业, taxable income ≤ ¥3M, 2024–2027) |

Select via metadata `tax_rate`: `standard` (25%) / `high_tech` (15%) / `small` (5% effective).

## CIT Calculation Mechanism
```
应纳税所得额 (taxable income) = 会计利润 (accounting profit)
                              + 纳税调增 (adjustments up)
                              − 纳税调减 (adjustments down)
应纳所得税额 (CIT payable)    = 应纳税所得额 × 税率 (rate)
应补 / 退税额 (top-up)        = 应纳所得税额 − 境外税收抵免 − 已预缴税额
```

### Foreign Tax Credit (境外税收抵免)
- Credit limit (抵免限额) = 境外所得 (overseas income) × the China rate.
- The actual credit is **capped at the limit**: `actual_ftc = min(foreign_tax_credit, ftc_limit)`. Excess foreign tax cannot be credited this period.

### DTA / DTL
- Deferred tax assets (`dta_recognized`) and liabilities (`dtl_recognized`) adjust the income-tax *expense*, not the cash payable. Pass them as line items when relevant.

### Quarterly vs Annual
- Quarterly filings are **prepayments** (预缴). The final liability is trued up in the annual **汇算清缴** (settlement), due by 31 May of the following year. `quarterly_prepaid` (已预缴税额) is subtracted to reach the top-up amount.

## Tool Calling Guide
The validate / submit values are passed as a `return_data` sub-object, NOT as
flat fields. `line_items` categories: `accounting_profit`, `tax_adjustment_up`,
`tax_adjustment_down`, `foreign_tax_credit`, `overseas_income`,
`dta_recognized`, `dtl_recognized`.

### get_cn_cit_obligations
```json
{
  "taxpayer_id": "91110000XXXXXXXXXX",
  "status_filter": "O"
}
```
(`uscc` is also accepted and mapped to `taxpayer_id`.)

### calculate_cn_cit_return
```json
{
  "line_items_json": "[{\"category\":\"accounting_profit\",\"amount\":8000000},{\"category\":\"tax_adjustment_up\",\"amount\":280000},{\"category\":\"tax_adjustment_down\",\"amount\":150000},{\"category\":\"foreign_tax_credit\",\"amount\":43679},{\"category\":\"overseas_income\",\"amount\":1639750}]"
}
```
(Rate is selected via metadata `tax_rate`; default `standard` = 25%.)

### validate_cn_cit_return
```json
{
  "return_data": {
    "income_tax_payable": "2032500.00",
    "foreign_tax_credit": "43679.00",
    "ftc_limit": "409937.50",
    "tax_payable": "1988821.00"
  }
}
```

### submit_cn_cit_return
```json
{
  "taxpayer_id": "91110000XXXXXXXXXX",
  "period_key": "FY2025",
  "return_data": {
    "income_tax_payable": "2032500.00",
    "foreign_tax_credit": "43679.00",
    "tax_payable": "1988821.00"
  }
}
```

### get_cn_cit_return
```json
{
  "taxpayer_id": "91110000XXXXXXXXXX",
  "period_key": "FY2025"
}
```

## Workflow
When a user wants to file a China CIT Return:

1. Use **get_cn_cit_obligations** to find open obligations (quarterly prepayments / annual settlement).
2. Use **calculate_cn_cit_return** to compute taxable income → CIT payable → foreign-tax-credit → top-up amount from the line items.
3. Use **validate_cn_cit_return** to check compliance (non-negative amounts; note any foreign-tax-credit over the limit).
4. Present the 应纳税所得额 / 适用税率 / 应纳所得税额 / 境外抵免 / 应补退 figures for confirmation.
5. Use **submit_cn_cit_return** to file (only after explicit user confirmation — see the pre-submit gate in your system prompt).
6. Return the (simulated) receipt.
