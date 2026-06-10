"""UK SDLT Adapter"""

from backend.models.tax_data import TaxType, TaxData
from backend.models.template import DataTemplate
from backend.models.results import CalculationResult, ValidationReport, FilingPayload
from backend.channels.api_channel import APIChannel
from backend.channels import FilingChannel

from .template import SDLT_TEMPLATE
from .calculator import calculate_sdlt
from .agent_tools import UKSDLTAgentToolSet


def validate_sdlt(data: TaxData) -> ValidationReport:
    from backend.models.results import ValidationError
    errors = []
    if data.taxpayer.tax_id and not data.taxpayer.tax_id.isdigit():
        errors.append(ValidationError(field="utr", message="UTR must be digits"))
    return ValidationReport(is_valid=len(errors) == 0, errors=errors, warnings=[])


class UKSDLTAdapter:
    """UK SDLT (Stamp Duty Land Tax)"""

    tax_type = TaxType.STAMP_DUTY

    def __init__(self):
        from backend.jurisdictions.uk.config import hmrc_config
        self._channel = APIChannel(
            base_url=hmrc_config.base_url,
            oauth_config=hmrc_config.sdlt_oauth,
            submit_endpoint=hmrc_config.SDLT_SUBMIT_ENDPOINT,
            status_endpoint=None,
            accept_header="application/vnd.hmrc.2.0+json",
        )
        self._tools = UKSDLTAgentToolSet()

    def get_template(self, tax_type: TaxType) -> DataTemplate:
        return SDLT_TEMPLATE

    def calculate(self, tax_type: TaxType, data: TaxData) -> CalculationResult:
        return calculate_sdlt(data)

    def validate(self, tax_type: TaxType, data: TaxData) -> ValidationReport:
        return validate_sdlt(data)

    def get_channel(self, tax_type: TaxType) -> FilingChannel:
        return self._channel

    def get_agent_tools(self, tax_type: TaxType):
        return self._tools

    def to_filing_format(self, tax_type: TaxType, data: TaxData) -> FilingPayload:
        line_map = {li.category: float(li.amount) for li in data.line_items}
        body = {
            "transaction": {
                "value": line_map.get("property_value", 0),
                "type": data.metadata.get("property_type", "residential"),
                "buyerType": data.metadata.get("buyer_type", "individual"),
                "effectiveDate": data.period.end_date.isoformat(),
            },
            "calculation": {
                "sdltPayable": line_map.get("sdlt_payable", 0),
                "effectiveRate": line_map.get("effective_rate", 0),
            },
        }
        return FilingPayload(
            tax_type=TaxType.STAMP_DUTY,
            period=data.period,
            taxpayer=data.taxpayer,
            body=body,
        )
