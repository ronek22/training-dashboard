import sqlite3
from typing import Optional

from ..repositories.metrics import insert_metric, list_metric_rows


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
