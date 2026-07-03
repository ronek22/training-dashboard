import sqlite3
from typing import Optional


def get_activity_detail_row(conn: sqlite3.Connection, activity_id: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        """
        SELECT activity_id, fetched_at, source_status, detail_json, streams_json, route_polyline
        FROM activity_details
        WHERE activity_id = ?
        """,
        (activity_id,),
    ).fetchone()


def upsert_activity_detail_row(
    conn: sqlite3.Connection,
    activity_id: str,
    fetched_at: str,
    source_status: str,
    detail_json: Optional[str],
    streams_json: Optional[str],
    route_polyline: Optional[str],
) -> None:
    conn.execute(
        """
        INSERT INTO activity_details
        (activity_id, fetched_at, source_status, detail_json, streams_json, route_polyline, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(activity_id) DO UPDATE SET
            fetched_at=excluded.fetched_at,
            source_status=excluded.source_status,
            detail_json=excluded.detail_json,
            streams_json=excluded.streams_json,
            route_polyline=excluded.route_polyline,
            updated_at=CURRENT_TIMESTAMP
        """,
        (activity_id, fetched_at, source_status, detail_json, streams_json, route_polyline),
    )
