import sqlite3
from typing import Optional

from ..repositories.metrics import insert_metric, list_metric_rows
from .settings import get_performance_settings_for_conn


def create_metric_data(conn: sqlite3.Connection, date: str, metric: str, value: float, unit: Optional[str], notes: Optional[str]) -> dict:
    metric_id = insert_metric(conn, date, metric, value, unit, notes)
    conn.commit()
    return {"status": "ok", "id": metric_id}


def get_metric_history_data(
    conn: sqlite3.Connection,
    metric_name: str,
    limit: int,
    compute_activity_streak_fn,
) -> list[dict]:
    if metric_name == "streak":
        streak = compute_activity_streak_fn(conn)
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

    rows = list_metric_rows(conn, metric_name, limit)
    return [dict(row) for row in rows]


def _pace_to_seconds(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    parts = str(value).strip().split(":")
    if len(parts) != 2:
        return None
    try:
        minutes = int(parts[0])
        seconds = int(parts[1])
    except ValueError:
        return None
    if minutes < 0 or seconds < 0 or seconds >= 60:
        return None
    return float(minutes * 60 + seconds)


def _recent_best_run_benchmark(conn: sqlite3.Connection, distance_km: float) -> dict:
    benchmark_key = f"run_{int(distance_km) if float(distance_km).is_integer() else str(distance_km).replace('.', '_')}_best"
    min_distance = max(distance_km * 0.97, distance_km - 0.2)
    max_distance = distance_km * 1.03
    row = conn.execute(
        """
        SELECT id, date, name, distance_km, duration_min
        FROM activities
        WHERE type = 'Run'
          AND distance_km >= ? AND distance_km <= ?
          AND duration_min IS NOT NULL
        ORDER BY duration_min ASC, date DESC
        LIMIT 1
        """,
        (min_distance, max_distance),
    ).fetchone()
    if not row:
        return {
            "key": benchmark_key,
            "label": f"Best recent {distance_km:g}k",
            "available": False,
            "value": None,
            "unit": "min",
            "activity_id": None,
            "date": None,
            "name": None,
        }
    return {
        "key": benchmark_key,
        "label": f"Best recent {distance_km:g}k",
        "available": True,
        "value": round(float(row["duration_min"] or 0), 1),
        "unit": "min",
        "activity_id": row["id"],
        "date": row["date"],
        "name": row["name"],
    }


def _best_recent_ride_power(conn: sqlite3.Connection, duration_min: float = 10.0) -> dict:
    row = conn.execute(
        """
        SELECT id, date, name, avg_watts, duration_min
        FROM activities
        WHERE type IN ('Ride', 'VirtualRide')
          AND duration_min >= ?
          AND avg_watts IS NOT NULL
        ORDER BY avg_watts DESC, date DESC
        LIMIT 1
        """,
        (duration_min,),
    ).fetchone()
    if not row:
        return {
            "key": "ride_best_10min_power",
            "label": "Best recent 10-minute power",
            "available": False,
            "value": None,
            "unit": "W",
            "activity_id": None,
            "date": None,
            "name": None,
        }
    return {
        "key": "ride_best_10min_power",
        "label": "Best recent 10-minute power",
        "available": True,
        "value": round(float(row["avg_watts"] or 0)),
        "unit": "W",
        "activity_id": row["id"],
        "date": row["date"],
        "name": row["name"],
    }


def _zone2_window(conn: sqlite3.Connection, settings: dict, *, start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
    run_anchor = (((settings or {}).get("anchors") or {}).get("run_threshold_pace") or {}).get("value")
    ride_anchor = (((settings or {}).get("anchors") or {}).get("ride_threshold_power") or {}).get("value")
    run_zone = (((settings or {}).get("zones") or {}).get("run") or {})
    ride_zone = (((settings or {}).get("zones") or {}).get("ride") or {})
    params: list[object] = []
    clauses = []
    if start_date:
        clauses.append("a.date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("a.date <= ?")
        params.append(end_date)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""
        SELECT
            a.id,
            a.date,
            a.type,
            a.name,
            a.duration_min,
            a.avg_pace,
            a.avg_watts,
            s.low_aerobic_seconds
        FROM activities a
        LEFT JOIN activity_stream_summaries s ON s.activity_id = a.id
        {where_sql}
        ORDER BY a.date DESC, a.created_at DESC
        """,
        params,
    ).fetchall()

    total_seconds = 0
    best_seconds = 0
    best_activity = None
    contributing_sessions = 0
    run_ready = bool(run_anchor)
    ride_ready = bool(ride_anchor)

    for row in rows:
        zone_seconds = 0
        if row["type"] == "Run" and run_ready:
            if row["low_aerobic_seconds"]:
                zone_seconds = int(row["low_aerobic_seconds"] or 0)
            else:
                avg_pace_seconds = _pace_to_seconds(row["avg_pace"])
                lower = float(run_anchor) * float(run_zone.get("zone2_lower_pct") or 1.15)
                upper = float(run_anchor) * float(run_zone.get("zone2_upper_pct") or 1.3)
                if avg_pace_seconds and lower <= avg_pace_seconds <= upper:
                    zone_seconds = int(round(float(row["duration_min"] or 0) * 60))
        elif row["type"] in {"Ride", "VirtualRide"} and ride_ready:
            if row["low_aerobic_seconds"]:
                zone_seconds = int(row["low_aerobic_seconds"] or 0)
            else:
                avg_watts = float(row["avg_watts"] or 0)
                lower = float(ride_anchor) * float(ride_zone.get("zone2_lower_pct") or 0.56)
                upper = float(ride_anchor) * float(ride_zone.get("zone2_upper_pct") or 0.75)
                if avg_watts and lower <= avg_watts <= upper:
                    zone_seconds = int(round(float(row["duration_min"] or 0) * 60))

        if zone_seconds <= 0:
            continue
        contributing_sessions += 1
        total_seconds += zone_seconds
        if zone_seconds > best_seconds:
            best_seconds = zone_seconds
            best_activity = row

    missing = []
    if not run_ready:
        missing.append("running threshold pace")
    if not ride_ready:
        missing.append("cycling threshold power")

    return {
        "available": run_ready or ride_ready,
        "missing": missing,
        "total_hours": round(total_seconds / 3600.0, 1),
        "session_count": contributing_sessions,
        "best_block_minutes": round(best_seconds / 60.0, 1) if best_seconds else None,
        "best_block_activity_id": best_activity["id"] if best_activity else None,
        "best_block_date": best_activity["date"] if best_activity else None,
        "best_block_name": best_activity["name"] if best_activity else None,
    }


def get_performance_summary_data(conn: sqlite3.Connection) -> dict:
    settings = get_performance_settings_for_conn(conn)
    zone2 = _zone2_window(conn, settings, start_date="1970-01-01")
    return {
        "settings": settings,
        "derived": {
            "benchmarks": [
                _recent_best_run_benchmark(conn, 5.0),
                _recent_best_run_benchmark(conn, 10.0),
                _best_recent_ride_power(conn, 10.0),
            ],
            "zone2_foundation": {
                "available": zone2["available"],
                "missing": zone2["missing"],
                "total_hours": zone2["total_hours"],
                "session_count": zone2["session_count"],
                "longest_recent_block_min": zone2["best_block_minutes"],
                "longest_recent_block_date": zone2["best_block_date"],
                "longest_recent_block_name": zone2["best_block_name"],
                "summary": (
                    f"Longest recent zone 2 block: {zone2['best_block_minutes']:.1f} min."
                    if zone2["best_block_minutes"] else
                    "Zone 2 anchors are set, but no recent qualifying block is available."
                    if zone2["available"] else
                    "Zone 2 reads stay unavailable until at least one manual threshold anchor is set."
                ),
            },
        },
    }


def get_zone2_foundation_for_window(
    conn: sqlite3.Connection,
    *,
    start_date: str,
    end_date: str,
) -> dict:
    settings = get_performance_settings_for_conn(conn)
    return _zone2_window(conn, settings, start_date=start_date, end_date=end_date)
