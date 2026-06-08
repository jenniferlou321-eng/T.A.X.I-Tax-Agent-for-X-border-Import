"""状态机 — FilingStatus 合法转换规则"""

from ..models.results import FilingStatus


# 合法状态转换映射
_TRANSITIONS: dict[FilingStatus, set[FilingStatus]] = {
    FilingStatus.PENDING: {FilingStatus.IN_PROGRESS},
    FilingStatus.IN_PROGRESS: {FilingStatus.SUBMITTED, FilingStatus.ERROR},
    FilingStatus.SUBMITTED: {FilingStatus.ACCEPTED, FilingStatus.REJECTED},
    FilingStatus.ACCEPTED: set(),           # 终态
    FilingStatus.REJECTED: {FilingStatus.PENDING},  # 修复后重新提交
    FilingStatus.ERROR: {FilingStatus.SUBMITTED, FilingStatus.PENDING},
}


class StateMachine:
    """FilingStatus 状态机"""

    @staticmethod
    def can_transition(current: FilingStatus, target: FilingStatus) -> bool:
        """检查状态转换是否合法"""
        return target in _TRANSITIONS.get(current, set())

    @staticmethod
    def transition(current: FilingStatus, target: FilingStatus) -> FilingStatus:
        """执行状态转换，非法转换抛出 ValueError"""
        if not StateMachine.can_transition(current, target):
            raise ValueError(
                f"Illegal state transition: {current.value} → {target.value}"
            )
        return target

    @staticmethod
    def is_terminal(status: FilingStatus) -> bool:
        """是否为终态"""
        return len(_TRANSITIONS.get(status, set())) == 0