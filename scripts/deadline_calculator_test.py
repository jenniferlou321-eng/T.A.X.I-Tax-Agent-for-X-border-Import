"""Tax Filing Deadline Calculator — standalone test script.

Computes upcoming filing deadlines for UK/DE/FR/CN/SG VAT and CIT.
No external API calls — purely computational.

Usage:
    cd /root/TAXI && python scripts/deadline_calculator_test.py
"""

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import calendar

# ── Deadline Rules (UK/DE/FR/CN/SG VAT and CIT) ──

DEADLINE_RULES = [
    # UK
    {"jurisdiction": "UK", "tax_type": "VAT", "period": "quarterly",
     "due_month_offset": 1, "due_day": 7,
     "period_end_months": [1, 4, 7, 10],
     "description": "UK VAT Quarterly Return"},
    {"jurisdiction": "UK", "tax_type": "CIT", "period": "annual",
     "due_month_offset": 9, "due_day": 1,
     "period_end_months": [3],
     "description": "UK Corporation Tax Return (CT600)"},

    # Germany
    {"jurisdiction": "DE", "tax_type": "VAT", "period": "monthly",
     "due_month_offset": 0, "due_day": 10,
     "period_end_months": list(range(1, 13)),
     "description": "DE Umsatzsteuer-Voranmeldung (monthly)"},
    {"jurisdiction": "DE", "tax_type": "CIT", "period": "annual",
     "due_month_offset": 7, "due_day": 31,
     "period_end_months": [12],
     "description": "DE Koerperschaftsteuererklaerung"},

    # France
    {"jurisdiction": "FR", "tax_type": "VAT", "period": "monthly",
     "due_month_offset": 0, "due_day": 19,
     "period_end_months": list(range(1, 13)),
     "description": "FR TVA (monthly)"},
    {"jurisdiction": "FR", "tax_type": "CIT", "period": "annual",
     "due_month_offset": 4, "due_day": 15,
     "period_end_months": [12],
     "description": "FR Impot sur les Societes"},

    # China
    {"jurisdiction": "CN", "tax_type": "VAT", "period": "monthly",
     "due_month_offset": 0, "due_day": 15,
     "period_end_months": list(range(1, 13)),
     "description": "CN VAT (monthly)"},
    {"jurisdiction": "CN", "tax_type": "CIT", "period": "quarterly",
     "due_month_offset": 0, "due_day": 15,
     "period_end_months": [1, 4, 7, 10],
     "description": "CN CIT Quarterly Pre-payment"},

    # Singapore
    {"jurisdiction": "SG", "tax_type": "VAT", "period": "quarterly",
     "due_month_offset": 1, "due_day": 30,
     "period_end_months": [3, 6, 9, 12],
     "description": "SG GST F5 Quarterly Return"},
    {"jurisdiction": "SG", "tax_type": "CIT", "period": "annual",
     "due_month_offset": 10, "due_day": 30,
     "period_end_months": [12],
     "description": "SG Corporate Income Tax (Form C)"},
]


def end_of_month(year: int, month: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


def compute_period_start(year: int, end_month: int, rule: dict) -> date:
    if rule["period"] == "monthly":
        return date(year, end_month, 1)
    elif rule["period"] == "quarterly":
        start_month = end_month - 2
        if start_month < 1:
            return date(year - 1, start_month + 12, 1)
        return date(year, start_month, 1)
    else:  # annual
        if rule["jurisdiction"] == "UK" and rule["tax_type"] == "CIT":
            return date(year - 1, 4, 1)
        if end_month == 12:
            return date(year, 1, 1)
        return date(year - 1, end_month + 1, 1)


def format_period_key(period_start: date, end_month: int, rule: dict) -> str:
    if rule["period"] == "quarterly":
        q = (end_month - 1) // 3 + 1
        return f"{period_start.year}-Q{q}"
    elif rule["period"] == "annual":
        return f"{period_start.year}-{end_month:02d}"
    else:
        return f"{period_start.year}-{period_start.month:02d}"


def compute_deadlines(rule: dict, today: date, count: int = 4) -> list[dict]:
    """Compute the next `count` deadlines for a given rule."""
    deadlines = []

    for year_offset in range(-1, 3):
        year = today.year + year_offset
        for end_month in rule["period_end_months"]:
            period_end = end_of_month(year, end_month)
            period_start = compute_period_start(year, end_month, rule)

            due_date = period_end + relativedelta(months=rule["due_month_offset"])
            last_day = calendar.monthrange(due_date.year, due_date.month)[1]
            actual_due_day = min(rule["due_day"], last_day)
            due_date = date(due_date.year, due_date.month, actual_due_day)

            # Skip deadlines more than 30 days in the past
            if due_date < today - timedelta(days=30):
                continue

            period_key = format_period_key(period_start, end_month, rule)
            deadlines.append({
                "jurisdiction": rule["jurisdiction"],
                "tax_type": rule["tax_type"],
                "period_key": period_key,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "due_date": due_date.isoformat(),
                "description": rule["description"],
                "days_remaining": (due_date - today).days,
            })

    deadlines.sort(key=lambda d: d["due_date"])
    return deadlines[:count]


def main():
    today = date.today()
    print(f"Tax Filing Deadline Calendar (computed on {today.isoformat()})")
    print("=" * 80)

    for rule in DEADLINE_RULES:
        print(f"\n--- {rule['jurisdiction']} {rule['tax_type']}: {rule['description']} ---")
        deadlines = compute_deadlines(rule, today)
        if not deadlines:
            print("  No upcoming deadlines found")
            continue
        for d in deadlines:
            urgency = ""
            if d["days_remaining"] < 0:
                urgency = " [OVERDUE]"
            elif d["days_remaining"] <= 7:
                urgency = " [URGENT]"
            elif d["days_remaining"] <= 14:
                urgency = " [SOON]"
            print(
                f"  {d['period_key']:12s}  "
                f"period: {d['period_start']} to {d['period_end']}  "
                f"due: {d['due_date']}  "
                f"({d['days_remaining']:>4d} days){urgency}"
            )

    print("\n" + "=" * 80)
    print("Deadline calculator test complete.")


if __name__ == "__main__":
    main()
