"""UK VAT 数据模板 — 9-box VAT Return"""

from datetime import date
from backend.models.tax_data import TaxType
from backend.models.template import (
    DataTemplate, TemplateSection, TemplateField,
    FieldType, FieldValidation,
)

UK_VAT_TEMPLATE = DataTemplate(
    tax_type=TaxType.VAT,
    jurisdiction="uk",
    version="1.0",
    valid_from=date(2019, 4, 1),       # MTD for VAT 实施日期
    sections=[
        # ── VAT Due (Box 1–3) ──
        TemplateSection(
            title="VAT due in this period on sales and other outputs",
            description="Box 1: VAT due on sales and other outputs",
            fields=[
                TemplateField(
                    key="vat_due_sales",
                    label="Box 1 — VAT due on sales",
                    field_type=FieldType.NUMBER,
                    required=False,
                    hint="VAT due in this period on sales and other outputs",
                    auto_calculated=True,
                    allow_manual_override=True,
                    validation=FieldValidation(min=0, decimal_places=2),
                ),
            ],
        ),
        TemplateSection(
            title="VAT due on acquisitions from EU member states",
            description="Box 2: VAT due on acquisitions from EU",
            fields=[
                TemplateField(
                    key="vat_due_acquisitions",
                    label="Box 2 — VAT due on EC acquisitions",
                    field_type=FieldType.NUMBER,
                    required=False,
                    validation=FieldValidation(min=0, decimal_places=2),
                ),
            ],
        ),
        TemplateSection(
            title="Total VAT due",
            description="Box 3: Total VAT due (Box 1 + Box 2)",
            fields=[
                TemplateField(
                    key="total_vat_due",
                    label="Box 3 — Total VAT due",
                    field_type=FieldType.NUMBER,
                    required=True,
                    hint="Auto-calculated: Box 1 + Box 2",
                    auto_calculated=True,
                    allow_manual_override=False,
                    validation=FieldValidation(min=0, decimal_places=2),
                ),
            ],
        ),

        # ── VAT Reclaimed (Box 4–5) ──
        TemplateSection(
            title="VAT reclaimed on purchases",
            description="Box 4: VAT reclaimed on purchases and other inputs",
            fields=[
                TemplateField(
                    key="vat_reclaimed_purchases",
                    label="Box 4 — VAT reclaimed on purchases",
                    field_type=FieldType.NUMBER,
                    required=True,
                    hint="VAT reclaimed in this period on purchases and other inputs",
                    validation=FieldValidation(min=0, decimal_places=2),
                ),
            ],
        ),
        TemplateSection(
            title="Net VAT due",
            description="Box 5: Net VAT to pay or reclaim (Box 3 − Box 4)",
            fields=[
                TemplateField(
                    key="net_vat_due",
                    label="Box 5 — Net VAT due",
                    field_type=FieldType.NUMBER,
                    required=True,
                    hint="Auto-calculated: Box 3 − Box 4",
                    auto_calculated=True,
                    allow_manual_override=False,
                    validation=FieldValidation(decimal_places=2),
                ),
            ],
        ),

        # ── Supplementary Info (Box 6–9) ──
        TemplateSection(
            title="Total value of sales and other supplies",
            description="Box 6: Total value of sales excluding VAT",
            fields=[
                TemplateField(
                    key="total_sales_ex_vat",
                    label="Box 6 — Total sales (ex VAT)",
                    field_type=FieldType.NUMBER,
                    required=True,
                    validation=FieldValidation(min=0, decimal_places=2),
                ),
            ],
        ),
        TemplateSection(
            title="Total value of purchases and other inputs",
            description="Box 7: Total value of purchases excluding VAT",
            fields=[
                TemplateField(
                    key="total_purchases_ex_vat",
                    label="Box 7 — Total purchases (ex VAT)",
                    field_type=FieldType.NUMBER,
                    required=True,
                    validation=FieldValidation(min=0, decimal_places=2),
                ),
            ],
        ),
        TemplateSection(
            title="Total value of supplies of goods to EU",
            description="Box 8: Total value of goods supplied to EU (ex VAT)",
            fields=[
                TemplateField(
                    key="total_goods_supplied_eu",
                    label="Box 8 — Supplies to EU",
                    field_type=FieldType.NUMBER,
                    required=False,
                    validation=FieldValidation(min=0, decimal_places=2),
                ),
            ],
        ),
        TemplateSection(
            title="Total value of acquisitions of goods from EU",
            description="Box 9: Total value of goods acquired from EU (ex VAT)",
            fields=[
                TemplateField(
                    key="total_goods_acquired_eu",
                    label="Box 9 — Acquisitions from EU",
                    field_type=FieldType.NUMBER,
                    required=False,
                    validation=FieldValidation(min=0, decimal_places=2),
                ),
            ],
        ),
    ],
)