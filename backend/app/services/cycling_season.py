"""This season's outdoor riding, for the strip at the top of the Cycling page.

Outdoor totals run from 1 January to today and sit next to the same stretch
of last year. The monthly bars cover the last twelve months and split each
month's riding hours into outdoor and indoor, so the move to the trainer in
winter and back out in spring reads at a glance. Hours, not km, because a
Zwift kilometre is not a road kilometre.

Outdoor means Ride or GravelRide without Strava's trainer flag; indoor is
VirtualRide or a Ride recorded on a trainer.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any, Optional

RIDE_TYPES = ("Ride", "GravelRide", "VirtualRide")


def _same_day_last_year(day: date) -> date:
    try:
        return day.replace(year=day.year - 1)
    except ValueError:  # 29 February
        return day.replace(year=day.year - 1, day=28)


def _totals(rides: list[dict]) -> dict[str, Any]:
    return {
        "rides": len(rides),
        "km": round(sum(ride["km"] for ride in rides), 1),
        "elevation": round(sum(ride["elevation"] for ride in rides)),
        "hours": round(sum(ride["minutes"] for ride in rides) / 60.0, 1),
    }


def _longest(rides: list[dict]) -> Optional[dict[str, Any]]:
    if not rides:
        return None
    ride = max(rides, key=lambda item: item["km"])
    if ride["km"] <= 0:
        return None
    return {"id": ride["id"], "date": ride["day"], "name": ride["name"], "km": round(ride["km"], 1), "elevation": round(ride["elevation"])}


def build_cycling_season(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, Any]:
    today = today or date.today()
    last_year_today = _same_day_last_year(today)
    first_month = date(today.year - 1, today.month + 1, 1) if today.month < 12 else date(today.year, 1, 1)
    since = min(date(today.year - 1, 1, 1), first_month)
    rows = conn.execute(
        f"""
        SELECT a.id, substr(a.date, 1, 10) AS day, a.type, a.name,
               COALESCE(a.distance_km, 0) AS km, COALESCE(a.duration_min, 0) AS minutes,
               COALESCE(a.elevation_m, 0) AS elevation,
               COALESCE(json_extract(d.detail_json, '$.trainer'), 0) AS trainer
        FROM activities a
        LEFT JOIN activity_details d ON d.activity_id = a.id
        WHERE a.type IN ({','.join('?' * len(RIDE_TYPES))}) AND substr(a.date, 1, 10) BETWEEN ? AND ?
        ORDER BY a.date
        """,
        (*RIDE_TYPES, since.isoformat(), today.isoformat()),
    ).fetchall()

    rides = []
    for row in rows:
        ride = dict(row)
        ride["outdoor"] = ride["type"] != "VirtualRide" and ride["trainer"] not in (1, True, "true")
        rides.append(ride)
    outdoor = [ride for ride in rides if ride["outdoor"]]
    this_year = [ride for ride in outdoor if ride["day"] >= f"{today.year}-01-01"]
    last_year = [ride for ride in outdoor if f"{today.year - 1}-01-01" <= ride["day"] <= last_year_today.isoformat()]

    months = []
    year, month = first_month.year, first_month.month
    for _ in range(12):
        prefix = f"{year:04d}-{month:02d}"
        in_month = [ride for ride in rides if ride["day"].startswith(prefix)]
        months.append({
            "month": prefix,
            "outdoor_hours": round(sum(r["minutes"] for r in in_month if r["outdoor"]) / 60.0, 1),
            "indoor_hours": round(sum(r["minutes"] for r in in_month if not r["outdoor"]) / 60.0, 1),
            "outdoor_km": round(sum(r["km"] for r in in_month if r["outdoor"])),
            "indoor_km": round(sum(r["km"] for r in in_month if not r["outdoor"])),
        })
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)

    return {
        "as_of": today.isoformat(),
        "year": today.year,
        "outdoor": _totals(this_year),
        "last_year": _totals(last_year),
        "longest": _longest(this_year),
        "longest_last_year": _longest(last_year),
        "months": months,
    }
