"""Deadlines router — upcoming filing deadlines API endpoints.

GET /api/deadlines/upcoming  — compute upcoming deadlines (optional filters)
GET /api/deadlines/rules      — list configured deadline rules
"""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Query

from backend.services.deadline_calculator import DeadlineCalculator

router = APIRouter(prefix="/deadlines", tags=["deadlines"])

_calculator = DeadlineCalculator()


@router.get("/upcoming")
async def get_upcoming_deadlines(
    jurisdiction: Optional[str] = Query(
        None, description="Filter by jurisdiction (UK, DE, FR, CN, SG)"
    ),
    tax_type: Optional[str] = Query(
        None, description="Filter by tax type (VAT, CIT)"
    ),
    count: int = Query(4, ge=1, le=20, description="Number of deadlines to return"),
):
    """Get upcoming tax filing deadlines across supported jurisdictions.

    Pure computation — no external API calls, no authentication required.
    Returns deadlines sorted by due date ascending.
    """
    deadlines = _calculator.compute_upcoming(
        jurisdiction=jurisdiction,
        tax_type=tax_type,
        count=count,
    )
    return {
        "deadlines": [
            {
                "jurisdiction": d.jurisdiction,
                "tax_type": d.tax_type,
                "period_key": d.period_key,
                "period_start": d.period_start.isoformat(),
                "period_end": d.period_end.isoformat(),
                "due_date": d.due_date.isoformat(),
                "description": d.description,
                "days_remaining": d.days_remaining,
            }
            for d in deadlines
        ],
        "count": len(deadlines),
    }


@router.get("/rules")
async def list_deadline_rules(
    jurisdiction: Optional[str] = Query(None),
    tax_type: Optional[str] = Query(None),
):
    """List configured deadline rules, optionally filtered."""
    rules = _calculator.get_rules(jurisdiction=jurisdiction, tax_type=tax_type)
    return {
        "rules": [
            {
                "jurisdiction": r.jurisdiction,
                "tax_type": r.tax_type,
                "period": r.period,
                "due_day": r.due_day,
                "due_month_offset": r.due_month_offset,
                "description": r.description,
            }
            for r in rules
        ],
        "count": len(rules),
    }
