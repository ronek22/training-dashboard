import sqlite3


def upsert_weekly_summary_row(conn: sqlite3.Connection, summary: dict) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO weekly_summary
        (week_start, run_km, ride_km, strength_sessions, total_elevation, avg_hr, notes)
        VALUES (?,?,?,?,?,?,?)
        """,
        (
            summary["week_start"],
            summary["run_km"],
            summary["ride_km"],
            summary["strength_sessions"],
            summary["total_elevation"],
            summary["avg_hr"],
            summary["notes"],
        ),
    )


def list_weekly_summary_rows(conn: sqlite3.Connection, limit: int = 16) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM weekly_summary ORDER BY week_start DESC LIMIT ?",
        (limit,),
    ).fetchall()
