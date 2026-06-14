"""CN CIT BrowserChannel — 中国企业所得税电子税务局申报

支持两种申报方式:
- 季度预缴: 季度后 15 日内
- 年度汇算清缴: 次年 1月1日 - 5月31日

流程类似 VAT,但表单字段更多:
- 利润总额
- 纳税调整 (调增/调减)
- 减免所得
- 抵免所得税额 (境外税收抵免)
- 实际应纳税额
"""

from __future__ import annotations

import logging
from datetime import datetime

from backend.channels.browser_channel import BrowserChannel
from backend.models.results import FilingPayload, FilingStatus

logger = logging.getLogger(__name__)


class CNCITBrowserChannel(BrowserChannel):
    """中国企业所得税电子税务局申报渠道。"""

    def __init__(self, province: str = "beijing", declaration_type: str = "annual", headless: bool = True):
        super().__init__(
            jurisdiction="cn",
            tax_type="cn_cit",
            headless=headless,
        )
        self.province = province
        self.declaration_type = declaration_type  # "quarterly" / "annual"
        self._base_url = f"https://etax.{province}.chinatax.gov.cn"

    def login_url(self) -> str:
        return f"{self._base_url}/login"

    def form_url(self) -> str:
        if self.declaration_type == "annual":
            return f"{self._base_url}/bszm/yyzzx/sb/qydsds_hscz"
        return f"{self._base_url}/bszm/yyzzx/sb/qydsds_jdys"

    async def fill_form(self, page, payload: FilingPayload) -> None:
        """填写企业所得税申报表。

        payload.body 字段:
        - accounting_profit: 会计利润
        - tax_adjustment_up: 纳税调增
        - tax_adjustment_down: 纳税调减
        - overseas_income: 境外所得
        - foreign_tax_credit: 境外已缴税款
        - dta_recognized: 递延所得税资产确认
        """
        body = payload.body

        # 1. 选择所属期
        period_key = payload.period.period_key
        await page.fill('input[name="skssq"]', period_key)
        await page.click('button:has-text("下一步")')

        # 2. 利润总额
        if "accounting_profit" in body:
            await page.fill('input[name="lrze"]', str(body["accounting_profit"]))

        # 3. 纳税调整
        if "tax_adjustment_up" in body:
            await page.fill('input[name="nstz_z"]', str(body["tax_adjustment_up"]))
        if "tax_adjustment_down" in body:
            await page.fill('input[name="nstz_j"]', str(body["tax_adjustment_down"]))

        # 4. 境外所得与抵免
        if "overseas_income" in body:
            await page.fill('input[name="jwsdsd"]', str(body["overseas_income"]))
        if "foreign_tax_credit" in body:
            await page.fill('input[name="jwjsk"]', str(body["foreign_tax_credit"]))

        # 5. 等待自动计算
        await page.wait_for_selector('input[name="sjyjse"]', timeout=self.timeout_ms)

    async def submit_form(self, page, payload: FilingPayload) -> str:
        """提交并获取回执。"""
        await page.click('button:has-text("申报")')
        try:
            await page.click('button:has-text("确定")', timeout=5000)
        except Exception:
            pass
        await page.wait_for_selector(
            'div:has-text("申报成功")',
            timeout=self.timeout_ms,
        )
        receipt_el = await page.query_selector('span.sbhz_no, .receipt-no')
        if receipt_el:
            return (await receipt_el.inner_text()).strip()
        return f"CN-CIT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    async def parse_status(self, page, receipt_id: str) -> tuple[FilingStatus, str]:
        """查询 CIT 申报状态。"""
        await page.goto(
            f"{self._base_url}/bszm/yyzzx/sb/sbjgcx",
            timeout=self.timeout_ms,
        )
        try:
            await page.fill('input[name="sbbh"]', receipt_id, timeout=5000)
            await page.click('button:has-text("查询")')
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception as e:
            return FilingStatus.SUBMITTED, f"状态查询失败: {e}"

        body_text = await page.inner_text("body")
        if "申报成功" in body_text:
            return FilingStatus.ACCEPTED, "CIT 申报已受理"
        if "申报失败" in body_text:
            return FilingStatus.REJECTED, "CIT 申报被退回"
        return FilingStatus.SUBMITTED, "已提交"
