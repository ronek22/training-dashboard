import math
import sqlite3
from datetime import datetime, timedelta
from typing import Callable, Optional

from .plans import build_multi_week_execution_trend, serialize_weekly_plan
from .plans import format_workout_intent_label, normalize_workout_intent
from .activity_feedback import attach_feedback_by_activity_id, list_recent_feedback_data
from .goals import aggregate_goal_risk_summary, list_goals_data
from .recommendations import build_daily_recommendation, latest_subjective_state
from .settings import get_modality_restrictions_for_conn


def select_active_weekly_plan_row(conn: sqlite3.Connection) -> Optional[sqlite3.Row]:
    today = datetime.now().date()
    current_week_start = (today - timedelta(days=today.weekday())).isoformat()
    current_week_end = (today + timedelta(days=(6 - today.weekday()))).isoformat()

    current_row = conn.execute(
        """
        SELECT *
        FROM weekly_plans
        WHERE week_start >= ? AND week_start <= ?
        ORDER BY week_start ASC
        LIMIT 1
        """,
        (current_week_start, current_week_end),
    ).fetchone()
    if current_row:
        return current_row

    upcoming_row = conn.execute(
        """
        SELECT *
        FROM weekly_plans
        WHERE week_start > ?
        ORDER BY week_start ASC
        LIMIT 1
        """,
        (current_week_end,),
    ).fetchone()
    if upcoming_row:
        return upcoming_row

    return conn.execute(
        """
        SELECT *
        FROM weekly_plans
        WHERE week_start < ?
        ORDER BY week_start DESC
        LIMIT 1
        """,
        (current_week_start,),
    ).fetchone()


def compute_activity_streak(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT DISTINCT date FROM activities ORDER BY date DESC"
    ).fetchall()
    if not rows:
        return {"value": 0, "unit": "days", "date": None}

    dates = [datetime.strptime(row["date"], "%Y-%m-%d").date() for row in rows]
    today = datetime.now().date()
    latest = dates[0]

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


def build_activity_heatmap(conn: sqlite3.Connection) -> dict:
    today = datetime.now().date()
    year_start = today.replace(month=1, day=1)
    year_end = today.replace(month=12, day=31)
    grid_start = year_start - timedelta(days=year_start.weekday())
    grid_end = year_end + timedelta(days=(6 - year_end.weekday()))

    rows = conn.execute(
        """
        SELECT
            date,
            COUNT(*) AS sessions,
            ROUND(SUM(duration_min), 0) AS total_duration_min,
            ROUND(SUM(distance_km), 1) AS total_distance_km
        FROM activities
        WHERE date >= ? AND date <= ?
        GROUP BY date
        ORDER BY date
        """,
        (grid_start.isoformat(), grid_end.isoformat()),
    ).fetchall()

    by_date = {
        row["date"]: {
            "sessions": int(row["sessions"] or 0),
            "total_duration_min": int(row["total_duration_min"] or 0),
            "total_distance_km": float(row["total_distance_km"] or 0),
        }
        for row in rows
    }

    active_scores = []
    cells = []
    month_labels = []
    current = grid_start
    week_index = 0
    previous_month = None

    while current <= grid_end:
        if current.weekday() == 0:
            month_label = current.strftime("%b")
            if previous_month != current.month:
                month_labels.append({"label": month_label, "week_index": week_index})
                previous_month = current.month
            week_index += 1 if cells else 0

        entry = by_date.get(current.isoformat(), {"sessions": 0, "total_duration_min": 0, "total_distance_km": 0.0})
        score = entry["total_duration_min"] + (entry["sessions"] * 20)
        if score > 0:
            active_scores.append(score)
        cells.append(
            {
                "date": current.isoformat(),
                "weekday_index": current.weekday(),
                "week_index": (len(cells) // 7),
                "day_of_month": current.day,
                "in_year": current >= year_start and current <= year_end,
                "is_future": current > today and current <= year_end,
                "sessions": entry["sessions"],
                "total_duration_min": entry["total_duration_min"],
                "total_distance_km": round(entry["total_distance_km"], 1),
                "score": score,
            }
        )
        current += timedelta(days=1)

    if active_scores:
        max_score = max(active_scores)
        thresholds = [
            max_score * 0.25,
            max_score * 0.5,
            max_score * 0.75,
            max_score,
        ]
    else:
        thresholds = [0, 0, 0, 0]

    for cell in cells:
        score = cell["score"]
        if score <= 0:
            cell["level"] = 0
        elif score <= thresholds[0]:
            cell["level"] = 1
        elif score <= thresholds[1]:
            cell["level"] = 2
        elif score <= thresholds[2]:
            cell["level"] = 3
        else:
            cell["level"] = 4

    return {
        "year": today.year,
        "range_start": year_start.isoformat(),
        "range_end": year_end.isoformat(),
        "total_active_days": sum(1 for cell in cells if cell["score"] > 0 and not cell["is_future"] and cell["in_year"]),
        "month_labels": month_labels,
        "cells": cells,
    }


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


def build_activity_intent_summary(activities: list[dict]) -> dict:
    by_intent: dict[str, dict] = {}
    for activity in activities:
        normalized_intent = normalize_workout_intent(activity.get("workout_intent"), activity.get("type"))
        if not normalized_intent:
            continue
        bucket = by_intent.setdefault(
            normalized_intent,
            {
                "intent": normalized_intent,
                "label": format_workout_intent_label(normalized_intent),
                "sessions": 0,
                "total_min": 0.0,
            },
        )
        bucket["sessions"] += 1
        bucket["total_min"] += float(activity.get("duration_min") or 0)

    ranked = sorted(
        by_intent.values(),
        key=lambda item: (-item["sessions"], -item["total_min"], item["label"]),
    )
    for item in ranked:
        item["total_min"] = round(item["total_min"], 0)
    return {
        "count": len(ranked),
        "top": ranked[:6],
    }


def build_planned_intent_summary(active_plan: Optional[dict]) -> dict:
    if not active_plan:
        return {"count": 0, "top": []}

    by_intent: dict[str, dict] = {}
    for day in active_plan.get("days", []):
        normalized_intent = normalize_workout_intent(day.get("workout_intent"), day.get("session_type"))
        if not normalized_intent:
            continue
        bucket = by_intent.setdefault(
            normalized_intent,
            {
                "intent": normalized_intent,
                "label": format_workout_intent_label(normalized_intent),
                "sessions": 0,
            },
        )
        bucket["sessions"] += 1

    ranked = sorted(
        by_intent.values(),
        key=lambda item: (-item["sessions"], item["label"]),
    )
    return {
        "count": len(ranked),
        "top": ranked[:6],
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
        SELECT id, date, type, workout_intent, name, distance_km, duration_min, avg_hr, avg_pace, avg_watts, zone2, linked_planned_session_id
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
    training_load = build_training_load_summary(conn)
    active_goals = list_goals_data(conn, active_only=True, limit=8)
    modality_restrictions = get_modality_restrictions_for_conn(conn)
    goal_risk_summary = aggregate_goal_risk_summary(active_goals)
    planning_priority = sorted(
        active_goals,
        key=lambda goal: (
            {"constrained": 0, "at_risk": 1, "under_pressure": 2, "watch": 3, "on_track": 4, "completed": 5}.get(
                goal.get("risk_summary", {}).get("status", "on_track"),
                6,
            ),
            goal.get("days_remaining", 9999),
        ),
    )

    latest_plan = select_active_weekly_plan_row(conn)
    serialized_latest_plan = serialize_weekly_plan(latest_plan, conn) if latest_plan else None
    daily_recommendation = build_daily_recommendation(conn, training_load_summary=training_load, weekly_plan=serialized_latest_plan)
    recent_activities = attach_feedback_by_activity_id(conn, [dict(row) for row in activities])
    recent_activity_intents = build_activity_intent_summary(recent_activities)
    planned_intents = build_planned_intent_summary(serialized_latest_plan)

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
        "recent_activities": recent_activities,
        "recent_feedback": list_recent_feedback_data(conn, limit=5),
        "latest_subjective_state": latest_subjective_state(conn),
        "recent_notes": [dict(row) for row in notes],
        "latest_metrics": [dict(row) for row in latest_metrics],
        "weekly_mix": weekly_mix,
        "strength_consistency": strength_consistency,
        "modality_restrictions": modality_restrictions,
        "active_goals": active_goals,
        "goal_risk_summary": goal_risk_summary,
        "goal_planning_summary": {
            "count": len(active_goals),
            "constrained": sum(1 for goal in active_goals if goal.get("is_constrained")),
            "most_urgent": planning_priority[:3],
            "statuses": {
                "constrained": sum(1 for goal in active_goals if goal.get("planning_guidance", {}).get("status") == "constrained"),
                "urgent": sum(1 for goal in active_goals if goal.get("planning_guidance", {}).get("status") == "urgent"),
                "pressured": sum(1 for goal in active_goals if goal.get("planning_guidance", {}).get("status") == "pressured"),
                "steady": sum(1 for goal in active_goals if goal.get("planning_guidance", {}).get("status") == "steady"),
                "comfortable": sum(1 for goal in active_goals if goal.get("planning_guidance", {}).get("status") == "comfortable"),
                "completed": sum(1 for goal in active_goals if goal.get("planning_guidance", {}).get("status") == "completed"),
            },
        },
        "workout_intent_summary": {
            "recent_activities": recent_activity_intents,
            "active_plan": planned_intents,
        },
        "active_plan": serialized_latest_plan,
        "daily_recommendation": daily_recommendation,
        "training_load": training_load,
    }


def build_dashboard_data(
    conn: sqlite3.Connection,
    list_goals_data_fn: Callable[[sqlite3.Connection, bool, int], list[dict]],
) -> dict:
    computed_streak = compute_activity_streak(conn)

    recent = conn.execute("""
        SELECT type, COUNT(*) as count,
               ROUND(SUM(distance_km),1) as km,
               ROUND(AVG(avg_hr),0) as avg_hr,
               ROUND(SUM(duration_min),0) as total_min
        FROM activities WHERE date >= date('now', '-14 days')
        GROUP BY type
    """).fetchall()

    runs = conn.execute("""
        SELECT date, name, distance_km, avg_pace, avg_hr, zone2
        FROM activities WHERE type='Run'
        ORDER BY date DESC LIMIT 5
    """).fetchall()

    rides = conn.execute("""
        SELECT date, name, distance_km, avg_hr, avg_watts
        FROM activities WHERE type IN ('Ride','VirtualRide')
        ORDER BY date DESC LIMIT 5
    """).fetchall()

    notes = conn.execute("""
        SELECT date, category, content FROM coach_notes
        ORDER BY date DESC, created_at DESC LIMIT 5
    """).fetchall()

    z2_trend = conn.execute("""
        SELECT date, avg_pace, avg_hr FROM activities
        WHERE type='Run' AND zone2=1
        ORDER BY date DESC LIMIT 10
    """).fetchall()

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
    activity_heatmap = build_activity_heatmap(conn)
    weekly_mix = build_weekly_mix(conn, 6)
    cycling_efficiency_trend = build_cycling_efficiency_trend(conn, 8)
    strength_consistency = build_strength_consistency(conn, 8, 2)
    active_goals = list_goals_data_fn(conn, active_only=True, limit=4)
    modality_restrictions = get_modality_restrictions_for_conn(conn)
    goal_risk_summary = aggregate_goal_risk_summary(active_goals)
    training_load = build_training_load_summary(conn)
    latest_plan = select_active_weekly_plan_row(conn)
    serialized_latest_plan = serialize_weekly_plan(latest_plan, conn) if latest_plan else None
    daily_recommendation = build_daily_recommendation(conn, training_load_summary=training_load, weekly_plan=serialized_latest_plan)
    execution_trend = build_multi_week_execution_trend(conn, weeks=6)

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
        "activity_heatmap": activity_heatmap,
        "weekly_mix": weekly_mix,
        "cycling_efficiency_trend": cycling_efficiency_trend,
        "strength_consistency": strength_consistency,
        "modality_restrictions": modality_restrictions,
        "active_goals": active_goals,
        "goal_risk_summary": goal_risk_summary,
        "weekly_plan": serialized_latest_plan,
        "execution_trend": execution_trend,
        "computed_streak": computed_streak,
        "recent_feedback": list_recent_feedback_data(conn, limit=5),
        "latest_subjective_state": latest_subjective_state(conn),
        "daily_recommendation": daily_recommendation,
    }
