"""A data-first report for one training week, measured against the athlete's own norm.

The weekly review page leads with this: what the week held compared with a usual week
(the four weeks before it), what the plan asked for day by day and what got done, how the
body responded (sleep, HRV, resting HR against the 28 days before the week), weekly goals,
an eight-week trend and a few plain observations. Nothing here calls an LLM, so it shows
instantly for any week; the AI reviews sit below it as commentary.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Optional

from .dashboard import build_training_load_summary
from .goals import goal_value_for_window
from .health_data import get_health_metric_history, get_sleep_history
from .life_load import get_life_load_days
from .plans import serialize_weekly_plan
from .sick_mode import sick_dates

BASELINE_WEEKS = 4
TREND_WEEKS = 8
HEALTH_BASELINE_DAYS = 28
LOAD_WINDOW_DAYS = 120

SPORTS = {
    "Ride": "cycling", "VirtualRide": "cycling",
    "Run": "running",
    "WeightTraining": "strength",
    "Hike": "walking", "Walk": "walking",
}
SPORT_ORDER = ("cycling", "running", "strength", "walking", "other")
SPORT_LABELS = {"cycling": "Cycling", "running": "Running", "strength": "Strength", "walking": "Walks & hikes", "other": "Other"}
# Walks count as movement, not training, the same way the wins card counts sessions.
NON_TRAINING = {"walking"}
DONE_STATUSES = {"linked", "matched", "partially_matched", "moved", "replaced", "rest_day_changed"}
REST_TYPES = {"rest", ""}


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _sport(activity_type: str) -> str:
    return SPORTS.get(activity_type, "other")


def _hours(minutes: float) -> str:
    rounded = round(minutes)
    return f"{rounded // 60}h {rounded % 60:02d}m" if rounded >= 60 else f"{rounded}m"


def _pct(value: float, base: float) -> Optional[int]:
    return round((value - base) / base * 100) if base else None


def _activities(conn: sqlite3.Connection, start: str, end: str) -> list[dict]:
    rows = conn.execute(
        "SELECT id, substr(date, 1, 10) AS day, type, name, duration_min, distance_km, elevation_m FROM activities "
        "WHERE substr(date, 1, 10) BETWEEN ? AND ? ORDER BY date, created_at",
        (start, end),
    ).fetchall()
    return [{
        "id": str(row["id"]), "date": row["day"], "type": row["type"], "sport": _sport(row["type"]),
        "name": row["name"] or row["type"], "duration_min": round(float(row["duration_min"] or 0)),
        "distance_km": round(float(row["distance_km"]), 1) if row["distance_km"] else None,
        "elevation_m": row["elevation_m"],
    } for row in rows]


def _week_totals(activities: list[dict], load_by_day: dict[str, float], start: date, through: date) -> dict:
    """Totals for activities in [start, through]; load is None when the load window does not cover it."""
    days = [(start + timedelta(days=offset)).isoformat() for offset in range((through - start).days + 1)]
    inside = [item for item in activities if start.isoformat() <= item["date"] <= through.isoformat()]
    training = [item for item in inside if item["sport"] not in NON_TRAINING]
    by_sport = {sport: {"minutes": 0, "sessions": 0} for sport in SPORT_ORDER}
    for item in inside:
        by_sport[item["sport"]]["minutes"] += item["duration_min"]
        by_sport[item["sport"]]["sessions"] += 1
    covered = all(day in load_by_day for day in days)
    return {
        "minutes": sum(item["duration_min"] for item in training),
        "movement_minutes": sum(item["duration_min"] for item in inside),
        "sessions": len(training),
        "active_days": len({item["date"] for item in inside}),
        "distance_km": round(sum(item["distance_km"] or 0 for item in inside if item["sport"] in {"cycling", "running"}), 1),
        "elevation_m": round(sum(item["elevation_m"] or 0 for item in inside)),
        "load": round(sum(load_by_day.get(day, 0) for day in days)) if covered else None,
        "by_sport": by_sport,
    }


def _average(weeks: list[dict], key: str) -> Optional[float]:
    values = [week[key] for week in weeks if week[key] is not None]
    return round(sum(values) / len(values), 1) if values else None


def _plan(conn: sqlite3.Connection, start: str, through: str, today: str) -> tuple[Optional[dict], dict[str, dict]]:
    row = conn.execute("SELECT * FROM weekly_plans WHERE week_start = ?", (start,)).fetchone()
    if not row:
        return None, {}
    try:
        plan = serialize_weekly_plan(row, conn)
    except (sqlite3.Error, KeyError, ValueError, TypeError):
        return None, {}
    by_day, planned, done, missed = {}, 0, 0, []
    for day in plan.get("days", []):
        session_type = str(day.get("session_type") or "").lower()
        comparison = day.get("comparison") or {}
        status = comparison.get("status")
        is_session = session_type not in REST_TYPES
        past = day["date"] <= through
        done_already = status in DONE_STATUSES
        # Today's session is still open until it is done, so it is neither counted nor missed yet.
        open_today = day["date"] == today and not done_already
        state = ("rest" if not is_session else "done" if past and done_already
                 else "upcoming" if not past or open_today else "missed")
        if is_session and past and not open_today:
            planned += 1
            if state == "done":
                done += 1
            else:
                missed.append(day.get("title") or session_type.title())
        by_day.setdefault(day["date"], []).append({
            "title": day.get("title") or session_type.title(),
            "session_type": session_type or "rest",
            "intent": day.get("workout_intent_label"),
            "target_duration_min": day.get("target_duration_min"),
            "state": state,
            "status_label": comparison.get("label"),
        })
    return {"title": plan.get("title"), "focus": plan.get("focus"), "planned": planned, "done": done, "missed": missed}, by_day


def _goals(conn: sqlite3.Connection, start: str, through: str) -> list[dict]:
    try:
        goals = conn.execute(
            "SELECT * FROM goals WHERE is_active = 1 AND COALESCE(lifecycle_status, 'active') = 'active' AND period_type = 'week' "
            "ORDER BY CASE commitment WHEN 'anchor' THEN 0 ELSE 1 END, id"
        ).fetchall()
    except sqlite3.Error:
        return []
    result = []
    for goal in goals:
        try:
            done = float(goal_value_for_window(conn, goal, start_date=start, end_date=through))
        except (sqlite3.Error, KeyError, ValueError):
            continue
        target = float(goal["target_value"] or 0)
        result.append({"id": goal["id"], "title": goal["title"], "metric": goal["metric_type"], "done": round(done, 1),
                       "target": target, "anchor": goal["commitment"] == "anchor", "met": bool(target) and done >= target})
    return result


def _health(conn: sqlite3.Connection, start: date, through: date, today: date) -> tuple[dict, dict[str, dict]]:
    """Weekly averages against the 28 days before the week, plus per-day values."""
    days_back = (today - start).days + HEALTH_BASELINE_DAYS + 2
    if days_back > 730:
        return {}, {}
    sources = {
        "sleep": get_sleep_history(conn, days_back),
        "hrv": get_health_metric_history(conn, "hrv", days_back),
        "resting_hr": get_health_metric_history(conn, "resting_hr", days_back),
        "steps": get_health_metric_history(conn, "steps", days_back),
    }
    base_start = (start - timedelta(days=HEALTH_BASELINE_DAYS)).isoformat()
    per_day: dict[str, dict] = {}
    summary = {}
    for metric, history in sources.items():
        values = {item["date"]: float(item["value"]) for item in history}
        week = [value for day, value in values.items() if start.isoformat() <= day <= through.isoformat()]
        base = [value for day, value in values.items() if base_start <= day < start.isoformat()]
        for day, value in values.items():
            if start.isoformat() <= day <= through.isoformat():
                per_day.setdefault(day, {})[metric] = value
        if week:
            summary[metric] = {
                "value": round(sum(week) / len(week), 1 if metric != "steps" else None),
                "baseline": round(sum(base) / len(base), 1 if metric != "steps" else None) if len(base) >= 7 else None,
                "days": len(week),
            }
    return summary, per_day


def _longest_gap(activities: list[dict], start: date, through: date) -> int:
    trained = {item["date"] for item in activities if item["sport"] not in NON_TRAINING}
    longest = current = 0
    for offset in range((through - start).days + 1):
        current = 0 if (start + timedelta(days=offset)).isoformat() in trained else current + 1
        longest = max(longest, current)
    return longest


def _insights(report: dict, sick_count: int, finished: bool) -> list[dict]:
    """A handful of plain observations, most important first. Tones: good, warn, info."""
    items: list[dict] = []
    totals, norm = report["totals"], report["norm"]
    usual = norm["minutes_to_date"] if not finished else norm["minutes"]
    when = "for a full week" if finished else "by this point in a usual week"
    if usual:
        diff = _pct(totals["minutes"], usual)
        plan = report["plan"]
        planned_step_back = finished and plan and plan["planned"] and plan["done"] == plan["planned"]
        if diff is not None and diff <= -20:
            reason = (f" {sick_count} sick {'day' if sick_count == 1 else 'days'} explain most of it." if sick_count
                      else " The plan was done in full, so this was a planned step back." if planned_step_back else "")
            items.append({"tone": "info" if reason else "warn", "key": "volume",
                          "text": f"{_hours(totals['minutes'])} of training, {abs(diff)}% under your usual {_hours(usual)} {when}." + reason})
        elif diff is not None and diff >= 20:
            items.append({"tone": "info", "key": "volume",
                          "text": f"{_hours(totals['minutes'])} of training, {diff}% over your usual {_hours(usual)} {when}."})
        else:
            items.append({"tone": "good", "key": "volume",
                          "text": f"{_hours(totals['minutes'])} of training, in line with your usual {_hours(usual)} {when}."})
    elif sick_count:
        items.append({"tone": "info", "key": "sick", "text": f"{sick_count} sick {'day' if sick_count == 1 else 'days'} this week."})

    if finished and totals["load"] and norm["load"] and totals["load"] > norm["load"] * 1.3:
        items.append({"tone": "warn", "key": "load",
                      "text": f"Training load jumped {_pct(totals['load'], norm['load'])}% above your norm. Start next week easy."})

    plan = report["plan"]
    if plan and plan["planned"]:
        if plan["done"] == plan["planned"]:
            items.append({"tone": "good", "key": "plan",
                          "text": f"Every planned session done{'' if finished else ' so far'} ({plan['done']} of {plan['planned']})."})
        else:
            missed = ", ".join(plan["missed"][:3])
            items.append({"tone": "warn" if plan["done"] / plan["planned"] < 0.6 else "info", "key": "plan",
                          "text": f"{plan['done']} of {plan['planned']} planned sessions done. Not done: {missed}."})

    for sport in ("cycling", "running", "strength"):
        usual_sessions = norm["sessions_by_sport"].get(sport) or 0
        got = totals["by_sport"][sport]["sessions"]
        if finished and usual_sessions >= 1.5 and got == 0:
            items.append({"tone": "info", "key": f"missing-{sport}",
                          "text": f"No {SPORT_LABELS[sport].lower()} this week; you usually do {usual_sessions:g}."})

    health = report["recovery"]
    sleep = health.get("sleep")
    if sleep and sleep["baseline"] and sleep["days"] >= 3:
        diff = sleep["value"] - sleep["baseline"]
        if diff <= -0.4:
            items.append({"tone": "warn", "key": "sleep", "text": f"Sleep averaged {sleep['value']:.1f} h, {abs(diff) * 60:.0f} min less than your recent norm."})
        elif diff >= 0.4:
            items.append({"tone": "good", "key": "sleep", "text": f"Sleep averaged {sleep['value']:.1f} h, {diff * 60:.0f} min more than your recent norm."})
    hrv = health.get("hrv")
    if hrv and hrv["baseline"] and hrv["days"] >= 3:
        diff = _pct(hrv["value"], hrv["baseline"])
        if diff is not None and diff <= -8:
            items.append({"tone": "warn", "key": "hrv", "text": f"HRV {abs(diff)}% below your 4-week baseline: the body is still absorbing something."})
        elif diff is not None and diff >= 8:
            items.append({"tone": "good", "key": "hrv", "text": f"HRV {diff}% above your 4-week baseline: recovery is going well."})
    rhr = health.get("resting_hr")
    if rhr and rhr["baseline"] and rhr["days"] >= 3 and rhr["value"] - rhr["baseline"] >= 3:
        items.append({"tone": "warn", "key": "rhr", "text": f"Resting HR {rhr['value'] - rhr['baseline']:.0f} bpm above baseline."})

    finished_weeks = [week["minutes"] for week in report["history"] if not week["current"] or finished]
    falling = 0
    for later, earlier in zip(reversed(finished_weeks), list(reversed(finished_weeks))[1:]):
        if later >= earlier * 0.9:
            break
        falling += 1
    if falling >= 3:
        first = finished_weeks[-1 - falling]
        items.append({"tone": "warn", "key": "trend",
                      "text": f"Training time has dropped {falling} weeks in a row, from {_hours(first)} to {_hours(finished_weeks[-1])}. "
                              "Decide whether that is a deliberate block or drift."})

    if report["longest_gap"] >= 3 and not sick_count:
        items.append({"tone": "info", "key": "gap", "text": f"{report['longest_gap']} days in a row without training."})
    return items


def build_week_report(conn: sqlite3.Connection, week_start: Optional[date] = None, today: Optional[date] = None) -> dict[str, Any]:
    today = today or datetime.now().date()
    monday = _monday(week_start or today)
    end = monday + timedelta(days=6)
    finished = today > end
    if monday > today:
        raise ValueError("That week has not started yet")
    through = end if finished else today
    day_offset = (through - monday).days

    trend_start = monday - timedelta(weeks=TREND_WEEKS - 1)
    activities = _activities(conn, trend_start.isoformat(), end.isoformat())
    try:
        chart = build_training_load_summary(conn, days=LOAD_WINDOW_DAYS)["chart"]
    except (sqlite3.Error, KeyError, ValueError, ZeroDivisionError):
        chart = []
    load_by_day = {item["date"]: float(item["load"]) for item in chart}
    ctl_by_day = {item["date"]: item for item in chart}

    week_items = [item for item in activities if monday.isoformat() <= item["date"] <= end.isoformat()]
    totals = _week_totals(week_items, load_by_day, monday, through)

    history, baseline = [], []
    for index in range(TREND_WEEKS):
        start = trend_start + timedelta(weeks=index)
        is_current = start == monday
        week_end = through if is_current else start + timedelta(days=6)
        items = [item for item in activities if start.isoformat() <= item["date"] <= (start + timedelta(days=6)).isoformat()]
        full = _week_totals(items, load_by_day, start, week_end)
        history.append({"week_start": start.isoformat(), "current": is_current, "minutes": full["minutes"], "load": full["load"],
                        "sessions": full["sessions"],
                        "minutes_by_sport": {sport: value["minutes"] for sport, value in full["by_sport"].items()}})
        if index >= TREND_WEEKS - 1 - BASELINE_WEEKS and not is_current:
            to_date = _week_totals(items, load_by_day, start, start + timedelta(days=day_offset))
            baseline.append({**full, "to_date": to_date["minutes"]})

    norm = {
        "weeks": len(baseline),
        "minutes": _average(baseline, "minutes"),
        "minutes_to_date": _average([{"v": week["to_date"]} for week in baseline], "v"),
        "sessions": _average(baseline, "sessions"),
        "load": _average(baseline, "load"),
        "sessions_by_sport": {sport: round(sum(week["by_sport"][sport]["sessions"] for week in baseline) / len(baseline), 1)
                              for sport in SPORT_ORDER} if baseline else {},
        "minutes_by_sport": {sport: round(sum(week["by_sport"][sport]["minutes"] for week in baseline) / len(baseline))
                             for sport in SPORT_ORDER} if baseline else {},
    }

    plan, plan_days = _plan(conn, monday.isoformat(), through.isoformat(), today.isoformat())
    recovery, health_days = _health(conn, monday, through, today)
    tags = get_life_load_days(conn, monday.isoformat(), end.isoformat())
    sick = sick_dates(conn)
    week_sick = [day for day in sick if monday.isoformat() <= day <= through.isoformat()]

    days = []
    for offset in range(7):
        day = (monday + timedelta(days=offset)).isoformat()
        load_point = ctl_by_day.get(day)
        days.append({
            "date": day,
            "future": day > through.isoformat(),
            "today": day == today.isoformat(),
            "planned": plan_days.get(day, []),
            "activities": [item for item in week_items if item["date"] == day],
            "load": round(load_point["load"]) if load_point and day <= through.isoformat() else None,
            "health": health_days.get(day, {}),
            "sick": day in sick,
            "tags": tags.get(day, {}).get("labels", []),
        })

    start_point = ctl_by_day.get((monday - timedelta(days=1)).isoformat())
    end_point = ctl_by_day.get(through.isoformat())
    fitness = ({"start": round(start_point["ctl"]), "end": round(end_point["ctl"]), "form": round(end_point["tsb"])}
               if start_point and end_point else None)

    report = {
        "week_start": monday.isoformat(),
        "week_end": end.isoformat(),
        "through": through.isoformat(),
        "finished": finished,
        "day_of_week": day_offset + 1,
        "previous_week": (monday - timedelta(weeks=1)).isoformat(),
        "next_week": (monday + timedelta(weeks=1)).isoformat() if monday + timedelta(weeks=1) <= today else None,
        "totals": totals,
        "norm": norm,
        "fitness": fitness,
        "plan": plan,
        "goals": _goals(conn, monday.isoformat(), through.isoformat()),
        "recovery": recovery,
        "sick_days": len(week_sick),
        "longest_gap": _longest_gap(week_items, monday, through),
        "days": days,
        "history": history,
        "sport_labels": SPORT_LABELS,
    }
    report["insights"] = _insights(report, len(week_sick), finished)
    return report
