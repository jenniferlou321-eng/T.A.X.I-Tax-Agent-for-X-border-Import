"""UK Self Assessment Adapter — 适配器与子模块导出"""

from .template import SA_TEMPLATE
from .calculator import calculate_self_assessment
from .validator import validate_self_assessment
from .agent_tools import UKSAAgentToolSet
from backend.models.tax_data import TaxType, TaxData, ChannelType
from backend.models.template import DataTemplate
from backend.models.results import CalculationResult, ValidationReport, FilingPayload
from backend.channels.api_channel import APIChannel
from backend.jurisdictions import JurisdictionAdapter
from backend.channels import FilingChannel


class UKSAAdapter:
    """UK Self Assessment (MTD for ITSA)"""

    tax_type = TaxType.SELF_ASSESSMENT

    def __init__(self):
        from backend.jurisdictions.uk.config import hmrc_config
        self._channel = APIChannel(
            base_url=hmrc_config.base_url,
            oauth_config=hmrc_config.sa_oauth,
            submit_endpoint=hmrc_config.SA_SUBMIT_ENDPOINT,
            status_endpoint=None,  # SA 没有简单的 GET endpoint
            accept_header="application/vnd.hmrc.2.0+json",
        )
        self._tools = UKSAAgentToolSet()

    def get_template(self, tax_type: TaxType) -> DataTemplate:
        return SA_TEMPLATE

    def calculate(self, tax_type: TaxType, data: TaxData) -> CalculationResult:
        return calculate_self_assessment(data)

    def validate(self, tax_type: TaxType, data: TaxData) -> ValidationReport:
        return validate_self_assessment(data)

    def get_channel(self, tax_type: TaxType) -> FilingChannel:
        return self._channel

    def get_agent_tools(self, tax_type: TaxType):
        return self._tools

    def to_filing_format(self, tax_type: TaxType, data: TaxData) -> FilingPayload:
        """转换为 HMRC ITSA JSON 格式"""
        line_map = {li.category: float(li.amount) for li in data.line_items}
        body = {
            "taxYear": data.period.period_key,
            "nino": data.taxpayer.tax_id,
            "income": {
                "employment": line_map.get("employment_income", 0),
                "selfEmployment": line_map.get("self_employment_net_profit", 0),
                "property": line_map.get("property_net_income", 0),
                "foreign": line_map.get("foreign_income", 0),
                "savings": line_map.get("savings_income", 0),
                "dividends": line_map.get("dividend_income", 0),
            },
            "deductions": {
                "pensionContributions": line_map.get("pension_contributions", 0),
                "giftAid": line_map.get("gift_aid", 0),
            },
            "capitalGains": {
                "totalGains": line_map.get("total_gains", 0),
                "totalLosses": line_map.get("total_losses", 0),
            },
            "calculations": {
                "totalIncome": line_map.get("total_income", 0),
                "taxableIncome": line_map.get("taxable_income", 0),
                "incomeTaxDue": line_map.get("income_tax_due", 0),
                "capitalGainsTaxDue": line_map.get("capital_gains_tax_due", 0),
                "totalTaxDue": line_map.get("total_tax_due", 0),
                "taxAlreadyPaid": line_map.get("tax_already_paid", 0),
                "balancingPayment": line_map.get("balancing_payment", 0),
            },
        }
        return FilingPayload(
            tax_type=TaxType.SELF_ASSESSMENT,
            period=data.period,
            taxpayer=data.taxpayer,
            body=body,
        )
