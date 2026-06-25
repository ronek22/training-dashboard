import sqlite3
from typing import Optional


def get_latest_activity_date(conn: sqlite3.Connection) -> Optional[str]:
    row = conn.execute("SELECT MAX(date) AS date FROM activities").fetchone()
    return row["date"] if row and row["date"] else None


def upsert_activity_row(conn: sqlite3.Connection, activity: dict, preserve_annotations: bool = False) -> None:
    if preserve_annotations:
        existing = conn.execute(
            "SELECT notes, zone2 FROM activities WHERE id = ?",
            (activity["id"],),
        ).fetchone()
        if existing:
            activity["notes"] = existing["notes"]
            if existing["zone2"] is not None:
                activity["zone2"] = bool(existing["zone2"])

    conn.execute(
        """
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
        """,
        (
            activity["id"],
            activity["date"],
            activity["type"],
            activity["name"],
            activity["distance_km"],
            activity["duration_min"],
            activity["avg_hr"],
            activity["max_hr"],
            activity["avg_pace"],
            activity["avg_watts"],
            activity["elevation_m"],
            activity["calories"],
            1 if activity["zone2"] else 0,
            activity["notes"],
        ),
    )


def list_activity_rows(
    conn: sqlite3.Connection,
    limit: int = 50,
    activity_type: Optional[str] = None,
    days: Optional[int] = None,
) -> list[sqlite3.Row]:
    query = "SELECT * FROM activities WHERE 1=1"
    params: list[object] = []
    if activity_type:
        if activity_type == "Ride":
            query += " AND type IN (?, ?)"
            params.extend(["Ride", "VirtualRide"])
        else:
            query += " AND type = ?"
            params.append(activity_type)
    if days:
        query += " AND date >= date('now', ?)"
        params.append(f"-{days} days")
    query += " ORDER BY date DESC LIMIT ?"
    params.append(limit)
    return conn.execute(query, params).fetchall()


def list_activity_stat_rows(conn: sqlite3.Connection, days: int = 30) -> list[sqlite3.Row]:
    return conn.execute(
        """
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
        """,
        (f"-{days} days",),
    ).fetchall()


def list_calendar_activity_rows(
    conn: sqlite3.Connection,
    start_date: str,
    end_date: str,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, date, type, name, distance_km, duration_min, avg_hr, avg_pace,
               avg_watts, elevation_m, zone2
        FROM activities
        WHERE date >= ? AND date <= ?
        ORDER BY date DESC, created_at DESC
        """,
        (start_date, end_date),
    ).fetchall()
