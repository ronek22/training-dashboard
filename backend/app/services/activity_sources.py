import json
import sqlite3
from datetime import datetime
from typing import Optional


def get_source_activity_id(conn: sqlite3.Connection, source: str, external_id: str) -> Optional[str]:
    row = conn.execute(
        "SELECT activity_id FROM activity_source_refs WHERE source = ? AND external_id = ?",
        (source, external_id),
    ).fetchone()
    return row["activity_id"] if row and row["activity_id"] else None


def upsert_source_ref(
    conn: sqlite3.Connection,
    *,
    source: str,
    external_id: str,
    activity_id: Optional[str],
    started_at: Optional[str],
    status: str = "linked",
    file_name: Optional[str] = None,
    file_hash: Optional[str] = None,
    match_reason: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO activity_source_refs
        (source, external_id, activity_id, started_at, file_name, file_hash, status, match_reason, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, external_id) DO UPDATE SET
            activity_id=excluded.activity_id,
            started_at=excluded.started_at,
            file_name=excluded.file_name,
            file_hash=excluded.file_hash,
            status=excluded.status,
            match_reason=excluded.match_reason,
            metadata_json=excluded.metadata_json,
            updated_at=CURRENT_TIMESTAMP
        """,
        (
            source, external_id, activity_id, started_at, file_name, file_hash,
            status, match_reason, json.dumps(metadata or {}),
        ),
    )


def _relative_delta(left: Optional[float], right: Optional[float], floor: float) -> Optional[float]:
    if left is None or right is None:
        return None
    return abs(float(left) - float(right)) / max(abs(float(left)), abs(float(right)), floor)


def find_activity_match(conn: sqlite3.Connection, candidate: dict) -> dict:
    rows = conn.execute(
        "SELECT * FROM activities WHERE date = ? AND type = ? ORDER BY created_at, id",
        (candidate["date"], candidate["type"]),
    ).fetchall()
    scored = []
    for row in rows:
        duration_delta = _relative_delta(candidate.get("duration_min"), row["duration_min"], 10.0)
        distance_delta = _relative_delta(candidate.get("distance_km"), row["distance_km"], 1.0)
        hr_delta = _relative_delta(candidate.get("avg_hr"), row["avg_hr"], 100.0)
        if duration_delta is not None and duration_delta > 0.08:
            continue
        if distance_delta is not None and distance_delta > 0.08:
            continue
        evidence = 0
        score = 0.0
        if duration_delta is not None:
            evidence += 1
            score += duration_delta * 5
        if distance_delta is not None:
            evidence += 1
            score += distance_delta * 5
        if hr_delta is not None:
            evidence += 1
            score += min(hr_delta, 0.2)
        if evidence:
            scored.append((score, dict(row)))

    scored.sort(key=lambda item: item[0])
    if not scored:
        return {"status": "none", "activity": None, "reason": "No same-day activity passed conservative metric tolerances."}
    best_score, best = scored[0]
    if len(scored) > 1 and scored[1][0] - best_score < 0.04:
        return {"status": "ambiguous", "activity": None, "reason": "Multiple same-day activities have similarly close metrics."}
    return {
        "status": "matched",
        "activity": best,
        "reason": "Unique same-day type match with compatible duration, distance, and heart rate.",
    }


def strava_started_at(item: dict) -> Optional[str]:
    value = item.get("start_date") or item.get("start_date_local")
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return value
