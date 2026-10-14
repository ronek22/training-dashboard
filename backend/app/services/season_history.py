"""All years side by side: one sport's volume, year by year and month by month.

The companion to the season review. Where the review tells one year's story,
this lays every year of a sport next to the others: a year-by-month grid,
cumulative lines from 1 January and yearly totals. Cycling is split into
outdoor and trainer rides so the shift indoors stays visible.

Every year from the sport's first activity to today is listed, empty years
included, so gaps read as gaps. The running year is marked as not complete.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any, Optional

SPORTS = (
    # key, label, parts as (key, label, activity types), metrics shown
    ("ride", "Cycling", (("outdoor", "Outdoor", ("Ride", "GravelRide")), ("trainer", "Trainer", ("VirtualRide",))), ("km", "hours", "elevation", "sessions")),
    ("run", "Running", (("run", "Run", ("Run",)),), ("km", "hours", "elevation", "sessions")),
    ("hike", "Hiking", (("hike", "Hike", ("Hike",)),), ("km", "hours", "elevation", "sessions")),
    ("walk", "Walking", (("walk", "Walk", ("Walk",)),), ("km", "hours", "elevation", "sessions")),
    ("strength", "Strength", (("strength", "Strength", ("WeightTraining",)),), ("hours", "sessions")),
)
METRICS = {
    "km": {"label": "Distance", "unit": "km"},
    "hours": {"label": "Time", "unit": "h"},
    "elevation": {"label": "Climbing", "unit": "m"},
    "sessions": {"label": "Sessions", "unit": ""},
}


def _empty() -> dict[str, float]:
    return {"km": 0.0, "hours": 0.0, "elevation": 0.0, "sessions": 0}


def _add(into: dict[str, float], km: float, minutes: float, elevation: float, sessions: int = 1) -> None:
    into["km"] += km
    into["hours"] += minutes / 60.0
    into["elevation"] += elevation
    into["sessions"] += sessions


def _rounded(values: dict[str, float], metrics: tuple[str, ...]) -> dict[str, float]:
    out = {}
    for metric in metrics:
        value = values[metric]
        out[metric] = int(value) if metric == "sessions" else round(value) if metric == "elevation" else round(value, 1)
    return out


def _sport(key: str):
    for sport in SPORTS:
        if sport[0] == key:
            return sport
    raise ValueError(f"Unknown sport: {key}")


def build_season_history(conn: sqlite3.Connection, sport: str = "ride", today: Optional[date] = None) -> dict[str, Any]:
    today = today or date.today()
    key, label, parts, metrics = _sport(sport)
    part_of = {kind: part_key for part_key, _, kinds in parts for kind in kinds}
    kinds = tuple(part_of)
    rows = conn.execute(
        f"SELECT substr(date, 1, 10) AS day, type, COALESCE(distance_km, 0) AS km, COALESCE(duration_min, 0) AS minutes, "
        f"COALESCE(elevation_m, 0) AS elevation FROM activities "
        f"WHERE type IN ({','.join('?' * len(kinds))}) AND substr(date, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' AND substr(date, 1, 10) <= ? "
        f"ORDER BY date",
        (*kinds, today.isoformat()),
    ).fetchall()

    base = {
        "sport": key, "label": label, "as_of": today.isoformat(),
        "sports": [{"key": item[0], "label": item[1]} for item in SPORTS],
        "parts": [{"key": part_key, "label": part_label} for part_key, part_label, _ in parts],
        "metrics": [{"key": metric, **METRICS[metric]} for metric in metrics],
    }
    if not rows:
        return {**base, "years": [], "best": {}}

    first = int(rows[0]["day"][:4])
    years: dict[int, dict[str, Any]] = {
        year: {
            "total": _empty(),
            "parts": {part_key: _empty() for part_key, _, _ in parts},
            "months": [{"total": _empty(), "parts": {part_key: _empty() for part_key, _, _ in parts}} for _ in range(12)],
            "days": {},
        }
        for year in range(first, today.year + 1)
    }
    for row in rows:
        year, month = int(row["day"][:4]), int(row["day"][5:7])
        part = part_of[row["type"]]
        item = years[year]
        values = (float(row["km"]), float(row["minutes"]), float(row["elevation"]))
        _add(item["total"], *values)
        _add(item["parts"][part], *values)
        _add(item["months"][month - 1]["total"], *values)
        _add(item["months"][month - 1]["parts"][part], *values)
        _add(item["days"].setdefault(row["day"], _empty()), *values)

    result = []
    for year in sorted(years, reverse=True):
        item = years[year]
        result.append({
            "year": year,
            "complete": year < today.year,
            "total": _rounded(item["total"], metrics),
            "parts": {part: _rounded(values, metrics) for part, values in item["parts"].items()},
            "months": [
                {"month": index + 1, "total": _rounded(month["total"], metrics),
                 "parts": {part: _rounded(values, metrics) for part, values in month["parts"].items()}}
                for index, month in enumerate(item["months"])
            ],
            # Active days only, for the cumulative lines: [day, km, hours, elevation, sessions].
            "days": [
                [day, round(values["km"], 2), round(values["hours"], 3), round(values["elevation"]), int(values["sessions"])]
                for day, values in sorted(item["days"].items())
            ],
        })

    best = {}
    for metric in metrics:
        top = max(result, key=lambda entry: entry["total"][metric])
        if top["total"][metric] > 0:
            best[metric] = {"year": top["year"], "value": top["total"][metric]}
    return {**base, "years": result, "best": best}
