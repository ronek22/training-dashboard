"""Weekly relative effort: heart-rate load per week against the athlete's own recent range.

Modelled on Strava's Relative Effort (Banister TRIMP). Every session is scored from heart
rate: the per-second stream TRIMP when it was fetched, otherwise TRIMP from the session's
average heart rate, and only with no heart rate at all a duration estimate. Power never
enters, so rides and lifts sit on the same heart-rate scale.

A week's range is built from the three full weeks before it, so it follows the athlete:
after a lighter block the range drops too.
"""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from .dashboard import (
    estimate_thresholds,
    generic_load_details,
    strength_load_details,
    trimp_score,
)

DISPLAY_WEEKS = 8
BASELINE_WEEKS = 3
RANGE_LOW = 0.67
RANGE_HIGH = 1.33
WEEKDAY_LETTERS = ["M", "T", "W", "T", "F", "S", "S"]


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def session_effort(row: sqlite3.Row, thresholds: dict) -> dict:
    """Heart-rate effort for one session, with how it was measured."""
    stream_trimp = row["stream_hr_trimp"]
    if stream_trimp is not None and float(stream_trimp) > 0:
        return {"effort": float(stream_trimp), "source": "hr_stream"}

    duration_min = float(row["duration_min"] or 0)
    max_hr = thresholds["run_max_hr"] if row["type"] == "Run" else thresholds["ride_max_hr"]
    trimp = trimp_score(duration_min, row["avg_hr"], thresholds["resting_hr"], max_hr)
    if trimp > 0:
        return {"effort": trimp, "source": "hr_average"}

    if row["type"] == "WeightTraining":
        fallback = strength_load_details(row)
    else:
        fallback = generic_load_details(row)
    return {"effort": float(fallback["load"]), "source": "duration" if fallback["load"] > 0 else "none"}


def _range_for(baseline: Optional[float]) -> Optional[dict]:
    if not baseline:
        return None
    return {"low": round(baseline * RANGE_LOW), "high": round(baseline * RANGE_HIGH), "baseline": round(baseline)}


def _status(score: float, effort_range: Optional[dict]) -> str:
    if not effort_range:
        return "unknown"
    if score < effort_range["low"]:
        return "below"
    if score > effort_range["high"]:
        return "above"
    return "in"


def _message(status: str, score: int, effort_range: Optional[dict], days_left: int) -> dict:
    if status == "unknown":
        return {
            "headline": "Building your range",
            "detail": "Three full weeks of training are needed before a weekly range can be set.",
        }
    low, high = effort_range["low"], effort_range["high"]
    if status == "below":
        if days_left > 0:
            detail = f"Lighter than your last three weeks so far. {low - score} more reaches your range; if you are recovering, stay under {low}."
        else:
            detail = f"A lighter week than your last three. Fine if it was planned recovery; {low} was the bottom of your range."
        return {"headline": "Below weekly range", "detail": detail}
    if status == "above":
        return {
            "headline": "Above weekly range",
            "detail": f"Heavier than your last three weeks (range tops out at {high}). Keep the rest of the week easy unless the build is deliberate.",
        }
    return {
        "headline": "In weekly range",
        "detail": f"In line with your last three weeks. Staying under {high} keeps the week steady.",
    }


def build_relative_effort(
    conn: sqlite3.Connection,
    today: Optional[date] = None,
    thresholds: Optional[dict] = None,
) -> dict:
    today = today or datetime.now().date()
    thresholds = thresholds or estimate_thresholds(conn)
    current_week = _week_start(today)
    first_week = current_week - timedelta(weeks=DISPLAY_WEEKS - 1 + BASELINE_WEEKS)

    rows = conn.execute(
        """
        SELECT a.date, a.type, a.duration_min, a.avg_hr, s.hr_trimp AS stream_hr_trimp
        FROM activities a
        LEFT JOIN activity_stream_summaries s ON s.activity_id = a.id
        WHERE a.date >= ? AND a.date <= ?
        """,
        (first_week.isoformat(), today.isoformat()),
    ).fetchall()

    weeks: dict[date, dict] = {}
    for offset in range(DISPLAY_WEEKS + BASELINE_WEEKS):
        start = first_week + timedelta(weeks=offset)
        weeks[start] = {"effort": 0.0, "sessions": 0, "estimated": 0}
    days = {current_week + timedelta(days=offset): 0.0 for offset in range(7)}

    for row in rows:
        day = datetime.strptime(str(row["date"])[:10], "%Y-%m-%d").date()
        scored = session_effort(row, thresholds)
        if scored["source"] == "none":
            continue
        bucket = weeks.get(_week_start(day))
        if bucket is None:
            continue
        bucket["effort"] += scored["effort"]
        bucket["sessions"] += 1
        if scored["source"] == "duration":
            bucket["estimated"] += 1
        if day in days:
            days[day] += scored["effort"]

    starts = sorted(weeks)
    history = []
    for index in range(BASELINE_WEEKS, len(starts)):
        start = starts[index]
        prior = [weeks[starts[index - back]]["effort"] for back in range(1, BASELINE_WEEKS + 1)]
        effort_range = _range_for(sum(prior) / BASELINE_WEEKS)
        score = round(weeks[start]["effort"])
        history.append({
            "week_start": start.isoformat(),
            "score": score,
            "range": effort_range,
            "status": _status(score, effort_range),
            "sessions": weeks[start]["sessions"],
            "estimated_sessions": weeks[start]["estimated"],
            "is_current": start == current_week,
        })

    current = history[-1]
    days_left = 6 - today.weekday()
    return {
        "week_start": current["week_start"],
        "score": current["score"],
        "range": current["range"],
        "status": current["status"],
        **_message(current["status"], current["score"], current["range"], days_left),
        "days": [
            {
                "date": day.isoformat(),
                "label": WEEKDAY_LETTERS[day.weekday()],
                "effort": round(effort),
                "is_future": day > today,
            }
            for day, effort in sorted(days.items())
        ],
        "estimated_sessions": current["estimated_sessions"],
        "sessions": current["sessions"],
        "weeks": history,
    }
