"""One month in review for the phone: is the training working?

Weight, strength, aerobic base and run fitness move over months, not weeks, so this puts the
month's signals side by side: time and active days against the three months before (the same
totals as the monthly letter), a day-by-day calendar with sick and record days, plans done, the
7-day weight trend against the lean-gain lane (the muscle-gain check's rule), best estimated 1RM
per lift against the month before, lift days per week for the anchor goal, ride hours by
intensity (ride-balance classification) and VDOT against the all-time peak. A finished month
also carries the monthly letter's wins and focus: the saved letter when there is one, otherwise
built on the fly and not saved. Nothing here calls an LLM.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Optional

from .block_recap import _classified_rides
from .guided_sessions import guided_completion_dates
from .monthly_letters import _bounds, _label, _prior_average, _shift, _totals, build_monthly_letter
from .muscle_gain import GAIN_PCT_MAX, GAIN_PCT_MIN, SMOOTHING_DAYS, _weigh_ins
from .personal_records import _iter_ranked, build_personal_records, epley_1rm
from .running_fitness import build_running_fitness
from .sick_mode import sick_dates
from .strength_progression import _session_index
from .week_report import _plan

MIN_WEIGH_INS = 3  # fewer weigh-ins in the month: dots, no trend
MIN_WEIGHT_SPAN_DAYS = 7
HELD_KG = 0.5  # a best e1RM within this of last month's counts as held
TOP_LIFTS = 5
LIFTS_PER_WEEK = 3
RIDE_INTENSITIES = ("recovery", "z2", "sweet_spot", "vo2")

# Activity type -> the calendar's sport key. Hikes are training (the letter counts them); walks are not.
SPORTS = {
    "Ride": "cycling", "VirtualRide": "cycling",
    "Run": "running", "TrailRun": "running",
    "WeightTraining": "strength",
    "Hike": "hiking",
    "Walk": "walking",
    "Workout": "mobility", "Yoga": "mobility", "PhysicalTherapy": "mobility",
}


def _sport(activity_type: str) -> str:
    return SPORTS.get(activity_type, "other")


def _days(conn: sqlite3.Connection, start: date, end: date, through: date, records: list[dict]) -> list[dict]:
    rows = conn.execute(
        "SELECT substr(date, 1, 10) AS day, type, duration_min FROM activities WHERE substr(date, 1, 10) BETWEEN ? AND ?",
        (start.isoformat(), through.isoformat()),
    ).fetchall()
    by_day: dict[str, dict[str, float]] = {}
    for row in rows:
        sports = by_day.setdefault(row["day"], {})
        sports[_sport(row["type"])] = sports.get(_sport(row["type"]), 0) + float(row["duration_min"] or 0)
    sick = sick_dates(conn)
    record_days = {item["date"] for item in records}
    days = []
    day = start
    while day <= end:
        key = day.isoformat()
        sports = by_day.get(key, {})
        # The day's training sport wins over a longer walk; a walk-only day is a walk.
        training = {sport: minutes for sport, minutes in sports.items() if sport != "walking"}
        pool = training or sports
        days.append({
            "date": key,
            "minutes": round(sum(sports.values())),
            "sport": max(pool, key=pool.get) if pool else None,
            "sick": key in sick,
            "record": key in record_days,
            "future": day > through,
        })
        day += timedelta(days=1)
    return days


def _plan_done(conn: sqlite3.Connection, start: date, through: date, today: date) -> Optional[dict]:
    planned = done = 0
    week = start - timedelta(days=start.weekday())
    while week <= through:
        plan, by_day = _plan(conn, week.isoformat(), through.isoformat(), today.isoformat())
        if plan:
            for day, items in by_day.items():
                if start.isoformat() <= day <= through.isoformat():
                    for item in items:
                        if item["state"] in ("done", "missed"):
                            planned += 1
                            done += item["state"] == "done"
        week += timedelta(weeks=1)
    return {"planned": planned, "done": done} if planned else None


def _streak(conn: sqlite3.Connection, through: date, today: date) -> int:
    """Days in a row with an activity or a guided session, up to the month's last day (or yesterday, if today is still open)."""
    keys = {row[0][:10] for row in conn.execute("SELECT DISTINCT date FROM activities")} | guided_completion_dates(conn)
    day = through - timedelta(days=1) if through == today and through.isoformat() not in keys else through
    length = 0
    while day.isoformat() in keys:
        length += 1
        day -= timedelta(days=1)
    return length


def _records(conn: sqlite3.Connection, start: date, through: date) -> list[dict]:
    """All-time bests set in the month that beat an earlier best (same rule as the letter's record win)."""
    found = []
    for category, label, ranked in _iter_ranked(build_personal_records(conn, today=through)):
        steps = ranked.get("progression") or []
        before = [step for step in steps if step["date"][:10] < start.isoformat()]
        inside = [step for step in steps if start.isoformat() <= step["date"][:10] <= through.isoformat()]
        if before and inside:
            found.append({"date": inside[-1]["date"][:10], "name": f"{category} {label}", "display": inside[-1]["display"],
                          "previous": before[-1]["display"]})
    return sorted(found, key=lambda item: item["date"])


def _weight(conn: sqlite3.Connection, start: date, through: date) -> dict:
    """7-day averages at each weigh-in in the month, against the gentle-gain lane."""
    floor = start - timedelta(days=SMOOTHING_DAYS - 1)
    weigh_ins = _weigh_ins(conn, floor.isoformat(), through.isoformat())
    points = []
    for item in weigh_ins:
        if item["date"] < start.isoformat():
            continue
        window = (date.fromisoformat(item["date"]) - timedelta(days=SMOOTHING_DAYS - 1)).isoformat()
        values = [other["kg"] for other in weigh_ins if window <= other["date"] <= item["date"]]
        points.append({"date": item["date"], "kg": item["kg"], "avg_kg": round(sum(values) / len(values), 2)})
    base = {"weigh_ins": points, "lane_pct_per_week": [GAIN_PCT_MIN, GAIN_PCT_MAX]}
    span = (date.fromisoformat(points[-1]["date"]) - date.fromisoformat(points[0]["date"])).days if points else 0
    if len(points) < MIN_WEIGH_INS or span < MIN_WEIGHT_SPAN_DAYS:
        return {**base, "available": False, "needed": MIN_WEIGH_INS}
    first, last = points[0]["avg_kg"], points[-1]["avg_kg"]
    kg_per_week = (last - first) / span * 7
    pct = kg_per_week / first * 100
    status = "fast_gain" if pct > GAIN_PCT_MAX else "gentle_gain" if pct >= GAIN_PCT_MIN else "flat" if pct > -GAIN_PCT_MIN else "losing"
    return {
        **base,
        "available": True,
        "status": status,
        "start_kg": first,
        "end_kg": last,
        "change_kg": round(last - first, 2),
        "kg_per_week": round(kg_per_week, 2),
        "pct_per_week": round(pct, 2),
        "lane_kg_per_week": [round(first * GAIN_PCT_MIN / 100, 2), round(first * GAIN_PCT_MAX / 100, 2)],
    }


def _best_e1rm(sessions: list[dict], start: str, end: str) -> tuple[dict[str, float], dict[str, int]]:
    best: dict[str, float] = {}
    sets: dict[str, int] = {}
    for session in sessions:
        if not start <= session["workout_date"][:10] <= end:
            continue
        for exercise in session.get("exercises", []):
            name = exercise.get("exercise_name") or ""
            for item in exercise.get("sets", []):
                if item.get("is_warmup") or not item.get("weight_kg") or not item.get("reps"):
                    continue
                best[name] = max(best.get(name, 0), epley_1rm(float(item["weight_kg"]), int(item["reps"])))
                sets[name] = sets.get(name, 0) + 1
    return best, sets


def _lift_days(conn: sqlite3.Connection, start: date, through: date) -> list[dict]:
    """Lift days in each Monday-to-Sunday week that touches the month, for the 3x-a-week anchor."""
    first = start - timedelta(days=start.weekday())
    last = through + timedelta(days=6 - through.weekday())
    rows = conn.execute(
        "SELECT DISTINCT substr(date, 1, 10) AS day FROM activities WHERE type = 'WeightTraining' "
        "AND substr(date, 1, 10) BETWEEN ? AND ? AND (workout_intent IS NULL OR workout_intent NOT IN ('recovery', 'mobility'))",
        (first.isoformat(), min(last, through).isoformat()),
    ).fetchall()
    lifted = {row["day"] for row in rows}
    sick = sick_dates(conn)
    weeks = []
    week = first
    while week <= through:
        keys = [(week + timedelta(days=offset)).isoformat() for offset in range(7)]
        weeks.append({
            "week_start": week.isoformat(),
            "week_number": week.isocalendar()[1],
            "days": sum(key in lifted for key in keys),
            "sick": any(key in sick for key in keys),
        })
        week += timedelta(weeks=1)
    return weeks


def _strength(conn: sqlite3.Connection, start: date, through: date, previous_start: date) -> dict:
    sessions = _session_index(conn)
    now, sets = _best_e1rm(sessions, start.isoformat(), through.isoformat())
    before, _ = _best_e1rm(sessions, previous_start.isoformat(), (start - timedelta(days=1)).isoformat())
    lifts = []
    for name in now:
        if name not in before:
            continue
        delta = now[name] - before[name]
        trend = "up" if delta >= HELD_KG else "down" if delta <= -HELD_KG else "held"
        lifts.append({"name": name, "e1rm_kg": round(now[name], 1), "previous_kg": round(before[name], 1),
                      "change_kg": round(delta, 1), "trend": trend, "sets": sets[name]})
    lifts.sort(key=lambda item: (-item["sets"], item["name"]))
    lift_days = _lift_days(conn, start, through)
    in_month = {row["day"] for row in conn.execute(
        "SELECT DISTINCT substr(date, 1, 10) AS day FROM activities WHERE type = 'WeightTraining' AND substr(date, 1, 10) BETWEEN ? AND ? "
        "AND (workout_intent IS NULL OR workout_intent NOT IN ('recovery', 'mobility'))",
        (start.isoformat(), through.isoformat()),
    ).fetchall()}
    return {
        "up": sum(item["trend"] == "up" for item in lifts),
        "held": sum(item["trend"] == "held" for item in lifts),
        "down": sum(item["trend"] == "down" for item in lifts),
        "top": lifts[:TOP_LIFTS],
        "dropped": sorted((item for item in lifts if item["trend"] == "down"), key=lambda item: item["change_kg"]),
        "lift_days": len(in_month),
        "weeks": lift_days,
        "per_week_target": LIFTS_PER_WEEK,
    }


def _rides(conn: sqlite3.Connection, start: date, through: date, previous_start: date, today: date) -> dict:
    def minutes_by(rides: list[dict]) -> dict[str, int]:
        totals = {key: 0 for key in RIDE_INTENSITIES}
        for ride in rides:
            totals[ride["type"] if ride["type"] in totals else "z2"] += ride["minutes"]
        return totals

    rides = _classified_rides(conn, start.isoformat(), through.isoformat(), today)
    previous = _classified_rides(conn, previous_start.isoformat(), (start - timedelta(days=1)).isoformat(), today)
    hiking = conn.execute(
        "SELECT COALESCE(SUM(duration_min), 0) FROM activities WHERE type = 'Hike' AND substr(date, 1, 10) BETWEEN ? AND ?",
        (start.isoformat(), through.isoformat()),
    ).fetchone()[0]
    return {
        "rides": len(rides),
        "minutes": sum(ride["minutes"] for ride in rides),
        "by_intensity": minutes_by(rides),
        "previous_minutes": sum(ride["minutes"] for ride in previous),
        "previous_by_intensity": minutes_by(previous),
        "hiking_minutes": round(float(hiking or 0)),
    }


def _run(conn: sqlite3.Connection, month: str, previous_month: str, through: date) -> Optional[dict]:
    fitness = build_running_fitness(conn, today=through)
    vdot = fitness.get("vdot") or {}
    if not vdot.get("current"):
        return None
    timeline = {item["month"]: item for item in fitness.get("timeline") or []}
    this, before = timeline.get(month, {}), timeline.get(previous_month, {})
    key = "hr_vdot" if vdot.get("basis") == "heart_rate" else "effort_vdot"
    last_known = ((vdot.get("estimates") or {}).get("heart_rate") or {}).get("last_known") or {}
    return {
        "vdot": vdot["current"],
        "basis": vdot.get("basis"),
        "peak": (vdot.get("peak") or {}).get("vdot"),
        "share_of_peak_pct": vdot.get("share_of_peak_pct"),
        "projected": vdot.get("projected"),
        "runs": this.get("runs", 0),
        "km": this.get("km", 0),
        "previous_vdot": before.get(key),
        "last_estimate_date": last_known.get("date"),
    }


def _letter(conn: sqlite3.Connection, month: str, today: date) -> Optional[dict]:
    row = conn.execute("SELECT letter_json FROM monthly_letters WHERE month = ?", (month,)).fetchone()
    if row:
        letter = json.loads(row["letter_json"])
    else:
        try:
            letter = build_monthly_letter(conn, month, today=today)
        except ValueError:
            return None
    strip = lambda item: {key: item.get(key) for key in ("kind", "source", "headline", "detail") if item.get(key) is not None}
    return {"wins": [strip(win) for win in letter.get("wins") or []],
            "focus": strip(letter["focus"]) if letter.get("focus") else None}


def build_month_report(conn: sqlite3.Connection, month: Optional[str] = None, today: Optional[date] = None) -> dict[str, Any]:
    today = today or datetime.now().date()
    month = month or today.strftime("%Y-%m")
    start, end = _bounds(month)
    if start > today:
        raise ValueError("That month has not started yet")
    finished = end < today
    through = min(end, today)
    previous_start = _shift(start, -1)
    previous_month = previous_start.strftime("%Y-%m")
    next_start = _shift(start, 1)

    totals = _totals(conn, start, through)
    totals["movement_minutes"] = round(float(conn.execute(
        "SELECT COALESCE(SUM(duration_min), 0) FROM activities WHERE substr(date, 1, 10) BETWEEN ? AND ?",
        (start.isoformat(), through.isoformat()),
    ).fetchone()[0] or 0))
    totals["elapsed_days"] = (through - start).days + 1
    totals["days"] = (end - start).days + 1
    prior = _prior_average(conn, start)
    if prior:
        prior["minutes_to_date"] = round(prior["minutes"] * totals["elapsed_days"] / totals["days"], 1)

    records = _records(conn, start, through)
    letter = _letter(conn, month, today) if finished else None
    return {
        "month": month,
        "label": _label(start),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "finished": finished,
        "previous_month": previous_month,
        "next_month": next_start.strftime("%Y-%m") if next_start <= today else None,
        "totals": totals,
        "prior_average": prior,
        "streak_days": _streak(conn, through, today),
        "plan": _plan_done(conn, start, through, today),
        "days": _days(conn, start, end, through, records),
        "records": records,
        "weight": _weight(conn, start, through),
        "strength": _strength(conn, start, through, previous_start),
        "rides": _rides(conn, start, through, previous_start, today),
        "run": _run(conn, month, previous_month, through),
        "wins": letter["wins"] if letter else [],
        "focus": letter["focus"] if letter else None,
    }
