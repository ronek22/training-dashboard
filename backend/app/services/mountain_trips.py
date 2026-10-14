"""Mountain trips: a run of consecutive days tagged Mountains, recapped as one memory.

A trip is found from the life-load tags (the same "mountains" tag the re-entry window reads) and
holds the hikes, walks and trail runs logged on its days; a tagged run with none of them is only
an upcoming or empty trip, not a recap. Its recap adds the days up (distance, ascent, hours on
foot), takes new trail and first summits from the trail coverage when the hike's GPS track is in
a mapped range, draws every track on one map and gives each day its highlight and profile.
Everything is read from data the app already keeps; there is no new tracking.

Each trip is addressed by its first day (``/mountains/trips/2026-10-19``).
"""
import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Optional

from ..repositories import trails as trail_repo
from .life_load import get_life_load_days
from .trail_coverage import REGIONS, Projection, thin_track

ON_FOOT = ("Hike", "Walk", "TrailRun")
TRACK_SPACING_M = 25  # Enough for a week of tracks on one map and a day's profile.


def _today(today: Optional[date]) -> date:
    return today or datetime.now().date()


def _runs(conn: sqlite3.Connection) -> list[tuple[date, date]]:
    """Every run of consecutive Mountains days, oldest first."""
    tagged = sorted(date.fromisoformat(key) for key, item in get_life_load_days(conn).items() if "mountains" in item["tags"])
    runs: list[list[date]] = []
    for day in tagged:
        if runs and day - runs[-1][1] == timedelta(days=1):
            runs[-1][1] = day
        else:
            runs.append([day, day])
    return [(first, last) for first, last in runs]


def _activities(conn: sqlite3.Connection, first: date, last: date) -> list[dict]:
    marks = ",".join("?" for _ in ON_FOOT)
    rows = conn.execute(
        f"SELECT id, substr(date, 1, 10) AS day, type, name, distance_km, duration_min, elevation_m FROM activities "
        f"WHERE substr(date, 1, 10) BETWEEN ? AND ? AND type IN ({marks}) ORDER BY date, id",
        (first.isoformat(), last.isoformat(), *ON_FOOT),
    ).fetchall()
    return [dict(row) for row in rows]


def _sums(activities: list[dict]) -> dict:
    return {
        "distance_km": round(sum(a["distance_km"] or 0 for a in activities), 1),
        "ascent_m": round(sum(a["elevation_m"] or 0 for a in activities)),
        "hours": round(sum(a["duration_min"] or 0 for a in activities) / 60, 1),
    }


def _summary(first: date, last: date, activities: list[dict], today: date) -> dict:
    return {
        "start_date": first.isoformat(),
        "end_date": last.isoformat(),
        "days": (last - first).days + 1,
        "hike_days": len({a["day"] for a in activities}),
        "hikes": len(activities),
        "ongoing": last >= today,
        "url": f"/mountains/trips/{first.isoformat()}",
        **_sums(activities),
    }


def list_trips(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    """Trips with at least one hike, newest first, plus tagged runs still ahead with none yet."""
    day = _today(today)
    trips, upcoming = [], []
    for first, last in reversed(_runs(conn)):
        activities = _activities(conn, first, last)
        if activities:
            trips.append(_summary(first, last, activities, day))
        elif last >= day:
            upcoming.append({"start_date": first.isoformat(), "end_date": last.isoformat(), "days": (last - first).days + 1})
    return {"trips": trips, "upcoming": list(reversed(upcoming))}


def trip_for_date(conn: sqlite3.Connection, day: str) -> Optional[tuple[date, date]]:
    """The tagged run that contains `day`, if any."""
    target = date.fromisoformat(day)
    return next(((first, last) for first, last in _runs(conn) if first <= target <= last), None)


def _track(conn: sqlite3.Connection, activity_id: str) -> tuple[Optional[str], list]:
    """(mapped region, [[lat, lon, alt]]) from the trail sync, else from the activity's streams."""
    try:
        row = conn.execute("SELECT region, latlng_json FROM mountain_tracks WHERE activity_id = ?", (activity_id,)).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row:
        latlng, altitude, region = json.loads(row["latlng_json"]), None, row["region"]
    else:
        region = None
        detail = conn.execute("SELECT streams_json FROM activity_details WHERE activity_id = ?", (activity_id,)).fetchone()
        streams = json.loads(detail["streams_json"] or "{}") if detail else {}
        latlng = (streams.get("latlng") or {}).get("data") or []
        altitude = (streams.get("altitude") or {}).get("data") or None
    if len(latlng) < 2:
        return region, []
    projection = Projection(latlng[0][0])
    return region, thin_track(latlng, TRACK_SPACING_M, projection, altitude)


def _coverage(conn: sqlite3.Connection, regions: set[str], ids: set[str]) -> tuple[dict[str, dict], list[dict]]:
    """Per activity: trail km walked for the first time on it; and every place the trip reached."""
    first_km: dict[str, float] = {}
    reached: list[dict] = []
    for region in regions:
        try:
            sections = trail_repo.list_sections(conn, region)
            pois = trail_repo.list_pois(conn, region)
        except sqlite3.OperationalError:
            continue
        for s in sections:
            if s["status"] == "done" and s["walked_by"] and s["walked_by"][0] in ids:
                first_km[s["walked_by"][0]] = first_km.get(s["walked_by"][0], 0) + s["length_m"] / 1000
        for p in pois:
            here = [activity for activity in p["visited_by"] if activity in ids]
            if here:
                reached.append({
                    "name": p["name"], "kind": p["kind"], "ele": p["ele"], "lat": p["lat"], "lon": p["lon"],
                    "activity_id": here[0], "first_time": p["visited_by"][0] in ids,
                })
    return {key: round(value, 1) for key, value in first_km.items()}, reached


def _highlight(places: list[dict], activities: list[dict]) -> Optional[dict]:
    """The day's top: its highest summit, else its highest named place, else the longest outing."""
    for kinds in (("peak",), ("pass", "hut")):
        found = [p for p in places if p["kind"] in kinds]
        if found:
            top = max(found, key=lambda p: p["ele"] or 0)
            return {"kind": top["kind"], "name": top["name"], "ele": top["ele"], "first_time": top["first_time"]}
    if activities:
        longest = max(activities, key=lambda a: a["distance_km"] or 0)
        return {"kind": "activity", "name": longest["name"], "ele": None, "first_time": False}
    return None


def _season_ascent(conn: sqlite3.Connection, year: int) -> int:
    row = conn.execute("SELECT COALESCE(SUM(elevation_m), 0) FROM activities WHERE substr(date, 1, 4) = ?", (str(year),)).fetchone()
    return round(row[0] or 0)


def build_trip_recap(conn: sqlite3.Connection, start_date: str, today: Optional[date] = None) -> Optional[dict[str, Any]]:
    """The recap for the trip whose tagged run contains `start_date`; None without a trip or hikes."""
    run = trip_for_date(conn, start_date)
    if not run:
        return None
    first, last = run
    activities = _activities(conn, first, last)
    if not activities:
        return None

    tracks: dict[str, list] = {}
    regions: set[str] = set()
    for activity in activities:
        region, points = _track(conn, activity["id"])
        tracks[activity["id"]] = points
        if region:
            regions.add(region)
    ids = {a["id"] for a in activities}
    new_km, reached = _coverage(conn, regions, ids)

    days = []
    for offset in range((last - first).days + 1):
        day = (first + timedelta(days=offset)).isoformat()
        on_day = [a for a in activities if a["day"] == day]
        day_ids = {a["id"] for a in on_day}
        places = [p for p in reached if p["activity_id"] in day_ids]
        days.append({
            "date": day,
            "number": offset + 1,
            "rest": not on_day,
            **_sums(on_day),
            "new_trail_km": round(sum(new_km.get(a["id"], 0) for a in on_day), 1) if regions else None,
            "highlight": _highlight(places, on_day),
            "summits": sorted(
                ({"name": p["name"], "ele": p["ele"], "first_time": p["first_time"]} for p in places if p["kind"] == "peak"),
                key=lambda p: -(p["ele"] or 0),
            ),
            "activities": [
                {
                    "id": a["id"], "type": a["type"], "name": a["name"], "distance_km": a["distance_km"],
                    "duration_min": a["duration_min"], "elevation_m": a["elevation_m"], "track": tracks[a["id"]],
                }
                for a in on_day
            ],
        })

    totals = _summary(first, last, activities, _today(today))
    peaks = [p for p in reached if p["kind"] == "peak"]
    totals["new_trail_km"] = round(sum(new_km.values()), 1) if regions else None
    totals["summits"] = len(peaks)
    totals["new_summits"] = sum(1 for p in peaks if p["first_time"])
    highest = max((point[2] for points in tracks.values() for point in points if len(point) > 2 and point[2] is not None), default=None)
    totals["highest_m"] = round(highest) if highest is not None else None

    # Share of the calendar year's climbing (all sports), like the Season in review totals.
    season_m = _season_ascent(conn, first.year)
    season = {
        "year": first.year,
        "ascent_m": season_m,
        "share_pct": round(totals["ascent_m"] / season_m * 100, 1) if season_m else None,
        "url": f"/season/{first.year}",
    }
    return {
        "trip": totals,
        "regions": [{"key": key, "name": REGIONS[key]["name"], "url": f"/mountains/{key}"} for key in sorted(regions) if key in REGIONS],
        "season": season,
        "days": days,
        "places": [{k: p[k] for k in ("name", "kind", "ele", "lat", "lon", "first_time")} for p in reached if p["kind"] != "cave"],
    }
