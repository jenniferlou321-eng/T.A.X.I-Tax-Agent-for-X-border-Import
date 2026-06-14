"""CN VAT BrowserChannel — 中国增值税电子税务局申报

电子税务局 URL:
- 总局: https://etax.chinatax.gov.cn
- 各省有子域名: etax.{省份}.chinatax.gov.cn

申报流程:
1. 登录 (账号/密码/短信验证)
2. 进入"我要办税" → "税费申报及缴纳" → "增值税申报"
3. 选择申报所属期 (YYYY-MM)
4. 填写销项/进项数据
5. 系统自动计算应纳税额
6. 提交申报
7. 获取回执 (PDF + 申报号)

注意: 实际部署需要:
- 各省电子税务局账号
- 实名认证 + CA 证书 或 短信验证
- 解决验证码 (OCR 或人工接管)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from backend.channels.browser_channel import BrowserChannel
from backend.models.results import FilingPayload, FilingStatus

logger = logging.getLogger(__name__)


class CNVATBrowserChannel(BrowserChannel):
    """中国增值税电子税务局申报渠道。

    警告: 此实现在生产环境使用前必须:
    1. 完成各省电子税务局账号接入
    2. 配置 CA 证书 或 短信验证服务
    3. 实现验证码 OCR / 人工接管机制
    4. 通过沙箱环境充分测试
    """

    def __init__(self, province: str = "beijing", headless: bool = True):
        super().__init__(
            jurisdiction="cn",
            tax_type="cn_vat",
            headless=headless,
        )
        self.province = province
        # 总局 URL, 各省用 etax.{省}.chinatax.gov.cn
        self._base_url = f"https://etax.{province}.chinatax.gov.cn"

    def login_url(self) -> str:
        return f"{self._base_url}/login"

    def form_url(self) -> str:
        # 增值税申报表页面
        return f"{self._base_url}/bszm/yyzzx/sb/zzs"

    async def fill_form(self, page, payload: FilingPayload) -> None:
        """填写增值税申报表。

        从 payload.body 提取:
        - output_13, output_9, output_6, output_5, output_3: 各税率销项
        - input_13, input_9, input_6: 各税率进项
        - period_key: YYYY-MM 格式
        """
        body = payload.body
        period_key = payload.period.period_key  # "2023-Q1" / "2023-01"

        # 1. 选择所属期
        # 实际 selector 取决于电子税务局版本,以下是典型模式
        await page.fill('input[name="skssq_z"]', period_key)  # 所属期起
        await page.fill('input[name="skssq_q"]', period_key)  # 所属期止
        await page.click('button:has-text("下一步")')

        # 2. 填写销项 (按税率)
        output_items = {
            "13": ("xse_13", "xxse_13"),   # 销售额 + 销项税额
            "9": ("xse_9", "xxse_9"),
            "6": ("xse_6", "xxse_6"),
            "5": ("xse_5", "xxse_5"),
            "3": ("xse_3", "xxse_3"),
        }
        for rate, (xse_field, xxse_field) in output_items.items():
            xse = body.get(f"output_{rate}")
            if xse is not None:
                await page.fill(f'input[name="{xse_field}"]', str(xse))

        # 3. 填写进项
        input_items = {"13": "jxse_13", "9": "jxse_9", "6": "jxse_6"}
        for rate, field_name in input_items.items():
            jxse = body.get(f"input_{rate}")
            if jxse is not None:
                await page.fill(f'input[name="{field_name}"]', str(jxse))

        # 4. 等待自动计算应纳税额
        await page.wait_for_selector('input[name="ynse"]', timeout=self.timeout_ms)

    async def submit_form(self, page, payload: FilingPayload) -> str:
        """点击申报按钮,等待回执,返回申报号。"""
        # 1. 点击"申报"按钮
        await page.click('button:has-text("申报"), button:has-text("提交")')

        # 2. 确认弹窗
        try:
            await page.click('button:has-text("确定")', timeout=5000)
        except Exception:
            pass  # 没有确认弹窗

        # 3. 等待申报成功页面
        await page.wait_for_selector(
            'div:has-text("申报成功"), div:has-text("申报受理")',
            timeout=self.timeout_ms,
        )

        # 4. 提取申报号 (回执号)
        receipt_el = await page.query_selector('span.sbhz_no, .receipt-no, [data-receipt]')
        if receipt_el:
            receipt_id = await receipt_el.inner_text()
            return receipt_id.strip()

        # Fallback: 从 URL 提取
        url = page.url
        match = re.search(r'sb(?:hz)?[=_-]([A-Z0-9-]+)', url)
        if match:
            return match.group(1)

        # 最后 fallback: 用时间戳生成
        return f"CN-VAT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    async def parse_status(self, page, receipt_id: str) -> tuple[FilingStatus, str]:
        """查询申报状态。"""
        # 导航到"申报结果查询"
        await page.goto(f"{self._base_url}/bszm/yyzzx/sb/sbjgcx", timeout=self.timeout_ms)

        # 输入申报号查询
        try:
            await page.fill('input[name="sbbh"]', receipt_id, timeout=5000)
            await page.click('button:has-text("查询")')
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception as e:
            return FilingStatus.SUBMITTED, f"状态查询失败: {e}"

        # 解析状态
        body_text = await page.inner_text("body")
        if "申报成功" in body_text or "已受理" in body_text:
            return FilingStatus.ACCEPTED, "申报已受理"
        if "申报失败" in body_text or "已退回" in body_text:
            return FilingStatus.REJECTED, "申报被退回"
        if "审核中" in body_text:
            return FilingStatus.IN_PROGRESS, "税务局审核中"
        return FilingStatus.SUBMITTED, "已提交,等待处理"
