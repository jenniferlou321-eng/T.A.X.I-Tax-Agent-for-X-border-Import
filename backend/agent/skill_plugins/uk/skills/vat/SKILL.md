---
name: vat
description: "UK VAT (HMRC Making Tax Digital, 9-box) filing. Load this BEFORE computing or filing any UK VAT return — it has the VAT rates, EU / reverse-charge / import-VAT rules, the 9-box structure, the calculate→validate→submit workflow, and the exact tool-call JSON for every UK VAT tool."
---

# UK VAT Filing (HMRC MTD, 9-Box)

This skill is the working procedure for UK VAT. The safety gate (pre-submit
re-statement) and the never-invent-numbers discipline are in your always-on
system prompt — this skill is the *how*: rates, rules, tool formats, workflow.

## Your Capabilities (UK VAT)
You have access to the following tools (namespace `mcp__tax_agent_uk_vat__*`):

1. **analyze_business_data** — Analyze raw invoice/transaction data and calculate VAT Return with regulatory compliance notes
2. **get_vat_obligations** — Query HMRC for open VAT filing obligations for a given VRN
3. **calculate_vat_return** — Calculate the 9-box VAT Return from pre-aggregated line items
4. **validate_vat_return** — Validate a VAT Return calculation for compliance
5. **submit_vat_return** — Submit a completed VAT Return to HMRC
6. **get_vat_return** — Retrieve a previously submitted VAT Return
7. **ingest_erp_data** — Load raw ERP data: either a built-in demo case (source='demo', case_id='...') or a user-supplied CSV (source='csv', csv_base64='...'). Returns an ImportResult that you pass to `analyze_business_data`.
8. **filter_invoices** — Filter / list invoices from the current session's ImportResult. **v0 STUB**: returns empty list. Use direct API instead.

## Field Naming (HMRC vs legacy)
9-Box values in tool outputs use **HMRC field names** (`vat_due_sales`, `total_sales_ex_vat`, `net_vat_due`, ...). These match what `validate_vat_return` / `submit_vat_return` expect as the `return_data` sub-object. The older `box1_vat_due_sales` / `box6_total_sales` style is **deprecated** and will be removed; do not use it.

## Tool Calling Guide
When calling tools, use the exact parameter names and types. The 9-Box values for validate / submit are passed as a `return_data` sub-object, NOT as flat fields.

### analyze_business_data
```json
{
  "company_data_json": "{...raw business data or ingest_erp_data output...}"
}
```

### get_vat_obligations
```json
{
  "taxpayer_id": "123456789",
  "status_filter": "O"
}
```
(`vrn` is also accepted and mapped to `taxpayer_id`.)

### calculate_vat_return
```json
{
  "line_items_json": "[{\"category\":\"vat_due_sales\",\"amount\":2500.00,\"currency\":\"GBP\"}]"
}
```

### validate_vat_return
```json
{
  "return_data": {
    "vat_due_sales": "2500.00",
    "vat_due_acquisitions": "0.00",
    "vat_reclaimed_purchases": "1200.00",
    "total_sales_ex_vat": "12500",
    "total_purchases_ex_vat": "6000",
    "total_goods_supplied_eu": "0",
    "total_goods_acquired_eu": "0"
  }
}
```

### submit_vat_return
```json
{
  "taxpayer_id": "123456789",
  "period_key": "26A1",
  "return_data": {
    "vat_due_sales": "2500.00",
    "vat_due_acquisitions": "0.00",
    "total_vat_due": "2500.00",
    "vat_reclaimed_purchases": "1200.00",
    "net_vat_due": "1300.00",
    "total_sales_ex_vat": "12500",
    "total_purchases_ex_vat": "6000",
    "total_goods_supplied_eu": "0",
    "total_goods_acquired_eu": "0"
  }
}
```

### get_vat_return
```json
{
  "taxpayer_id": "123456789",
  "period_key": "26A1"
}
```

### ingest_erp_data
```json
{
  "source": "demo",
  "case_id": "case-b-cn-parent"
}
```
(Omit `case_id` to list available cases. Use `source: "csv"` + `csv_base64` for a user-supplied file.)

### filter_invoices
```json
{
  "txn_type": "sale",
  "flagged_only": false
}
```
(v0 stub — returns empty list. Do not rely on this tool.)

## UK VAT Knowledge Base
Apply the following UK VAT rules when analyzing business data:

### VAT Rates and Categories
- **Standard Rate (20%)**: Applies to most goods and services. Domestic B2B and B2C sales.
- **Zero Rate (0%)**: Children's clothing, printed books, most food. Still counted in Box 6 (sales) but no VAT in Box 1.
- **Exempt**: Insurance, financial services, postal services. Not included in VAT Return at all.
- **Export outside EU**: VAT exempt. Evidence of export required. Included in Box 6.

### EU Transactions
- **EU B2B Sales**: Zero-rated under intra-EU supply rules. Customer must provide valid EU VAT number. Reported in Box 8 only.
- **EU Acquisitions**: Box 2 (VAT due at UK rate) + Box 4 (same amount reclaimable) + Box 7 (net) + Box 9 (EU goods). Net effect zero but must be declared.

### Special Schemes
- **Reverse Charge (B2B Digital Services)**: For digital services from outside UK (e.g., Google Ads from Ireland). Box 1 (VAT due) + Box 4 (reclaimable) + Box 6 (net). Net effect zero.
- **Import VAT (C79)**: VAT paid at customs on imports from outside EU. Reclaimable with C79 certificate. Customs duty is NOT reclaimable. Box 4 + Box 7.
- **Flat Rate Scheme**: Not currently supported; warn user if detected.

### Non-Recoverable VAT
- **Business Entertainment**: Client meals, hospitality — VAT not recoverable per HMRC.
- **Exempt Purchases**: Insurance, financial services — no VAT to reclaim.
- **Mileage Claims**: Reimbursed at HMRC approved rates — no VAT element.
- **International Transport**: Flights outside UK — no UK VAT.

### VAT Adjustments
- **Bad Debt Relief**: VAT on debts > 6 months old where customer has gone into liquidation. Added to Box 4.
- **Pre-Registration VAT**: VAT on stock purchased within 4 years and services within 6 months before VAT registration. Added to Box 4.

## VAT Return 9-Box Structure
| Box | Description | Format |
|-----|-------------|--------|
| Box 1 | VAT due on sales | Numeric, 2 decimals |
| Box 2 | VAT due on acquisitions from EU | Numeric, 2 decimals |
| Box 3 | Total VAT due (Box 1 + Box 2) | Auto-calculated |
| Box 4 | VAT reclaimed on purchases | Numeric, 2 decimals |
| Box 5 | Net VAT due (|Box 3 - Box 4|) | Auto-calculated, must be ≥ 0 |
| Box 6 | Total value of sales ex VAT | Integer, whole pounds |
| Box 7 | Total value of purchases ex VAT | Integer, whole pounds |
| Box 8 | Total value of goods supplied to EU | Integer, whole pounds |
| Box 9 | Total value of goods acquired from EU | Integer, whole pounds |

## Workflow
When a user wants to file a VAT Return:

### Path A: Raw Business Data Available
0. (Optional) Call **ingest_erp_data** with `source: "demo"` and a `case_id` from the available list (or omit `case_id` to list them). The result includes `import_result` (sales, purchases, erp_provided_boxes) and a `summary`. Serialize `import_result` back to JSON and pass it as `company_data_json` to `analyze_business_data`.
1. Use **get_vat_obligations** to find open filing periods
2. Use **analyze_business_data** to process the raw data
3. Review the analysis with the user, explain any unusual items
4. **Cross-Check (do this BEFORE calling validate_vat_return)** — verify these structural invariants manually. If any fail, investigate and fix before proceeding:
   | Check | Rule | What to do if it fails |
   |-------|------|------------------------|
   | **EU Acquisition Symmetry** | If Box 9 > 0, Box 2 must also > 0 (and vice versa). EU reverse charge acquisitions generate **both** Box 2 (VAT due) and Box 4 (reclaim) with the same amount. | Re-run `analyze_business_data` or check if `is_reverse_charge` / `is_eu_acquisition` flags are missing in the raw data. |
   | **PVA Self-Cancel** | PVA Import VAT (e.g. C1-103 £33,075) must increase **both** Box 1 and Box 4 by the same amount. Net effect on Box 5 = £0. | Check `analyze_business_data` output for `import_pva` breakdown. If missing, the purchase row may lack `pva_eligible: true` or `pva_used: true`. |
   | **Input VAT vs Purchases** | If Box 4 > 0, Box 7 should generally also > 0 (unless 100% from PVA/RC with no net purchase value). | Verify purchase invoices are included in the data feed. |
   | **Box 3 = Box 1 + Box 2** | Must hold exactly. | Recalculate; never submit manually patched numbers. |
   | **Box 5 = \|Box 3 − Box 4\|** | Must hold exactly (and ≥ 0 per HMRC). | Same as above. |
5. Use **validate_vat_return** to double-check compliance (pass the `nine_box` sub-object from `analyze_business_data` as `return_data`). Treat validator warnings as **mandatory review items**, not suggestions.
6. Present the results for confirmation
7. Use **submit_vat_return** to file with HMRC (only after explicit user confirmation — see the pre-submit gate in your system prompt)
8. Return the HMRC receipt

### Path B: Pre-Aggregated Data Only
1. Use **get_vat_obligations** to find open filing periods
2. Use **calculate_vat_return** to compute from the pre-aggregated line items (Box 1-9 values)
3. **Cross-Check** — apply the same 5 structural checks from Path A step 4. Pre-aggregated data is especially risky because agent or user may have manually assembled numbers from different sources.
4. Use **validate_vat_return** to check compliance
5. Present results for confirmation
6. Use **submit_vat_return** to file
