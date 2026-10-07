"""Ascent and descent per trail section, from OpenTopoData's public API (EU-DEM, 25 m).
The public API allows 100 points per request, one request a second and 1000 a day (Open-Meteo
counts every point as a request, 600 a minute, which is far too few for a mountain range).
Points are cached by rounded coordinate, so re-importing a range costs no requests."""
import sqlite3
import time
from typing import Callable, Optional

import httpx

from ..repositories import trails as repo

ELEVATION_URL = "https://api.opentopodata.org/v1/eudem25m"
PROFILE_SPACING_M = 100
BATCH = 100            # points per request
REQUEST_GAP_S = 1.05   # the public API allows one request per second

Lookup = Callable[[list[tuple[float, float]]], list[Optional[float]]]


def opentopodata_elevations(points: list[tuple[float, float]], client: Optional[httpx.Client] = None) -> list[Optional[float]]:
    owned = client is None
    client = client or httpx.Client(timeout=30)
    heights: list[Optional[float]] = []
    try:
        for start in range(0, len(points), BATCH):
            chunk = points[start:start + BATCH]
            if start:
                time.sleep(REQUEST_GAP_S)
            for attempt in range(4):
                response = client.get(ELEVATION_URL, params={"locations": "|".join(f"{lat:.5f},{lon:.5f}" for lat, lon in chunk)})
                if response.status_code == 429 and attempt < 3:
                    time.sleep(2 * (attempt + 1))
                    continue
                response.raise_for_status()
                heights.extend(r.get("elevation") for r in response.json().get("results") or [{}] * len(chunk))
                break
    finally:
        if owned:
            client.close()
    return heights


def _key(lat: float, lon: float) -> tuple[float, float]:
    return round(lat, 4), round(lon, 4)


def apply_section_elevation(conn: sqlite3.Connection, sections: list[dict], projection, sample_polyline, lookup: Lookup = opentopodata_elevations) -> bool:
    """Adds ascent_m / descent_m (in stored coordinate order) and ele_min / ele_max to each section.
    Returns False, leaving the sections untouched, when the elevation service is unavailable."""
    profiles = []
    for section in sections:
        points = sample_polyline([projection.xy(lat, lon) for lat, lon in section["coords"]], PROFILE_SPACING_M)
        profiles.append([_key(*projection.latlon(x, y)) for x, y in points])

    wanted = sorted({key for profile in profiles for key in profile})
    known = repo.cached_elevations(conn, wanted)
    missing = [key for key in wanted if key not in known]
    # Fetch and cache in chunks, so hitting the daily limit keeps what was fetched for next time.
    for start in range(0, len(missing), 1000):
        chunk = missing[start:start + 1000]
        try:
            heights = lookup(chunk)
        except (httpx.HTTPError, ValueError):
            break
        fresh = {key: height for key, height in zip(chunk, heights) if height is not None}
        repo.cache_elevations(conn, fresh)
        conn.commit()
        known.update(fresh)

    for section, profile in zip(sections, profiles):
        heights = [known.get(key) for key in profile]
        if any(height is None for height in heights):
            continue
        rises = [b - a for a, b in zip(heights, heights[1:])]
        section["ascent_m"] = round(sum(r for r in rises if r > 0))
        section["descent_m"] = round(-sum(r for r in rises if r < 0))
        section["ele_min"] = round(min(heights))
        section["ele_max"] = round(max(heights))
    return all(section.get("ascent_m") is not None for section in sections)


def route_profile(conn: sqlite3.Connection, steps: list[tuple[dict, bool]], projection, sample_polyline) -> list[list]:
    """[[lat, lon, ele]] along a route of (section, forward) steps, from the elevation cache only.
    Samples each section exactly as apply_section_elevation did, so every point is a cache hit;
    points that were never fetched get ele None."""
    profiles = []
    for section, forward in steps:
        points = [projection.latlon(x, y) for x, y in sample_polyline([projection.xy(lat, lon) for lat, lon in section["coords"]], PROFILE_SPACING_M)]
        profiles.append(points if forward else points[::-1])
    known = repo.cached_elevations(conn, sorted({_key(*p) for profile in profiles for p in profile}))
    track = []
    for profile in profiles:
        for lat, lon in profile[1:] if track else profile:  # consecutive sections share their junction point
            ele = known.get(_key(lat, lon))
            track.append([round(lat, 5), round(lon, 5), round(ele) if ele is not None else None])
    return track
