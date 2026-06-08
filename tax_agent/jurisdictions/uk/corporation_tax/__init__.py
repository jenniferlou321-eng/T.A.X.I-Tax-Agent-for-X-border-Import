"""UK Corporation Tax Adapter (增强版)"""

from tax_agent.models.tax_data import TaxType, TaxData
from tax_agent.models.template import DataTemplate
from tax_agent.models.results import CalculationResult, ValidationReport, FilingPayload
from tax_agent.channels.api_channel import APIChannel
from tax_agent.channels import FilingChannel

from .template import CT600_FULL_TEMPLATE
from .calculator import calculate_corporation_tax
from .validator import validate_corporation_tax
from .agent_tools import UKCTAgentToolSet
from .financials import (
    convert_financials_to_ct600,
    import_profit_and_loss,
    import_balance_sheet,
    import_trial_balance,
    CT600Mapping,
)


class UKCTAdapter:
    """UK Corporation Tax (MTD for CT) - 增强版

    支持：
    - 完整 CT600 模板（6 个 sections, 30+ 字段）
    - 详细资本减免（AIA, FYA, Main Pool, Special Rate Pool, SBA）
    - 关联企业规则（边际税率阈值分摊）
    - Group Relief（集团减免转移）
    - Loss Relief（carry back 1 year + carry forward）
    - R&D Relief（SME 86% / RDEC 20%）
    - 财务数据导入器（P&L → CT600）
    - AI 优化建议
    """

    tax_type = TaxType.CORPORATION_TAX

    def __init__(self):
        from tax_agent.jurisdictions.uk.config import hmrc_config
        self._channel = APIChannel(
            base_url=hmrc_config.base_url,
            oauth_config=hmrc_config.ct_oauth,
            submit_endpoint=hmrc_config.CT_SUBMIT_ENDPOINT,
            status_endpoint=None,
            accept_header="application/vnd.hmrc.2.0+json",
        )
        self._tools = UKCTAgentToolSet()

    def get_template(self, tax_type: TaxType) -> DataTemplate:
        return CT600_FULL_TEMPLATE

    def calculate(self, tax_type: TaxType, data: TaxData) -> CalculationResult:
        return calculate_corporation_tax(data)

    def validate(self, tax_type: TaxType, data: TaxData) -> ValidationReport:
        return validate_corporation_tax(data)

    def get_channel(self, tax_type: TaxType) -> FilingChannel:
        return self._channel

    def get_agent_tools(self, tax_type: TaxType):
        return self._tools

    def to_filing_format(self, tax_type: TaxType, data: TaxData) -> FilingPayload:
        """转换为 HMRC CT JSON 格式 (扩展版，含资本减免、损失、R&D 详细字段)"""
        line_map = {li.category: float(li.amount) for li in data.line_items}
        num_assoc = int(data.metadata.get("num_associated_companies", 1))

        body = {
            "ctref": data.taxpayer.tax_id,
            "companyName": data.taxpayer.name,
            "periodStart": data.period.start_date.isoformat(),
            "periodEnd": data.period.end_date.isoformat(),
            "numAssociatedCompanies": num_assoc,

            # Section A: Trading
            "trading": {
                "turnover": line_map.get("trading_income", 0),
                "expenses": line_map.get("trading_expenses", 0),
                "netProfit": line_map.get("trading_profit", 0),
            },

            # Section B: Non-trading income
            "nonTradingIncome": {
                "investment": line_map.get("investment_income", 0),
                "property": line_map.get("property_income", 0),
                "chargeableGains": line_map.get("chargeable_gains", 0),
                "dividends": line_map.get("dividend_income", 0),
            },

            # Section C: Capital allowances (detailed)
            "capitalAllowances": {
                "aia": line_map.get("aia_allowance", 0),
                "fya": line_map.get("fya_allowance", 0),
                "mainPoolWda": line_map.get("main_pool_wda", 0),
                "specialRatePoolWda": line_map.get("special_rate_pool_wda", 0),
                "sba": line_map.get("sba_allowance", 0),
                "balancingCharges": line_map.get("balancing_charges", 0),
                "totalAllowance": line_map.get("total_capital_allowances", 0),
            },

            # Section D: Reliefs
            "reliefs": {
                "lossesBroughtForward": line_map.get("losses_brought_forward", 0),
                "lossReliefClaimed": line_map.get("loss_relief_claimed", 0),
                "lossCarryBackClaimed": line_map.get("loss_carry_back_claimed", 0),
                "groupReliefClaimed": line_map.get("group_relief_claimed", 0),
                "consortiumReliefClaimed": line_map.get("consortium_relief_claimed", 0),
                "rdRelief": line_map.get("rd_relief", 0),
                "patentsRelief": line_map.get("patents_relief", 0),
            },

            # Section E: Tax computation
            "calculations": {
                "totalProfits": line_map.get("total_profits", 0),
                "profitsChargeable": line_map.get("profits_chargeable_to_ct", 0),
                "taxAtLowerRate": line_map.get("tax_at_lower_rate", 0),
                "taxAtMainRate": line_map.get("tax_at_main_rate", 0),
                "marginalRelief": line_map.get("marginal_relief", 0),
                "ctChargeable": line_map.get("ct_chargeable", 0),
                "taxAlreadyPaid": line_map.get("tax_already_paid", 0),
                "amountPayable": line_map.get("amount_payable", 0),
            },
        }
        return FilingPayload(
            tax_type=TaxType.CORPORATION_TAX,
            period=data.period,
            taxpayer=data.taxpayer,
            body=body,
        )

    def import_financials(
        self,
        profit_and_loss: dict,
        balance_sheet: dict = None,
        opening_main_pool=None,
        rd_qualifying_expenditure=None,
        num_associated_companies: int = 1,
    ) -> CT600Mapping:
        """从财务报表自动生成 CT600 数据

        便捷方法：调用 financials 模块的转换器
        """
        from decimal import Decimal
        return convert_financials_to_ct600(
            profit_and_loss=profit_and_loss,
            balance_sheet=balance_sheet,
            opening_main_pool=opening_main_pool or Decimal("0"),
            rd_qualifying_expenditure=rd_qualifying_expenditure or Decimal("0"),
            num_associated_companies=num_associated_companies,
        )
