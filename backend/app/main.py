from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import sqlite3
from datetime import datetime, timedelta
import os
import math
import json

import httpx

app = FastAPI(title="Training Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "/data/training.db"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
STRAVA_ACTIVITY_STREAMS_URL = "https://www.strava.com/api/v3/activities/{activity_id}/streams"
STRAVA_PAGE_SIZE = 100
STRAVA_STREAM_FETCH_LIMIT = 12
STRAVA_STREAM_RECENT_DAYS = 120
METRIC_CATALOG = [
    {"key": "z2_pace", "label": "Z2 Pace", "unit": "s/km", "entry_mode": "manual", "description": "Aerobic pace benchmark. Store pace as seconds per kilometer."},
    {"key": "weight", "label": "Weight", "unit": "kg", "entry_mode": "manual", "description": "Body weight tracking."},
    {"key": "resting_hr", "label": "Resting HR", "unit": "bpm", "entry_mode": "manual", "description": "Morning or resting heart rate."},
    {"key": "ftp", "label": "FTP", "unit": "W", "entry_mode": "manual", "description": "Cycling functional threshold power."},
    {"key": "heel_pain", "label": "Heel Pain", "unit": "0-10", "entry_mode": "manual", "description": "Pain score on a 0-10 scale."},
    {"key": "streak", "label": "Streak", "unit": "days", "entry_mode": "computed", "description": "Computed automatically from consecutive activity days."},
]

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs("/data", exist_ok=True)
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS activities (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            name TEXT,
            distance_km REAL,
            duration_min REAL,
            avg_hr INTEGER,
            max_hr INTEGER,
            avg_pace TEXT,
            avg_watts REAL,
            elevation_m INTEGER,
            calories INTEGER,
            zone2 INTEGER DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS coach_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS weekly_summary (
            week_start TEXT PRIMARY KEY,
            run_km REAL DEFAULT 0,
            ride_km REAL DEFAULT 0,
            strength_sessions INTEGER DEFAULT 0,
            total_elevation INTEGER DEFAULT 0,
            avg_hr REAL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS weekly_plans (
            week_start TEXT PRIMARY KEY,
            title TEXT,
            focus TEXT,
            overview TEXT,
            days_json TEXT NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS activity_stream_summaries (
            activity_id TEXT PRIMARY KEY,
            fetched_at TEXT NOT NULL,
            source TEXT NOT NULL,
            hr_trimp REAL,
            power_tss REAL,
            normalized_power REAL,
            low_aerobic_seconds INTEGER DEFAULT 0,
            high_aerobic_seconds INTEGER DEFAULT 0,
            anaerobic_seconds INTEGER DEFAULT 0,
            has_heartrate INTEGER DEFAULT 0,
            has_watts INTEGER DEFAULT 0,
            stream_version TEXT DEFAULT 'v1'
        );

        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            period_type TEXT NOT NULL,
            metric_type TEXT NOT NULL,
            target_value REAL NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            activity_type TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

init_db()

# --- Models ---

class Activity(BaseModel):
    id: str
    date: str
    type: str
    name: Optional[str] = None
    distance_km: Optional[float] = None
    duration_min: Optional[float] = None
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    avg_pace: Optional[str] = None
    avg_watts: Optional[float] = None
    elevation_m: Optional[int] = None
    calories: Optional[int] = None
    zone2: Optional[bool] = False
    notes: Optional[str] = None

class CoachNote(BaseModel):
    date: str
    category: str  # "heel", "running", "cycling", "strength", "nutrition", "general"
    content: str

class WeeklySummary(BaseModel):
    week_start: str
    run_km: Optional[float] = 0
    ride_km: Optional[float] = 0
    strength_sessions: Optional[int] = 0
    total_elevation: Optional[int] = 0
    avg_hr: Optional[float] = None
    notes: Optional[str] = None

class Metric(BaseModel):
    date: str
    metric: str  # "weight", "resting_hr", "z2_pace", "ftp", "heel_pain"
    value: float
    unit: Optional[str] = None
    notes: Optional[str] = None

class WeeklyPlanDay(BaseModel):
    date: str
    label: str
    session_type: Optional[str] = None
    title: str
    details: Optional[str] = None
    target_duration_min: Optional[int] = None
    target_distance_km: Optional[float] = None

class WeeklyPlan(BaseModel):
    week_start: str
    title: Optional[str] = None
    focus: Optional[str] = None
    overview: Optional[str] = None
    days: list[WeeklyPlanDay] = Field(default_factory=list)
    notes: Optional[str] = None

class WeeklyPlanAdjustment(BaseModel):
    week_start: str
    days: list[WeeklyPlanDay] = Field(default_factory=list)
    effective_from: Optional[str] = None
    title: Optional[str] = None
    focus: Optional[str] = None
    overview: Optional[str] = None
    notes: Optional[str] = None
    adaptation_reason: Optional[str] = None

class StravaImportRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    fetch_streams: Optional[bool] = True

class StravaImportResult(BaseModel):
    imported: int
    fetched: int
    start_date: str
    end_date: str
    streams_fetched: int = 0

class StravaStreamBackfillRequest(BaseModel):
    limit: Optional[int] = STRAVA_STREAM_FETCH_LIMIT

class StravaStreamBackfillResult(BaseModel):
    scanned: int
    streams_fetched: int
    remaining_candidates: int

class Goal(BaseModel):
    title: str
    period_type: str  # week, month, year
    metric_type: str  # ride_km, run_km, strength_sessions, activities_count
    target_value: float
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    activity_type: Optional[str] = None
    is_active: Optional[bool] = True

def get_latest_activity_date(conn: sqlite3.Connection) -> Optional[str]:
    row = conn.execute("SELECT MAX(date) AS date FROM activities").fetchone()
    return row["date"] if row and row["date"] else None

def get_setting(key: str) -> Optional[str]:
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (key,)
        ).fetchone()
        return row["value"] if row else None
    finally:
        conn.close()

def set_setting(key: str, value: str):
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        conn.commit()
    finally:
        conn.close()

def strava_config():
    return {
        "client_id": os.getenv("STRAVA_CLIENT_ID"),
        "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
        "refresh_token": get_setting("strava_refresh_token") or os.getenv("STRAVA_REFRESH_TOKEN"),
    }

def require_strava_config():
    config = strava_config()
    missing = [key for key, value in config.items() if not value]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing Strava configuration: {', '.join(missing)}"
        )
    return config

def parse_iso_date(value: str) -> datetime:
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

def upsert_activity(conn: sqlite3.Connection, activity: dict, preserve_annotations: bool = False):
    if preserve_annotations:
        existing = conn.execute(
            "SELECT notes, zone2 FROM activities WHERE id = ?",
            (activity["id"],)
        ).fetchone()
        if existing:
            activity["notes"] = existing["notes"]
            if existing["zone2"] is not None:
                activity["zone2"] = bool(existing["zone2"])

    conn.execute("""
        INSERT INTO activities
        (id, date, type, name, distance_km, duration_min, avg_hr, max_hr,
         avg_pace, avg_watts, elevation_m, calories, zone2, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            date=excluded.date,
            type=excluded.type,
            name=excluded.name,
            distance_km=excluded.distance_km,
            duration_min=excluded.duration_min,
            avg_hr=excluded.avg_hr,
            max_hr=excluded.max_hr,
            avg_pace=excluded.avg_pace,
            avg_watts=excluded.avg_watts,
            elevation_m=excluded.elevation_m,
            calories=excluded.calories,
            zone2=excluded.zone2,
            notes=excluded.notes
    """, (
        activity["id"], activity["date"], activity["type"], activity["name"],
        activity["distance_km"], activity["duration_min"], activity["avg_hr"],
        activity["max_hr"], activity["avg_pace"], activity["avg_watts"],
        activity["elevation_m"], activity["calories"],
        1 if activity["zone2"] else 0, activity["notes"]
    ))

def get_strava_access_token() -> str:
    config = require_strava_config()
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
        set_setting("strava_refresh_token", refresh_token)
    access_token = data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="Strava token refresh returned no access_token")
    return access_token

def resolve_strava_import_range(
    conn: sqlite3.Connection,
    start_date: Optional[str],
    end_date: Optional[str],
) -> tuple[str, str]:
    today = datetime.now().date().isoformat()
    resolved_end = end_date or today

    if start_date:
        resolved_start = start_date
    else:
        latest_activity_date = get_latest_activity_date(conn)
        resolved_start = latest_activity_date or today

    start_dt = parse_iso_date(resolved_start)
    end_dt = parse_iso_date(resolved_end)
    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date must be before or equal to end_date")

    return resolved_start, resolved_end

def fetch_strava_activities(start_date: str, end_date: str, access_token: Optional[str] = None) -> list[dict]:
    start_dt = parse_iso_date(start_date)
    end_dt = parse_iso_date(end_date)
    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start_date must be before or equal to end_date")

    token = access_token or get_strava_access_token()
    after_ts = math.floor(start_dt.timestamp())
    before_ts = math.floor(end_dt.replace(hour=23, minute=59, second=59).timestamp())
    items = []
    page = 1

    with httpx.Client(timeout=20, headers={"Authorization": f"Bearer {token}"}) as client:
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

def summarize_activity_streams(activity: dict, streams: Optional[dict], thresholds: dict) -> Optional[dict]:
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

        bucket = intensity_bucket_from_hr(hr, zone2_upper, zone3_upper)
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

def compute_activity_streak(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT DISTINCT date FROM activities ORDER BY date DESC"
    ).fetchall()
    if not rows:
        return {"value": 0, "unit": "days", "date": None}

    dates = [datetime.strptime(row["date"], "%Y-%m-%d").date() for row in rows]
    today = datetime.now().date()
    latest = dates[0]

    # Treat yesterday as an active streak; anything older is broken.
    if latest < (today - timedelta(days=1)):
        return {"value": 0, "unit": "days", "date": latest.isoformat()}

    streak = 1
    previous = latest
    for current in dates[1:]:
        if current == previous - timedelta(days=1):
            streak += 1
            previous = current
            continue
        if current == previous:
            continue
        break

    return {"value": streak, "unit": "days", "date": latest.isoformat()}

def goal_metric_unit(metric_type: str) -> str:
    if metric_type in {"ride_km", "run_km"}:
        return "km"
    if metric_type == "strength_sessions":
        return "sessions"
    if metric_type == "activities_count":
        return "activities"
    return ""

def goal_period_window(period_type: str, today: Optional[datetime.date] = None) -> tuple[datetime.date, datetime.date, str]:
    current = today or datetime.now().date()

    if period_type == "week":
        start_day = current - timedelta(days=current.weekday())
        end_day = start_day + timedelta(days=6)
        return start_day, end_day, "This week"

    if period_type == "month":
        start_day = current.replace(day=1)
        if start_day.month == 12:
            next_month = start_day.replace(year=start_day.year + 1, month=1, day=1)
        else:
            next_month = start_day.replace(month=start_day.month + 1, day=1)
        end_day = next_month - timedelta(days=1)
        return start_day, end_day, "This month"

    start_day = current.replace(month=1, day=1)
    end_day = current.replace(month=12, day=31)
    return start_day, end_day, "This year"

def goal_current_value(conn: sqlite3.Connection, goal: sqlite3.Row) -> float:
    metric_type = goal["metric_type"]
    start_day, end_day, _ = goal_period_window(goal["period_type"])
    start_date = start_day.isoformat()
    end_date = end_day.isoformat()

    if metric_type == "ride_km":
        row = conn.execute(
            """
            SELECT COALESCE(SUM(distance_km), 0) AS value
            FROM activities
            WHERE type IN ('Ride', 'VirtualRide')
              AND date >= ? AND date <= ?
            """,
            (start_date, end_date),
        ).fetchone()
        return float(row["value"] or 0)

    if metric_type == "run_km":
        row = conn.execute(
            """
            SELECT COALESCE(SUM(distance_km), 0) AS value
            FROM activities
            WHERE type = 'Run'
              AND date >= ? AND date <= ?
            """,
            (start_date, end_date),
        ).fetchone()
        return float(row["value"] or 0)

    if metric_type == "strength_sessions":
        row = conn.execute(
            """
            SELECT COUNT(*) AS value
            FROM activities
            WHERE type = 'WeightTraining'
              AND date >= ? AND date <= ?
            """,
            (start_date, end_date),
        ).fetchone()
        return float(row["value"] or 0)

    if metric_type == "activities_count":
        if goal["activity_type"]:
            row = conn.execute(
                """
                SELECT COUNT(*) AS value
                FROM activities
                WHERE type = ?
                  AND date >= ? AND date <= ?
                """,
                (goal["activity_type"], start_date, end_date),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT COUNT(*) AS value
                FROM activities
                WHERE date >= ? AND date <= ?
                """,
                (start_date, end_date),
            ).fetchone()
        return float(row["value"] or 0)

    return 0.0

def serialize_goal(row: sqlite3.Row, conn: sqlite3.Connection) -> dict:
    current_value = round(goal_current_value(conn, row), 1)
    target_value = float(row["target_value"] or 0)
    today = datetime.now().date()
    start_day, end_day, period_label = goal_period_window(row["period_type"], today)
    total_days = max((end_day - start_day).days + 1, 1)
    elapsed_days = min(max((today - start_day).days + 1, 0), total_days)
    days_remaining = max((end_day - today).days, 0)
    progress_pct = round(min((current_value / target_value) * 100, 999), 1) if target_value > 0 else 0
    expected_pct = round((elapsed_days / total_days) * 100, 1)
    remaining_value = round(max(target_value - current_value, 0), 1)
    expected_value = round((target_value * elapsed_days) / total_days, 1) if target_value > 0 else 0.0
    pace_delta_value = round(current_value - expected_value, 1)
    pace_delta_pct = round(progress_pct - expected_pct, 1)

    if current_value >= target_value:
        status = "completed"
    elif pace_delta_pct >= 5:
        status = "ahead_of_pace"
    elif pace_delta_pct >= -5:
        status = "on_pace"
    else:
        status = "behind_pace"

    return {
        "id": row["id"],
        "title": row["title"],
        "period_type": row["period_type"],
        "period_label": period_label,
        "metric_type": row["metric_type"],
        "target_value": target_value,
        "current_value": current_value,
        "unit": goal_metric_unit(row["metric_type"]),
        "start_date": start_day.isoformat(),
        "end_date": end_day.isoformat(),
        "activity_type": row["activity_type"],
        "is_active": bool(row["is_active"]),
        "progress_pct": progress_pct,
        "remaining_value": remaining_value,
        "days_remaining": days_remaining,
        "expected_pct": expected_pct,
        "expected_value": expected_value,
        "pace_delta_value": pace_delta_value,
        "pace_delta_pct": pace_delta_pct,
        "status": status,
    }

def list_goals_data(conn: sqlite3.Connection, active_only: bool = False, limit: int = 24) -> list[dict]:
    query = "SELECT * FROM goals"
    params = []
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY is_active DESC, created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [serialize_goal(row, conn) for row in rows]

def build_calendar_weeks(conn: sqlite3.Connection, weeks: int = 8) -> list[dict]:
    latest_activity = get_latest_activity_date(conn)
    if latest_activity:
        anchor_date = datetime.strptime(latest_activity, "%Y-%m-%d").date()
    else:
        anchor_date = datetime.now().date()

    latest_week_start = anchor_date - timedelta(days=anchor_date.weekday())
    earliest_week_start = latest_week_start - timedelta(weeks=max(weeks - 1, 0))
    range_start = earliest_week_start
    range_end = latest_week_start + timedelta(days=6)

    rows = conn.execute(
        """
        SELECT id, date, type, name, distance_km, duration_min, avg_hr, avg_pace,
               avg_watts, elevation_m, zone2
        FROM activities
        WHERE date >= ? AND date <= ?
        ORDER BY date DESC, created_at DESC
        """,
        (range_start.isoformat(), range_end.isoformat()),
    ).fetchall()

    by_date: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_date.setdefault(row["date"], []).append(row)

    output = []
    for week_index in range(weeks):
        week_start = latest_week_start - timedelta(weeks=week_index)
        week_end = week_start + timedelta(days=6)
        days = []
        total_duration = 0.0
        total_distance = 0.0
        total_elevation = 0
        total_sessions = 0
        run_km = 0.0
        ride_km = 0.0
        strength_sessions = 0

        for day_offset in range(7):
            day = week_start + timedelta(days=day_offset)
            day_key = day.isoformat()
            activities = by_date.get(day_key, [])
            day_distance = round(sum((activity["distance_km"] or 0) for activity in activities), 1)
            day_duration = round(sum((activity["duration_min"] or 0) for activity in activities), 1)
            day_elevation = round(sum((activity["elevation_m"] or 0) for activity in activities))
            type_counts: dict[str, int] = {}

            for activity in activities:
                activity_type = activity["type"]
                type_counts[activity_type] = type_counts.get(activity_type, 0) + 1
                if activity_type == "Run":
                    run_km += activity["distance_km"] or 0
                if activity_type in {"Ride", "VirtualRide"}:
                    ride_km += activity["distance_km"] or 0
                if activity_type == "WeightTraining":
                    strength_sessions += 1

            total_duration += day_duration
            total_distance += day_distance
            total_elevation += day_elevation
            total_sessions += len(activities)

            days.append({
                "date": day_key,
                "weekday": day.strftime("%a"),
                "total_distance_km": day_distance,
                "total_duration_min": day_duration,
                "total_elevation_m": day_elevation,
                "sessions": len(activities),
                "type_counts": type_counts,
                "activities": [
                    {
                        "id": activity["id"],
                        "type": activity["type"],
                        "name": activity["name"],
                        "distance_km": activity["distance_km"],
                        "duration_min": activity["duration_min"],
                        "avg_hr": activity["avg_hr"],
                        "avg_pace": activity["avg_pace"],
                        "avg_watts": activity["avg_watts"],
                        "zone2": bool(activity["zone2"]),
                    }
                    for activity in activities
                ],
            })

        output.append({
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "total_distance_km": round(total_distance, 1),
            "total_duration_min": round(total_duration, 1),
            "total_elevation_m": total_elevation,
            "total_sessions": total_sessions,
            "run_km": round(run_km, 1),
            "ride_km": round(ride_km, 1),
            "strength_sessions": strength_sessions,
            "days": days,
        })

    return output

def build_yearly_distance_series(conn: sqlite3.Connection, activity_types: tuple[str, ...]) -> list[dict]:
    current_year = datetime.now().strftime("%Y")
    current_month = int(datetime.now().strftime("%m"))
    placeholders = ",".join("?" for _ in activity_types)
    rows = conn.execute(
        f"""
        SELECT strftime('%m', date) AS month_num, ROUND(SUM(distance_km), 1) AS km
        FROM activities
        WHERE type IN ({placeholders})
          AND strftime('%Y', date) = ?
        GROUP BY month_num
        ORDER BY month_num
        """,
        (*activity_types, current_year),
    ).fetchall()

    monthly = {int(row["month_num"]): float(row["km"] or 0) for row in rows}
    cumulative = 0.0
    series = []
    for month in range(1, current_month + 1):
        monthly_km = monthly.get(month, 0.0)
        cumulative += monthly_km
        series.append({
            "month": datetime.strptime(f"{current_year}-{month:02d}-01", "%Y-%m-%d").strftime("%b"),
            "monthly_km": round(monthly_km, 1),
            "cumulative_km": round(cumulative, 1),
        })
    return series

def build_yearly_duration_series(conn: sqlite3.Connection, activity_types: tuple[str, ...]) -> list[dict]:
    current_year = datetime.now().strftime("%Y")
    current_month = int(datetime.now().strftime("%m"))
    placeholders = ",".join("?" for _ in activity_types)
    rows = conn.execute(
        f"""
        SELECT strftime('%m', date) AS month_num, ROUND(SUM(duration_min), 1) AS duration_min
        FROM activities
        WHERE type IN ({placeholders})
          AND strftime('%Y', date) = ?
        GROUP BY month_num
        ORDER BY month_num
        """,
        (*activity_types, current_year),
    ).fetchall()

    monthly = {int(row["month_num"]): float(row["duration_min"] or 0) for row in rows}
    cumulative = 0.0
    series = []
    for month in range(1, current_month + 1):
        monthly_min = monthly.get(month, 0.0)
        cumulative += monthly_min
        series.append({
            "month": datetime.strptime(f"{current_year}-{month:02d}-01", "%Y-%m-%d").strftime("%b"),
            "monthly_hours": round(monthly_min / 60.0, 1),
            "cumulative_hours": round(cumulative / 60.0, 1),
        })
    return series

def build_weekly_mix(conn: sqlite3.Connection, weeks: int = 6) -> list[dict]:
    today = datetime.now().date()
    current_week_start = today - timedelta(days=today.weekday())
    output = []

    for offset in range(weeks - 1, -1, -1):
        week_start = current_week_start - timedelta(weeks=offset)
        week_end = week_start + timedelta(days=6)
        rows = conn.execute(
            """
            SELECT type, ROUND(SUM(duration_min), 0) AS total_min, COUNT(*) AS sessions
            FROM activities
            WHERE date >= ? AND date <= ?
            GROUP BY type
            """,
            (week_start.isoformat(), week_end.isoformat()),
        ).fetchall()

        bucket = {
            "week_start": week_start.isoformat(),
            "label": week_start.strftime("%b %d"),
            "run_min": 0,
            "ride_min": 0,
            "strength_min": 0,
            "run_sessions": 0,
            "ride_sessions": 0,
            "strength_sessions": 0,
        }

        for row in rows:
            activity_type = row["type"]
            total_min = int(row["total_min"] or 0)
            sessions = int(row["sessions"] or 0)
            if activity_type == "Run":
                bucket["run_min"] += total_min
                bucket["run_sessions"] += sessions
            elif activity_type in {"Ride", "VirtualRide"}:
                bucket["ride_min"] += total_min
                bucket["ride_sessions"] += sessions
            elif activity_type == "WeightTraining":
                bucket["strength_min"] += total_min
                bucket["strength_sessions"] += sessions

        bucket["total_min"] = bucket["run_min"] + bucket["ride_min"] + bucket["strength_min"]
        output.append(bucket)

    return output

def build_cycling_efficiency_trend(conn: sqlite3.Connection, limit: int = 8) -> list[dict]:
    rows = conn.execute(
        """
        SELECT date, name, avg_hr, avg_watts, duration_min
        FROM activities
        WHERE type IN ('Ride','VirtualRide')
          AND zone2 = 1
          AND avg_hr IS NOT NULL
          AND avg_watts IS NOT NULL
        ORDER BY date DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    trend = []
    for row in reversed(rows):
        avg_hr = float(row["avg_hr"])
        avg_watts = float(row["avg_watts"])
        trend.append({
            "date": row["date"],
            "name": row["name"],
            "avg_hr": round(avg_hr),
            "avg_watts": round(avg_watts, 1),
            "duration_min": round(float(row["duration_min"] or 0), 1),
            "efficiency": round(avg_watts / avg_hr, 3) if avg_hr else None,
        })
    return trend

def build_strength_consistency(conn: sqlite3.Connection, weeks: int = 8, target_sessions: int = 2) -> dict:
    today = datetime.now().date()
    current_week_start = today - timedelta(days=today.weekday())
    history = []

    for offset in range(weeks - 1, -1, -1):
        week_start = current_week_start - timedelta(weeks=offset)
        week_end = week_start + timedelta(days=6)
        row = conn.execute(
            """
            SELECT COUNT(*) AS sessions, ROUND(SUM(duration_min), 0) AS total_min
            FROM activities
            WHERE type = 'WeightTraining'
              AND date >= ? AND date <= ?
            """,
            (week_start.isoformat(), week_end.isoformat()),
        ).fetchone()
        sessions = int(row["sessions"] or 0)
        history.append({
            "week_start": week_start.isoformat(),
            "label": week_start.strftime("%b %d"),
            "sessions": sessions,
            "total_min": int(row["total_min"] or 0),
            "hit_target": sessions >= target_sessions,
        })

    current_streak = 0
    for item in reversed(history):
        if item["hit_target"]:
            current_streak += 1
        else:
            break

    weeks_hit = sum(1 for item in history if item["hit_target"])
    return {
        "target_sessions": target_sessions,
        "current_streak_weeks": current_streak,
        "weeks_hit": weeks_hit,
        "weeks_total": len(history),
        "history": history,
    }

def latest_metric_value(conn: sqlite3.Connection, metric_name: str) -> Optional[float]:
    row = conn.execute(
        """
        SELECT value
        FROM metrics
        WHERE metric = ?
        ORDER BY date DESC, id DESC
        LIMIT 1
        """,
        (metric_name,),
    ).fetchone()
    if not row:
        return None
    return float(row["value"])

def estimate_thresholds(conn: sqlite3.Connection) -> dict:
    resting_hr = latest_metric_value(conn, "resting_hr") or 58.0
    ftp = latest_metric_value(conn, "ftp")

    run_max_hr_row = conn.execute(
        """
        SELECT MAX(max_hr) AS max_hr
        FROM activities
        WHERE type = 'Run' AND max_hr IS NOT NULL
        """
    ).fetchone()
    ride_max_hr_row = conn.execute(
        """
        SELECT MAX(max_hr) AS max_hr
        FROM activities
        WHERE type IN ('Ride', 'VirtualRide') AND max_hr IS NOT NULL
        """
    ).fetchone()
    recent_run_hr_row = conn.execute(
        """
        SELECT ROUND(AVG(avg_hr), 0) AS avg_hr
        FROM (
            SELECT avg_hr
            FROM activities
            WHERE type = 'Run' AND avg_hr IS NOT NULL
            ORDER BY date DESC
            LIMIT 12
        )
        """
    ).fetchone()
    recent_ride_hr_row = conn.execute(
        """
        SELECT ROUND(AVG(avg_hr), 0) AS avg_hr
        FROM (
            SELECT avg_hr
            FROM activities
            WHERE type IN ('Ride', 'VirtualRide') AND avg_hr IS NOT NULL
            ORDER BY date DESC
            LIMIT 12
        )
        """
    ).fetchone()

    run_lthr = max(170.0, float(recent_run_hr_row["avg_hr"] or 0) + 6.0) if recent_run_hr_row else 172.0
    ride_lthr = max(160.0, float(recent_ride_hr_row["avg_hr"] or 0) + 4.0) if recent_ride_hr_row else 162.0
    run_max_hr = max(float(run_max_hr_row["max_hr"] or 0), run_lthr + 8.0, 183.0)
    ride_max_hr = max(float(ride_max_hr_row["max_hr"] or 0), ride_lthr + 8.0, 173.0)

    return {
        "resting_hr": resting_hr,
        "ftp": ftp,
        "run_lthr": run_lthr,
        "ride_lthr": ride_lthr,
        "run_max_hr": run_max_hr,
        "ride_max_hr": ride_max_hr,
    }

def trimp_score(duration_min: float, avg_hr: Optional[int], resting_hr: float, max_hr: float) -> float:
    if duration_min <= 0 or not avg_hr or max_hr <= resting_hr:
        return 0.0
    hr_ratio = (float(avg_hr) - resting_hr) / (max_hr - resting_hr)
    hr_ratio = max(0.0, min(hr_ratio, 1.0))
    return duration_min * hr_ratio * 0.64 * math.exp(1.92 * hr_ratio)

def intensity_bucket_from_hr(avg_hr: Optional[int], zone2_upper: int, zone3_upper: int) -> str:
    if not avg_hr or avg_hr <= zone2_upper:
        return "low_aerobic"
    if avg_hr <= zone3_upper:
        return "high_aerobic"
    return "anaerobic"

def run_load_details(row: sqlite3.Row, thresholds: dict) -> dict:
    duration_min = float(row["duration_min"] or 0)
    avg_hr = row["avg_hr"]
    distance_km = float(row["distance_km"] or 0)
    if duration_min <= 0:
        return {"load": 0.0, "bucket": "low_aerobic", "source": "none"}

    trimp = trimp_score(duration_min, avg_hr, thresholds["resting_hr"], thresholds["run_max_hr"])
    if trimp > 0:
        if avg_hr and avg_hr >= thresholds["run_lthr"]:
            trimp *= 1.08
        bucket = intensity_bucket_from_hr(avg_hr, 162, 172)
        return {"load": round(trimp, 1), "bucket": bucket, "source": "hr_trimp"}

    fallback_multiplier = 0.95 if distance_km >= 10 else 0.8
    return {"load": round(duration_min * fallback_multiplier, 1), "bucket": "low_aerobic", "source": "duration"}

def ride_load_details(row: sqlite3.Row, thresholds: dict) -> dict:
    duration_min = float(row["duration_min"] or 0)
    avg_hr = row["avg_hr"]
    avg_watts = float(row["avg_watts"] or 0)
    ftp = thresholds["ftp"]
    if duration_min <= 0:
        return {"load": 0.0, "bucket": "low_aerobic", "source": "none"}

    if ftp and avg_watts > 0:
        hours = duration_min / 60.0
        intensity_factor = min((avg_watts / ftp) * 1.03, 1.5)
        tss = hours * (intensity_factor ** 2) * 100
        if intensity_factor <= 0.75:
            bucket = "low_aerobic"
        elif intensity_factor <= 0.9:
            bucket = "high_aerobic"
        else:
            bucket = "anaerobic"
        return {"load": round(tss, 1), "bucket": bucket, "source": "power_tss"}

    trimp = trimp_score(duration_min, avg_hr, thresholds["resting_hr"], thresholds["ride_max_hr"])
    if trimp > 0:
        bucket = intensity_bucket_from_hr(avg_hr, 152, 162)
        return {"load": round(trimp, 1), "bucket": bucket, "source": "hr_trimp"}

    return {"load": round(duration_min * 0.75, 1), "bucket": "low_aerobic", "source": "duration"}

def strength_load_details(row: sqlite3.Row) -> dict:
    duration_min = float(row["duration_min"] or 0)
    if duration_min <= 0:
        return {"load": 0.0, "bucket": "low_aerobic", "source": "none"}
    return {"load": round(duration_min * 0.8, 1), "bucket": "high_aerobic", "source": "duration"}

def generic_load_details(row: sqlite3.Row) -> dict:
    activity_type = row["type"]
    duration_min = float(row["duration_min"] or 0)
    if duration_min <= 0:
        return {"load": 0.0, "bucket": "low_aerobic", "source": "none"}
    if activity_type == "Walk":
        return {"load": round(duration_min * 0.35, 1), "bucket": "low_aerobic", "source": "duration"}
    if activity_type == "Hike":
        return {"load": round(duration_min * 0.6, 1), "bucket": "low_aerobic", "source": "duration"}
    return {"load": round(duration_min * 0.7, 1), "bucket": "low_aerobic", "source": "duration"}

def bucket_from_stream_summary(row: sqlite3.Row) -> Optional[str]:
    low = int(row["stream_low_aerobic_seconds"] or 0)
    high = int(row["stream_high_aerobic_seconds"] or 0)
    anaerobic = int(row["stream_anaerobic_seconds"] or 0)
    total = low + high + anaerobic
    if total <= 0:
        return None
    if anaerobic >= max(low, high):
        return "anaerobic"
    if high >= low:
        return "high_aerobic"
    return "low_aerobic"

def activity_load_details(row: sqlite3.Row, thresholds: dict) -> dict:
    if row["stream_power_tss"] is not None or row["stream_hr_trimp"] is not None:
        stream_load = row["stream_power_tss"] if row["stream_power_tss"] is not None else row["stream_hr_trimp"]
        bucket = bucket_from_stream_summary(row) or "low_aerobic"
        return {
            "load": round(float(stream_load or 0), 1),
            "bucket": bucket,
            "source": row["stream_source"] or "stream",
        }

    activity_type = row["type"]
    if activity_type == "Run":
        return run_load_details(row, thresholds)
    if activity_type in {"Ride", "VirtualRide"}:
        return ride_load_details(row, thresholds)
    if activity_type == "WeightTraining":
        return strength_load_details(row)
    return generic_load_details(row)

def ewma(values: list[float], time_constant_days: float) -> list[float]:
    if not values:
        return []

    alpha = 1 - math.exp(-1 / time_constant_days)
    output = []
    current = values[0]
    for value in values:
        current = current + alpha * (value - current)
        output.append(current)
    return output

def build_training_load_summary(conn: sqlite3.Connection, days: int = 42, focus_days: int = 28) -> dict:
    safe_days = max(14, min(days, 120))
    safe_focus_days = max(7, min(focus_days, safe_days))
    today = datetime.now().date()
    start_day = today - timedelta(days=safe_days - 1)
    thresholds = estimate_thresholds(conn)

    activity_rows = conn.execute(
        """
        SELECT
            a.date,
            a.type,
            a.duration_min,
            a.avg_hr,
            a.avg_watts,
            a.max_hr,
            a.distance_km,
            s.source AS stream_source,
            s.hr_trimp AS stream_hr_trimp,
            s.power_tss AS stream_power_tss,
            s.low_aerobic_seconds AS stream_low_aerobic_seconds,
            s.high_aerobic_seconds AS stream_high_aerobic_seconds,
            s.anaerobic_seconds AS stream_anaerobic_seconds
        FROM activities a
        LEFT JOIN activity_stream_summaries s ON s.activity_id = a.id
        WHERE a.date >= ?
        ORDER BY a.date ASC, a.created_at ASC
        """,
        (start_day.isoformat(),),
    ).fetchall()

    by_day: dict[str, dict] = {}
    focus_loads = {"low_aerobic": 0.0, "high_aerobic": 0.0, "anaerobic": 0.0}

    for offset in range(safe_days):
        day = start_day + timedelta(days=offset)
        key = day.isoformat()
        by_day[key] = {
            "date": key,
            "load": 0.0,
            "run_load": 0.0,
            "ride_load": 0.0,
            "strength_load": 0.0,
            "load_source": "none",
        }

    focus_cutoff = today - timedelta(days=safe_focus_days - 1)
    load_sources = {"power_tss": 0, "hr_trimp": 0, "duration": 0}

    for row in activity_rows:
        day = row["date"]
        if day not in by_day:
            continue

        details = activity_load_details(row, thresholds)
        load = details["load"]
        bucket = details["bucket"]
        by_day[day]["load"] += load
        by_day[day]["load_source"] = details["source"]
        if details["source"] in load_sources:
            load_sources[details["source"]] += 1

        if row["type"] == "Run":
            by_day[day]["run_load"] += load
        elif row["type"] in {"Ride", "VirtualRide"}:
            by_day[day]["ride_load"] += load
        elif row["type"] == "WeightTraining":
            by_day[day]["strength_load"] += load

        row_day = datetime.strptime(day, "%Y-%m-%d").date()
        if row_day >= focus_cutoff and bucket in focus_loads:
            focus_loads[bucket] += load

    series = []
    daily_values = []
    for day in sorted(by_day.keys()):
        item = by_day[day]
        item["load"] = round(item["load"], 1)
        item["run_load"] = round(item["run_load"], 1)
        item["ride_load"] = round(item["ride_load"], 1)
        item["strength_load"] = round(item["strength_load"], 1)
        series.append(item)
        daily_values.append(item["load"])

    ctl_series = ewma(daily_values, 42)
    atl_series = ewma(daily_values, 7)

    chart = []
    for index, item in enumerate(series):
        ctl = round(ctl_series[index], 1)
        atl = round(atl_series[index], 1)
        tsb = round(ctl - atl, 1)
        chart.append({
            **item,
            "ctl": ctl,
            "atl": atl,
            "tsb": tsb,
        })

    current = chart[-1] if chart else {
        "ctl": 0.0,
        "atl": 0.0,
        "tsb": 0.0,
        "load": 0.0,
    }
    total_focus_load = sum(focus_loads.values())
    ratio = round(current["atl"] / current["ctl"], 2) if current["ctl"] > 0 else 0.0
    detailed_sources = {"power_tss", "hr_trimp"}
    detailed_sessions = sum(load_sources.get(source, 0) for source in detailed_sources)
    fallback_sessions = max(load_sources.get("duration", 0), 0)
    total_scored_sessions = detailed_sessions + fallback_sessions
    eligible_row = conn.execute(
        """
        SELECT
            COUNT(*) AS total_sessions,
            SUM(CASE WHEN s.activity_id IS NOT NULL THEN 1 ELSE 0 END) AS detailed_sessions,
            SUM(CASE WHEN s.activity_id IS NULL THEN 1 ELSE 0 END) AS fallback_sessions
        FROM activities a
        LEFT JOIN activity_stream_summaries s ON s.activity_id = a.id
        WHERE a.date >= ?
          AND a.type IN ('Run', 'Ride', 'VirtualRide')
          AND (a.avg_hr IS NOT NULL OR a.avg_watts IS NOT NULL)
        """,
        (start_day.isoformat(),),
    ).fetchone()
    eligible_total_sessions = int(eligible_row["total_sessions"] or 0) if eligible_row else 0
    eligible_detailed_sessions = int(eligible_row["detailed_sessions"] or 0) if eligible_row else 0
    eligible_fallback_sessions = int(eligible_row["fallback_sessions"] or 0) if eligible_row else 0

    if ratio >= 1.2:
        ratio_status = "high"
    elif ratio >= 0.9:
        ratio_status = "balanced"
    elif ratio > 0:
        ratio_status = "recovery"
    else:
        ratio_status = "low"

    return {
        "current": {
            "fitness": round(current["ctl"]),
            "fatigue": round(current["atl"]),
            "form": round(current["tsb"]),
            "daily_load": round(current["load"], 1),
        },
        "ratio": {
            "value": ratio,
            "status": ratio_status,
        },
        "focus": {
            "window_days": safe_focus_days,
            "low_aerobic": round((focus_loads["low_aerobic"] / total_focus_load) * 100) if total_focus_load else 0,
            "high_aerobic": round((focus_loads["high_aerobic"] / total_focus_load) * 100) if total_focus_load else 0,
            "anaerobic": round((focus_loads["anaerobic"] / total_focus_load) * 100) if total_focus_load else 0,
        },
        "model": {
            "name": "hybrid_trimp_tss_v1",
            "resting_hr": round(thresholds["resting_hr"]),
            "ftp": round(thresholds["ftp"]) if thresholds["ftp"] else None,
            "run_lthr": round(thresholds["run_lthr"]),
            "ride_lthr": round(thresholds["ride_lthr"]),
            "sources": load_sources,
            "coverage": {
                "detailed_sessions": eligible_detailed_sessions,
                "fallback_sessions": eligible_fallback_sessions,
                "total_sessions": eligible_total_sessions,
                "detailed_pct": round((eligible_detailed_sessions / eligible_total_sessions) * 100) if eligible_total_sessions else 0,
                "overall_scored_sessions": total_scored_sessions,
                "overall_detailed_sources": detailed_sessions,
                "overall_pct": round((detailed_sessions / total_scored_sessions) * 100) if total_scored_sessions else 0,
            },
        },
        "chart": chart,
    }

def build_recent_context(
    conn: sqlite3.Connection,
    lookback_days: int = 14,
    context_days: int = 30,
    recent_activity_limit: int = 12,
    recent_note_limit: int = 5,
) -> dict:
    recent_rows = conn.execute(
        """
        SELECT
            type,
            COUNT(*) AS sessions,
            ROUND(SUM(distance_km), 1) AS total_km,
            ROUND(SUM(duration_min), 0) AS total_min,
            ROUND(AVG(avg_hr), 0) AS avg_hr,
            ROUND(AVG(avg_watts), 1) AS avg_watts
        FROM activities
        WHERE date >= date('now', ?)
        GROUP BY type
        ORDER BY total_min DESC, sessions DESC
        """,
        (f"-{lookback_days} days",),
    ).fetchall()

    recent_totals = conn.execute(
        """
        SELECT
            COUNT(*) AS sessions,
            ROUND(SUM(distance_km), 1) AS total_km,
            ROUND(SUM(duration_min), 0) AS total_min
        FROM activities
        WHERE date >= date('now', ?)
        """,
        (f"-{lookback_days} days",),
    ).fetchone()

    context_totals = conn.execute(
        """
        SELECT
            COUNT(*) AS sessions,
            ROUND(SUM(distance_km), 1) AS total_km,
            ROUND(SUM(duration_min), 0) AS total_min,
            ROUND(AVG(avg_hr), 0) AS avg_hr
        FROM activities
        WHERE date >= date('now', ?)
        """,
        (f"-{context_days} days",),
    ).fetchone()

    current_week = conn.execute(
        """
        SELECT
            COUNT(*) AS sessions,
            ROUND(SUM(distance_km), 1) AS total_km,
            ROUND(SUM(duration_min), 0) AS total_min,
            SUM(CASE WHEN type = 'Run' THEN COALESCE(distance_km, 0) ELSE 0 END) AS run_km,
            SUM(CASE WHEN type IN ('Ride', 'VirtualRide') THEN COALESCE(distance_km, 0) ELSE 0 END) AS ride_km,
            SUM(CASE WHEN type = 'WeightTraining' THEN 1 ELSE 0 END) AS strength_sessions
        FROM activities
        WHERE date >= date('now', 'weekday 1', '-7 days')
        """
    ).fetchone()

    activities = conn.execute(
        """
        SELECT date, type, name, distance_km, duration_min, avg_hr, avg_pace, avg_watts, zone2
        FROM activities
        ORDER BY date DESC, created_at DESC
        LIMIT ?
        """,
        (recent_activity_limit,),
    ).fetchall()

    notes = conn.execute(
        """
        SELECT date, category, content
        FROM coach_notes
        ORDER BY date DESC, created_at DESC
        LIMIT ?
        """,
        (recent_note_limit,),
    ).fetchall()

    latest_metrics = conn.execute(
        """
        SELECT metric, value, unit, date
        FROM metrics
        WHERE (metric, date) IN (
            SELECT metric, MAX(date) FROM metrics GROUP BY metric
        )
        ORDER BY date DESC, metric
        """
    ).fetchall()

    weekly_mix = build_weekly_mix(conn, 4)
    strength_consistency = build_strength_consistency(conn, 8, 2)
    computed_streak = compute_activity_streak(conn)

    latest_plan = conn.execute(
        """
        SELECT *
        FROM weekly_plans
        WHERE week_start <= date('now', '+7 days')
        ORDER BY week_start DESC
        LIMIT 1
        """
    ).fetchone()

    return {
        "generated_at": datetime.now().isoformat(),
        "focus_window_days": lookback_days,
        "context_window_days": context_days,
        "streak": computed_streak,
        "focus_window": {
            "totals": dict(recent_totals) if recent_totals else {},
            "by_type": [dict(row) for row in recent_rows],
        },
        "context_window": {
            "totals": dict(context_totals) if context_totals else {},
        },
        "current_week": {
            "sessions": int(current_week["sessions"] or 0),
            "total_km": round(float(current_week["total_km"] or 0), 1),
            "total_min": round(float(current_week["total_min"] or 0), 0),
            "run_km": round(float(current_week["run_km"] or 0), 1),
            "ride_km": round(float(current_week["ride_km"] or 0), 1),
            "strength_sessions": int(current_week["strength_sessions"] or 0),
        },
        "recent_activities": [dict(row) for row in activities],
        "recent_notes": [dict(row) for row in notes],
        "latest_metrics": [dict(row) for row in latest_metrics],
        "weekly_mix": weekly_mix,
        "strength_consistency": strength_consistency,
        "active_plan": serialize_weekly_plan(latest_plan, conn) if latest_plan else None,
    }

def normalize_plan_session_type(session_type: Optional[str]) -> Optional[str]:
    if not session_type:
        return None
    normalized = session_type.strip().lower()
    mapping = {
        "run": "Run",
        "ride": "Ride",
        "cycling": "Ride",
        "bike": "Ride",
        "strength": "WeightTraining",
        "weights": "WeightTraining",
        "recovery": "Recovery",
        "rest": "Rest",
        "walk": "Walk",
        "hike": "Hike",
    }
    return mapping.get(normalized, session_type)

def append_plan_note(existing_notes: Optional[str], adjustment_reason: Optional[str], effective_from: str) -> Optional[str]:
    adjustment_stamp = f"Adjusted from {effective_from}"
    if adjustment_reason:
        adjustment_stamp = f"{adjustment_stamp}: {adjustment_reason}"
    if existing_notes:
        return f"{existing_notes}\n{adjustment_stamp}"
    return adjustment_stamp

def get_weekly_plan_row(conn: sqlite3.Connection, week_start: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM weekly_plans WHERE week_start = ?",
        (week_start,),
    ).fetchone()

def upsert_weekly_plan_row(conn: sqlite3.Connection, plan: WeeklyPlan):
    conn.execute(
        """
        INSERT INTO weekly_plans
        (week_start, title, focus, overview, days_json, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(week_start) DO UPDATE SET
            title=excluded.title,
            focus=excluded.focus,
            overview=excluded.overview,
            days_json=excluded.days_json,
            notes=excluded.notes
        """,
        (
            plan.week_start,
            plan.title,
            plan.focus,
            plan.overview,
            json.dumps([day.model_dump() for day in plan.days]),
            plan.notes,
        ),
    )

def adjust_weekly_plan_data(conn: sqlite3.Connection, adjustment: WeeklyPlanAdjustment) -> dict:
    plan_row = get_weekly_plan_row(conn, adjustment.week_start)
    if not plan_row:
        raise HTTPException(status_code=404, detail=f"Weekly plan not found for {adjustment.week_start}")

    existing_plan = WeeklyPlan(
        week_start=plan_row["week_start"],
        title=plan_row["title"],
        focus=plan_row["focus"],
        overview=plan_row["overview"],
        days=[WeeklyPlanDay(**day) for day in json.loads(plan_row["days_json"])],
        notes=plan_row["notes"],
    )
    if not existing_plan.days:
        raise HTTPException(status_code=400, detail="Weekly plan has no days to adjust")

    week_dates = {day.date for day in existing_plan.days}
    effective_from = adjustment.effective_from or datetime.now().date().isoformat()
    parse_iso_date(effective_from)

    if effective_from not in week_dates:
        raise HTTPException(
            status_code=400,
            detail=f"effective_from {effective_from} is outside plan week {adjustment.week_start}",
        )

    incoming_by_date: dict[str, WeeklyPlanDay] = {}
    for day in adjustment.days:
        parse_iso_date(day.date)
        if day.date not in week_dates:
            raise HTTPException(
                status_code=400,
                detail=f"Adjusted day {day.date} is outside plan week {adjustment.week_start}",
            )
        if day.date < effective_from:
            raise HTTPException(
                status_code=400,
                detail=f"Adjusted day {day.date} is before effective_from {effective_from}",
            )
        if day.date in incoming_by_date:
            raise HTTPException(status_code=400, detail=f"Duplicate adjusted day {day.date}")
        incoming_by_date[day.date] = day

    week_end = max(week_dates)
    activity_rows = conn.execute(
        """
        SELECT DISTINCT date
        FROM activities
        WHERE date >= ? AND date <= ?
        """,
        (adjustment.week_start, week_end),
    ).fetchall()
    completed_dates = {row["date"] for row in activity_rows}

    protected_dates = {
        day.date
        for day in existing_plan.days
        if day.date < effective_from or day.date in completed_dates
    }
    conflicting_dates = sorted(protected_dates.intersection(incoming_by_date.keys()))
    if conflicting_dates:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot adjust protected days with completed or past sessions: {', '.join(conflicting_dates)}",
        )

    merged_days: list[WeeklyPlanDay] = []
    changed_dates: list[str] = []
    for day in sorted(existing_plan.days, key=lambda item: item.date):
        replacement = incoming_by_date.get(day.date)
        final_day = day if day.date in protected_dates or replacement is None else replacement
        merged_days.append(final_day)
        if final_day.model_dump() != day.model_dump():
            changed_dates.append(day.date)

    updated_plan = WeeklyPlan(
        week_start=existing_plan.week_start,
        title=adjustment.title if adjustment.title is not None else existing_plan.title,
        focus=adjustment.focus if adjustment.focus is not None else existing_plan.focus,
        overview=adjustment.overview if adjustment.overview is not None else existing_plan.overview,
        days=merged_days,
        notes=adjustment.notes if adjustment.notes is not None else append_plan_note(existing_plan.notes, adjustment.adaptation_reason, effective_from),
    )
    upsert_weekly_plan_row(conn, updated_plan)
    conn.commit()

    updated_row = get_weekly_plan_row(conn, adjustment.week_start)
    return {
        "status": "ok",
        "week_start": adjustment.week_start,
        "effective_from": effective_from,
        "changed_dates": changed_dates,
        "preserved_dates": sorted(protected_dates),
        "plan": serialize_weekly_plan(updated_row, conn) if updated_row else None,
    }

def build_plan_day_comparison(day: dict, activities: list[sqlite3.Row]) -> dict:
    planned_type = normalize_plan_session_type(day.get("session_type"))
    completed = [
        {
            "id": row["id"],
            "type": row["type"],
            "name": row["name"],
            "distance_km": row["distance_km"],
            "duration_min": row["duration_min"],
            "avg_pace": row["avg_pace"],
            "avg_watts": row["avg_watts"],
        }
        for row in activities
    ]

    if not completed:
        return {
            "status": "not_completed_yet",
            "label": "Not completed yet",
            "planned_type": planned_type,
            "completed_activities": [],
        }

    completed_types = {item["type"] for item in completed}
    total_duration = sum((item["duration_min"] or 0) for item in completed)
    target_duration = day.get("target_duration_min")

    if planned_type in {"Rest", "Recovery"}:
        label = "Recovery changed" if planned_type == "Recovery" else "Rest day changed"
        return {
            "status": "rest_day_changed",
            "label": label,
            "planned_type": planned_type,
            "completed_activities": completed,
        }

    if planned_type in completed_types:
        if target_duration and total_duration < (target_duration * 0.6):
            status = "partially_matched"
            label = "Partially matched"
        else:
            status = "matched"
            label = "Matched"
    else:
        status = "different"
        label = "Different"

    return {
        "status": status,
        "label": label,
        "planned_type": planned_type,
        "completed_activities": completed,
    }

def serialize_weekly_plan(row: sqlite3.Row, conn: Optional[sqlite3.Connection] = None) -> dict:
    days = json.loads(row["days_json"])
    if conn:
        dates = [day["date"] for day in days if day.get("date")]
        by_date: dict[str, list[sqlite3.Row]] = {}
        if dates:
            placeholders = ",".join("?" for _ in dates)
            activity_rows = conn.execute(
                f"""
                SELECT id, date, type, name, distance_km, duration_min, avg_pace, avg_watts
                FROM activities
                WHERE date IN ({placeholders})
                ORDER BY date ASC, created_at DESC
                """,
                dates,
            ).fetchall()
            for activity in activity_rows:
                by_date.setdefault(activity["date"], []).append(activity)

        enriched_days = []
        for day in days:
            comparison = build_plan_day_comparison(day, by_date.get(day.get("date"), []))
            enriched_day = dict(day)
            enriched_day["comparison"] = comparison
            enriched_days.append(enriched_day)
        days = enriched_days

    return {
        "week_start": row["week_start"],
        "title": row["title"],
        "focus": row["focus"],
        "overview": row["overview"],
        "days": days,
        "notes": row["notes"],
        "created_at": row["created_at"],
    }

MCP_SERVER_INFO = {"name": "training-dashboard", "version": "1.1.0"}
MCP_SECURITY_SCHEMES = [{"type": "noauth"}]

MCP_TOOLS = [
    {
        "name": "log_activity",
        "description": "Log a training activity to the dashboard (run, ride, strength session)",
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Unique ID (use strava ID if available)"},
                "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                "type": {"type": "string", "enum": ["Run", "Ride", "VirtualRide", "WeightTraining", "Walk", "Hike"]},
                "name": {"type": "string"},
                "distance_km": {"type": "number"},
                "duration_min": {"type": "number"},
                "avg_hr": {"type": "integer"},
                "max_hr": {"type": "integer"},
                "avg_pace": {"type": "string", "description": "e.g. 5:46"},
                "avg_watts": {"type": "number"},
                "elevation_m": {"type": "integer"},
                "calories": {"type": "integer"},
                "zone2": {"type": "boolean", "description": "Was this a Zone 2 session?"},
                "notes": {"type": "string"},
            },
            "required": ["id", "date", "type"],
        },
    },
    {
        "name": "add_coach_note",
        "description": "Add a coaching observation or analysis note to the dashboard",
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": False,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                "category": {"type": "string", "enum": ["running", "cycling", "strength", "heel", "nutrition", "general"]},
                "content": {"type": "string", "description": "The coaching note content"},
            },
            "required": ["date", "category", "content"],
        },
    },
    {
        "name": "log_metric",
        "description": "Log a personal metric like weight, resting HR, Z2 pace, FTP, heel pain level, or streak",
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": False,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                "metric": {"type": "string", "enum": ["weight", "resting_hr", "z2_pace", "ftp", "heel_pain", "streak"]},
                "value": {"type": "number", "description": "For z2_pace use seconds per km. For heel_pain use 0-10 scale."},
                "unit": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["date", "metric", "value"],
        },
    },
    {
        "name": "update_weekly_summary",
        "description": "Update or create a weekly training summary",
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "week_start": {"type": "string", "description": "Monday date YYYY-MM-DD"},
                "run_km": {"type": "number"},
                "ride_km": {"type": "number"},
                "strength_sessions": {"type": "integer"},
                "total_elevation": {"type": "integer"},
                "avg_hr": {"type": "number"},
                "notes": {"type": "string"},
            },
            "required": ["week_start"],
        },
    },
    {
        "name": "set_weekly_plan",
        "description": "Create or update a structured weekly training plan for the dashboard",
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "week_start": {"type": "string", "description": "Monday date YYYY-MM-DD"},
                "title": {"type": "string"},
                "focus": {"type": "string", "description": "Main focus of the week"},
                "overview": {"type": "string", "description": "Short summary of the week's intent"},
                "days": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                            "label": {"type": "string", "description": "Mon, Tue, etc."},
                            "session_type": {"type": "string", "description": "run, ride, strength, recovery, rest"},
                            "title": {"type": "string"},
                            "details": {"type": "string"},
                            "target_duration_min": {"type": "integer"},
                            "target_distance_km": {"type": "number"},
                        },
                        "required": ["date", "label", "title"],
                    },
                },
                "notes": {"type": "string"},
            },
            "required": ["week_start", "days"],
        },
    },
    {
        "name": "adjust_weekly_plan",
        "description": "Adjust the remaining part of an existing weekly plan while preserving past or completed days",
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": False,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "week_start": {"type": "string", "description": "Monday date YYYY-MM-DD for the plan to adjust"},
                "effective_from": {"type": "string", "description": "First date that may be changed; defaults to today"},
                "title": {"type": "string", "description": "Optional replacement title for the week"},
                "focus": {"type": "string", "description": "Optional replacement focus"},
                "overview": {"type": "string", "description": "Optional replacement overview"},
                "notes": {"type": "string", "description": "Optional full replacement notes"},
                "adaptation_reason": {"type": "string", "description": "Short explanation appended to plan notes when notes are not replaced"},
                "days": {
                    "type": "array",
                    "description": "Only include days you want to change on or after effective_from",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                            "label": {"type": "string", "description": "Mon, Tue, etc."},
                            "session_type": {"type": "string", "description": "run, ride, strength, recovery, rest"},
                            "title": {"type": "string"},
                            "details": {"type": "string"},
                            "target_duration_min": {"type": "integer"},
                            "target_distance_km": {"type": "number"},
                        },
                        "required": ["date", "label", "title"],
                    },
                },
            },
            "required": ["week_start", "days"],
        },
    },
    {
        "name": "get_dashboard_summary",
        "description": "Get current dashboard data to see what's already logged",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_recent_context",
        "description": "Get a compact coaching context bundle with recent load, latest activities, notes, metrics, weekly mix, streak, and active plan",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "lookback_days": {"type": "integer", "description": "Primary analysis window, defaults to 14 days"},
                "context_days": {"type": "integer", "description": "Broader context window, defaults to 30 days"},
                "recent_activity_limit": {"type": "integer", "description": "How many recent activities to include"},
                "recent_note_limit": {"type": "integer", "description": "How many recent notes to include"},
            },
        },
    },
    {
        "name": "get_activities",
        "description": "Read activities already stored in the training dashboard",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of activities to return"},
                "type": {"type": "string", "description": "Optional activity type filter like Run, Ride, WeightTraining"},
                "days": {"type": "integer", "description": "Optional lookback window in days"},
            },
        },
    },
    {
        "name": "get_activity_stats",
        "description": "Read aggregated activity stats from the dashboard",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Lookback window in days"},
            },
        },
    },
    {
        "name": "get_coach_notes",
        "description": "Read coach notes already stored in the dashboard",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of notes to return"},
                "category": {"type": "string", "description": "Optional note category filter"},
            },
        },
    },
    {
        "name": "get_metric_history",
        "description": "Read metric history from the dashboard",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "metric_name": {
                    "type": "string",
                    "enum": ["weight", "resting_hr", "z2_pace", "ftp", "heel_pain", "streak"],
                },
                "limit": {"type": "integer", "description": "Maximum number of entries to return"},
            },
            "required": ["metric_name"],
        },
    },
    {
        "name": "get_metrics_catalog",
        "description": "Discover supported metrics, expected units, and whether each metric is manual or computed",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_weekly_plans",
        "description": "Read saved weekly training plans from the dashboard",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of weekly plans to return"},
            },
        },
    },
    {
        "name": "get_calendar_weeks",
        "description": "Read weekly calendar summaries and day-by-day activities from the dashboard",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "weeks": {"type": "integer", "description": "Number of recent weeks to return"},
            },
        },
    },
]

def make_mcp_response(msg_id, result=None, error=None):
    response = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        response["error"] = error
    else:
        response["result"] = result
    return response

def build_mcp_tools():
    tools = []
    for tool in MCP_TOOLS:
        meta = dict(tool.get("_meta", {}))
        meta["securitySchemes"] = MCP_SECURITY_SCHEMES
        enriched = dict(tool)
        enriched["securitySchemes"] = MCP_SECURITY_SCHEMES
        enriched["_meta"] = meta
        tools.append(enriched)
    return tools

def call_mcp_tool(name: str, args: dict) -> dict:
    conn = get_db()
    try:
        if name == "log_activity":
            activity = Activity(**args)
            upsert_activity(conn, activity.model_dump())
            conn.commit()
            message = f"Activity logged: {activity.name or activity.type} on {activity.date}"
            data = {"status": "ok", "id": activity.id, "message": message}

        elif name == "add_coach_note":
            note = CoachNote(**args)
            conn.execute(
                "INSERT INTO coach_notes (date, category, content) VALUES (?, ?, ?)",
                (note.date, note.category, note.content),
            )
            conn.commit()
            message = f"Coach note added for {note.date}"
            data = {"status": "ok", "message": message}

        elif name == "log_metric":
            metric = Metric(**args)
            conn.execute(
                "INSERT INTO metrics (date, metric, value, unit, notes) VALUES (?, ?, ?, ?, ?)",
                (metric.date, metric.metric, metric.value, metric.unit, metric.notes),
            )
            conn.commit()
            message = f"Metric logged: {metric.metric} = {metric.value} on {metric.date}"
            data = {"status": "ok", "message": message}

        elif name == "update_weekly_summary":
            summary = WeeklySummary(**args)
            conn.execute(
                """
                INSERT INTO weekly_summary
                (week_start, run_km, ride_km, strength_sessions, total_elevation, avg_hr, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(week_start) DO UPDATE SET
                    run_km=excluded.run_km,
                    ride_km=excluded.ride_km,
                    strength_sessions=excluded.strength_sessions,
                    total_elevation=excluded.total_elevation,
                    avg_hr=excluded.avg_hr,
                    notes=excluded.notes
                """,
                (
                    summary.week_start,
                    summary.run_km,
                    summary.ride_km,
                    summary.strength_sessions,
                    summary.total_elevation,
                    summary.avg_hr,
                    summary.notes,
                ),
            )
            conn.commit()
            message = f"Weekly summary updated for {summary.week_start}"
            data = {"status": "ok", "message": message}

        elif name == "set_weekly_plan":
            plan = WeeklyPlan(**args)
            upsert_weekly_plan_row(conn, plan)
            conn.commit()
            message = f"Weekly plan saved for {plan.week_start}"
            data = {"status": "ok", "message": message}

        elif name == "adjust_weekly_plan":
            adjustment = WeeklyPlanAdjustment(**args)
            data = adjust_weekly_plan_data(conn, adjustment)
            message = f"Weekly plan adjusted for {adjustment.week_start} from {data['effective_from']}"

        elif name == "get_dashboard_summary":
            data = dashboard()
            message = json.dumps(data, indent=2)

        elif name == "get_recent_context":
            data = recent_context(
                lookback_days=int(args.get("lookback_days", 14)),
                context_days=int(args.get("context_days", 30)),
                recent_activity_limit=int(args.get("recent_activity_limit", 12)),
                recent_note_limit=int(args.get("recent_note_limit", 5)),
            )
            message = json.dumps(data, indent=2)

        elif name == "get_activities":
            data = list_activities(
                limit=int(args.get("limit", 50)),
                type=args.get("type"),
                days=args.get("days"),
            )
            message = json.dumps(data, indent=2)

        elif name == "get_activity_stats":
            data = activity_stats(days=int(args.get("days", 30)))
            message = json.dumps(data, indent=2)

        elif name == "get_coach_notes":
            data = list_notes(
                limit=int(args.get("limit", 50)),
                category=args.get("category"),
            )
            message = json.dumps(data, indent=2)

        elif name == "get_metric_history":
            data = get_metric(
                metric_name=args["metric_name"],
                limit=int(args.get("limit", 100)),
            )
            message = json.dumps(data, indent=2)

        elif name == "get_metrics_catalog":
            data = {"metrics": METRIC_CATALOG}
            message = json.dumps(data, indent=2)

        elif name == "get_weekly_plans":
            data = list_weekly_plans(limit=int(args.get("limit", 12)))
            message = json.dumps(data, indent=2)

        elif name == "get_calendar_weeks":
            data = calendar_weeks(weeks=int(args.get("weeks", 8)))
            message = json.dumps(data, indent=2)

        else:
            raise ValueError(f"Unknown tool: {name}")

        return {
            "structuredContent": data,
            "content": [{"type": "text", "text": message}],
        }
    finally:
        conn.close()

# --- Activity endpoints ---

@app.post("/activities", status_code=201)
def create_activity(activity: Activity):
    conn = get_db()
    try:
        upsert_activity(conn, activity.model_dump())
        conn.commit()
        return {"status": "ok", "id": activity.id}
    finally:
        conn.close()

@app.get("/activities")
def list_activities(limit: int = 50, type: Optional[str] = None, days: Optional[int] = None):
    conn = get_db()
    query = "SELECT * FROM activities WHERE 1=1"
    params = []
    if type:
        if type == "Ride":
            query += " AND type IN (?, ?)"
            params.extend(["Ride", "VirtualRide"])
        else:
            query += " AND type = ?"
            params.append(type)
    if days:
        query += " AND date >= date('now', ?)"
        params.append(f"-{days} days")
    query += " ORDER BY date DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def backfill_stream_summaries(
    conn: sqlite3.Connection,
    activities: list[dict],
    access_token: str,
    thresholds: Optional[dict] = None,
) -> int:
    if not activities:
        return 0

    computed_thresholds = thresholds or estimate_thresholds(conn)
    streams_fetched = 0
    with httpx.Client(timeout=20, headers={"Authorization": f"Bearer {access_token}"}) as client:
        for activity in activities:
            streams, rate_limit = fetch_strava_activity_streams(client, activity["id"])
            summary = summarize_activity_streams(activity, streams, computed_thresholds)
            if summary:
                upsert_activity_stream_summary(conn, summary)
                streams_fetched += 1
            if should_pause_stream_fetch(rate_limit):
                break
    return streams_fetched

@app.get("/activities/stats")
def activity_stats(days: int = 30):
    conn = get_db()
    stats = conn.execute("""
        SELECT
            type,
            COUNT(*) as count,
            ROUND(SUM(distance_km), 1) as total_km,
            ROUND(AVG(avg_hr), 0) as avg_hr,
            ROUND(SUM(duration_min), 0) as total_min,
            ROUND(SUM(elevation_m), 0) as total_elevation
        FROM activities
        WHERE date >= date('now', ?)
        GROUP BY type
    """, (f"-{days} days",)).fetchall()
    conn.close()
    return [dict(r) for r in stats]

@app.get("/calendar/weeks")
def calendar_weeks(weeks: int = 8):
    safe_weeks = max(1, min(weeks, 16))
    conn = get_db()
    try:
        return build_calendar_weeks(conn, safe_weeks)
    finally:
        conn.close()

@app.get("/integrations/strava/status")
def strava_status():
    conn = get_db()
    latest_activity_date = get_latest_activity_date(conn)
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
    conn.close()
    config = strava_config()
    return {
        "configured": all(config.values()),
        "has_client_id": bool(config["client_id"]),
        "has_client_secret": bool(config["client_secret"]),
        "has_refresh_token": bool(config["refresh_token"]),
        "last_import_at": get_setting("strava_last_import_at"),
        "latest_activity_date": latest_activity_date,
        "pending_stream_backfill": int(pending_stream_backfill["count"] or 0) if pending_stream_backfill else 0,
        "stream_fetch_limit": STRAVA_STREAM_FETCH_LIMIT,
    }

@app.post("/integrations/strava/import", response_model=StravaImportResult)
def import_strava_activities(payload: StravaImportRequest):
    conn = get_db()
    try:
        resolved_start, resolved_end = resolve_strava_import_range(
            conn,
            payload.start_date,
            payload.end_date,
        )
        access_token = get_strava_access_token()
        raw_items = fetch_strava_activities(resolved_start, resolved_end, access_token=access_token)
        imported = 0
        activities = []
        for item in raw_items:
            activity = build_activity_from_strava(item)
            upsert_activity(conn, activity, preserve_annotations=True)
            activities.append(activity)
            imported += 1

        streams_fetched = 0
        if payload.fetch_streams and activities:
            thresholds = estimate_thresholds(conn)
            candidates = stream_fetch_candidates(conn, activities, limit=STRAVA_STREAM_FETCH_LIMIT)
            if candidates:
                streams_fetched = backfill_stream_summaries(conn, candidates, access_token, thresholds)
        conn.commit()
    finally:
        conn.close()

    set_setting("strava_last_import_at", datetime.now().isoformat())
    return StravaImportResult(
        imported=imported,
        fetched=len(raw_items),
        start_date=resolved_start,
        end_date=resolved_end,
        streams_fetched=streams_fetched,
    )

@app.post("/integrations/strava/streams/backfill", response_model=StravaStreamBackfillResult)
def backfill_strava_streams(payload: StravaStreamBackfillRequest):
    conn = get_db()
    try:
        candidates = list_stream_backfill_candidates(conn, limit=payload.limit or STRAVA_STREAM_FETCH_LIMIT)
        streams_fetched = 0
        if candidates:
            access_token = get_strava_access_token()
            streams_fetched = backfill_stream_summaries(conn, candidates, access_token)
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
    finally:
        conn.close()

    return StravaStreamBackfillResult(
        scanned=len(candidates),
        streams_fetched=streams_fetched,
        remaining_candidates=int(remaining_row["count"] or 0) if remaining_row else 0,
    )

# --- Coach notes endpoints ---

@app.post("/notes", status_code=201)
def create_note(note: CoachNote):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO coach_notes (date, category, content) VALUES (?,?,?)",
        (note.date, note.category, note.content)
    )
    conn.commit()
    note_id = cursor.lastrowid
    conn.close()
    return {"status": "ok", "id": note_id}

@app.get("/notes")
def list_notes(limit: int = 20, category: Optional[str] = None):
    conn = get_db()
    query = "SELECT * FROM coach_notes WHERE 1=1"
    params = []
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY date DESC, created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# --- Weekly summary endpoints ---

@app.post("/weekly", status_code=201)
def upsert_weekly(summary: WeeklySummary):
    conn = get_db()
    conn.execute("""
        INSERT OR REPLACE INTO weekly_summary
        (week_start, run_km, ride_km, strength_sessions, total_elevation, avg_hr, notes)
        VALUES (?,?,?,?,?,?,?)
    """, (
        summary.week_start, summary.run_km, summary.ride_km,
        summary.strength_sessions, summary.total_elevation,
        summary.avg_hr, summary.notes
    ))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/weekly")
def list_weekly(limit: int = 16):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM weekly_summary ORDER BY week_start DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/plans/weekly", status_code=201)
def upsert_weekly_plan(plan: WeeklyPlan):
    conn = get_db()
    upsert_weekly_plan_row(conn, plan)
    conn.commit()
    conn.close()
    return {"status": "ok", "week_start": plan.week_start}

@app.post("/plans/weekly/adjust")
def adjust_weekly_plan(adjustment: WeeklyPlanAdjustment):
    conn = get_db()
    try:
        return adjust_weekly_plan_data(conn, adjustment)
    finally:
        conn.close()

@app.get("/plans/weekly")
def list_weekly_plans(limit: int = 8):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM weekly_plans ORDER BY week_start DESC LIMIT ?",
        (limit,),
    ).fetchall()
    try:
        return [serialize_weekly_plan(row, conn) for row in rows]
    finally:
        conn.close()

# --- Metrics endpoints ---

@app.post("/metrics", status_code=201)
def create_metric(metric: Metric):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO metrics (date, metric, value, unit, notes) VALUES (?,?,?,?,?)",
        (metric.date, metric.metric, metric.value, metric.unit, metric.notes)
    )
    conn.commit()
    metric_id = cursor.lastrowid
    conn.close()
    return {"status": "ok", "id": metric_id}

@app.get("/metrics/{metric_name}")
def get_metric(metric_name: str, limit: int = 30):
    conn = get_db()
    if metric_name == "streak":
        streak = compute_activity_streak(conn)
        conn.close()
        if streak["date"] is None:
            return []
        return [{
            "id": "computed-streak",
            "date": streak["date"],
            "metric": "streak",
            "value": streak["value"],
            "unit": streak["unit"],
            "notes": "Computed automatically from consecutive activity days.",
        }]

    rows = conn.execute(
        "SELECT * FROM metrics WHERE metric = ? ORDER BY date DESC LIMIT ?",
        (metric_name, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/goals", status_code=201)
def create_goal(goal: Goal):
    start_day, end_day, _ = goal_period_window(goal.period_type)
    conn = get_db()
    cursor = conn.execute(
        """
        INSERT INTO goals
        (title, period_type, metric_type, target_value, start_date, end_date, activity_type, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            goal.title,
            goal.period_type,
            goal.metric_type,
            goal.target_value,
            goal.start_date or start_day.isoformat(),
            goal.end_date or end_day.isoformat(),
            goal.activity_type,
            1 if goal.is_active else 0,
        ),
    )
    conn.commit()
    goal_id = cursor.lastrowid
    conn.close()
    return {"status": "ok", "id": goal_id}

@app.get("/goals")
def list_goals(active_only: bool = False, limit: int = 24):
    conn = get_db()
    try:
        return list_goals_data(conn, active_only=active_only, limit=limit)
    finally:
        conn.close()

# --- Dashboard summary ---

@app.get("/dashboard")
def dashboard():
    conn = get_db()
    computed_streak = compute_activity_streak(conn)

    # Last 14 days stats
    recent = conn.execute("""
        SELECT type, COUNT(*) as count,
               ROUND(SUM(distance_km),1) as km,
               ROUND(AVG(avg_hr),0) as avg_hr,
               ROUND(SUM(duration_min),0) as total_min
        FROM activities WHERE date >= date('now', '-14 days')
        GROUP BY type
    """).fetchall()

    # Last 5 runs
    runs = conn.execute("""
        SELECT date, name, distance_km, avg_pace, avg_hr, zone2
        FROM activities WHERE type='Run'
        ORDER BY date DESC LIMIT 5
    """).fetchall()

    # Last 5 rides
    rides = conn.execute("""
        SELECT date, name, distance_km, avg_hr, avg_watts
        FROM activities WHERE type IN ('Ride','VirtualRide')
        ORDER BY date DESC LIMIT 5
    """).fetchall()

    # Latest coach notes
    notes = conn.execute("""
        SELECT date, category, content FROM coach_notes
        ORDER BY date DESC, created_at DESC LIMIT 5
    """).fetchall()

    # Z2 pace trend (last 10 runs)
    z2_trend = conn.execute("""
        SELECT date, avg_pace, avg_hr FROM activities
        WHERE type='Run' AND zone2=1
        ORDER BY date DESC LIMIT 10
    """).fetchall()

    # Latest metrics
    latest_metrics = conn.execute("""
        SELECT metric, value, unit, date FROM metrics
        WHERE (metric, date) IN (
            SELECT metric, MAX(date) FROM metrics GROUP BY metric
        )
    """).fetchall()

    cycling_snapshot = conn.execute("""
        SELECT
            ROUND(SUM(distance_km), 1) as total_km,
            ROUND(SUM(duration_min), 0) as total_min,
            ROUND(AVG(avg_hr), 0) as avg_hr,
            ROUND(AVG(avg_watts), 1) as avg_watts,
            COUNT(*) as sessions
        FROM activities
        WHERE type IN ('Ride','VirtualRide')
          AND date >= date('now', '-14 days')
    """).fetchone()

    cycling_daily = conn.execute("""
        SELECT
            date,
            ROUND(SUM(distance_km), 1) as km,
            ROUND(SUM(duration_min), 0) as total_min,
            ROUND(AVG(avg_watts), 1) as avg_watts
        FROM activities
        WHERE type IN ('Ride','VirtualRide')
        GROUP BY date
        ORDER BY date DESC
        LIMIT 8
    """).fetchall()

    ride_year_series = build_yearly_distance_series(conn, ("Ride", "VirtualRide"))
    run_year_series = build_yearly_distance_series(conn, ("Run",))
    strength_year_series = build_yearly_duration_series(conn, ("WeightTraining",))
    weekly_mix = build_weekly_mix(conn, 6)
    cycling_efficiency_trend = build_cycling_efficiency_trend(conn, 8)
    strength_consistency = build_strength_consistency(conn, 8, 2)
    active_goals = list_goals_data(conn, active_only=True, limit=4)
    latest_plan = conn.execute(
        """
        SELECT * FROM weekly_plans
        WHERE week_start <= date('now', '+7 days')
        ORDER BY week_start DESC
        LIMIT 1
        """
    ).fetchone()
    serialized_latest_plan = serialize_weekly_plan(latest_plan, conn) if latest_plan else None

    conn.close()
    return {
        "last_14_days": [dict(r) for r in recent],
        "recent_runs": [dict(r) for r in runs],
        "recent_rides": [dict(r) for r in rides],
        "coach_notes": [dict(r) for r in notes],
        "z2_pace_trend": [dict(r) for r in z2_trend],
        "latest_metrics": [dict(r) for r in latest_metrics],
        "cycling_snapshot": dict(cycling_snapshot) if cycling_snapshot else None,
        "cycling_daily": [dict(r) for r in cycling_daily],
        "ride_year_series": ride_year_series,
        "run_year_series": run_year_series,
        "strength_year_series": strength_year_series,
        "weekly_mix": weekly_mix,
        "cycling_efficiency_trend": cycling_efficiency_trend,
        "strength_consistency": strength_consistency,
        "active_goals": active_goals,
        "weekly_plan": serialized_latest_plan,
        "computed_streak": computed_streak,
    }

@app.get("/training-load")
def training_load(days: int = 42, focus_days: int = 28):
    conn = get_db()
    try:
        return build_training_load_summary(conn, days=days, focus_days=focus_days)
    finally:
        conn.close()

@app.get("/context/recent")
def recent_context(
    lookback_days: int = 14,
    context_days: int = 30,
    recent_activity_limit: int = 12,
    recent_note_limit: int = 5,
):
    safe_lookback = max(1, min(lookback_days, 60))
    safe_context = max(safe_lookback, min(context_days, 120))
    safe_activity_limit = max(1, min(recent_activity_limit, 30))
    safe_note_limit = max(1, min(recent_note_limit, 20))
    conn = get_db()
    try:
        return build_recent_context(
            conn,
            lookback_days=safe_lookback,
            context_days=safe_context,
            recent_activity_limit=safe_activity_limit,
            recent_note_limit=safe_note_limit,
        )
    finally:
        conn.close()

@app.get("/mcp")
def mcp_info():
    return {
        "name": MCP_SERVER_INFO["name"],
        "version": MCP_SERVER_INFO["version"],
        "endpoint": "/mcp",
        "transport": "jsonrpc-http",
    }

@app.post("/mcp")
def mcp_rpc(message: dict):
    try:
        method = message.get("method")
        msg_id = message.get("id")

        if msg_id is None:
            return {}

        if method == "initialize":
            return make_mcp_response(
                msg_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": MCP_SERVER_INFO,
                },
            )

        if method == "ping":
            return make_mcp_response(msg_id, {})

        if method == "tools/list":
            return make_mcp_response(msg_id, {"tools": build_mcp_tools()})

        if method == "tools/call":
            params = message.get("params", {})
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            if not tool_name:
                return make_mcp_response(
                    msg_id,
                    error={"code": -32602, "message": "Missing tool name"},
                )
            return make_mcp_response(msg_id, call_mcp_tool(tool_name, tool_args))

        return make_mcp_response(
            msg_id,
            error={"code": -32601, "message": f"Method not found: {method}"},
        )
    except HTTPException as exc:
        return make_mcp_response(
            message.get("id"),
            error={"code": -32000, "message": str(exc.detail)},
        )
    except Exception as exc:
        return make_mcp_response(
            message.get("id"),
            error={"code": -32000, "message": str(exc)},
        )

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
