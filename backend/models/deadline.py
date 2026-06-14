"""Deadline models — filing deadline rules, computed deadlines, and reminder config.

Pure dataclasses — no external dependencies, no async, no I/O.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class DeadlineRule:
    """A recurring deadline rule for a specific jurisdiction + tax type combination.

    Examples:
        UK VAT quarterly: period_end_months=[1,4,7,10], due_month_offset=1, due_day=7
        → Q1 (Jan-Mar) due May 7, Q2 (Apr-Jun) due Aug 7, etc.

        CN CIT quarterly: period_end_months=[1,4,7,10], due_month_offset=0, due_day=15
        → Q1 prepayment due Apr 15, Q2 due Jul 15, etc.
    """
    jurisdiction: str          # "UK", "DE", "FR", "CN", "SG"
    tax_type: str               # "VAT", "CIT"
    description: str            # Human-readable, e.g. "UK VAT Quarterly Return"
    period: str                 # "monthly", "quarterly", "annual"
    due_day: int = 7            # Day of month the filing is due
    due_month_offset: int = 1   # Months after period end before due date
    period_end_months: list[int] = field(default_factory=list)  # e.g. [1,4,7,10]


@dataclass
class FilingDeadline:
    """A computed upcoming filing deadline."""
    jurisdiction: str
    tax_type: str
    period_key: str             # "2026-Q2", "2026-04"
    period_start: date
    period_end: date
    due_date: date
    description: str
    days_remaining: int


@dataclass
class ReminderConfig:
    """Configuration for deadline reminders."""
    days_before: list[int] = field(default_factory=lambda: [30, 14, 7, 3, 1])
    enabled: bool = True
