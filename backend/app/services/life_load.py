"""Life-load tags: days where life, not the body, limits training.

Unlike sick mode (a period about the body), these are per-day tags about time and attention:
travel, deadline, family, poor sleep, late night. They are set ahead or afterwards. Ahead,
the plan flags hard or long sessions on tagged days and suggests a calmer day to swap with;
afterwards, the weekly review can see that missed sessions fell on tagged days, and a falling
volume week with 3+ tagged days is labelled "life" instead of a motivation problem.
"""
import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

TAGS = {
    "travel": {"label": "Travel", "icon": "✈"},
    "deadline": {"label": "Deadline", "icon": "⚑"},
    "family": {"label": "Family", "icon": "⌂"},
    "poor_sleep": {"label": "Poor sleep", "icon": "☾"},
    "late_night": {"label": "Late night", "icon": "✦"},
}

# Intensity and length that do not belong on a tagged day; lifts and easy sessions are fine.
HARD_INTENTS = {"interval": "hard intensity", "tempo": "hard intensity", "race_specific": "hard intensity"}
LONG_SESSION_MIN = 90


def _today(today: Optional[date]) -> date:
    return today or datetime.now().date()


def public_tags() -> list[dict]:
    return [{"key": key, **meta} for key, meta in TAGS.items()]


def tag_labels(tags: list[str]) -> list[str]:
    return [TAGS[tag]["label"] for tag in tags if tag in TAGS]


def get_life_load_days(conn: sqlite3.Connection, start: Optional[str] = None, end: Optional[str] = None) -> dict[str, dict]:
    """Tagged days keyed by ISO date, optionally limited to [start, end]."""
    query, params = "SELECT date, tags_json, note, created_at FROM life_load_days", []
    if start and end:
        query, params = query + " WHERE date BETWEEN ? AND ?", [start, end]
    try:
        rows = conn.execute(query + " ORDER BY date", params).fetchall()
    except sqlite3.OperationalError:
        return {}
    days = {}
    for row in rows:
        tags = [tag for tag in json.loads(row["tags_json"] or "[]") if tag in TAGS]
        if tags:
            days[row["date"]] = {
                "date": row["date"],
                "tags": tags,
                "labels": tag_labels(tags),
                "note": row["note"],
                # Tagged after the day passed: a look back, not a plan.
                "tagged_after": bool(row["created_at"]) and row["created_at"][:10] > row["date"],
            }
    return days


def set_life_load_day(conn: sqlite3.Connection, day: str, tags: list[str], note: Optional[str] = None) -> Optional[dict]:
    """Replace a day's tags; no tags clears the day."""
    date.fromisoformat(day)
    unknown = [tag for tag in tags if tag not in TAGS]
    if unknown:
        raise ValueError(f"Unknown life-load tag: {', '.join(unknown)}")
    clean = [tag for tag in TAGS if tag in tags]
    if not clean:
        conn.execute("DELETE FROM life_load_days WHERE date = ?", (day,))
    else:
        conn.execute(
            """
            INSERT INTO life_load_days (date, tags_json, note) VALUES (?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET tags_json = excluded.tags_json, note = excluded.note, updated_at = CURRENT_TIMESTAMP
            """,
            (day, json.dumps(clean), (note or "").strip() or None),
        )
    conn.commit()
    return get_life_load_days(conn, day, day).get(day)


def tagged_days_between(conn: sqlite3.Connection, start: date, end: date) -> int:
    return len(get_life_load_days(conn, start.isoformat(), end.isoformat()))


def _is_session(day: dict) -> bool:
    # Stored plans may use lowercase types ("rest", "ride").
    return str(day.get("session_type") or "").strip().lower() not in ("", "rest")


def session_load_reason(day: dict) -> Optional[str]:
    """Why a planned session is too much for a tagged day, or None if it fits."""
    if not _is_session(day) or str(day.get("session_type")).strip().lower() == "recovery":
        return None
    reason = HARD_INTENTS.get(day.get("workout_intent") or "")
    if reason:
        return reason
    if day.get("workout_intent") == "long" or (day.get("target_duration_min") or 0) >= LONG_SESSION_MIN:
        return "long session"
    return None


def _swap_target(day: dict, days: list[dict], tagged: dict, busy: set[str], today: str) -> Optional[str]:
    """Nearest open day this week with a calm session (or none) and no hard neighbour."""
    by_date = {item["date"]: item for item in days}
    source = date.fromisoformat(day["date"])
    week = [source - timedelta(days=source.weekday()) + timedelta(days=offset) for offset in range(7)]

    def hard_on(candidate: date) -> bool:
        item = by_date.get(candidate.isoformat())
        return bool(item) and item["date"] != day["date"] and session_load_reason(item) is not None

    options = []
    for candidate in week:
        key = candidate.isoformat()
        if key == day["date"] or key < today or key in busy or key in tagged:
            continue
        if by_date.get(key) and session_load_reason(by_date[key]):
            continue
        if hard_on(candidate - timedelta(days=1)) or hard_on(candidate + timedelta(days=1)):
            continue
        options.append((abs((candidate - source).days), -candidate.toordinal(), key))
    return min(options)[2] if options else None


def build_plan_life_load(conn: Optional[sqlite3.Connection], days: list[dict], week_start: str, today: Optional[date] = None) -> Optional[dict]:
    """Tags per plan day and the hard or long sessions that sit on a tagged day from today on."""
    if conn is None or not days:
        return None
    week_end = (date.fromisoformat(week_start) + timedelta(days=6)).isoformat()
    tagged = get_life_load_days(conn, week_start, week_end)
    if not tagged:
        return None
    today_key = _today(today).isoformat()
    busy = {row["date"] for row in conn.execute("SELECT DISTINCT date FROM activities WHERE date BETWEEN ? AND ?", (week_start, week_end))}
    conflicts = []
    for day in days:
        tags = tagged.get(day["date"])
        reason = session_load_reason(day) if tags else None
        if not reason or day["date"] < today_key or day["date"] in busy:
            continue
        conflicts.append({
            "date": day["date"],
            "title": day.get("title"),
            "tags": tags["tags"],
            "labels": tags["labels"],
            "reason": reason,
            "suggested_date": _swap_target(day, days, tagged, busy, today_key),
        })
    return {"days": tagged, "conflicts": conflicts}


def missed_on_tagged_days(conn: sqlite3.Connection, week_start: date, today: Optional[date] = None) -> dict:
    """Planned sessions with no activity that day, and which of them fell on tagged days."""
    week_end = week_start + timedelta(days=6)
    last = min(week_end, _today(today) - timedelta(days=1))
    row = conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (week_start.isoformat(),)).fetchone()
    if not row or last < week_start:
        return {"missed": 0, "missed_on_tagged": [], "summary": None}
    active = {item["date"] for item in conn.execute("SELECT DISTINCT date FROM activities WHERE date BETWEEN ? AND ?", (week_start.isoformat(), week_end.isoformat()))}
    tagged = get_life_load_days(conn, week_start.isoformat(), week_end.isoformat())
    missed = [
        day for day in json.loads(row["days_json"])
        if _is_session(day) and day["date"] <= last.isoformat() and day["date"] not in active
    ]
    on_tagged = [
        {"date": day["date"], "title": day.get("title"), "tags": tagged[day["date"]]["tags"], "labels": tagged[day["date"]]["labels"]}
        for day in missed if day["date"] in tagged
    ]
    return {"missed": len(missed), "missed_on_tagged": on_tagged, "summary": _missed_summary(len(missed), on_tagged)}


def _missed_summary(missed: int, on_tagged: list[dict]) -> Optional[str]:
    if not on_tagged:
        return None
    labels = list(dict.fromkeys(label.lower() for item in on_tagged for label in item["labels"]))
    kinds = " or ".join(labels)
    noun = f"{missed} session{'s' if missed > 1 else ''}"
    if len(on_tagged) == 1:
        where = f"on a {kinds} day" if missed == 1 else f"1 on a {kinds} day"
    else:
        where = f"{'both' if missed == 2 else 'all'} on {kinds} days" if len(on_tagged) == missed else f"{len(on_tagged)} on {kinds} days"
    return f"Missed {noun}, {where}."


def life_load_readiness_factor(conn: sqlite3.Connection, today: Optional[date] = None) -> Optional[dict]:
    """Poor sleep tagged today or a late night yesterday, for readiness when no check-in covers it."""
    day = _today(today)
    tagged = get_life_load_days(conn, (day - timedelta(days=1)).isoformat(), day.isoformat())
    reasons = []
    if "poor_sleep" in tagged.get(day.isoformat(), {}).get("tags", []):
        reasons.append("poor sleep tagged")
    if "late_night" in tagged.get((day - timedelta(days=1)).isoformat(), {}).get("tags", []):
        reasons.append("late night yesterday")
    if not reasons:
        return None
    return {"key": "life_load", "label": "Life load", "detail": ", ".join(reasons), "tone": "caution", "points": 1}


def life_load_coaching_context(conn: sqlite3.Connection, today: Optional[date] = None) -> Optional[dict]:
    """Tagged days in the last 7 and next 14 days, for coaching and weekly planning."""
    day = _today(today)
    tagged = get_life_load_days(conn, (day - timedelta(days=7)).isoformat(), (day + timedelta(days=14)).isoformat())
    if not tagged:
        return None
    entries = [{"date": item["date"], "tags": item["labels"], **({"note": item["note"]} if item["note"] else {})} for item in tagged.values()]
    return {
        "recent": [item for item in entries if item["date"] < day.isoformat()],
        "upcoming": [item for item in entries if item["date"] >= day.isoformat()],
        "guidance": (
            "Life-load days limit time and attention, not the body. Do not put intervals, tempo, race-specific "
            "or 90+ minute sessions on upcoming tagged days; easy sessions and short lifts are fine. Anchor goals "
            "stay. Missed sessions on tagged days are life, not a motivation problem."
        ),
    }
