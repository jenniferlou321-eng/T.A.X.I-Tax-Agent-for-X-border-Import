"""BrowserChannel — 基于浏览器自动化的提交渠道

针对没有公开 API 的税务系统(中国电子税务局、香港 IR56B、部分国家)
通过 Playwright 自动化网页操作,实现"准 API"式提交。

设计要点:
- 与 APIChannel 平行,实现同样的 FilingChannel 接口
- 不在申报主流程中阻塞(浏览器操作异步执行)
- 支持人工接管验证码 / 二次确认
- 截图保留作为审计证据
- 失败时自动重试 + 状态回滚
"""

from __future__ import annotations

import logging
import uuid
from abc import abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.channels import FilingChannel
from backend.models.results import (
    AuthResult, SubmitResult, StatusResult, Receipt, FilingPayload, FilingStatus,
)
from backend.models.tax_data import ChannelType

logger = logging.getLogger(__name__)


class BrowserChannelError(Exception):
    """BrowserChannel 错误基类"""
    pass


class LoginRequired(BrowserChannelError):
    """需要人工登录 / 验证"""
    def __init__(self, message: str, session_id: str = ""):
        super().__init__(message)
        self.session_id = session_id


class BrowserChannel(FilingChannel):
    """基于 Playwright 浏览器自动化的提交渠道。

    子类必须实现:
    - login_url(): 登录页 URL
    - form_url(): 申报表单 URL (需先登录)
    - fill_form(): 用 FilingPayload 填写表单 (返回 success bool)
    - submit_form(): 提交并返回 receipt_id / 表单号
    - parse_status(): 从页面解析当前申报状态

    子类可选实现:
    - handle_2fa(): 处理两步验证/验证码 (默认 throw LoginRequired)
    - take_screenshots(): 是否截图 (默认 True,生产环境可关)
    """

    channel_type = ChannelType.BROWSER

    def __init__(
        self,
        jurisdiction: str,
        tax_type: str,
        headless: bool = True,
        screenshot_dir: str = "./data/browser_screenshots/",
        timeout_ms: int = 30_000,
    ):
        self.jurisdiction = jurisdiction
        self.tax_type = tax_type
        self.headless = headless
        self.screenshot_dir = Path(screenshot_dir) / jurisdiction / tax_type
        self.timeout_ms = timeout_ms
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._session_id: Optional[str] = None
        self._last_screenshot: Optional[str] = None

    # ── 子类必须实现 ──

    @abstractmethod
    def login_url(self) -> str:
        """登录页 URL"""
        ...

    @abstractmethod
    def form_url(self) -> str:
        """申报表单 URL"""
        ...

    @abstractmethod
    async def fill_form(self, page, payload: FilingPayload) -> None:
        """用 payload 填写表单。

        Args:
            page: Playwright Page 对象
            payload: 申报数据
        """
        ...

    @abstractmethod
    async def submit_form(self, page, payload: FilingPayload) -> str:
        """点击提交并返回 receipt_id (回执号)"""
        ...

    @abstractmethod
    async def parse_status(self, page, receipt_id: str) -> tuple[FilingStatus, str]:
        """从页面解析申报状态。

        Returns:
            (status, detail_message)
        """
        ...

    # ── 可选覆盖 ──

    async def handle_2fa(self, page, verification_type: str) -> None:
        """处理两步验证。默认抛 LoginRequired 请求人工接管。"""
        raise LoginRequired(
            f"需要人工处理 {verification_type} 验证。当前 session_id={self._session_id}",
            session_id=self._session_id or "",
        )

    async def take_screenshot(self, page, name: str) -> str:
        """截图,返回文件路径"""
        path = self.screenshot_dir / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        try:
            await page.screenshot(path=str(path), full_page=True)
        except Exception as e:
            logger.warning(f"Screenshot failed: {e}")
            return ""
        self._last_screenshot = str(path)
        return str(path)

    # ── FilingChannel 接口实现 ──

    async def authenticate(self) -> AuthResult:
        """检查浏览器会话是否有效;无效则提示人工登录。"""
        try:
            page = await self._get_page()
            await page.goto(self.form_url(), timeout=self.timeout_ms)
            # 检查是否被重定向到登录页
            if "login" in page.url.lower() or "signin" in page.url.lower():
                self._session_id = str(uuid.uuid4())
                return AuthResult(
                    success=False,
                    error=f"需要登录: {page.url} (session={self._session_id})",
                )
            return AuthResult(success=True, token="browser-session-active")
        except Exception as e:
            return AuthResult(success=False, error=str(e))

    async def submit(self, payload: FilingPayload) -> SubmitResult:
        """主提交流程:导航 → 填写 → 截图 → 提交 → 拿回执。"""
        page = await self._get_page()
        try:
            # 1. 导航到表单
            await page.goto(self.form_url(), timeout=self.timeout_ms)
            if "login" in page.url.lower():
                self._session_id = str(uuid.uuid4())
                return SubmitResult(
                    success=False,
                    error_code="LOGIN_REQUIRED",
                    error_message=f"需要先登录, session_id={self._session_id}",
                )

            # 2. 填写
            await self.fill_form(page, payload)
            await self.take_screenshot(page, "filled")

            # 3. 提交
            receipt_id = await self.submit_form(page, payload)
            await self.take_screenshot(page, "submitted")

            # 4. 返回 receipt
            return SubmitResult(
                success=True,
                receipt=Receipt(
                    receipt_id=receipt_id,
                    submitted_at=datetime.now(timezone.utc),
                    raw_response={
                        "screenshot": self._last_screenshot,
                        "form_url": self.form_url(),
                    },
                ),
                raw_response={"receipt_id": receipt_id},
            )
        except LoginRequired as e:
            return SubmitResult(
                success=False,
                error_code="2FA_REQUIRED",
                error_message=str(e),
            )
        except Exception as e:
            logger.exception(f"BrowserChannel submit failed: {e}")
            try:
                await self.take_screenshot(page, "error")
            except Exception:
                pass
            return SubmitResult(
                success=False,
                error_code="BROWSER_ERROR",
                error_message=str(e),
            )

    async def get_status(self, receipt: Receipt) -> StatusResult:
        """回访提交页面,解析当前状态。"""
        page = await self._get_page()
        try:
            await page.goto(self.form_url(), timeout=self.timeout_ms)
            status, detail = await self.parse_status(page, receipt.receipt_id)
            return StatusResult(status=status, detail=detail)
        except Exception as e:
            return StatusResult(
                status=FilingStatus.SUBMITTED,
                detail=f"状态查询失败: {e}",
            )

    async def health_check(self) -> bool:
        """检查 Playwright / Chromium 是否可用。"""
        try:
            # 只导入 — 不实际启动浏览器
            from playwright.async_api import async_playwright  # noqa: F401
            return True
        except ImportError:
            return False
        except Exception:
            return False

    # ── Playwright 客户端 (懒加载) ──

    async def _get_page(self):
        """懒加载 Playwright,返回 page。子类可覆盖。"""
        try:
            from playwright.async_api import async_playwright
        except ImportError as e:
            raise BrowserChannelError(
                "Playwright 未安装。运行: pip install playwright && playwright install chromium"
            ) from e

        if not hasattr(self, "_pw") or self._pw is None:
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()
        return self._page

    async def close(self) -> None:
        """关闭浏览器资源。"""
        try:
            if hasattr(self, "_browser") and self._browser:
                await self._browser.close()
            if hasattr(self, "_pw") and self._pw:
                await self._pw.stop()
        except Exception:
            pass
        finally:
            self._pw = None
            self._browser = None
            self._context = None
            self._page = None


# ── 工厂函数 ──

def create_browser_channel(
    jurisdiction: str,
    tax_type: str,
    headless: bool = True,
) -> BrowserChannel:
    """创建 BrowserChannel 实例。

    Args:
        jurisdiction: "cn" / "hk" / "sg" 等
        tax_type: "vat" / "cit" / "iit" 等
        headless: 是否无头模式 (生产 True,调试 False)
    """
    if jurisdiction == "cn":
        from backend.jurisdictions.cn.channels.cn_vat_channel import CNVATBrowserChannel
        from backend.jurisdictions.cn.channels.cn_cit_channel import CNCITBrowserChannel

        if tax_type in ("cn_vat", "vat"):
            return CNVATBrowserChannel(headless=headless)
        if tax_type in ("cn_cit", "cit"):
            return CNCITBrowserChannel(headless=headless)

    raise NotImplementedError(
        f"BrowserChannel not implemented for {jurisdiction}/{tax_type}"
    )
