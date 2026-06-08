"""UK VAT Adapter"""

from decimal import Decimal

from tax_agent.models.tax_data import TaxType, ChannelType, TaxData
from tax_agent.models.template import DataTemplate
from tax_agent.models.results import (
    CalculationResult, ValidationReport, FilingPayload,
)
from tax_agent.channels.api_channel import APIChannel
from tax_agent.channels import FilingChannel

from ..config import hmrc_config
from .template import UK_VAT_TEMPLATE
from .calculator import calculate_uk_vat
from .validator import validate_uk_vat


class UKVATAdapter:
    """UK VAT — Making Tax Digital for VAT"""

    tax_type = TaxType.VAT

    def __init__(self):
        self._channel = APIChannel(
            base_url=hmrc_config.base_url,
            oauth_config=hmrc_config.vat_oauth,
            submit_endpoint=hmrc_config.VAT_SUBMIT_ENDPOINT,
            status_endpoint=hmrc_config.VAT_STATUS_ENDPOINT,
            fraud_headers=True,
            accept_header="application/vnd.hmrc.1.0+json",
        )

    def get_template(self, tax_type: TaxType) -> DataTemplate:
        return UK_VAT_TEMPLATE

    def calculate(self, tax_type: TaxType, data: TaxData) -> CalculationResult:
        return calculate_uk_vat(data)

    def validate(self, tax_type: TaxType, data: TaxData) -> ValidationReport:
        return validate_uk_vat(data)

    def get_channel(self, tax_type: TaxType) -> FilingChannel:
        return self._channel

    def to_filing_format(self, tax_type: TaxType, data: TaxData) -> FilingPayload:
        """转换为 HMRC VAT Return JSON 格式

        HMRC 规范:
        - Box 1-5: 2 位小数 numeric
        - Box 6-9: 整磅 integer（无小数位）
        - netVatDue: 必须 ≥ 0
        - finalised: 必须为 true
        """
        line_map = {li.category: li.amount for li in data.line_items}

        # 自动计算 Box 3 和 Box 5
        calc = calculate_uk_vat(data)

        # Box 1-5: 保留 2 位小数
        box1 = float(line_map.get("vat_due_sales", Decimal("0")))
        box2 = float(line_map.get("vat_due_acquisitions", Decimal("0")))
        box3 = float(calc.breakdown[2].amount) if len(calc.breakdown) > 2 else 0.0
        box4 = float(line_map.get("vat_reclaimed_purchases", Decimal("0")))
        box5 = float(calc.breakdown[4].amount) if len(calc.breakdown) > 4 else 0.0

        # Box 6-9: 整磅数（HMRC 要求无小数位）
        box6 = int(line_map.get("total_sales_ex_vat", Decimal("0")))
        box7 = int(line_map.get("total_purchases_ex_vat", Decimal("0")))
        box8 = int(line_map.get("total_goods_supplied_eu", Decimal("0")))
        box9 = int(line_map.get("total_goods_acquired_eu", Decimal("0")))

        body = {
            "periodKey": data.period.period_key,
            "vatDueSales": round(box1, 2),
            "vatDueAcquisitions": round(box2, 2),
            "totalVatDue": round(box3, 2),
            "vatReclaimedCurrPeriod": round(box4, 2),
            "netVatDue": round(box5, 2),
            "totalValueSalesExVAT": box6,
            "totalValuePurchasesExVAT": box7,
            "totalValueGoodsSuppliedExVAT": box8,
            "totalAcquisitionsExVAT": box9,
            "finalised": True,
        }

        return FilingPayload(
            tax_type=TaxType.VAT,
            period=data.period,
            taxpayer=data.taxpayer,
            body=body,
        )