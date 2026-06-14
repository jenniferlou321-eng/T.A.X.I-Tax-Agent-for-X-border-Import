"""GovTalk 专用异常层级"""


class GovTalkError(Exception):
    """GovTalk 错误基类"""
    pass


class TransientError(GovTalkError):
    """临时错误 — 网络抖动 / HMRC 后端繁忙,可重试"""
    pass


class PermanentError(GovTalkError):
    """永久错误 — 校验失败 / 格式错误,不可重试"""
    pass


class AuthError(GovTalkError):
    """认证错误 — Vendor ID / Password 无效"""
    pass
