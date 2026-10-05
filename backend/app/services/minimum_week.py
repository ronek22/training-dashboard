"""Minimum viable week: shrink the rest of this week's plan to the smallest version that keeps
the streak habit and the anchor goals.

The target is the anchor session counts (e.g. "Lift three times per week") plus a couple of
easy rides, minus what is already done this week. Lifts stay lifts (short, main lifts only, the
A/B rotation keeps moving) so an anchor is never traded away; everything else becomes rest.
Days are chosen to keep lifts apart and off life-load days (travel and sick days get nothing). It is
applied as an ordinary plan adjustment, so past and completed days are protected, the change is
a plan revision, and "Restore full week" puts back the plan saved in that revision.
"""
import json
import sqlite3
from datetime import date, datetime, timedelta
from itertools import combinations
from typing import Optional

from fastapi import HTTPException

from ..models.plans import WeeklyPlanAdjustment, WeeklyPlanDay
from ..repositories.goals import ACTIVE_GOAL_CONDITION
from .life_load import get_life_load_days
from .plans import adjust_weekly_plan_data, preview_weekly_plan_adjustment_data
from .sick_mode import sick_dates

REASON = "Minimum viable week"
RESTORE_REASON = "Restored full week"
DEFAULT_LIFTS = 2
EASY_RIDES = 2
LIFT_MIN = 30
RIDE_MIN = 40
RIDE_TYPES = ("Ride", "VirtualRide")

LIFT_DETAILS = "Short version: main lifts only (first 2-3 exercises), 3 working sets, skip accessories. Keeps the anchor and the rotation moving."
RIDE_DETAILS = "Zone 2, conversational. Indoors is fine. Stop at 40 minutes even if you feel good."
REST_DETAILS = "Minimum viable week: rest. Any extra walk or mobility is a bonus, not a debt."


def _today(today: Optional[date]) -> date:
    return today or datetime.now().date()


def _anchor_targets(conn: sqlite3.Connection, week_start: str, week_end: str) -> tuple[int, int, list[str]]:
    """Weekly session-count anchors: lifts and rides to keep. Anchors outlast their end date."""
    rows = conn.execute(
        f"""
        SELECT title, metric_type, target_value, activity_type FROM goals
        WHERE {ACTIVE_GOAL_CONDITION} AND COALESCE(lifecycle_status, 'active') = 'active'
          AND commitment = 'anchor' AND period_type = 'week' AND start_date <= ?
        """,
        (week_start, week_end),
    ).fetchall()
    lifts = rides = 0
    titles = []
    for row in rows:
        count = int(round(row["target_value"] or 0))
        if row["metric_type"] == "strength_sessions" or (row["metric_type"] == "activities_count" and row["activity_type"] == "WeightTraining"):
            lifts, titles = max(lifts, count), titles + [row["title"]]
        elif row["metric_type"] == "activities_count" and row["activity_type"] in RIDE_TYPES:
            rides, titles = max(rides, count), titles + [row["title"]]
    return lifts or DEFAULT_LIFTS, max(rides, EASY_RIDES), titles


def _done_this_week(conn: sqlite3.Connection, week_start: str, week_end: str) -> tuple[int, int, set[str], set[str]]:
    """Lifts and rides already recorded this week, and the dates with any activity / a lift."""
    rows = conn.execute(
        "SELECT date, type, workout_intent FROM activities WHERE date BETWEEN ? AND ?",
        (week_start, week_end),
    ).fetchall()
    lift_dates = {row["date"] for row in rows if row["type"] == "WeightTraining" and row["workout_intent"] not in ("mobility", "recovery")}
    rides = sum(1 for row in rows if row["type"] in RIDE_TYPES)
    lifts = sum(1 for row in rows if row["type"] == "WeightTraining" and row["workout_intent"] not in ("mobility", "recovery"))
    return lifts, rides, {row["date"] for row in rows}, lift_dates


def _pick(days: list[str], count: int, cost) -> tuple[str, ...]:
    """Cheapest set of `count` days (at most 7 days, so brute force is fine); earlier wins ties."""
    count = min(count, len(days))
    if count <= 0:
        return ()
    return min(combinations(days, count), key=lambda chosen: (cost(chosen), chosen))


def _adjacent(first: str, second: str) -> bool:
    return abs((date.fromisoformat(first) - date.fromisoformat(second)).days) == 1


def _lift_day(day: dict) -> dict:
    return {
        "date": day["date"], "label": day["label"], "session_type": "WeightTraining", "title": "Strength",
        "details": LIFT_DETAILS, "target_duration_min": LIFT_MIN, "planning_rule_reason": REASON,
    }


def _ride_day(day: dict) -> dict:
    return {
        "date": day["date"], "label": day["label"], "session_type": "Ride", "workout_intent": "easy", "title": "Easy ride",
        "details": RIDE_DETAILS, "target_duration_min": RIDE_MIN, "planning_rule_reason": REASON,
    }


def _rest_day(day: dict) -> dict:
    return {"date": day["date"], "label": day["label"], "session_type": "Rest", "title": "Rest", "details": REST_DETAILS, "planning_rule_reason": REASON}


def build_minimum_week(conn: sqlite3.Connection, week_start: str, today: Optional[date] = None) -> dict:
    """The proposed days for the rest of the week, plus the numbers behind them."""
    row = conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (week_start,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Weekly plan not found for {week_start}")
    plan_days = sorted(json.loads(row["days_json"]), key=lambda item: item["date"])
    week_end = (date.fromisoformat(week_start) + timedelta(days=6)).isoformat()
    today_key = _today(today).isoformat()

    lift_target, ride_target, anchors = _anchor_targets(conn, week_start, week_end)
    lifts_done, rides_done, busy, lift_dates = _done_this_week(conn, week_start, week_end)
    open_days = [day for day in plan_days if day["date"] >= today_key and day["date"] not in busy]
    if not open_days:
        raise HTTPException(status_code=400, detail="No days left this week to change")

    tagged = get_life_load_days(conn, week_start, week_end)
    # Travel days and sick days get nothing: no gym on the road, and sick mode means rest.
    blocked = {key for key, item in tagged.items() if "travel" in item["tags"]} | sick_dates(conn)
    planned_type = {day["date"]: str(day.get("session_type") or "").lower() for day in plan_days}
    usable = [day["date"] for day in open_days if day["date"] not in blocked]

    def lift_cost(chosen: tuple[str, ...]) -> int:
        days = sorted(chosen) + sorted(lift_dates)
        back_to_back = sum(1 for first, second in combinations(days, 2) if _adjacent(first, second))
        return 10 * back_to_back + sum(1 for key in chosen if key in tagged) - sum(1 for key in chosen if planned_type[key] in ("strength", "weighttraining"))

    lifts = _pick(usable, max(0, lift_target - lifts_done), lift_cost)
    remaining = [key for key in usable if key not in lifts]

    def ride_cost(chosen: tuple[str, ...]) -> int:
        return sum(2 for key in chosen if key in tagged) - sum(1 for key in chosen if planned_type[key] in ("ride", "virtualride"))

    rides = _pick(remaining, max(0, ride_target - rides_done), ride_cost)

    days = [_lift_day(day) if day["date"] in lifts else _ride_day(day) if day["date"] in rides else _rest_day(day) for day in open_days]
    short_lifts = max(0, lift_target - lifts_done - len(lifts))
    return {
        "week_start": week_start,
        "effective_from": open_days[0]["date"],
        "targets": {"lifts": lift_target, "rides": ride_target},
        "done": {"lifts": lifts_done, "rides": rides_done},
        "planned": {"lifts": len(lifts), "rides": len(rides)},
        "anchors": anchors,
        "shortfall": {"lifts": short_lifts, "rides": max(0, ride_target - rides_done - len(rides))},
        "summary": _summary(lift_target, ride_target, lifts_done, rides_done, short_lifts),
        "days": days,
    }


def _summary(lift_target: int, ride_target: int, lifts_done: int, rides_done: int, short_lifts: int) -> str:
    def part(target: int, done: int, noun: str) -> str:
        return f"{target} {noun}{'s' if target != 1 else ''}" + (f" ({done} done)" if done else "")

    text = f"{part(lift_target, lifts_done, 'short lift')} and {part(ride_target, rides_done, 'easy ride')}; everything else rests."
    if short_lifts:
        text += f" Only room for {lift_target - lifts_done - short_lifts} more lift{'s' if lift_target - lifts_done - short_lifts != 1 else ''} this week."
    return text


def _adjustment(proposal: dict, reason: str) -> WeeklyPlanAdjustment:
    return WeeklyPlanAdjustment(
        week_start=proposal["week_start"],
        effective_from=proposal["effective_from"],
        days=[WeeklyPlanDay(**day) for day in proposal["days"]],
        adaptation_reason=reason,
    )


def preview_minimum_week(conn: sqlite3.Connection, week_start: str, today: Optional[date] = None) -> dict:
    proposal = build_minimum_week(conn, week_start, today)
    preview = preview_weekly_plan_adjustment_data(conn, _adjustment(proposal, REASON))
    return {**proposal, "diff": preview["diff"]}


def apply_minimum_week(conn: sqlite3.Connection, week_start: str, today: Optional[date] = None) -> dict:
    proposal = build_minimum_week(conn, week_start, today)
    result = adjust_weekly_plan_data(conn, _adjustment(proposal, f"{REASON}: {proposal['summary']}"))
    return {**proposal, "plan": result["plan"], "changed_dates": result["changed_dates"]}


def minimum_week_state(conn: sqlite3.Connection, week_start: str) -> Optional[dict]:
    """The week's latest minimum-viable-week revision, unless a restore came after it."""
    try:
        rows = conn.execute(
            "SELECT id, adaptation_reason, created_at FROM plan_revisions WHERE week_start = ? ORDER BY id DESC",
            (week_start,),
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    for row in rows:
        reason = row["adaptation_reason"] or ""
        if reason.startswith(RESTORE_REASON):
            return None
        if reason.startswith(REASON):
            summary = reason.removeprefix(f"{REASON}: ").strip() or None
            return {"active": True, "revision_id": row["id"], "summary": summary, "since": row["created_at"]}
    return None


def restore_full_week(conn: sqlite3.Connection, week_start: str, today: Optional[date] = None) -> dict:
    """Put back the plan saved before the minimum week, for days that are still open."""
    state = minimum_week_state(conn, week_start)
    if not state:
        raise HTTPException(status_code=400, detail="This week is not a minimum viable week")
    previous = json.loads(conn.execute("SELECT previous_plan_json FROM plan_revisions WHERE id = ?", (state["revision_id"],)).fetchone()[0])
    week_end = (date.fromisoformat(week_start) + timedelta(days=6)).isoformat()
    today_key = _today(today).isoformat()
    busy = {row["date"] for row in conn.execute("SELECT DISTINCT date FROM activities WHERE date BETWEEN ? AND ?", (week_start, week_end))}
    current_dates = {day["date"] for day in json.loads(conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (week_start,)).fetchone()[0])}
    days = [
        WeeklyPlanDay(**day) for day in sorted(previous["days"], key=lambda item: item["date"])
        if day["date"] >= today_key and day["date"] not in busy and day["date"] in current_dates
    ]
    if not days:
        raise HTTPException(status_code=400, detail="No days left this week to restore")
    result = adjust_weekly_plan_data(conn, WeeklyPlanAdjustment(
        week_start=week_start, effective_from=days[0].date, days=days, adaptation_reason=RESTORE_REASON,
    ))
    return {"plan": result["plan"], "changed_dates": result["changed_dates"]}
