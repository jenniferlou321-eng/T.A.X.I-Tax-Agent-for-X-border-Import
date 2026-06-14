"""UK Corporation Tax (CT600) 完整模板

CT600 是英国企业税申报表，包含 200+ 字段，分 10+ sections。
本模板提供接近完整版的核心字段。
"""

from datetime import date

from backend.models.template import (
    DataTemplate, TemplateSection, TemplateField,
    FieldType, FieldValidation,
)
from backend.models.tax_data import TaxType


CT600_FULL_TEMPLATE = DataTemplate(
    tax_type=TaxType.CORPORATION_TAX,
    jurisdiction="uk",
    version="2.0.0",
    valid_from=date(2024, 4, 1),
    sections=[
        # ── 公司信息 ──
        TemplateSection(
            title="Company Details (CT600 Page 1)",
            description="Company details and accounting period",
            fields=[
                TemplateField(
                    key="ctref", label="Corporation Tax Reference",
                    field_type=FieldType.TEXT, required=True,
                    example="1234567890",
                ),
                TemplateField(
                    key="company_name", label="Company Name",
                    field_type=FieldType.TEXT, required=True,
                ),
                TemplateField(
                    key="company_registration_number", label="Company Registration Number",
                    field_type=FieldType.TEXT, required=True,
                    example="12345678",
                ),
                TemplateField(
                    key="utr", label="Unique Taxpayer Reference",
                    field_type=FieldType.TEXT, required=True,
                    hint="10-digit UTR",
                ),
                TemplateField(
                    key="period_start", label="Accounting Period Start",
                    field_type=FieldType.DATE, required=True,
                ),
                TemplateField(
                    key="period_end", label="Accounting Period End",
                    field_type=FieldType.DATE, required=True,
                ),
                TemplateField(
                    key="num_associated_companies", label="Number of Associated Companies",
                    field_type=FieldType.NUMBER, required=False,
                    example="1",
                    hint="Including this company. Affects marginal rate thresholds.",
                ),
            ],
        ),

        # ── CT600A: Trading Profits ──
        TemplateSection(
            title="Trading Profits (CT600A)",
            description="Turnover, expenses, and trading profit",
            fields=[
                TemplateField(
                    key="trading_income", label="Turnover (Box 145)",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="trading_expenses", label="Allowable Trading Expenses (Box 150)",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="trading_profit", label="Net Trading Profit (Box 155)",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
            ],
        ),

        # ── CT600B: Non-Trading Income ──
        TemplateSection(
            title="Non-Trading Income (CT600B)",
            description="Investment, property, and other non-trading income",
            fields=[
                TemplateField(
                    key="investment_income", label="Investment Income (Box 180)",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="property_income", label="Property Income (Box 190)",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="chargeable_gains", label="Chargeable Gains (Box 200)",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="dividend_income", label="Non-exempt Dividends (Box 210)",
                    field_type=FieldType.NUMBER, required=False,
                ),
            ],
        ),

        # ── CT600C: Capital Allowances (详细) ──
        TemplateSection(
            title="Capital Allowances (CT600C)",
            description="Detailed capital allowances by pool and type",
            fields=[
                # AIA
                TemplateField(
                    key="aia_expenditure", label="AIA-Qualifying Expenditure",
                    field_type=FieldType.NUMBER, required=False,
                    hint="Annual Investment Allowance (max £1m)",
                ),
                # FYA
                TemplateField(
                    key="fya_expenditure", label="FYA-Qualifying Expenditure",
                    field_type=FieldType.NUMBER, required=False,
                    hint="First Year Allowance (electric cars etc.)",
                ),
                # Main Pool
                TemplateField(
                    key="main_pool_expenditure", label="Main Pool Additions",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="main_pool_opening_balance", label="Main Pool Opening Balance",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="main_pool_wda", label="Main Pool WDA (18%)",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                # Special Rate Pool
                TemplateField(
                    key="special_rate_pool_expenditure", label="Special Rate Pool Additions",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="special_rate_pool_opening_balance", label="Special Rate Pool Opening Balance",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="special_rate_pool_wda", label="Special Rate Pool WDA (6%)",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                # SBA
                TemplateField(
                    key="sba_expenditure", label="New Structures and Buildings",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="sba_opening_balance", label="SBA Opening Balance",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="sba_allowance", label="SBA (3%)",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                # Disposals
                TemplateField(
                    key="disposals_proceeds", label="Disposal Proceeds (Box 230)",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="disposals_pool", label="Disposal Pool (main/special)",
                    field_type=FieldType.SELECT, required=False,
                    validation=FieldValidation(options=["main", "special"]),
                ),
                TemplateField(
                    key="balancing_charges", label="Balancing Charges (Box 225)",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="total_capital_allowances", label="Total Capital Allowances (Box 220)",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
            ],
        ),

        # ── CT600D: Charges and Reliefs ──
        TemplateSection(
            title="Charges and Reliefs (CT600D)",
            description="Losses, group relief, R&D, and other reliefs",
            fields=[
                # Loss Relief
                TemplateField(
                    key="current_year_trading_loss", label="Current Year Trading Loss",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="losses_brought_forward", label="Losses Brought Forward (Box 290)",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="loss_relief_claimed", label="Loss Relief Claimed (Box 295)",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                TemplateField(
                    key="loss_carry_back_claimed", label="Loss Carry Back Claimed (Box 300)",
                    field_type=FieldType.NUMBER, required=False,
                ),
                # Group Relief
                TemplateField(
                    key="group_relief_claimed", label="Group Relief Claimed (Box 305)",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="consortium_relief_claimed", label="Consortium Relief (Box 310)",
                    field_type=FieldType.NUMBER, required=False,
                ),
                # R&D
                TemplateField(
                    key="rd_qualifying_expenditure", label="R&D Qualifying Expenditure (Box 315)",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="rd_relief", label="R&D Tax Relief (Box 320)",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                # Other
                TemplateField(
                    key="patents_relief", label="Patent Box Relief (Box 325)",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="creative_industries_relief", label="Creative Industries Relief",
                    field_type=FieldType.NUMBER, required=False,
                ),
            ],
        ),

        # ── CT600E: Tax Computation ──
        TemplateSection(
            title="Tax Computation (CT600E)",
            description="Tax payable calculation",
            is_optional=True,
            fields=[
                TemplateField(
                    key="total_profits", label="Total Profits (Box 350)",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                TemplateField(
                    key="profits_chargeable_to_ct", label="Profits Chargeable to CT (Box 360)",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                TemplateField(
                    key="tax_at_lower_rate", label="Tax at Lower Rate 19% (Box 370)",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                TemplateField(
                    key="tax_at_main_rate", label="Tax at Main Rate 25% (Box 375)",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                TemplateField(
                    key="marginal_relief", label="Marginal Relief Adjustment (Box 380)",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                TemplateField(
                    key="ct_chargeable", label="Corporation Tax Chargeable (Box 385)",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                TemplateField(
                    key="tax_already_paid", label="Tax Already Paid (Box 390)",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="amount_payable", label="Amount Payable / Repayable (Box 395)",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
            ],
        ),

        # ── CT600 Supplementary: WHT Disclosures ──
        # 当 UK 公司向境外关联方支付利息/特许权/股息,
        # 在 CT600 supplementary 披露已扣的预提税。
        # 平台会自动按 DTA 计算并嵌入到 GovTalk XML。
        TemplateSection(
            title="WHT Supplementary Disclosures",
            description=(
                "Cross-border WHT: interest, royalties, dividends paid to "
                "non-UK recipients. Auto-calculated via DTA rates; auto-embedded "
                "in CT600 GovTalk XML as supplementary pages."
            ),
            is_optional=True,
            fields=[
                TemplateField(
                    key="interest_amount", label="Interest Paid to Non-UK Recipients",
                    field_type=FieldType.NUMBER, required=False,
                    hint="Gross interest paid. WHT computed via DTA treaty rate.",
                ),
                TemplateField(
                    key="royalty_amount", label="Royalties Paid to Non-UK Recipients",
                    field_type=FieldType.NUMBER, required=False,
                    hint="Gross royalties paid. WHT computed via DTA treaty rate.",
                ),
                TemplateField(
                    key="dividend_amount", label="Dividends Paid to Non-UK Shareholders",
                    field_type=FieldType.NUMBER, required=False,
                    hint="Gross dividends. UK generally does not levy dividend WHT (0% for ≥25% holding under DTA).",
                ),
                TemplateField(
                    key="recipient_country", label="Recipient Country (ISO-2)",
                    field_type=FieldType.TEXT, required=False,
                    example="CN",
                    hint="ISO-3166-1 alpha-2 code (e.g. CN, HK, US, DE, FR).",
                ),
                TemplateField(
                    key="recipient_name", label="Recipient Name",
                    field_type=FieldType.TEXT, required=False,
                    hint="For 100% group companies: name of overseas parent/sister.",
                ),
                TemplateField(
                    key="ownership_pct", label="Ownership Percentage (dividends only)",
                    field_type=FieldType.NUMBER, required=False,
                    example="100",
                    hint="Used for tiered dividend WHT rates under DTA.",
                ),
            ],
        ),
    ],
)
