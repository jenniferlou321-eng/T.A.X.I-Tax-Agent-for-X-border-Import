"""提交渠道抽象 — FilingChannel ABC + API Channel 实现"""

from abc import ABC, abstractmethod
from ..models.results import AuthResult, SubmitResult, StatusResult, Receipt, FilingPayload
from ..models.tax_data import ChannelType


class FilingChannel(ABC):
    """所有提交渠道的抽象基类"""

    channel_type: ChannelType

    @abstractmethod
    async def authenticate(self) -> AuthResult:
        """认证：OAuth token 获取 / Cookie 恢复 / 手动登录"""
        ...

    @abstractmethod
    async def submit(self, payload: FilingPayload) -> SubmitResult:
        """提交申报数据到税局"""
        ...

    @abstractmethod
    async def get_status(self, receipt: Receipt) -> StatusResult:
        """查询提交后处理状态"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """渠道可用性快速检查"""
        ...