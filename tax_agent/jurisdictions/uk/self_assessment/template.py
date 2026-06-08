"""UK Self Assessment (ITSA) 数据模板

参考 HMRC SA100 主表 + 各子表（SA102 就业、SA103 自雇、SA108 资本利得等）。
本模板定义了 Self Assessment 申报的核心字段。
"""

from datetime import date

from tax_agent.models.template import (
    DataTemplate, TemplateSection, TemplateField,
    FieldType, FieldValidation,
)
from tax_agent.models.tax_data import TaxType


SA_TEMPLATE = DataTemplate(
    tax_type=TaxType.SELF_ASSESSMENT,
    jurisdiction="uk",
    version="1.0.0",
    valid_from=date(2024, 4, 6),
    valid_until=date(2025, 4, 5),
    sections=[
        # ── SA100: 主表 ──
        TemplateSection(
            title="Personal Details (SA100)",
            description="Personal information",
            fields=[
                TemplateField(
                    key="nino", label="National Insurance Number",
                    field_type=FieldType.TEXT, required=True,
                    example="AB123456C",
                ),
                TemplateField(
                    key="tax_year", label="Tax Year",
                    field_type=FieldType.TEXT, required=True,
                    example="2023-24",
                ),
                TemplateField(
                    key="date_of_birth", label="Date of Birth",
                    field_type=FieldType.DATE, required=True,
                ),
                TemplateField(
                    key="is_blind", label="Registered Blind",
                    field_type=FieldType.SELECT, required=False,
                    validation=FieldValidation(options=["yes", "no"]),
                ),
            ],
        ),

        # ── SA102: 就业收入 ──
        TemplateSection(
            title="Employment Income (SA102)",
            description="Income from employment (PAYE)",
            fields=[
                TemplateField(
                    key="employment_income", label="Total Employment Income",
                    field_type=FieldType.NUMBER, required=False,
                    hint="Total income from P60/P45",
                ),
                TemplateField(
                    key="tax_withheld", label="Tax Withheld (PAYE)",
                    field_type=FieldType.NUMBER, required=False,
                    hint="Total tax deducted by employer",
                ),
                TemplateField(
                    key="benefits_in_kind", label="Benefits in Kind",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="employment_expenses", label="Employment Expenses",
                    field_type=FieldType.NUMBER, required=False,
                ),
            ],
        ),

        # ── SA103: 自雇收入 ──
        TemplateSection(
            title="Self-Employment Income (SA103)",
            description="Income from self-employment",
            fields=[
                TemplateField(
                    key="self_employment_turnover", label="Turnover",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="self_employment_expenses", label="Allowable Expenses",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="self_employment_net_profit", label="Net Profit",
                    field_type=FieldType.NUMBER, required=False,
                    hint="Auto-calculated if turnover and expenses provided",
                    auto_calculated=True,
                ),
                TemplateField(
                    key="loss_brought_forward", label="Loss Brought Forward",
                    field_type=FieldType.NUMBER, required=False,
                ),
            ],
        ),

        # ── SA105: 财产/租金收入 ──
        TemplateSection(
            title="Property Income (SA105)",
            description="Income from UK property letting",
            fields=[
                TemplateField(
                    key="property_income", label="Total Property Income",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="property_expenses", label="Property Expenses",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="property_net_income", label="Net Property Income",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
            ],
        ),

        # ── SA106: 海外收入 ──
        TemplateSection(
            title="Foreign Income (SA106)",
            description="Income from overseas",
            fields=[
                TemplateField(
                    key="foreign_income", label="Total Foreign Income",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="foreign_tax_paid", label="Foreign Tax Paid (for relief)",
                    field_type=FieldType.NUMBER, required=False,
                ),
            ],
        ),

        # ── SA108: 资本利得（已合并到此模板） ──
        TemplateSection(
            title="Capital Gains (SA108)",
            description="Chargeable gains on disposal of assets",
            fields=[
                TemplateField(
                    key="total_gains", label="Total Disposal Gains",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="total_losses", label="Total Disposal Losses",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="annual_exempt_amount", label="Annual Exempt Amount",
                    field_type=FieldType.NUMBER, required=False,
                    example="6000",
                    hint="2024/25: £3,000",
                ),
                TemplateField(
                    key="chargeable_gain", label="Net Chargeable Gain",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
            ],
        ),

        # ── 扣除与减免 ──
        TemplateSection(
            title="Deductions and Reliefs",
            description="Allowable deductions and tax reliefs",
            fields=[
                TemplateField(
                    key="personal_allowance", label="Personal Allowance",
                    field_type=FieldType.NUMBER, required=False,
                    example="12570",
                    hint="2024/25: £12,570",
                ),
                TemplateField(
                    key="blind_persons_allowance", label="Blind Person's Allowance",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="marriage_allowance", label="Marriage Allowance Transfer",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="pension_contributions", label="Pension Contributions",
                    field_type=FieldType.NUMBER, required=False,
                    hint="Gross payments to registered pensions",
                ),
                TemplateField(
                    key="gift_aid", label="Gift Aid Donations",
                    field_type=FieldType.NUMBER, required=False,
                ),
            ],
        ),

        # ── 计算结果 ──
        TemplateSection(
            title="Tax Calculation",
            description="Auto-calculated tax liability",
            is_optional=True,
            fields=[
                TemplateField(
                    key="total_income", label="Total Income",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                TemplateField(
                    key="taxable_income", label="Taxable Income",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                TemplateField(
                    key="income_tax_due", label="Income Tax Due",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                TemplateField(
                    key="capital_gains_tax_due", label="Capital Gains Tax Due",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                TemplateField(
                    key="total_tax_due", label="Total Tax Due",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                TemplateField(
                    key="tax_already_paid", label="Tax Already Paid (PAYE + Foreign)",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="balancing_payment", label="Balancing Payment / Repayment",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
            ],
        ),
    ],
)
