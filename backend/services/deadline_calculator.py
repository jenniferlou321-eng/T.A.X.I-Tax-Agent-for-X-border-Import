"""DeadlineCalculator — compute upcoming filing deadlines across jurisdictions.

Pure computation service — no external API calls, no persistent state, no async.
Works reliably offline and requires no credentials.
"""

from __future__ import annotations

import calendar
import logging
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta

from backend.models.deadline import DeadlineRule, FilingDeadline, ReminderConfig

logger = logging.getLogger(__name__)


# ── Static deadline rule definitions ──

_DEFAULT_RULES: list[DeadlineRule] = [
    DeadlineRule(jurisdiction="UK", tax_type="VAT", period="quarterly",
                 due_month_offset=1, due_day=7, period_end_months=[1, 4, 7, 10],
                 description="UK VAT Quarterly Return"),
    DeadlineRule(jurisdiction="UK", tax_type="CIT", period="annual",
                 due_month_offset=9, due_day=1, period_end_months=[3],
                 description="UK Corporation Tax Return (CT600)"),
    DeadlineRule(jurisdiction="DE", tax_type="VAT", period="monthly",
                 due_month_offset=0, due_day=10,
                 period_end_months=list(range(1, 13)),
                 description="DE Umsatzsteuer-Voranmeldung"),
    DeadlineRule(jurisdiction="DE", tax_type="CIT", period="annual",
                 due_month_offset=7, due_day=31, period_end_months=[12],
                 description="DE Koerperschaftsteuererklaerung"),
    DeadlineRule(jurisdiction="FR", tax_type="VAT", period="monthly",
                 due_month_offset=0, due_day=19,
                 period_end_months=list(range(1, 13)),
                 description="FR TVA"),
    DeadlineRule(jurisdiction="FR", tax_type="CIT", period="annual",
                 due_month_offset=4, due_day=15, period_end_months=[12],
                 description="FR Impot sur les Societes"),
    DeadlineRule(jurisdiction="CN", tax_type="VAT", period="monthly",
                 due_month_offset=0, due_day=15,
                 period_end_months=list(range(1, 13)),
                 description="CN VAT"),
    DeadlineRule(jurisdiction="CN", tax_type="CIT", period="quarterly",
                 due_month_offset=0, due_day=15, period_end_months=[1, 4, 7, 10],
                 description="CN CIT Quarterly Pre-payment"),
    DeadlineRule(jurisdiction="SG", tax_type="VAT", period="quarterly",
                 due_month_offset=1, due_day=30, period_end_months=[3, 6, 9, 12],
                 description="SG GST F5 Quarterly Return"),
    DeadlineRule(jurisdiction="SG", tax_type="CIT", period="annual",
                 due_month_offset=10, due_day=30, period_end_months=[12],
                 description="SG Corporate Income Tax (Form C)"),
]


class DeadlineCalculator:
    """Compute upcoming filing deadlines for all supported jurisdictions.

    Pure computation — no external API calls, no persistent state, no async.
    Can be used as a module-level singleton or instantiated per-request.
    """

    def __init__(self, rules: list[DeadlineRule] | None = None):
        self._rules = rules or _DEFAULT_RULES

    def get_rules(
        self, jurisdiction: str | None = None, tax_type: str | None = None
    ) -> list[DeadlineRule]:
        """List applicable deadline rules, optionally filtered."""
        results = self._rules
        if jurisdiction:
            results = [r for r in results if r.jurisdiction.upper() == jurisdiction.upper()]
        if tax_type:
            results = [r for r in results if r.tax_type.upper() == tax_type.upper()]
        return results

    def compute_upcoming(
        self,
        jurisdiction: str | None = None,
        tax_type: str | None = None,
        count: int = 4,
        reference_date: date | None = None,
    ) -> list[FilingDeadline]:
        """Compute the next `count` deadlines, optionally filtered by jurisdiction/tax_type."""
        today = reference_date or date.today()
        rules = self.get_rules(jurisdiction=jurisdiction, tax_type=tax_type)
        all_deadlines: list[FilingDeadline] = []

        for rule in rules:
            deadlines = self._compute_for_rule(rule, today, count)
            all_deadlines.extend(deadlines)

        all_deadlines.sort(key=lambda d: d.due_date)
        return all_deadlines[:count]

    def _compute_for_rule(
        self, rule: DeadlineRule, today: date, count: int
    ) -> list[FilingDeadline]:
        """Compute deadlines for a single rule."""
        deadlines: list[FilingDeadline] = []

        for year_offset in range(-1, 3):
            year = today.year + year_offset
            for end_month in rule.period_end_months:
                period_end = self._end_of_month(year, end_month)
                period_start = self._compute_period_start(year, end_month, rule)

                due_date = period_end + relativedelta(months=rule.due_month_offset)
                last_day = calendar.monthrange(due_date.year, due_date.month)[1]
                actual_due_day = min(rule.due_day, last_day)
                due_date = date(due_date.year, due_date.month, actual_due_day)

                # Skip deadlines more than 30 days in the past
                if due_date < today - timedelta(days=30):
                    continue

                period_key = self._format_period_key(period_start, end_month, rule)
                deadlines.append(FilingDeadline(
                    jurisdiction=rule.jurisdiction,
                    tax_type=rule.tax_type,
                    period_key=period_key,
                    period_start=period_start,
                    period_end=period_end,
                    due_date=due_date,
                    description=rule.description,
                    days_remaining=(due_date - today).days,
                ))

        deadlines.sort(key=lambda d: d.due_date)
        return deadlines[:count]

    @staticmethod
    def _end_of_month(year: int, month: int) -> date:
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, last_day)

    @staticmethod
    def _compute_period_start(year: int, end_month: int, rule: DeadlineRule) -> date:
        if rule.period == "monthly":
            return date(year, end_month, 1)
        elif rule.period == "quarterly":
            start_month = end_month - 2
            if start_month < 1:
                return date(year - 1, start_month + 12, 1)
            return date(year, start_month, 1)
        else:  # annual
            if rule.jurisdiction == "UK" and rule.tax_type == "CIT":
                return date(year - 1, 4, 1)
            if end_month == 12:
                return date(year, 1, 1)
            return date(year - 1, end_month + 1, 1)

    @staticmethod
    def _format_period_key(period_start: date, end_month: int, rule: DeadlineRule) -> str:
        if rule.period == "quarterly":
            q = (end_month - 1) // 3 + 1
            return f"{period_start.year}-Q{q}"
        elif rule.period == "annual":
            return f"{period_start.year}-{end_month:02d}"
        else:
            return f"{period_start.year}-{period_start.month:02d}"

    def check_reminders(
        self,
        config: ReminderConfig | None = None,
        jurisdiction: str | None = None,
        reference_date: date | None = None,
    ) -> list[dict]:
        """Return deadlines that trigger reminders based on days-before config.

        Returns list of {deadline: FilingDeadline, trigger: str, remind_on: str}.
        """
        cfg = config or ReminderConfig()
        if not cfg.enabled:
            return []

        today = reference_date or date.today()
        all_deadlines = self.compute_upcoming(
            jurisdiction=jurisdiction, count=20, reference_date=today,
        )

        reminders = []
        for d in all_deadlines:
            for days_before in cfg.days_before:
                if d.days_remaining == days_before:
                    reminders.append({
                        "deadline": d,
                        "trigger": f"{days_before} days before due",
                        "remind_on": today.isoformat(),
                    })
                    break
        return reminders
