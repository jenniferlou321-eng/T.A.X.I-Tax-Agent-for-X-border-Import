"""UK PAYE (RTI) 数据模板

PAYE (Pay As You Earn) 是雇主为员工代扣代缴所得税的制度。
RTI (Real Time Information) 模式：每次发工资时通过 FPS 实时提交。
"""

from datetime import date

from backend.models.template import (
    DataTemplate, TemplateSection, TemplateField,
    FieldType, FieldValidation,
)
from backend.models.tax_data import TaxType


PAYE_TEMPLATE = DataTemplate(
    tax_type=TaxType.PAYE,
    jurisdiction="uk",
    version="1.0.0",
    valid_from=date(2024, 4, 6),
    sections=[
        # ── 雇主信息 ──
        TemplateSection(
            title="Employer Details",
            description="Employer PAYE scheme details",
            fields=[
                TemplateField(
                    key="empref", label="Employer PAYE Reference",
                    field_type=FieldType.TEXT, required=True,
                    example="123/AB456",
                ),
                TemplateField(
                    key="accounts_office_ref", label="Accounts Office Reference",
                    field_type=FieldType.TEXT, required=True,
                    example="123PA00123456",
                ),
                TemplateField(
                    key="payment_date", label="Payment Date",
                    field_type=FieldType.DATE, required=True,
                ),
            ],
        ),

        # ── FPS: Full Payment Submission ──
        TemplateSection(
            title="Full Payment Submission (FPS)",
            description="Payroll information for the period",
            fields=[
                TemplateField(
                    key="number_of_employees", label="Number of Employees",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="total_paye_income", label="Total Gross Pay",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="total_tax_deducted", label="Total Tax Deducted",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="total_employees_nics", label="Total Employee NICs",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="total_employer_nics", label="Total Employer NICs",
                    field_type=FieldType.NUMBER, required=False,
                ),
            ],
        ),

        # ── EPS: Employer Payment Summary ──
        TemplateSection(
            title="Employer Payment Summary (EPS)",
            description="Year-end adjustments and statutory payments",
            is_optional=True,
            fields=[
                TemplateField(
                    key="statutory_maternity_pay", label="Statutory Maternity Pay",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="statutory_sick_pay", label="Statutory Sick Pay",
                    field_type=FieldType.NUMBER, required=False,
                ),
                TemplateField(
                    key="employment_allowance_claimed", label="Employment Allowance",
                    field_type=FieldType.NUMBER, required=False,
                    hint="Up to £5,000 per year for eligible employers",
                ),
            ],
        ),
    ],
)
