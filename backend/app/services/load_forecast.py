"""Load forecast: where fitness (CTL) and fatigue (ATL) are heading under the current plan.

Past days come from the training-load model in ``dashboard.py`` (power TSS with the FTP valid on
each ride's day, heart-rate TRIMP otherwise, duration as the last resort). The model then runs on
through estimated days, which are always marked ``estimated``:

- the rest of this week: each planned session scored from its plan. A ride with a library workout
  uses that workout's intensity factor, other rides an intensity per ride type, runs the athlete's
  own recent load per minute, lifts and other sessions the same duration rates as logged ones.
- the preview weeks: one weekly load spread evenly over the days. Rides come from the winter arc
  block when there is one (its hours and key rides), else from this week's plan, else from the last
  four weeks. Everything else repeats this week's plan (or the last four weeks). Mountains days
  shrink the rides to the days off the trip and add a trip day each: the athlete's average load on
  past Mountains days in the last ``TRIP_LOOKBACK_DAYS``, else four hours of hiking.

The ramp is the change in fitness from one Sunday to the next. More than ``RAMP_STEEP`` points a
week is flagged as too steep (the upper end of the usual 5-8 CTL/week guidance). In a base,
sweet-spot or VO2 block the full (non-lighter) weeks should build: when they average under
``RAMP_FLAT`` a week, they are flagged as too flat. A maintain block and weeks outside the arc are
only checked for steep ramps. Nothing here is saved.
"""
import json
import math
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from .cycling_workouts import get_cycling_workout, render_cycling_workout
from .dashboard import build_training_load_summary, generic_load_details, strength_load_details
from .life_load import get_life_load_days
from .winter_arc import KEY_RIDES, QUALITY_TYPES, RIDE_TYPES, arc_week, ride_type
from .week_preview import PREVIEW_WEEKS

HISTORY_DAYS = 42
TRIP_LOOKBACK_DAYS = 120
RECENT_WEEKS = 4
CTL_DAYS = 42
ATL_DAYS = 7
RAMP_STEEP = 7.0  # CTL points per week
RAMP_FLAT = 1.0  # CTL points per week, averaged over a build block's full weeks
BUILD_FOCUSES = {"base", "sweet_spot", "vo2"}
# Whole-ride intensity factor for a planned ride without a library workout.
RIDE_IF = {"recovery": 0.55, "z2": 0.68, "sweet_spot": 0.80, "vo2": 0.78}
DEFAULT_RUN_LOAD_PER_MIN = 1.2
TRIP_DAY_HIKE_MIN = 240


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _tss(minutes: float, intensity_factor: float) -> float:
    return max(minutes, 0) / 60 * intensity_factor ** 2 * 100


def _workout(workout_id: Optional[str]) -> Optional[dict]:
    workout = get_cycling_workout(workout_id)
    return render_cycling_workout(workout) if workout else None


def planned_session_load(day: dict, run_rate: float = DEFAULT_RUN_LOAD_PER_MIN) -> dict:
    """Estimated load of one planned session, split into ride and other load."""
    kind = str(day.get("session_type") or "").strip().lower()
    minutes = float(day.get("target_duration_min") or 0)
    if kind in RIDE_TYPES:
        workout = _workout(day.get("cycling_workout_id"))
        if workout:
            return {"ride": _tss(minutes or workout["duration_min"], workout["intensity_factor"]), "other": 0.0}
        return {"ride": _tss(minutes, RIDE_IF.get(ride_type(day) or "z2", RIDE_IF["z2"])), "other": 0.0}
    if kind == "rest" or minutes <= 0:
        return {"ride": 0.0, "other": 0.0}
    if kind == "run":
        return {"ride": 0.0, "other": minutes * run_rate}
    if kind in {"strength", "weighttraining"}:
        return {"ride": 0.0, "other": strength_load_details({"duration_min": minutes})["load"]}
    activity_type = {"recovery": "Walk", "walk": "Walk", "hike": "Hike"}.get(kind, kind.title())
    return {"ride": 0.0, "other": generic_load_details({"type": activity_type, "duration_min": minutes})["load"]}


def arc_ride_load(target: dict) -> float:
    """A block week's rides: its key rides as the library workouts, the rest of the hours at Z2."""
    minutes_left = target["ride_hours"] * 60
    load = 0.0
    for kind in QUALITY_TYPES:
        count = target["ride_mix"].get(kind) or 0
        workout = _workout(KEY_RIDES[kind]["workout_id"]) if count else None
        if not workout:
            continue
        minutes = min(workout["duration_min"] * count, minutes_left)
        load += _tss(minutes, workout["intensity_factor"])
        minutes_left -= minutes
    return load + _tss(minutes_left, RIDE_IF["z2"])


def _plan_days(conn: sqlite3.Connection, week_start: str) -> Optional[list[dict]]:
    row = conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (week_start,)).fetchone()
    return json.loads(row["days_json"]) if row else None


def _run_rate(conn: sqlite3.Connection, history: list[dict]) -> float:
    """The athlete's own run load per minute over the history window."""
    if not history:
        return DEFAULT_RUN_LOAD_PER_MIN
    row = conn.execute(
        "SELECT SUM(duration_min) FROM activities WHERE type = 'Run' AND substr(date, 1, 10) BETWEEN ? AND ?",
        (history[0]["date"], history[-1]["date"]),
    ).fetchone()
    minutes = float(row[0] or 0) if row else 0.0
    load = sum(item["run_load"] for item in history)
    return load / minutes if minutes >= 30 and load > 0 else DEFAULT_RUN_LOAD_PER_MIN


def _recent_week(history: list[dict], this_monday: date) -> dict:
    """Average weekly ride and other load over the last full weeks."""
    start = (this_monday - timedelta(weeks=RECENT_WEEKS)).isoformat()
    days = [item for item in history if start <= item["date"] < this_monday.isoformat()]
    ride = sum(item["ride_load"] for item in days)
    total = sum(item["load"] for item in days)
    return {"ride": ride / RECENT_WEEKS, "other": (total - ride) / RECENT_WEEKS}


def _trip_day_load(history: list[dict], trip_days: set[str]) -> float:
    """Average load on past Mountains days, else a four-hour hike."""
    past = [item["load"] for item in history if item["date"] in trip_days]
    if past and sum(past) > 0:
        return sum(past) / len(past)
    return generic_load_details({"type": "Hike", "duration_min": TRIP_DAY_HIKE_MIN})["load"]


def _step(value: float, load: float, days: int) -> float:
    return value + (load - value) * (1 - math.exp(-1 / days))


def _fmt_day(value: str) -> str:
    return date.fromisoformat(value).strftime("%b %-d")


def _message(weeks: list[dict], start_ctl: float, end_ctl: float, end_date: str, basis: str) -> tuple[str, str]:
    steep = [week for week in weeks if week["flag"] == "steep"]
    if steep:
        week = max(steep, key=lambda item: item["ramp"])
        others = f" ({len(steep) - 1} more week{'s' if len(steep) > 2 else ''} too)" if len(steep) > 1 else ""
        if week["trip_days"]:
            return "steep", (
                f"The mountains week of {_fmt_day(week['week_start'])} raises fitness by ~{week['ramp']:.0f}, above the safe "
                f"{RAMP_STEEP:g} a week{others}: keep the rides around it easy."
            )
        return "steep", (
            f"Week of {_fmt_day(week['week_start'])} raises fitness by ~{week['ramp']:.0f}, above the safe "
            f"{RAMP_STEEP:g} a week{others}: trim its volume or make it lighter."
        )
    flat = [week for week in weeks if week["flag"] == "flat"]
    if flat:
        average = sum(week["ramp"] for week in flat) / len(flat)
        return "flat", (
            f"The {flat[0]['block_label']} weeks barely build fitness ({average:+.1f} a week, under +{RAMP_FLAT:g}): "
            "add some ride time or a key ride to make the block count."
        )
    per_week = (end_ctl - start_ctl) / max(len(weeks), 1)
    trend = "a steady, safe build" if per_week >= RAMP_FLAT else "holding steady" if per_week > -RAMP_FLAT else "easing off"
    load = "your recent load" if basis == "recent" else "the planned load"
    return "ok", f"Fitness {start_ctl:.0f} → ~{end_ctl:.0f} by {_fmt_day(end_date)} ({per_week:+.1f} a week): {trend} at {load}."


def build_load_forecast(conn: sqlite3.Connection, today: Optional[date] = None, weeks: int = PREVIEW_WEEKS) -> dict:
    today = today or datetime.now().date()
    summary = build_training_load_summary(conn, days=TRIP_LOOKBACK_DAYS, today=today)
    long_history = summary["chart"]
    history = long_history[-HISTORY_DAYS:]
    this_monday = _monday(today)
    run_rate = _run_rate(conn, history)
    recent = _recent_week(history, this_monday)

    plan = _plan_days(conn, this_monday.isoformat())
    plan_by_day: dict[str, dict] = {}
    for day in plan or []:
        load = planned_session_load(day, run_rate)
        slot = plan_by_day.setdefault(day["date"][:10], {"ride": 0.0, "other": 0.0})
        slot["ride"] += load["ride"]
        slot["other"] += load["other"]
    plan_week = {
        "ride": sum(item["ride"] for item in plan_by_day.values()),
        "other": sum(item["other"] for item in plan_by_day.values()),
    } if plan else None

    last = this_monday + timedelta(weeks=weeks + 1, days=-1)
    tagged = get_life_load_days(conn, long_history[0]["date"] if long_history else this_monday.isoformat(), last.isoformat())
    trip_days = {key for key, item in tagged.items() if "mountains" in item.get("tags", [])}
    hike_day = _trip_day_load(long_history, trip_days)

    # Daily estimated loads from tomorrow to the last preview Sunday.
    projected_loads: dict[str, float] = {}
    for offset in range(1, (this_monday + timedelta(days=6) - today).days + 1):
        key = (today + timedelta(days=offset)).isoformat()
        if plan is not None:
            item = plan_by_day.get(key, {"ride": 0.0, "other": 0.0})
            projected_loads[key] = item["ride"] + item["other"]
        else:
            projected_loads[key] = (recent["ride"] + recent["other"]) / 7

    week_meta = [{"week_start": this_monday.isoformat(), "kind": "current", "basis": "plan" if plan is not None else "recent", "target": arc_week(conn, this_monday.isoformat())}]
    for index in range(1, weeks + 1):
        start = this_monday + timedelta(weeks=index)
        days = [(start + timedelta(days=offset)).isoformat() for offset in range(7)]
        target = arc_week(conn, start.isoformat())
        base = plan_week or recent
        ride = arc_ride_load(target) if target else base["ride"]
        trip = sum(1 for day in days if day in trip_days)
        week_load = ride * (7 - trip) / 7 + base["other"] + trip * hike_day
        for day in days:
            projected_loads[day] = week_load / 7
        week_meta.append({
            "week_start": start.isoformat(), "kind": "preview", "target": target,
            "basis": "arc" if target else "plan" if plan_week else "recent",
        })

    ctl = history[-1]["ctl"] if history else 0.0
    atl = history[-1]["atl"] if history else 0.0
    ctl_by_day = {item["date"]: item["ctl"] for item in history}
    projection = []
    for key in sorted(projected_loads):
        ctl = _step(ctl, projected_loads[key], CTL_DAYS)
        atl = _step(atl, projected_loads[key], ATL_DAYS)
        ctl_by_day[key] = ctl
        projection.append({"date": key, "load": round(projected_loads[key], 1), "ctl": round(ctl, 1), "atl": round(atl, 1), "estimated": True})

    weeks_out = []
    for meta in week_meta:
        start = date.fromisoformat(meta["week_start"])
        end = (start + timedelta(days=6)).isoformat()
        before = ctl_by_day.get((start - timedelta(days=1)).isoformat(), history[0]["ctl"] if history else 0.0)
        ramp = round(ctl_by_day.get(end, before) - before, 1)
        days_load = [projected_loads.get((start + timedelta(days=offset)).isoformat()) for offset in range(7)]
        actual_load = sum(item["load"] for item in history if meta["week_start"] <= item["date"] <= end)
        target = meta["target"]
        weeks_out.append({
            "week_start": meta["week_start"],
            "week_end": end,
            "kind": meta["kind"],
            "basis": meta["basis"],
            "load": round(actual_load + sum(value for value in days_load if value is not None)),
            "ctl_end": round(ctl_by_day.get(end, before), 1),
            "ramp": ramp,
            "block_label": target["label"] if target else None,
            "block_focus": target["focus"] if target else None,
            "lighter": bool(target and target["lighter"]),
            "trip_days": sum(1 for offset in range(7) if (start + timedelta(days=offset)).isoformat() in trip_days),
            "flag": "steep" if ramp > RAMP_STEEP else None,
        })

    build_weeks = [week for week in weeks_out if week["block_focus"] in BUILD_FOCUSES and not week["lighter"] and not week["flag"]]
    if build_weeks and sum(week["ramp"] for week in build_weeks) / len(build_weeks) < RAMP_FLAT:
        for week in build_weeks:
            week["flag"] = "flat"

    has_history = any(item["load"] > 0 for item in history)
    start_ctl = history[-1]["ctl"] if history else 0.0
    end_date = projection[-1]["date"] if projection else today.isoformat()
    if has_history:
        status, message = _message(weeks_out, start_ctl, ctl, end_date, weeks_out[-1]["basis"])
    else:
        status, message = "unknown", "Not enough logged training to project fitness yet."

    return {
        "today": today.isoformat(),
        "status": status,
        "message": message,
        "thresholds": {"steep_per_week": RAMP_STEEP, "flat_per_week": RAMP_FLAT},
        "current": {"fitness": round(start_ctl, 1), "fatigue": round(history[-1]["atl"], 1) if history else 0.0},
        "ftp": summary["model"]["ftp"],
        "history": [{"date": item["date"], "load": item["load"], "ctl": item["ctl"], "atl": item["atl"]} for item in history],
        "projection": projection,
        "weeks": weeks_out,
    }
