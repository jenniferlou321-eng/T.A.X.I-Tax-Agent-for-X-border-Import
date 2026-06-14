"""CN CIT 申报表模板 — 中国企业所得税(汇算清缴口径)

字段对应 `calculate_cn_cit` 的 line_items category。
"""

from __future__ import annotations

from datetime import date

from backend.models.tax_data import TaxType
from backend.models.template import (
    DataTemplate,
    TemplateSection,
    TemplateField,
    FieldType,
)


CN_CIT_TEMPLATE = DataTemplate(
    tax_type=TaxType.CN_CIT,
    jurisdiction="cn",
    version="1.0.0",
    valid_from=date(2024, 1, 1),
    sections=[
        TemplateSection(
            title="应纳税所得额",
            description="会计利润 + 纳税调增 − 纳税调减",
            fields=[
                TemplateField(
                    key="accounting_profit", label="会计利润",
                    field_type=FieldType.NUMBER, required=True,
                    hint="利润总额(元)",
                ),
                TemplateField(
                    key="tax_adjustment_up", label="纳税调增",
                    field_type=FieldType.NUMBER, required=False,
                    hint="超标准业务招待费、罚款等调增项(元)",
                ),
                TemplateField(
                    key="tax_adjustment_down", label="纳税调减",
                    field_type=FieldType.NUMBER, required=False,
                    hint="权责发生制差异等调减项(元)",
                ),
            ],
        ),
        TemplateSection(
            title="境外税收抵免",
            description="境外已缴税款抵免(不超过抵免限额)",
            is_optional=True,
            fields=[
                TemplateField(
                    key="foreign_tax_credit", label="境外已缴税额",
                    field_type=FieldType.NUMBER, required=False,
                    hint="境外缴纳的所得税(元)",
                ),
                TemplateField(
                    key="overseas_income", label="境外应税所得",
                    field_type=FieldType.NUMBER, required=False,
                    hint="用于计算抵免限额 = 境外所得 × 中国税率(元)",
                ),
            ],
        ),
    ],
)
