"""UK Stamp Duty Land Tax (SDLT) 数据模板

SDLT 适用于英格兰和北爱尔兰的房产交易。
苏格兰有 Land and Buildings Transaction Tax (LBTT)，威尔士有 Land Transaction Tax (LTT)。
"""

from datetime import date

from tax_agent.models.template import (
    DataTemplate, TemplateSection, TemplateField,
    FieldType, FieldValidation,
)
from tax_agent.models.tax_data import TaxType


SDLT_TEMPLATE = DataTemplate(
    tax_type=TaxType.STAMP_DUTY,
    jurisdiction="uk",
    version="1.0.0",
    valid_from=date(2024, 4, 1),
    sections=[
        TemplateSection(
            title="Property Details",
            description="Property and transaction details",
            fields=[
                TemplateField(
                    key="transaction_id", label="Transaction Reference",
                    field_type=FieldType.TEXT, required=True,
                ),
                TemplateField(
                    key="property_value", label="Property Value (£)",
                    field_type=FieldType.NUMBER, required=True,
                ),
                TemplateField(
                    key="property_type", label="Property Type",
                    field_type=FieldType.SELECT, required=True,
                    validation=FieldValidation(options=["residential", "non_residential", "mixed"]),
                ),
                TemplateField(
                    key="buyer_type", label="Buyer Type",
                    field_type=FieldType.SELECT, required=True,
                    validation=FieldValidation(options=["individual", "company", "trust", "first_time_buyer"]),
                ),
                TemplateField(
                    key="effective_date", label="Effective Transaction Date",
                    field_type=FieldType.DATE, required=True,
                ),
            ],
        ),
        TemplateSection(
            title="Calculation",
            description="SDLT calculation breakdown",
            is_optional=True,
            fields=[
                TemplateField(
                    key="taxable_amount", label="Taxable Amount",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                TemplateField(
                    key="sdlt_payable", label="SDLT Payable",
                    field_type=FieldType.NUMBER, required=False,
                    auto_calculated=True,
                ),
                TemplateField(
                    key="effective_rate", label="Effective SDLT Rate",
                    field_type=FieldType.NUMBER, required=False,
                ),
            ],
        ),
    ],
)
