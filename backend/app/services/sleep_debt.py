"""Rolling 7-night sleep debt against your own median sleep.

The baseline is the median of the nights before the 7-night window, so a rough
week can't drag its own yardstick down. A long night pays back only part of a
short one, and debt never goes below zero.
"""
from datetime import date, datetime, timedelta
from statistics import median
from typing import Optional

WINDOW_NIGHTS = 7
MIN_WINDOW_NIGHTS = 5
BASELINE_NIGHTS = 60
MIN_BASELINE_NIGHTS = 14
SURPLUS_PAYBACK = 0.5
CAUTION_HOURS = 3.0
RISK_HOURS = 6.0
SERIES_DAYS = 90


def _as_date(value) -> date:
    return value if isinstance(value, date) else datetime.strptime(str(value), "%Y-%m-%d").date()


def _status(debt: float) -> str:
    return "risk" if debt >= RISK_HOURS else "caution" if debt >= CAUTION_HOURS else "ok"


def _debt_on(nights: dict[date, float], day: date) -> Optional[dict]:
    window_start = day - timedelta(days=WINDOW_NIGHTS - 1)
    baseline_start = window_start - timedelta(days=BASELINE_NIGHTS)
    window = [hours for night, hours in nights.items() if window_start <= night <= day]
    prior = [hours for night, hours in nights.items() if baseline_start <= night < window_start]
    if len(window) < MIN_WINDOW_NIGHTS or len(prior) < MIN_BASELINE_NIGHTS:
        return None
    baseline = median(prior)
    deficit = sum(max(0.0, baseline - hours) for hours in window)
    surplus = sum(max(0.0, hours - baseline) for hours in window)
    debt = max(0.0, deficit - SURPLUS_PAYBACK * surplus)
    return {
        "date": day.isoformat(),
        "value": round(debt, 1),
        "baseline_hours": round(baseline, 2),
        "average_hours": round(sum(window) / len(window), 2),
        "nights": len(window),
    }


def build_sleep_debt(sleep_history: list[dict], today=None, series_days: int = SERIES_DAYS) -> dict:
    """`sleep_history` is `get_sleep_history` output: one entry per wake date."""
    today = _as_date(today or datetime.now().date())
    nights = {_as_date(item["date"]): float(item["value"]) for item in sleep_history if item.get("value")}

    series = []
    for offset in range(series_days):
        point = _debt_on(nights, today - timedelta(days=offset))
        if point:
            series.append({**point, "unit": "h"})

    # The window ending today still counts when last night hasn't synced yet (6 of 7 nights).
    current = series[0] if series and series[0]["date"] == today.isoformat() else None
    if not current:
        return {
            "available": False,
            "status": "insufficient_data",
            "message": f"Needs {MIN_WINDOW_NIGHTS} of the last {WINDOW_NIGHTS} nights and {MIN_BASELINE_NIGHTS} earlier nights for a baseline.",
            "caution_hours": CAUTION_HOURS,
            "risk_hours": RISK_HOURS,
            "history": series,
        }

    status = _status(current["value"])
    return {
        "available": True,
        "status": status,
        "debt_hours": current["value"],
        "baseline_hours": current["baseline_hours"],
        "average_hours": current["average_hours"],
        "nights": current["nights"],
        "as_of": current["date"],
        "message": _message(status, current),
        "caution_hours": CAUTION_HOURS,
        "risk_hours": RISK_HOURS,
        "history": series,
    }


def _message(status: str, current: dict) -> str:
    debt, baseline = current["value"], current["baseline_hours"]
    if status == "risk":
        return f"About {debt:.0f} h short of your usual {baseline:.1f} h a night this week. Keep the next hard session easy and bank an early night."
    if status == "caution":
        return f"About {debt:.0f} h short of your usual {baseline:.1f} h a night this week. An early night or two clears it."
    return f"Sleep is close to your usual {baseline:.1f} h a night this week."
