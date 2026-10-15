"""Milestones worth a one-time celebration: long daily streaks, lift-3x weeks in a row and year km.

Detection reads existing data only. The daily streak counts days like the Records wall
(any activity or finished guided session, so short recovery days keep it alive). A lift week
counts when it has three strength sessions, the anchor "lift three times per week" goal. Year
km uses the Dashboard year-chart sports (Ride + VirtualRide, Run).

A milestone reached in the last ``CELEBRATE_WITHIN_DAYS`` days and not yet seen is offered
as a full-screen celebration once; every milestone stays on the Records shelf to reopen.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from typing import Any, Optional

from ..repositories.settings import get_setting_value, set_setting_value
from .guided_sessions import guided_completion_dates
from .personal_records import active_day_runs

STREAK_DAYS = (100, 200, 300, 365, 500, 1000)
LIFT_SESSIONS_PER_WEEK = 3
LIFT_WEEKS = (4, 8, 12, 26, 52)
YEAR_KM = {
    "ride": {"label": "Riding", "types": ("Ride", "VirtualRide"), "steps": (1000, 2500, 5000, 7500, 10000, 15000)},
    "run": {"label": "Running", "types": ("Run",), "steps": (100, 250, 500, 1000, 1500, 2000)},
}
CELEBRATE_WITHIN_DAYS = 14
LIGHT_DAY_MIN = 30
SEEN_KEY = "milestones_seen"
SPORTS = {"Ride": "ride", "VirtualRide": "ride", "Run": "run", "WeightTraining": "strength", "Hike": "hike", "Walk": "walk"}


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _streak_milestones(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    items = []
    for start, end in active_day_runs(conn):
        length = (end - start).days + 1
        for days in STREAK_DAYS:
            if length < days:
                break
            items.append({
                "id": f"streak-{days}-{start.isoformat()}", "kind": "streak", "value": days, "unit": "days",
                "title": f"{days}-day streak", "subtitle": f"{days} days in a row with training since {start:%-d %b %Y}",
                "start": start.isoformat(), "reached_on": (start + timedelta(days=days - 1)).isoformat(),
            })
    return items


def _lift_weeks(conn: sqlite3.Connection) -> list[tuple[date, date]]:
    """Weeks with three strength sessions, as (Monday, the day the third session landed)."""
    by_week: dict[date, list[date]] = {}
    for (raw,) in conn.execute("SELECT substr(date, 1, 10) FROM activities WHERE type = 'WeightTraining' ORDER BY date"):
        day = date.fromisoformat(raw)
        by_week.setdefault(_monday(day), []).append(day)
    return [(monday, sorted(days)[LIFT_SESSIONS_PER_WEEK - 1]) for monday, days in sorted(by_week.items())
            if len(days) >= LIFT_SESSIONS_PER_WEEK]


def _lift_runs(conn: sqlite3.Connection) -> list[list[tuple[date, date]]]:
    runs: list[list[tuple[date, date]]] = []
    for week in _lift_weeks(conn):
        if runs and week[0] == runs[-1][-1][0] + timedelta(weeks=1):
            runs[-1].append(week)
        else:
            runs.append([week])
    return runs


def _lift_milestones(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    items = []
    for run in _lift_runs(conn):
        start = run[0][0]
        for weeks in LIFT_WEEKS:
            if len(run) < weeks:
                break
            items.append({
                "id": f"lift3x-{weeks}-{start.isoformat()}", "kind": "lift", "value": weeks, "unit": "weeks",
                "title": f"Lift 3× for {weeks} weeks", "subtitle": f"{weeks} weeks in a row with {LIFT_SESSIONS_PER_WEEK}+ strength sessions",
                "start": start.isoformat(), "reached_on": run[weeks - 1][1].isoformat(),
            })
    return items


def _year_km_milestones(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    items = []
    for sport, spec in YEAR_KM.items():
        placeholders = ",".join("?" for _ in spec["types"])
        rows = conn.execute(
            f"SELECT id, name, substr(date, 1, 10) AS day, distance_km FROM activities WHERE type IN ({placeholders}) "
            "AND distance_km > 0 ORDER BY date, id",
            spec["types"],
        ).fetchall()
        year, total, steps = None, 0.0, []
        for row in rows:
            day = date.fromisoformat(row["day"])
            if day.year != year:
                year, total, steps = day.year, 0.0, list(spec["steps"])
            total += float(row["distance_km"])
            while steps and total >= steps[0]:
                km = steps.pop(0)
                items.append({
                    "id": f"year-{year}-{sport}-{km}", "kind": "year_km", "sport": sport, "value": km, "unit": "km",
                    "title": f"{km:,} km of {spec['label'].lower()} in {year}",
                    "subtitle": f"Crossed on {row['name'] or 'an activity'}",
                    "start": date(year, 1, 1).isoformat(), "reached_on": day.isoformat(),
                    "activity_id": row["id"],
                })
    return items


def _seen(conn: sqlite3.Connection) -> dict[str, str]:
    try:
        value = json.loads(get_setting_value(conn, SEEN_KEY) or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def detect_milestones(conn: sqlite3.Connection, today: Optional[date] = None) -> list[dict[str, Any]]:
    """Every milestone reached up to ``today``, newest first, with whether it was celebrated."""
    today = today or date.today()
    seen = _seen(conn)
    items = [item for item in _streak_milestones(conn) + _lift_milestones(conn) + _year_km_milestones(conn)
             if item["reached_on"] <= today.isoformat()]
    order = {"streak": 0, "lift": 1, "year_km": 2}
    items.sort(key=lambda item: (item["reached_on"], -order[item["kind"]], item["value"]), reverse=True)
    window = (today - timedelta(days=CELEBRATE_WITHIN_DAYS)).isoformat()
    for item in items:
        item["seen_on"] = seen.get(item["id"])
        item["celebrate"] = item["seen_on"] is None and item["reached_on"] >= window
    return items


def _next_up(conn: sqlite3.Connection, today: date) -> list[dict[str, Any]]:
    upcoming = []
    runs = active_day_runs(conn)
    if runs and runs[-1][1] >= today - timedelta(days=1):
        current = (runs[-1][1] - runs[-1][0]).days + 1
        target = next((days for days in STREAK_DAYS if days > current), None)
        if target:
            upcoming.append({"kind": "streak", "label": f"{target}-day streak", "current": current, "target": target,
                             "to_go": target - current, "unit": "days", "on": (runs[-1][1] + timedelta(days=target - current)).isoformat()})
    lift_runs = _lift_runs(conn)
    if lift_runs and lift_runs[-1][-1][0] >= _monday(today) - timedelta(weeks=1):
        current = len(lift_runs[-1])
        target = next((weeks for weeks in LIFT_WEEKS if weeks > current), None)
        if target:
            upcoming.append({"kind": "lift", "label": f"Lift 3× for {target} weeks", "current": current, "target": target,
                             "to_go": target - current, "unit": "weeks"})
    for sport, spec in YEAR_KM.items():
        placeholders = ",".join("?" for _ in spec["types"])
        total = conn.execute(
            f"SELECT COALESCE(SUM(distance_km), 0) FROM activities WHERE type IN ({placeholders}) AND substr(date, 1, 4) = ? AND substr(date, 1, 10) <= ?",
            (*spec["types"], str(today.year), today.isoformat()),
        ).fetchone()[0]
        target = next((km for km in spec["steps"] if km > total), None)
        if target and total > 0:
            upcoming.append({"kind": "year_km", "label": f"{target:,} km of {spec['label'].lower()} in {today.year}",
                             "current": round(total), "target": target, "to_go": round(target - total), "unit": "km"})
    return upcoming


def build_milestones(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, Any]:
    today = today or date.today()
    items = detect_milestones(conn, today)
    pending = next((item for item in items if item["celebrate"]), None)
    return {"milestones": items, "pending": pending["id"] if pending else None, "next": _next_up(conn, today)}


def _day_grid(conn: sqlite3.Connection, start: date, end: date, focus: Optional[str] = None) -> list[dict[str, Any]]:
    """Each day of the stretch with its main sport: ``focus`` when done that day, else the longest session."""
    rows = conn.execute(
        "SELECT substr(date, 1, 10) AS day, type, COALESCE(duration_min, 0) AS minutes FROM activities "
        "WHERE substr(date, 1, 10) BETWEEN ? AND ?",
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    best: dict[str, tuple[float, str]] = {}
    minutes: dict[str, float] = {}
    for row in rows:
        minutes[row["day"]] = minutes.get(row["day"], 0) + float(row["minutes"])
        sport = SPORTS.get(row["type"], "other")
        minutes_key = float("inf") if sport == focus else float(row["minutes"])
        if row["day"] not in best or minutes_key > best[row["day"]][0]:
            best[row["day"]] = (minutes_key, sport)
    guided = guided_completion_dates(conn)
    grid = []
    for offset in range((end - start).days + 1):
        iso = (start + timedelta(days=offset)).isoformat()
        sport = best[iso][1] if iso in best else "guided" if iso in guided else None
        grid.append({"date": iso, "sport": sport, "light": sport is not None and minutes.get(iso, 0) < LIGHT_DAY_MIN})
    return grid


def _highlights(conn: sqlite3.Connection, start: date, end: date, grid: list[dict[str, Any]]) -> list[dict[str, Any]]:
    row = conn.execute(
        """
        SELECT COUNT(*) AS sessions, COALESCE(SUM(duration_min), 0) / 60.0 AS hours,
               COALESCE(SUM(CASE WHEN type IN ('Ride','VirtualRide') THEN distance_km END), 0) AS ride_km,
               COALESCE(SUM(CASE WHEN type = 'Run' THEN distance_km END), 0) AS run_km,
               COALESCE(SUM(CASE WHEN type = 'WeightTraining' THEN 1 END), 0) AS lifts,
               COALESCE(SUM(elevation_m), 0) AS climb
        FROM activities WHERE substr(date, 1, 10) BETWEEN ? AND ?
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchone()
    longest = conn.execute(
        "SELECT id, name, distance_km FROM activities WHERE type IN ('Ride','VirtualRide') AND substr(date, 1, 10) BETWEEN ? AND ? "
        "ORDER BY distance_km DESC LIMIT 1",
        (start.isoformat(), end.isoformat()),
    ).fetchone()
    light = sum(1 for day in grid if day["light"])
    items = [
        {"key": "sessions", "label": "sessions", "value": int(row["sessions"])},
        {"key": "hours", "label": "hours moving", "value": round(float(row["hours"]))},
        {"key": "ride_km", "label": "km ridden", "value": round(float(row["ride_km"]))},
        {"key": "run_km", "label": "km run", "value": round(float(row["run_km"]))},
        {"key": "lifts", "label": "strength sessions", "value": int(row["lifts"])},
        {"key": "climb", "label": "m climbed", "value": int(row["climb"])},
        {"key": "light", "label": f"light days under {LIGHT_DAY_MIN} min kept it going", "value": light},
    ]
    if longest and longest["distance_km"]:
        items.append({"key": "longest_ride", "label": f"km longest ride · {longest['name']}", "value": round(float(longest["distance_km"])),
                      "to": f"/activities/{longest['id']}"})
    return [item for item in items if item["value"]]


def milestone_detail(conn: sqlite3.Connection, milestone_id: str, today: Optional[date] = None) -> dict[str, Any]:
    item = next((entry for entry in detect_milestones(conn, today) if entry["id"] == milestone_id), None)
    if item is None:
        raise ValueError(f"Unknown milestone {milestone_id}")
    start, end = date.fromisoformat(item["start"]), date.fromisoformat(item["reached_on"])
    grid = _day_grid(conn, start, end, focus={"lift": "strength", "year_km": item.get("sport")}.get(item["kind"]))
    return {**item, "grid": grid, "highlights": _highlights(conn, start, end, grid)}


def mark_seen(conn: sqlite3.Connection, milestone_id: str, today: Optional[date] = None) -> dict[str, str]:
    seen = _seen(conn)
    seen.setdefault(milestone_id, (today or date.today()).isoformat())
    set_setting_value(conn, SEEN_KEY, json.dumps(seen, sort_keys=True))
    conn.commit()
    return seen
