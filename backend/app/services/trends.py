"""Phone Trends page: recent weeks by sport and the year so far against the same date last year."""

import sqlite3
from collections import Counter
from datetime import date, timedelta
from typing import Any, Optional

# Keys match the iOS Sport enum, so each group takes its sport colour.
GROUPS = ("ride", "strength", "run", "mobility", "other")
GROUP_TYPES = {
    "Ride": "ride", "VirtualRide": "ride",
    "Run": "run",
    "WeightTraining": "strength",
    # Guided rehab routines are saved as "Workout".
    "Walk": "mobility", "Workout": "mobility", "Yoga": "mobility", "PhysicalTherapy": "mobility",
}
# The year card: sport, activity types, unit (km totals by distance, h by time).
YEAR_SPORTS = (
    ("ride", ("Ride", "VirtualRide"), "km"),
    ("strength", ("WeightTraining",), "h"),
    ("run", ("Run",), "km"),
)
WEEKS = 12


def _group(activity_type: str) -> str:
    return GROUP_TYPES.get(activity_type, "other")


def _weeks(conn: sqlite3.Connection, today: date) -> list[dict[str, Any]]:
    first = today - timedelta(days=today.weekday()) - timedelta(weeks=WEEKS - 1)
    rows = conn.execute(
        "SELECT substr(date, 1, 10) AS day, type, COALESCE(duration_min, 0) AS minutes FROM activities "
        "WHERE substr(date, 1, 10) BETWEEN ? AND ?",
        (first.isoformat(), today.isoformat()),
    ).fetchall()
    weeks = [{"start": (first + timedelta(weeks=i)).isoformat(), "minutes": dict.fromkeys(GROUPS, 0.0),
              "types": Counter(), "type_minutes": Counter()} for i in range(WEEKS)]
    for row in rows:
        week = weeks[(date.fromisoformat(row["day"]) - first).days // 7]
        week["minutes"][_group(row["type"])] += float(row["minutes"])
        week["types"][row["type"]] += 1
        week["type_minutes"][row["type"]] += float(row["minutes"])
    out = []
    for week in weeks:
        total = sum(week["minutes"].values())
        top: Optional[dict[str, Any]] = None
        if week["type_minutes"]:
            kind, minutes = week["type_minutes"].most_common(1)[0]
            top = {"type": kind, "sessions": week["types"][kind], "share": round(minutes / total, 2) if total else 0}
        out.append({
            "start": week["start"],
            "hours": {key: round(value / 60.0, 2) for key, value in week["minutes"].items()},
            "sessions": sum(week["types"].values()),
            "top": top,
        })
    return out


def _year(conn: sqlite3.Connection, year: int, types: tuple[str, ...], unit: str, until: Optional[str] = None) -> dict[str, Any]:
    """Monthly totals for a year (km or h), up to ``until`` ("MM-DD") when given."""
    placeholders = ",".join("?" for _ in types)
    rows = conn.execute(
        f"SELECT CAST(substr(date, 6, 2) AS INTEGER) AS month, COUNT(*) AS sessions, "
        f"COALESCE(SUM(distance_km), 0) AS km, COALESCE(SUM(duration_min), 0) AS minutes FROM activities "
        f"WHERE type IN ({placeholders}) AND substr(date, 1, 4) = ? AND substr(date, 6, 5) <= ? GROUP BY month",
        (*types, str(year), until or "12-31"),
    ).fetchall()
    months = [0.0] * 12
    for row in rows:
        months[row["month"] - 1] = float(row["km"]) if unit == "km" else float(row["minutes"]) / 60.0
    return {"total": round(sum(months), 1), "months": [round(value, 1) for value in months]}


def get_trends(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, Any]:
    today = today or date.today()
    until = today.strftime("%m-%d")
    sports = []
    for key, types, unit in YEAR_SPORTS:
        placeholders = ",".join("?" for _ in types)
        last = conn.execute(
            f"SELECT MAX(substr(date, 1, 10)) AS day FROM activities WHERE type IN ({placeholders}) AND substr(date, 1, 10) <= ?",
            (*types, today.isoformat()),
        ).fetchone()["day"]
        previous = _year(conn, today.year - 1, types, unit)
        sports.append({
            "sport": key,
            "unit": unit,
            "total": _year(conn, today.year, types, unit, until)["total"],
            "last_year_to_date": _year(conn, today.year - 1, types, unit, until)["total"],
            "last_year_months": previous["months"],
            "last_date": last,
        })
    return {"today": today.isoformat(), "weeks": _weeks(conn, today), "sports": sports}
