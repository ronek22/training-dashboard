"""Detect a multi-week slide in training volume that the plan did not ask for.

Rule (completed Monday-Sunday weeks only; walks and hikes are not training volume):
- Look at the last three completed weeks W1, W2, W3 (W3 = last week).
- Trigger when volume fell twice in a row (W1 > W2 > W3), W3 is at most 75% of W1,
  and W3 is at least 20% below the average of the four weeks before W1.
- A falling week counts as planned when its weekly plan is lighter by design: planned
  minutes at least 15% below the average of the previous three plans, or a title that
  says deload, taper or recovery week. If both falling weeks were planned, no alert.
- Coverage: the four baseline weeks need 4+ sessions in total and W1 needs 120+ minutes.
The athlete can label an alert (planned / life / illness_injury); the label is kept per
W3 week, hides the alert and is passed to coaching context.
"""
import json
import re
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

NON_TRAINING_TYPES = ("Walk", "Hike")
LABELS = {"planned": "Planned lighter stretch", "life": "Life got in the way", "illness_injury": "Illness or injury"}
LIGHTER_TITLE = re.compile(r"\b(deload|taper|recovery week|rest week)\b", re.IGNORECASE)
DROP_FROM_START = 0.75
DROP_FROM_BASELINE = 0.80
LIGHTER_PLAN = 0.85


def _week_minutes(conn: sqlite3.Connection, week_start: date) -> tuple[int, int]:
    placeholders = ",".join("?" for _ in NON_TRAINING_TYPES)
    row = conn.execute(
        f"""
        SELECT ROUND(COALESCE(SUM(duration_min), 0)) AS total_min, COUNT(*) AS sessions
        FROM activities
        WHERE date >= ? AND date <= ? AND type NOT IN ({placeholders})
        """,
        (week_start.isoformat(), (week_start + timedelta(days=6)).isoformat(), *NON_TRAINING_TYPES),
    ).fetchone()
    return int(row["total_min"] or 0), int(row["sessions"] or 0)


def _planned_minutes(conn: sqlite3.Connection, week_start: date) -> tuple[Optional[int], str]:
    row = conn.execute("SELECT title, days_json FROM weekly_plans WHERE week_start = ?", (week_start.isoformat(),)).fetchone()
    if not row:
        return None, ""
    total = 0
    for day in json.loads(row["days_json"] or "[]"):
        if str(day.get("session_type") or "").lower() in {"walk", "hike", "rest"}:
            continue
        total += int(day.get("target_duration_min") or 0)
    return total, row["title"] or ""


def _planned_lighter(conn: sqlite3.Connection, week_start: date) -> bool:
    planned, title = _planned_minutes(conn, week_start)
    if planned is None:
        return False
    if LIGHTER_TITLE.search(title):
        return True
    previous = [_planned_minutes(conn, week_start - timedelta(weeks=offset))[0] for offset in (1, 2, 3)]
    previous = [value for value in previous if value]
    return bool(previous) and planned <= LIGHTER_PLAN * (sum(previous) / len(previous))


def get_volume_trend_label(conn: sqlite3.Connection, week_start: str) -> Optional[dict]:
    try:
        row = conn.execute("SELECT week_start, label, note, updated_at FROM volume_trend_labels WHERE week_start = ?", (week_start,)).fetchone()
    except sqlite3.OperationalError:
        return None
    return dict(row) if row else None


def save_volume_trend_label(conn: sqlite3.Connection, week_start: str, label: str, note: Optional[str] = None) -> dict:
    conn.execute(
        """
        INSERT INTO volume_trend_labels (week_start, label, note) VALUES (?, ?, ?)
        ON CONFLICT(week_start) DO UPDATE SET label = excluded.label, note = excluded.note, updated_at = CURRENT_TIMESTAMP
        """,
        (week_start, label, note or None),
    )
    conn.commit()
    return get_volume_trend_label(conn, week_start)


def build_volume_trend(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    today = today or datetime.now().date()
    current_week_start = today - timedelta(days=today.weekday())
    window = [current_week_start - timedelta(weeks=offset) for offset in (3, 2, 1)]
    baseline_weeks = [window[0] - timedelta(weeks=offset) for offset in (4, 3, 2, 1)]

    weeks = [
        {"week_start": start.isoformat(), "label": start.strftime("%b %d"), "total_min": _week_minutes(conn, start)[0]}
        for start in window
    ]
    baseline = [_week_minutes(conn, start) for start in baseline_weeks]
    baseline_min = round(sum(minutes for minutes, _ in baseline) / len(baseline))
    baseline_sessions = sum(sessions for _, sessions in baseline)
    first, middle, last = (week["total_min"] for week in weeks)
    result = {
        "status": "steady",
        "alert": False,
        "weeks": weeks,
        "baseline_min": baseline_min,
        "week_start": weeks[-1]["week_start"],
        "label": None,
        "message": None,
    }

    if baseline_sessions < 4 or first < 120:
        return {**result, "status": "insufficient_data"}
    sliding = first > middle > last and last <= DROP_FROM_START * first and last <= DROP_FROM_BASELINE * baseline_min
    if not sliding:
        return result
    if all(_planned_lighter(conn, start) for start in window[1:]):
        return {**result, "status": "planned_lighter"}

    drop_pct = round(100 * (1 - last / first))
    label = get_volume_trend_label(conn, result["week_start"])
    return {
        **result,
        "status": "sliding",
        "alert": label is None,
        "drop_pct": drop_pct,
        "label": {**label, "label_text": LABELS.get(label["label"], label["label"])} if label else None,
        "message": f"Training volume fell two weeks in a row: {first} → {middle} → {last} min ({drop_pct}% down), "
                   f"below your usual ~{baseline_min} min and not planned as a lighter stretch.",
    }
