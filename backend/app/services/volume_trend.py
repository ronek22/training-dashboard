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
W3 week, hides the alert and is passed to coaching context. A falling week with 3+ days in
sick mode counts as illness automatically.

Every slide also carries a `reason`: why volume fell over the falling weeks (W2-W3), read
from sick days, life-load tags, daily check-ins (against the four baseline weeks) and the
planned sessions that never happened. It gives one summary line and one next step; the
coaching context gets the same read through `volume_trend`.
"""
import json
import re
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from .life_load import TAGS, get_life_load_days, tagged_days_between
from .sick_mode import sick_dates, sick_days_between

NON_TRAINING_TYPES = ("Walk", "Hike")
LABELS = {"planned": "Planned lighter stretch", "life": "Life got in the way", "illness_injury": "Illness or injury"}
LIGHTER_TITLE = re.compile(r"\b(deload|taper|recovery week|rest week)\b", re.IGNORECASE)
DROP_FROM_START = 0.75
DROP_FROM_BASELINE = 0.80
LIGHTER_PLAN = 0.85
# Check-ins are 1-5. A week reads as rough when it is poor outright or clearly below baseline.
POOR_SCORE = 2.5
HIGH_STRESS = 3.5
SCORE_SHIFT = 0.7
# Skips explain a drop only when they are a real share of the plan.
SKIPS_MIN, SKIPS_SHARE = 2, 0.25
# Session count held this well while minutes fell: the sessions got shorter.
SESSIONS_HELD = 0.8


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


def _days(start: date, end: date) -> list[str]:
    return [(start + timedelta(days=offset)).isoformat() for offset in range((end - start).days + 1)]


def _checkin_averages(conn: sqlite3.Connection, start: date, end: date) -> Optional[dict]:
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) AS days, AVG(sleep_quality) AS sleep, AVG(stress) AS stress, AVG(energy) AS energy
            FROM daily_checkins WHERE date BETWEEN ? AND ?
            """,
            (start.isoformat(), end.isoformat()),
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row or row["days"] < 3:
        return None
    return {"days": row["days"], **{key: round(row[key], 1) for key in ("sleep", "stress", "energy")}}


def _skipped_sessions(conn: sqlite3.Connection, week_starts: list[date]) -> tuple[int, list[dict]]:
    """Planned sessions with no training that day, net of sessions done on unplanned days.

    Returns (planned session count, skipped days). Moved sessions offset skips one for one,
    so the list keeps the unmatched planned days but never more than the net shortfall.
    """
    planned_total, skipped = 0, []
    placeholders = ",".join("?" for _ in NON_TRAINING_TYPES)
    for start in week_starts:
        row = conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (start.isoformat(),)).fetchone()
        if not row:
            continue
        planned = [
            day for day in json.loads(row["days_json"] or "[]")
            if day.get("date") and str(day.get("session_type") or "").lower() not in {"", "walk", "hike", "rest"}
        ]
        trained = {
            item["date"] for item in conn.execute(
                f"SELECT DISTINCT date FROM activities WHERE date BETWEEN ? AND ? AND type NOT IN ({placeholders})",
                (start.isoformat(), (start + timedelta(days=6)).isoformat(), *NON_TRAINING_TYPES),
            )
        }
        planned_dates = {day["date"] for day in planned}
        unmatched = [day for day in planned if day["date"] not in trained]
        net = max(0, len(unmatched) - len(trained - planned_dates))
        planned_total += len(planned)
        skipped += unmatched[:net]
    return planned_total, skipped


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _session_noun(kind: str) -> str:
    kind = kind.lower()
    return kind if kind in {"run", "ride", "swim", "hike"} else f"{kind} session"


def explain_volume_drop(conn: sqlite3.Connection, falling: list[date], baseline: list[date], usual_min: int, last_min: int) -> dict:
    """Why the falling weeks were light, as one line plus one thing to do next."""
    start, end = falling[0], falling[-1] + timedelta(days=6)
    days = set(_days(start, end))
    sick = sorted(days & sick_dates(conn))
    tagged = get_life_load_days(conn, start.isoformat(), end.isoformat())
    tag_counts: dict[str, int] = {}
    for day in tagged.values():
        for tag in day["tags"]:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    recent = _checkin_averages(conn, start, end)
    before = _checkin_averages(conn, baseline[0], baseline[-1] + timedelta(days=6))
    checkin_flags = []
    if recent:
        def worse(key, sign):
            return before is not None and sign * (recent[key] - before[key]) >= SCORE_SHIFT
        if recent["sleep"] <= POOR_SCORE or worse("sleep", -1):
            checkin_flags.append("low sleep")
        if recent["stress"] >= HIGH_STRESS or worse("stress", 1):
            checkin_flags.append("high stress")
        if recent["energy"] <= POOR_SCORE or worse("energy", -1):
            checkin_flags.append("low energy")
    # Poor-sleep tags and low check-in sleep are the same story; say it once.
    if "poor_sleep" in tag_counts and "low sleep" in checkin_flags:
        checkin_flags.remove("low sleep")

    planned, skipped = _skipped_sessions(conn, falling)
    busy = set(tagged) | set(sick)
    skipped_busy = sum(1 for day in skipped if day["date"] in busy)
    skipped_types: dict[str, int] = {}
    for day in skipped:
        kind = str(day.get("session_type") or "session").capitalize()
        skipped_types[kind] = skipped_types.get(kind, 0) + 1

    falling_sessions = sum(_week_minutes(conn, week)[1] for week in falling) / len(falling)
    usual_sessions = sum(_week_minutes(conn, week)[1] for week in baseline) / len(baseline)
    shorter = usual_sessions > 0 and falling_sessions >= SESSIONS_HELD * usual_sessions
    real_skips = len(skipped) >= SKIPS_MIN and len(skipped) >= SKIPS_SHARE * planned

    life_days = len(tagged)
    drivers = []
    if len(sick) >= 2:
        drivers.append(f"illness ({_plural(len(sick), 'sick day')})")
    for tag, count in sorted(tag_counts.items(), key=lambda item: -item[1])[:2]:
        drivers.append(f"{TAGS[tag]['label'].lower()} ({_plural(count, 'day')})")
    drivers += checkin_flags

    if len(sick) >= 3:
        cause = "illness"
    elif life_days >= 2 or (life_days and checkin_flags):
        cause = "life"
    elif checkin_flags:
        cause = "recovery"
    elif real_skips:
        cause = "skipped"
    elif shorter:
        cause = "shorter"
    else:
        cause = "unclear"

    weeks = len(falling)
    lead = f"{_plural(weeks, 'week')} down"
    if cause in ("illness", "life", "recovery"):
        summary = f"{lead}, mostly {', '.join(drivers[:3])}"
        if cause != "illness" and (not skipped or skipped_busy * 2 >= len(skipped)):
            summary += " — not lost motivation"
    elif cause == "skipped":
        top = max(skipped_types, key=skipped_types.get)
        summary = (f"{lead}: {len(skipped)} of {planned} planned sessions skipped (mostly {_session_noun(top)}s), "
                   "on ordinary days with no life-load tags or rough check-ins")
    elif cause == "shorter":
        summary = (f"{lead}, but not from skipping: about {falling_sessions:.0f} sessions a week as usual, "
                   f"just shorter ones, with no life-load tags or rough check-ins")
    else:
        summary = f"{lead} with nothing logged to explain it: no sick days, life-load tags or rough check-ins"
    if skipped and cause in ("illness", "life", "recovery"):
        summary += f"; {skipped_busy} of {_plural(len(skipped), 'skipped session')} fell on busy or sick days"

    # Back from illness: a little above last week, never jumping straight to most of the usual load.
    easy_min = int(round(min(usual_min * 0.6, max(last_min, 60) * 1.2) / 10) * 10)
    trimmed_min = int(round(usual_min * 0.75 / 10) * 10)
    if cause == "illness":
        next_step = f"Ease back in: keep this week to easy sessions around {easy_min} min total before building again."
    elif cause == "life" and ("low sleep" in checkin_flags or "poor_sleep" in tag_counts):
        next_step = ("Switch to a minimum week for now and put intensity only on your "
                     "best-slept day; tag busy days ahead so the plan moves hard sessions off them.")
    elif cause == "life":
        next_step = ("Switch to a minimum week for now and tag the busy days ahead "
                     "so the plan moves hard sessions off them.")
    elif cause == "recovery":
        next_step = (f"Treat it as a recovery signal: cap this week near {trimmed_min} min, keep it easy and "
                     "check in daily until sleep and energy are back.")
    elif cause == "skipped":
        top = max(skipped_types, key=skipped_types.get)
        next_step = (f"Pick one fixed day for the {_session_noun(top)} you keep missing, or swap it for a session "
                     "you will actually do — easier to keep than a full plan.")
    elif cause == "shorter":
        next_step = ("Keep the days you have and bring one session a week back to its usual length "
                     "(the long one first) rather than adding sessions.")
    else:
        next_step = ("Tag what got in the way or do a daily check-in, and plan next week near "
                     f"{trimmed_min} min on fixed days so the next read is clearer.")

    return {
        "cause": cause,
        "summary": summary + ".",
        "next_step": next_step,
        "signals": {
            "sick_days": len(sick),
            "life_load_days": life_days,
            "life_load_tags": {TAGS[tag]["label"]: count for tag, count in tag_counts.items()},
            "checkins": recent,
            "checkins_baseline": before,
            "checkin_flags": checkin_flags,
            "planned_sessions": planned,
            "skipped_sessions": len(skipped),
            "skipped_on_busy_days": skipped_busy,
            "skipped_by_type": skipped_types,
            "sessions_per_week": round(falling_sessions, 1),
            "usual_sessions_per_week": round(usual_sessions, 1),
        },
    }


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
    reason = explain_volume_drop(conn, window[1:], baseline_weeks, baseline_min, last)
    label = get_volume_trend_label(conn, result["week_start"])
    if label is None and any(sick_days_between(conn, start, start + timedelta(days=6)) >= 3 for start in window[1:]):
        label = {"week_start": result["week_start"], "label": "illness_injury", "note": "Sick mode", "updated_at": None, "auto": True}
    if label is None and any(tagged_days_between(conn, start, start + timedelta(days=6)) >= 3 for start in window[1:]):
        label = {"week_start": result["week_start"], "label": "life", "note": "Life-load tags", "updated_at": None, "auto": True}
    return {
        **result,
        "status": "sliding",
        "alert": label is None,
        "drop_pct": drop_pct,
        "reason": reason,
        "label": {**label, "label_text": LABELS.get(label["label"], label["label"])} if label else None,
        "message": f"Training volume fell two weeks in a row: {first} → {middle} → {last} min ({drop_pct}% down), "
                   f"below your usual ~{baseline_min} min and not planned as a lighter stretch.",
    }
