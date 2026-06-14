"""CN VAT 申报表模板 — 中国增值税(销项 / 进项)

最小可用模板:覆盖 demo 用到的销项税额、进项税额。calculator
(`calculate_cn_vat`)也支持按各档税率销售额展开,但 demo 直接给税额合计。
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


CN_VAT_TEMPLATE = DataTemplate(
    tax_type=TaxType.CN_VAT,
    jurisdiction="cn",
    version="1.0.0",
    valid_from=date(2024, 1, 1),
    sections=[
        TemplateSection(
            title="销项税额",
            description="本期销项税额(可直接填合计,或按各档税率销售额展开)",
            fields=[
                TemplateField(
                    key="output_tax",
                    label="销项税额合计",
                    field_type=FieldType.NUMBER,
                    required=True,
                    hint="本期全部销项税额合计(元)",
                ),
            ],
        ),
        TemplateSection(
            title="进项税额",
            description="本期可抵扣进项税额",
            fields=[
                TemplateField(
                    key="input_tax",
                    label="进项税额合计",
                    field_type=FieldType.NUMBER,
                    required=True,
                    hint="本期可抵扣进项税额合计(元)",
                ),
            ],
        ),
    ],
)
