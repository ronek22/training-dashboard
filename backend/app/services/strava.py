import math
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Callable, Optional

import httpx
from fastapi import HTTPException


STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
STRAVA_ACTIVITY_STREAMS_URL = "https://www.strava.com/api/v3/activities/{activity_id}/streams"
STRAVA_PAGE_SIZE = 100
STRAVA_STREAM_FETCH_LIMIT = 12
STRAVA_STREAM_RECENT_DAYS = 120


def require_strava_config(get_setting_fn: Callable[[str], Optional[str]]):
    config = {
        "client_id": os.getenv("STRAVA_CLIENT_ID"),
        "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
        "refresh_token": get_setting_fn("strava_refresh_token") or os.getenv("STRAVA_REFRESH_TOKEN"),
    }
    missing = [key for key, value in config.items() if not value]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing Strava configuration: {', '.join(missing)}"
        )
    return config


def parse_strava_date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date: {value}. Use YYYY-MM-DD.") from exc


def seconds_to_pace(seconds_per_km: Optional[float]) -> Optional[str]:
    if not seconds_per_km or seconds_per_km <= 0:
        return None
    total_seconds = int(round(seconds_per_km))
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def classify_activity_type(strava_type: str, sport_type: Optional[str]) -> str:
    normalized = sport_type or strava_type or ""
    mapping = {
        "Run": "Run",
        "Ride": "Ride",
        "VirtualRide": "VirtualRide",
        "Workout": "WeightTraining",
        "WeightTraining": "WeightTraining",
        "Walk": "Walk",
        "Hike": "Hike",
    }
    return mapping.get(normalized, "Run" if strava_type == "Run" else normalized or "Run")


def zone2_from_activity(activity_type: str, avg_hr: Optional[int]) -> bool:
    if not avg_hr:
        return False
    if activity_type == "Run":
        return 150 <= avg_hr <= 162
    if activity_type in {"Ride", "VirtualRide"}:
        return 140 <= avg_hr <= 152
    return False


def build_activity_from_strava(item: dict) -> dict:
    activity_type = classify_activity_type(item.get("type"), item.get("sport_type"))
    distance_m = item.get("distance")
    moving_time_s = item.get("moving_time") or item.get("elapsed_time")
    avg_speed = item.get("average_speed")
    avg_pace = None
    if activity_type == "Run" and avg_speed and avg_speed > 0:
        avg_pace = seconds_to_pace(1000 / avg_speed)

    avg_hr = item.get("average_heartrate")
    return {
        "id": str(item["id"]),
        "date": item["start_date_local"][:10],
        "type": activity_type,
        "name": item.get("name"),
        "distance_km": round(distance_m / 1000, 2) if distance_m is not None else None,
        "duration_min": round(moving_time_s / 60, 1) if moving_time_s is not None else None,
        "avg_hr": round(avg_hr) if avg_hr is not None else None,
        "max_hr": round(item["max_heartrate"]) if item.get("max_heartrate") is not None else None,
        "avg_pace": avg_pace,
        "avg_watts": round(item["average_watts"], 1) if item.get("average_watts") is not None else None,
        "elevation_m": round(item["total_elevation_gain"]) if item.get("total_elevation_gain") is not None else None,
        "calories": round(item["calories"]) if item.get("calories") is not None else None,
        "zone2": zone2_from_activity(activity_type, round(avg_hr) if avg_hr is not None else None),
        "notes": None,
    }


def get_strava_access_token(
    get_setting_fn: Callable[[str], Optional[str]],
    set_setting_fn: Callable[[str, str], None],
) -> str:
    config = require_strava_config(get_setting_fn)
    response = httpx.post(
        STRAVA_TOKEN_URL,
        data={
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "refresh_token": config["refresh_token"],
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Strava token refresh failed: {response.text}")

    data = response.json()
    refresh_token = data.get("refresh_token")
    if refresh_token:
        set_setting_fn("strava_refresh_token", refresh_token)
    access_token = data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="Strava token refresh returned no access_token")
    return access_token


def resolve_strava_import_range(
    conn: sqlite3.Connection,
    start_date: Optional[str],
    end_date: Optional[str],
    get_latest_activity_date_fn: Callable[[sqlite3.Connection], Optional[str]],
) -> tuple[str, str]:
    today = datetime.now().date().isoformat()
    resolved_end = end_date or today

    if start_date:
        resolved_start = start_date
    else:
        latest_activity_date = get_latest_activity_date_fn(conn)
        resolved_start = latest_activity_date or today

    start_dt = parse_strava_date(resolved_start)
    end_dt = parse_strava_date(resolved_end)
    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date must be before or equal to end_date")

    return resolved_start, resolved_end


def fetch_strava_activities(
    start_date: str,
    end_date: str,
    access_token: str,
) -> list[dict]:
    start_dt = parse_strava_date(start_date)
    end_dt = parse_strava_date(end_date)
    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date must be before or equal to end_date")

    after_ts = math.floor(start_dt.timestamp())
    before_ts = math.floor(end_dt.replace(hour=23, minute=59, second=59).timestamp())
    items = []
    page = 1

    with httpx.Client(timeout=20, headers={"Authorization": f"Bearer {access_token}"}) as client:
        while True:
            response = client.get(
                STRAVA_ACTIVITIES_URL,
                params={
                    "after": after_ts,
                    "before": before_ts,
                    "page": page,
                    "per_page": STRAVA_PAGE_SIZE,
                },
            )
            if response.status_code >= 400:
                raise HTTPException(status_code=502, detail=f"Strava activities fetch failed: {response.text}")
            page_items = response.json()
            if not page_items:
                break
            items.extend(page_items)
            if len(page_items) < STRAVA_PAGE_SIZE:
                break
            page += 1

    return items


def parse_strava_rate_limit_headers(response: httpx.Response) -> Optional[dict]:
    limit_header = response.headers.get("X-RateLimit-Limit")
    usage_header = response.headers.get("X-RateLimit-Usage")
    if not limit_header or not usage_header:
        return None
    try:
        short_limit, daily_limit = [int(part.strip()) for part in limit_header.split(",")]
        short_usage, daily_usage = [int(part.strip()) for part in usage_header.split(",")]
    except (ValueError, AttributeError):
        return None
    return {
        "short_limit": short_limit,
        "daily_limit": daily_limit,
        "short_usage": short_usage,
        "daily_usage": daily_usage,
        "short_remaining": max(short_limit - short_usage, 0),
        "daily_remaining": max(daily_limit - daily_usage, 0),
    }


def should_pause_stream_fetch(rate_limit: Optional[dict]) -> bool:
    if not rate_limit:
        return False
    short_buffer = max(5, math.ceil(rate_limit["short_limit"] * 0.1))
    daily_buffer = max(25, math.ceil(rate_limit["daily_limit"] * 0.05))
    return (
        rate_limit["short_remaining"] <= short_buffer
        or rate_limit["daily_remaining"] <= daily_buffer
    )


def fetch_strava_activity_streams(client: httpx.Client, activity_id: str) -> tuple[Optional[dict], Optional[dict]]:
    response = client.get(
        STRAVA_ACTIVITY_STREAMS_URL.format(activity_id=activity_id),
        params={
            "keys": "time,heartrate,watts",
            "key_by_type": "true",
        },
    )
    rate_limit = parse_strava_rate_limit_headers(response)
    if response.status_code == 404:
        return None, rate_limit
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Strava streams fetch failed: {response.text}")
    return response.json(), rate_limit


def rolling_average(values: list[float], window: int) -> list[float]:
    if not values:
        return []
    output = []
    total = 0.0
    for index, value in enumerate(values):
        total += value
        if index >= window:
            total -= values[index - window]
        current_window = min(index + 1, window)
        output.append(total / current_window)
    return output


def estimate_normalized_power(watts: list[float]) -> Optional[float]:
    valid = [max(0.0, float(value or 0)) for value in watts]
    if not valid:
        return None
    rolling = rolling_average(valid, 30)
    if not rolling:
        return None
    fourth_power_mean = sum(value ** 4 for value in rolling) / len(rolling)
    return fourth_power_mean ** 0.25


def summarize_activity_streams(
    activity: dict,
    streams: Optional[dict],
    thresholds: dict,
    intensity_bucket_from_hr_fn: Callable[[Optional[int], int, int], str],
) -> Optional[dict]:
    if not streams:
        return None

    time_stream = streams.get("time", {}).get("data") or []
    hr_stream = streams.get("heartrate", {}).get("data") or []
    watts_stream = streams.get("watts", {}).get("data") or []
    if not time_stream:
        return None

    low_aerobic_seconds = 0
    high_aerobic_seconds = 0
    anaerobic_seconds = 0
    hr_trimp = 0.0
    activity_type = activity["type"]

    for index in range(1, len(time_stream)):
        dt = max(int(time_stream[index] - time_stream[index - 1]), 1)
        hr = hr_stream[index] if index < len(hr_stream) else None
        if activity_type == "Run":
            max_hr = thresholds["run_max_hr"]
            zone2_upper = 162
            zone3_upper = 172
        else:
            max_hr = thresholds["ride_max_hr"]
            zone2_upper = 152
            zone3_upper = 162

        bucket = intensity_bucket_from_hr_fn(hr, zone2_upper, zone3_upper)
        if bucket == "low_aerobic":
            low_aerobic_seconds += dt
        elif bucket == "high_aerobic":
            high_aerobic_seconds += dt
        else:
            anaerobic_seconds += dt

        if hr:
            hr_ratio = (float(hr) - thresholds["resting_hr"]) / (max_hr - thresholds["resting_hr"])
            hr_ratio = max(0.0, min(hr_ratio, 1.0))
            hr_trimp += (dt / 60.0) * hr_ratio * 0.64 * math.exp(1.92 * hr_ratio)

    normalized_power = None
    power_tss = None
    if activity_type in {"Ride", "VirtualRide"} and thresholds["ftp"] and watts_stream:
        normalized_power = estimate_normalized_power(watts_stream)
        if normalized_power:
            hours = (time_stream[-1] - time_stream[0]) / 3600 if len(time_stream) > 1 else (float(activity.get("duration_min") or 0) / 60.0)
            hours = max(hours, float(activity.get("duration_min") or 0) / 60.0)
            intensity_factor = min(normalized_power / thresholds["ftp"], 1.5)
            power_tss = hours * (intensity_factor ** 2) * 100

            low_aerobic_seconds = 0
            high_aerobic_seconds = 0
            anaerobic_seconds = 0
            for index in range(1, len(time_stream)):
                dt = max(int(time_stream[index] - time_stream[index - 1]), 1)
                watts = float(watts_stream[index] or 0) if index < len(watts_stream) else 0.0
                intensity = watts / thresholds["ftp"] if thresholds["ftp"] else 0.0
                if intensity <= 0.75:
                    low_aerobic_seconds += dt
                elif intensity <= 0.9:
                    high_aerobic_seconds += dt
                else:
                    anaerobic_seconds += dt

    return {
        "activity_id": activity["id"],
        "fetched_at": datetime.now().isoformat(),
        "source": "power_tss" if power_tss is not None else ("hr_trimp" if hr_trimp > 0 else "duration"),
        "hr_trimp": round(hr_trimp, 1) if hr_trimp > 0 else None,
        "power_tss": round(power_tss, 1) if power_tss is not None else None,
        "normalized_power": round(normalized_power, 1) if normalized_power is not None else None,
        "low_aerobic_seconds": int(low_aerobic_seconds),
        "high_aerobic_seconds": int(high_aerobic_seconds),
        "anaerobic_seconds": int(anaerobic_seconds),
        "has_heartrate": 1 if hr_stream else 0,
        "has_watts": 1 if watts_stream else 0,
    }


def upsert_activity_stream_summary(conn: sqlite3.Connection, summary: dict):
    conn.execute(
        """
        INSERT INTO activity_stream_summaries
        (activity_id, fetched_at, source, hr_trimp, power_tss, normalized_power,
         low_aerobic_seconds, high_aerobic_seconds, anaerobic_seconds,
         has_heartrate, has_watts, stream_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'v1')
        ON CONFLICT(activity_id) DO UPDATE SET
            fetched_at=excluded.fetched_at,
            source=excluded.source,
            hr_trimp=excluded.hr_trimp,
            power_tss=excluded.power_tss,
            normalized_power=excluded.normalized_power,
            low_aerobic_seconds=excluded.low_aerobic_seconds,
            high_aerobic_seconds=excluded.high_aerobic_seconds,
            anaerobic_seconds=excluded.anaerobic_seconds,
            has_heartrate=excluded.has_heartrate,
            has_watts=excluded.has_watts,
            stream_version='v1'
        """,
        (
            summary["activity_id"],
            summary["fetched_at"],
            summary["source"],
            summary["hr_trimp"],
            summary["power_tss"],
            summary["normalized_power"],
            summary["low_aerobic_seconds"],
            summary["high_aerobic_seconds"],
            summary["anaerobic_seconds"],
            summary["has_heartrate"],
            summary["has_watts"],
        ),
    )


def stream_fetch_candidates(conn: sqlite3.Connection, activities: list[dict], limit: int = STRAVA_STREAM_FETCH_LIMIT) -> list[dict]:
    if not activities:
        return []

    cutoff = datetime.now().date() - timedelta(days=STRAVA_STREAM_RECENT_DAYS)
    activity_ids = [activity["id"] for activity in activities]
    placeholders = ",".join("?" for _ in activity_ids)
    existing_rows = conn.execute(
        f"SELECT activity_id FROM activity_stream_summaries WHERE activity_id IN ({placeholders})",
        activity_ids,
    ).fetchall() if activity_ids else []
    existing_ids = {row["activity_id"] for row in existing_rows}

    prioritized = []
    for activity in activities:
        if activity["id"] in existing_ids:
            continue
        if activity["type"] not in {"Run", "Ride", "VirtualRide"}:
            continue
        if not activity.get("avg_hr") and not activity.get("avg_watts"):
            continue
        activity_date = datetime.strptime(activity["date"], "%Y-%m-%d").date()
        if activity_date < cutoff:
            continue
        priority = 0
        if activity["type"] in {"Ride", "VirtualRide"} and activity.get("avg_watts"):
            priority += 3
        if activity["type"] == "Run" and activity.get("avg_hr"):
            priority += 2
        if activity.get("max_hr"):
            priority += 1
        prioritized.append((priority, activity["date"], activity))

    prioritized.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in prioritized[:limit]]


def list_stream_backfill_candidates(conn: sqlite3.Connection, limit: int = STRAVA_STREAM_FETCH_LIMIT) -> list[dict]:
    safe_limit = max(1, min(limit, 50))
    cutoff = (datetime.now().date() - timedelta(days=STRAVA_STREAM_RECENT_DAYS)).isoformat()
    rows = conn.execute(
        """
        SELECT
            a.id,
            a.date,
            a.type,
            a.name,
            a.duration_min,
            a.avg_hr,
            a.avg_watts,
            a.max_hr,
            a.distance_km
        FROM activities a
        LEFT JOIN activity_stream_summaries s ON s.activity_id = a.id
        WHERE s.activity_id IS NULL
          AND a.type IN ('Run', 'Ride', 'VirtualRide')
          AND a.date >= ?
          AND (a.avg_hr IS NOT NULL OR a.avg_watts IS NOT NULL)
        ORDER BY
          CASE
            WHEN a.type IN ('Ride', 'VirtualRide') AND a.avg_watts IS NOT NULL THEN 3
            WHEN a.type = 'Run' AND a.avg_hr IS NOT NULL THEN 2
            WHEN a.max_hr IS NOT NULL THEN 1
            ELSE 0
          END DESC,
          a.date DESC
        LIMIT ?
        """,
        (cutoff, safe_limit),
    ).fetchall()
    return [dict(row) for row in rows]


def backfill_stream_summaries(
    conn: sqlite3.Connection,
    activities: list[dict],
    access_token: str,
    thresholds: dict,
    intensity_bucket_from_hr_fn: Callable[[Optional[int], int, int], str],
) -> int:
    if not activities:
        return 0

    streams_fetched = 0
    with httpx.Client(timeout=20, headers={"Authorization": f"Bearer {access_token}"}) as client:
        for activity in activities:
            streams, rate_limit = fetch_strava_activity_streams(client, activity["id"])
            summary = summarize_activity_streams(activity, streams, thresholds, intensity_bucket_from_hr_fn)
            if summary:
                upsert_activity_stream_summary(conn, summary)
                streams_fetched += 1
            if should_pause_stream_fetch(rate_limit):
                break
    return streams_fetched


def build_strava_status_data(
    conn: sqlite3.Connection,
    get_setting_fn: Callable[[str], Optional[str]],
    get_latest_activity_date_fn: Callable[[sqlite3.Connection], Optional[str]],
) -> dict:
    latest_activity_date = get_latest_activity_date_fn(conn)
    pending_stream_backfill = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM activities a
        LEFT JOIN activity_stream_summaries s ON s.activity_id = a.id
        WHERE s.activity_id IS NULL
          AND a.type IN ('Run', 'Ride', 'VirtualRide')
          AND a.date >= ?
          AND (a.avg_hr IS NOT NULL OR a.avg_watts IS NOT NULL)
        """,
        ((datetime.now().date() - timedelta(days=STRAVA_STREAM_RECENT_DAYS)).isoformat(),),
    ).fetchone()
    config = require_strava_config(get_setting_fn)
    return {
        "configured": all(config.values()),
        "has_client_id": bool(config["client_id"]),
        "has_client_secret": bool(config["client_secret"]),
        "has_refresh_token": bool(config["refresh_token"]),
        "last_import_at": get_setting_fn("strava_last_import_at"),
        "latest_activity_date": latest_activity_date,
        "pending_stream_backfill": int(pending_stream_backfill["count"] or 0) if pending_stream_backfill else 0,
        "stream_fetch_limit": STRAVA_STREAM_FETCH_LIMIT,
    }


def import_strava_activities_data(
    conn: sqlite3.Connection,
    payload,
    *,
    get_latest_activity_date_fn: Callable[[sqlite3.Connection], Optional[str]],
    get_setting_fn: Callable[[str], Optional[str]],
    set_setting_fn: Callable[[str, str], None],
    upsert_activity_fn: Callable[[sqlite3.Connection, dict, bool], None],
    estimate_thresholds_fn: Callable[[sqlite3.Connection], dict],
    intensity_bucket_from_hr_fn: Callable[[Optional[int], int, int], str],
) -> dict:
    resolved_start, resolved_end = resolve_strava_import_range(
        conn,
        payload.start_date,
        payload.end_date,
        get_latest_activity_date_fn,
    )
    access_token = get_strava_access_token(get_setting_fn, set_setting_fn)
    raw_items = fetch_strava_activities(resolved_start, resolved_end, access_token=access_token)
    imported = 0
    activities = []
    for item in raw_items:
        activity = build_activity_from_strava(item)
        upsert_activity_fn(conn, activity, preserve_annotations=True)
        activities.append(activity)
        imported += 1

    streams_fetched = 0
    if payload.fetch_streams and activities:
        thresholds = estimate_thresholds_fn(conn)
        candidates = stream_fetch_candidates(conn, activities, limit=STRAVA_STREAM_FETCH_LIMIT)
        if candidates:
            streams_fetched = backfill_stream_summaries(
                conn,
                candidates,
                access_token,
                thresholds,
                intensity_bucket_from_hr_fn,
            )
    conn.commit()
    set_setting_fn("strava_last_import_at", datetime.now().isoformat())
    return {
        "imported": imported,
        "fetched": len(raw_items),
        "start_date": resolved_start,
        "end_date": resolved_end,
        "streams_fetched": streams_fetched,
    }


def backfill_strava_streams_data(
    conn: sqlite3.Connection,
    payload,
    *,
    get_setting_fn: Callable[[str], Optional[str]],
    set_setting_fn: Callable[[str, str], None],
    estimate_thresholds_fn: Callable[[sqlite3.Connection], dict],
    intensity_bucket_from_hr_fn: Callable[[Optional[int], int, int], str],
) -> dict:
    candidates = list_stream_backfill_candidates(conn, limit=payload.limit or STRAVA_STREAM_FETCH_LIMIT)
    streams_fetched = 0
    if candidates:
        access_token = get_strava_access_token(get_setting_fn, set_setting_fn)
        thresholds = estimate_thresholds_fn(conn)
        streams_fetched = backfill_stream_summaries(
            conn,
            candidates,
            access_token,
            thresholds,
            intensity_bucket_from_hr_fn,
        )
        conn.commit()

    remaining_row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM activities a
        LEFT JOIN activity_stream_summaries s ON s.activity_id = a.id
        WHERE s.activity_id IS NULL
          AND a.type IN ('Run', 'Ride', 'VirtualRide')
          AND a.date >= ?
          AND (a.avg_hr IS NOT NULL OR a.avg_watts IS NOT NULL)
        """,
        ((datetime.now().date() - timedelta(days=STRAVA_STREAM_RECENT_DAYS)).isoformat(),),
    ).fetchone()

    return {
        "scanned": len(candidates),
        "streams_fetched": streams_fetched,
        "remaining_candidates": int(remaining_row["count"] or 0) if remaining_row else 0,
    }
