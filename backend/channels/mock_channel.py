"""MockChannel — 模拟提交渠道(demo / 尚无真实 API 的税种用)

与 APIChannel 不同,MockChannel **不走任何网络**:submit() 直接返回一张
带模拟回执号的成功结果,get_status() 直接判为 ACCEPTED。这样 orchestrator
的 SUBMIT / TRACK 阶段能完整跑完,产出「模拟提交 = 完成申报」的演示效果,
而不需要真实凭证或税局沙箱。

用途:
- CN VAT / CN CIT(电子税务局只有 BrowserChannel,demo 跑不了)
- 未来任何「本地能算、但还没接通真实提交 API」的税种

⚠️ 这是模拟渠道 — 永远不会向任何税局真正提交。
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.channels import FilingChannel
from backend.models.tax_data import ChannelType
from backend.models.results import (
    AuthResult,
    SubmitResult,
    StatusResult,
    Receipt,
    FilingPayload,
    FilingStatus,
)


class MockChannel(FilingChannel):
    """模拟提交渠道 — 返回伪回执,不调用真实税局。"""

    channel_type = ChannelType.API

    def __init__(self, receipt_prefix: str = "MOCK"):
        """receipt_prefix: 回执号前缀,如 'CN-MOCK',便于区分管辖地。"""
        self._receipt_prefix = receipt_prefix

    async def authenticate(self) -> AuthResult:
        return AuthResult(success=True, token="MOCK")

    async def submit(self, payload: FilingPayload) -> SubmitResult:
        period_key = payload.period.period_key or "NA"
        tax_id = payload.taxpayer.tax_id or "000000"
        receipt_id = f"{self._receipt_prefix}-{period_key}-{tax_id[-6:]}"
        return SubmitResult(
            success=True,
            receipt=Receipt(
                receipt_id=receipt_id,
                submitted_at=datetime.now(timezone.utc),
                raw_response={
                    "mode": "mock",
                    "warning": "模拟提交 — 未向任何税局真正提交",
                    "body": payload.body,
                },
            ),
            raw_response={"mode": "mock", "receipt_id": receipt_id},
        )

    async def get_status(self, receipt: Receipt) -> StatusResult:
        return StatusResult(
            status=FilingStatus.ACCEPTED,
            detail="模拟提交 — 已受理(MockChannel)",
        )

    async def health_check(self) -> bool:
        return True
