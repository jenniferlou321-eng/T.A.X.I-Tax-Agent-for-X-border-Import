"""GovTalk XML Channel — HMRC Transaction Engine 网关客户端

GovTalk 是 HMRC 遗留 XML 消息协议,用于 Corporation Tax (CT600)、PAYE/RTI (FPS/EPS/EYU)、SDLT。
这三个税种共用同一个 Transaction Engine 网关,通过 envelope 中的 <Class> 字段区分。

核心流程: POST /submission → 返回 Poll URL → POST /poll → Accepted/Rejected
"""

from .client import GovTalkClient
from .exceptions import GovTalkError, TransientError, PermanentError, AuthError

__all__ = [
    "GovTalkClient",
    "GovTalkError",
    "TransientError",
    "PermanentError",
    "AuthError",
]
