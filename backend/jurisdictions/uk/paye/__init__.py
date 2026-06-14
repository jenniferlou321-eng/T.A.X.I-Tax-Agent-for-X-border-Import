"""UK PAYE Adapter"""

from backend.models.tax_data import TaxType, TaxData
from backend.models.template import DataTemplate
from backend.models.results import CalculationResult, ValidationReport, FilingPayload
from backend.channels.api_channel import APIChannel
from backend.channels import FilingChannel

from .template import PAYE_TEMPLATE
from .calculator import calculate_paye
from .agent_tools import UKPAYEAgentToolSet


def validate_paye(data: TaxData) -> ValidationReport:
    """PAYE 简化校验"""
    from backend.models.results import ValidationError
    errors = []
    if not data.taxpayer.tax_id:
        errors.append(ValidationError(field="empref", message="Employer PAYE reference required"))
    return ValidationReport(is_valid=len(errors) == 0, errors=errors, warnings=[])


class UKPAYEAdapter:
    """UK PAYE (RTI)"""

    tax_type = TaxType.PAYE

    def __init__(self):
        from backend.jurisdictions.uk.config import hmrc_config
        self._channel = APIChannel(
            base_url=hmrc_config.base_url,
            oauth_config=hmrc_config.paye_oauth,
            submit_endpoint=hmrc_config.PAYE_FPS_ENDPOINT,
            status_endpoint=None,
            accept_header="application/vnd.hmrc.2.0+json",
        )
        self._tools = UKPAYEAgentToolSet()

    def get_template(self, tax_type: TaxType) -> DataTemplate:
        return PAYE_TEMPLATE

    def calculate(self, tax_type: TaxType, data: TaxData) -> CalculationResult:
        return calculate_paye(data)

    def validate(self, tax_type: TaxType, data: TaxData) -> ValidationReport:
        return validate_paye(data)

    def get_channel(self, tax_type: TaxType) -> FilingChannel:
        return self._channel

    def get_agent_tools(self, tax_type: TaxType):
        return self._tools

    def to_filing_format(self, tax_type: TaxType, data: TaxData) -> FilingPayload:
        line_map = {li.category: float(li.amount) for li in data.line_items}
        submission_type = (data.metadata.get("submission_type") or "fps").lower()

        if submission_type == "eps":
            # EPS (Employer Payment Summary) — 包含学徒税、雇佣津贴、CIS 等调整项
            period_levy_allowance = float(line_map.get("levy_allowance", 1250))
            body = {
                "empref": data.taxpayer.tax_id,
                "periodStart": data.period.start_date.isoformat() if data.period.start_date else None,
                "periodEnd": data.period.end_date.isoformat() if data.period.end_date else None,
                "apprenticeshipLevy": {
                    "totalPayBill": line_map.get("total_pay_bill", 0),
                    "levyAllowance": period_levy_allowance,
                    "levyDueYTD": line_map.get("apprenticeship_levy_payable", 0),
                },
                "employmentAllowance": {
                    "amountClaimed": line_map.get("employment_allowance_claimed", 0),
                },
                "statutoryPayments": {
                    "statutoryMaternityPay": line_map.get("statutory_maternity_pay", 0),
                    "statutorySickPay": line_map.get("statutory_sick_pay", 0),
                },
            }
        else:
            # FPS (Full Payment Submission) — 每个工资周期的标准申报
            body = {
                "empref": data.taxpayer.tax_id,
                "paymentDate": data.period.end_date.isoformat(),
                "employees": line_map.get("number_of_employees", 0),
                "totals": {
                    "grossPay": line_map.get("total_paye_income", 0),
                    "taxDeducted": line_map.get("total_tax_deducted", 0),
                    "employeeNics": line_map.get("total_employees_nics", 0),
                    "employerNics": line_map.get("total_employer_nics", 0),
                },
            }
        return FilingPayload(
            tax_type=TaxType.PAYE,
            period=data.period,
            taxpayer=data.taxpayer,
            body=body,
        )
