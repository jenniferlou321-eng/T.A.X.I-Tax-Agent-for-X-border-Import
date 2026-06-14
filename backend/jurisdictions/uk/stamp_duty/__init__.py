"""UK SDLT Adapter — SDLT 通过 GovTalk XML 提交"""

from backend.models.tax_data import TaxType, TaxData
from backend.models.template import DataTemplate
from backend.models.results import CalculationResult, ValidationReport, FilingPayload
from backend.channels.api_channel import APIChannel
from backend.channels import FilingChannel

from .template import SDLT_TEMPLATE
from .calculator import calculate_sdlt
from .agent_tools import UKSDLTAgentToolSet
from .hmrc_service import HMRCSDLTService


def validate_sdlt(data: TaxData) -> ValidationReport:
    from backend.models.results import ValidationError
    errors = []
    if data.taxpayer.tax_id and not data.taxpayer.tax_id.isdigit():
        errors.append(ValidationError(field="utr", message="UTR must be digits"))
    return ValidationReport(is_valid=len(errors) == 0, errors=errors, warnings=[])


class UKSDLTAdapter:
    """UK SDLT (Stamp Duty Land Tax) — GovTalk XML 提交"""

    tax_type = TaxType.STAMP_DUTY

    def __init__(self):
        from backend.jurisdictions.uk.config import hmrc_config
        # 保留 APIChannel 用于向后兼容,但实际提交走 GovTalk
        self._channel = APIChannel(
            base_url=hmrc_config.base_url,
            oauth_config=hmrc_config.sdlt_oauth,
            submit_endpoint=hmrc_config.SDLT_SUBMIT_ENDPOINT,
            status_endpoint=None,
            accept_header="application/vnd.hmrc.2.0+json",
        )
        self._tools = UKSDLTAgentToolSet()
        self._hmrc_service = HMRCSDLTService()

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
        # SDLT body 兼容 GovTalk XML 格式
        body = {
            "utr": data.taxpayer.tax_id,
            "effective_date": data.period.end_date.isoformat(),
            "property_value": line_map.get("property_value", 0),
            "property_type": data.metadata.get("property_type", "residential"),
            "buyer_type": data.metadata.get("buyer_type", "individual"),
            "is_additional_dwelling": data.metadata.get("is_additional_dwelling", False),
            "sdlt_payable": line_map.get("sdlt_payable", 0),
            "effective_rate": line_map.get("effective_rate", 0),
            "property_address_postcode": data.metadata.get("property_address_postcode", ""),
        }
        return FilingPayload(
            tax_type=TaxType.STAMP_DUTY,
            period=data.period,
            taxpayer=data.taxpayer,
            body=body,
        )
