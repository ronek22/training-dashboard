"""Three wins and one focus for a training week.

Wins come first and come from evidence: the strongest session wins of the week
(records, progress, a session done on a tough day), weekly goals met, planned
sessions done and moving every day. The focus is one thing for next week: the
saved Sunday review's proposed change when there is one, otherwise the weekly
goal still open, otherwise the most important "next time" from this week's
session reads. Nothing here calls an LLM, so it shows instantly and on any day.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Optional

from ..repositories.activities import get_activity_row
from ..repositories.activity_details import get_activity_detail_row
from .activities import _build_activity_detail_payload
from .goals import goal_value_for_window
from .personal_records import build_activity_record_ranks
from .plans import serialize_weekly_plan
from .session_read import build_session_read
from .session_win import build_session_win

MAX_WINS = 3
SESSION_WIN_MIN_SCORE = 40
DONE_STATUSES = {"linked", "matched", "partially_matched", "moved", "replaced", "rest_day_changed"}
REST_TYPES = {"rest", ""}
TONE_ORDER = {"bad": 0, "warn": 1}


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _session_items(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    """Each training session of the week (walks excluded) with its read and win."""
    rows = conn.execute(
        "SELECT id FROM activities WHERE substr(date, 1, 10) BETWEEN ? AND ? AND type != 'Walk' ORDER BY date",
        (start, end),
    ).fetchall()
    if not rows:
        return []
    try:
        ranks = build_activity_record_ranks(conn)
    except (sqlite3.Error, KeyError, ValueError):
        ranks = {}
    items = []
    for row in rows:
        activity_row = get_activity_row(conn, row["id"])
        try:
            payload = _build_activity_detail_payload(conn, activity_row, get_activity_detail_row(conn, row["id"]))
            read = build_session_read(conn, payload)
            win = build_session_win(conn, payload, read, record_ranks=ranks)
        except (sqlite3.Error, KeyError, ValueError, TypeError):
            continue
        items.append({"activity": payload["activity"], "read": read, "win": win})
    return items


def _weekly_goals(conn: sqlite3.Connection, start: str, end: str) -> list[dict[str, Any]]:
    try:
        goals = conn.execute(
            "SELECT * FROM goals WHERE is_active = 1 AND COALESCE(lifecycle_status, 'active') = 'active' AND period_type = 'week' "
            "ORDER BY CASE commitment WHEN 'anchor' THEN 0 ELSE 1 END, id"
        ).fetchall()
    except sqlite3.Error:
        return []
    result = []
    for goal in goals:
        try:
            done = goal_value_for_window(conn, goal, start_date=start, end_date=end)
        except (sqlite3.Error, KeyError, ValueError):
            continue
        result.append({"title": goal["title"], "done": float(done), "target": float(goal["target_value"]),
                       "anchor": goal["commitment"] == "anchor"})
    return result


def _plan_counts(conn: sqlite3.Connection, start: str, through: str) -> Optional[tuple[int, int]]:
    """(done, planned) training days of the week up to ``through``."""
    row = conn.execute("SELECT * FROM weekly_plans WHERE week_start = ?", (start,)).fetchone()
    if not row:
        return None
    try:
        days = serialize_weekly_plan(row, conn)["days"]
    except (sqlite3.Error, KeyError, ValueError):
        return None
    planned = [day for day in days if str(day.get("session_type") or "").lower() not in REST_TYPES and day["date"] <= through]
    done = [day for day in planned if (day.get("comparison") or {}).get("status") in DONE_STATUSES]
    return len(done), len(planned)


def _number(value: float) -> str:
    return f"{value:g}"


def _week_level_wins(conn: sqlite3.Connection, goals: list[dict], start: str, through: str, finished: bool) -> list[dict]:
    wins = []
    for goal in goals:
        if goal["target"] and goal["done"] >= goal["target"]:
            count = (f"{_number(goal['done'])} of {_number(goal['target'])} this week." if goal["done"] == goal["target"]
                     else f"{_number(goal['done'])} this week against a target of {_number(goal['target'])}.")
            wins.append({"score": 92 if goal["anchor"] else 80, "kind": "goal", "headline": f"{goal['title']}: done",
                         "detail": count + (" That's the anchor goal kept." if goal["anchor"] else "")})
    counts = _plan_counts(conn, start, through)
    if counts and counts[1] >= 2:
        done, planned = counts
        if done == planned:
            wins.append({"score": 85, "kind": "plan", "headline": f"Every planned session done ({done} of {planned})",
                         "detail": "The plan only works when it gets done. This week it did."})
        elif done / planned >= 0.75:
            wins.append({"score": 55, "kind": "plan", "headline": f"{done} of {planned} planned sessions done",
                         "detail": "Most of the plan got done, which is what builds fitness."})
    active_days = conn.execute(
        "SELECT COUNT(DISTINCT substr(date, 1, 10)) FROM activities WHERE substr(date, 1, 10) BETWEEN ? AND ?",
        (start, through),
    ).fetchone()[0]
    days_so_far = (date.fromisoformat(through) - date.fromisoformat(start)).days + 1
    if active_days == days_so_far and days_so_far >= 3:
        wins.append({"score": 50, "kind": "consistency",
                     "headline": "Moved every day this week" if finished else f"Moved every day so far ({active_days} of {active_days})",
                     "detail": "Small days count. The habit is what carries the big ones."})
    return wins


def _fallback_win(sessions: int, minutes: float, active_days: int) -> Optional[dict]:
    if not sessions and not minutes:
        return None
    parts = [f"{sessions} training {'session' if sessions == 1 else 'sessions'}"] if sessions else []
    parts.append(f"{active_days} active {'day' if active_days == 1 else 'days'}")
    return {"score": 1, "kind": "consistency", "headline": f"{round(minutes)} min of movement in the bank",
            "detail": " and ".join(parts) + ". Showing up is the part that compounds."}


def _pick_wins(candidates: list[dict]) -> list[dict]:
    """The strongest wins, at most one per session and one per week-level kind."""
    chosen, seen = [], set()
    for win in sorted(candidates, key=lambda item: -item["score"]):
        key = win.get("activity_id") or f"week:{win['kind']}"
        if key in seen or win["headline"] in {item["headline"] for item in chosen}:
            continue
        seen.add(key)
        chosen.append(win)
        if len(chosen) == MAX_WINS:
            break
    return chosen


def _focus(conn: sqlite3.Connection, start: str, goals: list[dict], items: list[dict], finished: bool, through: str) -> dict:
    review = conn.execute(
        "SELECT proposed_change FROM weekly_reviews WHERE week_start = ? AND generator = 'codex-cli'", (start,)
    ).fetchone()
    if review and review["proposed_change"]:
        return {"source": "review", "headline": "One change for next week", "detail": review["proposed_change"]}

    if not finished:
        end = date.fromisoformat(start) + timedelta(days=6)
        days_left = (end - date.fromisoformat(through)).days
        for goal in goals:
            left = goal["target"] - goal["done"]
            if goal["target"] and left > 0:
                return {"source": "goal", "headline": f"{goal['title']}: {_number(left)} to go",
                        "detail": f"{_number(goal['done'])} of {_number(goal['target'])} done with {days_left} "
                                  f"{'day' if days_left == 1 else 'days'} left. Pick the day{'s' if left > 1 else ''} now so it happens."}

    reads = [item["read"] for item in items if item["read"].get("available") and item["read"].get("next_time")]
    flagged = sorted((read for read in reads if read["verdict"]["tone"] in TONE_ORDER),
                     key=lambda read: TONE_ORDER[read["verdict"]["tone"]])
    if flagged:
        read = flagged[0]
        return {"source": "session", "headline": read["verdict"]["headline"], "detail": read["next_time"]}
    if reads:
        read = reads[-1]
        return {"source": "session", "headline": "Build on the last session", "detail": read["next_time"]}
    return {"source": "default", "headline": "Keep the rhythm",
            "detail": "Nothing is off. Repeat this week's pattern before adding anything."}


_CACHE: dict[tuple, dict[str, Any]] = {}
# Per cached week: activity id -> (activity, full session win with its chat opener), for coach moments.
_SESSION_WINS: dict[tuple, dict[str, tuple[dict, dict]]] = {}
CACHE_SIZE = 16


def _signature(conn: sqlite3.Connection, start: str, through: str) -> tuple:
    """Everything the result depends on that can change: the week's sessions and their feedback and
    detail, the plan, the saved review and the goals. A cheap query instead of the full build."""
    def one(query: str, params: tuple = ()) -> tuple:
        try:
            return tuple(conn.execute(query, params).fetchone() or ())
        except sqlite3.Error:
            return ()
    week = (start, through)
    return (
        one("SELECT COUNT(*), GROUP_CONCAT(id), SUM(duration_min), GROUP_CONCAT(COALESCE(workout_intent, '')) "
            "FROM activities WHERE substr(date, 1, 10) BETWEEN ? AND ?", week),
        one("SELECT COUNT(*), MAX(fetched_at) FROM activity_details WHERE activity_id IN "
            "(SELECT id FROM activities WHERE substr(date, 1, 10) BETWEEN ? AND ?)", week),
        one("SELECT COUNT(*), GROUP_CONCAT(COALESCE(rpe, '') || COALESCE(pain_level, '') || COALESCE(energy, '')) FROM activity_feedback "
            "WHERE activity_id IN (SELECT id FROM activities WHERE substr(date, 1, 10) BETWEEN ? AND ?)", week),
        one("SELECT days_json FROM weekly_plans WHERE week_start = ?", (start,)),
        one("SELECT proposed_change FROM weekly_reviews WHERE week_start = ? AND generator = 'codex-cli'", (start,)),
        one("SELECT GROUP_CONCAT(id || ':' || target_value || ':' || COALESCE(lifecycle_status, '') || ':' || is_active) FROM goals"),
        one("SELECT COUNT(*), MAX(date) FROM activities"),
        # Lift progression reads logged sets from the app's own sessions and Fitbod imports.
        one("SELECT COUNT(*), MAX(updated_at) FROM strength_workout_sessions"),
        one("SELECT COUNT(*) FROM strength_session_sets"),
        one("SELECT COUNT(*) FROM fitbod_workout_sets"),
    )


def build_week_wins(conn: sqlite3.Connection, week_start: Optional[date] = None, today: Optional[date] = None) -> dict[str, Any]:
    today = today or datetime.now().date()
    monday = _monday(week_start or today)
    start, end = monday.isoformat(), (monday + timedelta(days=6)).isoformat()
    finished = today > monday + timedelta(days=6)
    through = end if finished else min(today, monday + timedelta(days=6)).isoformat()
    key = _key(conn, monday, today)
    if key not in _CACHE:
        if len(_CACHE) >= CACHE_SIZE:
            _SESSION_WINS.pop(next(iter(_CACHE)), None)
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key], _SESSION_WINS[key] = _build(conn, start, end, through, finished)
    return _CACHE[key]


def _key(conn: sqlite3.Connection, monday: date, today: date) -> tuple:
    start, end = monday.isoformat(), (monday + timedelta(days=6)).isoformat()
    finished = today > monday + timedelta(days=6)
    through = end if finished else min(today, monday + timedelta(days=6)).isoformat()
    return (start, through, finished, _signature(conn, start, through))


def session_wins_for_week(conn: sqlite3.Connection, day: date, today: date) -> dict[str, tuple[dict, dict]]:
    """Each training session's win in the week containing ``day``, sharing the week cache."""
    monday = _monday(day)
    build_week_wins(conn, monday, today=today)
    return _SESSION_WINS.get(_key(conn, monday, today), {})


def _build(conn: sqlite3.Connection, start: str, end: str, through: str, finished: bool) -> tuple[dict[str, Any], dict]:
    items = _session_items(conn, start, through)
    goals = _weekly_goals(conn, start, through)
    candidates = [
        {**{key: item["win"][key] for key in ("score", "kind", "headline", "detail")},
         "activity_id": str(item["activity"]["id"]), "date": str(item["activity"]["date"])[:10]}
        for item in items if item["win"] and item["win"]["score"] >= SESSION_WIN_MIN_SCORE
    ]
    candidates += _week_level_wins(conn, goals, start, through, finished)
    minutes, active_days = conn.execute(
        "SELECT COALESCE(SUM(duration_min), 0), COUNT(DISTINCT substr(date, 1, 10)) FROM activities "
        "WHERE substr(date, 1, 10) BETWEEN ? AND ?",
        (start, through),
    ).fetchone()
    wins = _pick_wins(candidates)
    if not wins:
        fallback = _fallback_win(len(items), float(minutes), active_days)
        wins = [fallback] if fallback else []
    session_wins = {str(item["activity"]["id"]): (item["activity"], item["win"]) for item in items if item["win"]}
    return {
        "week_start": start,
        "week_end": end,
        "through": through,
        "finished": finished,
        "sessions": len(items),
        "minutes": round(float(minutes)),
        "wins": [{key: value for key, value in win.items() if key != "score"} for win in wins],
        "focus": _focus(conn, start, goals, items, finished, through),
    }, session_wins
