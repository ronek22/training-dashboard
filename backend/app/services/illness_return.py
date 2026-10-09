"""Return from illness: the days right after sick mode ends, when effort should stay capped.

Sick mode covers being ill. Ending it does not mean the body is back: the days after are when a
hard session tends to drag symptoms out. The window lasts as long as the sickness did (3 to 7
days) and stretches while feedback or check-in notes still mention symptoms, up to 14 days.
The first half, and any day with symptoms in the last 2 days, is easy only; the rest allows
moderate work but still no intervals or max efforts. Sessions rated RPE 8+ inside the window
are named so the next ones stay easy.
"""
import math
import re
import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from .sick_mode import get_active_sick_period

MIN_DAYS, MAX_DAYS, MAX_STRETCH_DAYS = 3, 7, 14
SYMPTOM_TAIL_DAYS = 3  # days of capped effort after the last note that mentions symptoms
LINGERING_DAYS = 2  # a symptom note this recent keeps the easy phase on
HARD_RPE = 8

PHASES = {
    "easy": {
        "label": "Easy only",
        "rpe_cap": 5,
        "guidance": "Keep everything easy: rides and walks conversational (RPE ≤5), lifts with 3+ reps in reserve and about two thirds of the usual sets. No intervals or max efforts.",
    },
    "build": {
        "label": "Moderate",
        "rpe_cap": 7,
        "guidance": "Moderate work is fine (RPE ≤7, lifts with 2 reps in reserve). Still no intervals, max lifts or races until the window ends.",
    },
}

# English and Polish words for symptoms in free-text notes. "Cold" only counts as "a cold" or
# "head cold", so a cold morning is not an illness.
_SYMPTOM_RE = re.compile(
    r"\b(sick|ill|illness|flu|sinus\w*|headache|fever|cough\w*|sore throat|congest\w*|runny nose|(?:a|head|chest) cold"
    r"|chor\w*|przezięb\w*|katar\w*|gorącz\w*|kaszel|kaszl\w*|zatok\w*|ból głowy|gryp\w*)\b",
    re.IGNORECASE,
)
_NEGATED_RE = re.compile(r"\b(not|no longer|no more|nie|już nie)\s+(?:\w+\s+)?$", re.IGNORECASE)


def _today(today: Optional[date]) -> date:
    return today or datetime.now().date()


def mentions_symptoms(note: Optional[str]) -> bool:
    """A note mentions being ill, ignoring negations like "not sick anymore"."""
    for match in _SYMPTOM_RE.finditer(note or ""):
        if not _NEGATED_RE.search(note[: match.start()][-30:]):
            return True
    return False


def _last_sick_period(conn: sqlite3.Connection) -> Optional[dict]:
    try:
        row = conn.execute(
            "SELECT id, start_date, end_date FROM sick_periods WHERE end_date IS NOT NULL ORDER BY end_date DESC LIMIT 1"
        ).fetchone()
    except sqlite3.OperationalError:
        return None
    return dict(row) if row else None


def _notes_since(conn: sqlite3.Connection, start: str, end: str) -> list[tuple[str, str]]:
    """(date, note) from session feedback and morning check-ins in [start, end]."""
    notes = []
    queries = (
        """
        SELECT activity.date, feedback.note FROM activity_feedback feedback
        JOIN activities activity ON activity.id = feedback.activity_id
        WHERE activity.date BETWEEN ? AND ? AND feedback.note IS NOT NULL AND feedback.note != ''
        """,
        "SELECT date, note FROM daily_checkins WHERE date BETWEEN ? AND ? AND note IS NOT NULL AND note != ''",
    )
    for query in queries:
        try:
            notes.extend((row[0], row[1]) for row in conn.execute(query, (start, end)))
        except sqlite3.OperationalError:
            continue
    return notes


def _hard_sessions(conn: sqlite3.Connection, start: str, end: str) -> list[dict]:
    try:
        rows = conn.execute(
            """
            SELECT activity.id, activity.date, activity.name, activity.type, feedback.rpe
            FROM activity_feedback feedback JOIN activities activity ON activity.id = feedback.activity_id
            WHERE activity.date BETWEEN ? AND ? AND feedback.rpe >= ?
            ORDER BY activity.date
            """,
            (start, end, HARD_RPE),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [{"activity_id": row["id"], "date": row["date"], "name": row["name"] or row["type"], "rpe": row["rpe"]} for row in rows]


def _short_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%b %-d")


def build_illness_return(conn: sqlite3.Connection, today: Optional[date] = None) -> Optional[dict]:
    """The return window that is open today, or None (still sick, never sick, or long recovered)."""
    day = _today(today)
    if get_active_sick_period(conn):
        return None
    period = _last_sick_period(conn)
    if not period:
        return None
    ended = date.fromisoformat(period["end_date"])
    day_number = (day - ended).days
    if day_number < 1 or day_number > MAX_STRETCH_DAYS:
        return None

    sick_days = (ended - date.fromisoformat(period["start_date"])).days + 1
    base_days = min(MAX_DAYS, max(MIN_DAYS, sick_days))
    symptom_dates = sorted({note_date for note_date, note in _notes_since(conn, period["end_date"], day.isoformat()) if mentions_symptoms(note)})
    last_symptom = symptom_dates[-1] if symptom_dates else None
    length = base_days
    if last_symptom:
        stretched = (date.fromisoformat(last_symptom) - ended).days + SYMPTOM_TAIL_DAYS
        length = min(MAX_STRETCH_DAYS, max(base_days, stretched))
    if day_number > length:
        return None

    lingering = bool(last_symptom) and (day - date.fromisoformat(last_symptom)).days <= LINGERING_DAYS
    phase = "easy" if lingering or day_number <= math.ceil(length / 2) else "build"
    window_end = ended + timedelta(days=length)
    hard = _hard_sessions(conn, (ended + timedelta(days=1)).isoformat(), day.isoformat())

    reason = f"symptoms still in your notes on {_short_date(last_symptom)}" if lingering else None
    headline = f"Day {day_number} of {length} back from illness"
    message = f"{headline}{f' ({reason})' if reason else ''}. {PHASES[phase]['guidance']}"
    if hard:
        latest = hard[-1]
        message += f" {_short_date(latest['date'])} ({latest['name']}) was RPE {latest['rpe']}, too hard this soon, so the next sessions stay easy."
    return {
        "active": True,
        "sick_period": {"start_date": period["start_date"], "end_date": period["end_date"], "days": sick_days},
        "day_number": day_number,
        "length_days": length,
        "ends_on": window_end.isoformat(),
        "phase": phase,
        "phase_label": PHASES[phase]["label"],
        "rpe_cap": PHASES[phase]["rpe_cap"],
        "guidance": PHASES[phase]["guidance"],
        "lingering_symptoms": lingering,
        "last_symptom_date": last_symptom,
        "hard_sessions": hard,
        "headline": headline,
        "message": message,
    }


def illness_return_dates(conn: sqlite3.Connection, today: Optional[date] = None) -> set[str]:
    """ISO dates from today to the end of the open return window: no extra sets on them."""
    state = build_illness_return(conn, today)
    if not state:
        return set()
    day, end = _today(today), date.fromisoformat(state["ends_on"])
    return {(day + timedelta(days=offset)).isoformat() for offset in range((end - day).days + 1)}


def illness_return_readiness_factor(state: Optional[dict]) -> Optional[dict]:
    if not state:
        return None
    detail = f"day {state['day_number']} of {state['length_days']}"
    if state["lingering_symptoms"]:
        detail += ", symptoms still in notes"
    risky = state["lingering_symptoms"]
    return {"key": "illness_return", "label": "Back from illness", "detail": detail, "tone": "risk" if risky else "caution", "points": 2 if risky else 1}


def illness_return_coaching_context(conn: sqlite3.Connection, today: Optional[date] = None) -> Optional[dict]:
    """Compact note for coaching prompts and the weekly planner."""
    state = build_illness_return(conn, today)
    if not state:
        return None
    return {
        "ended_sick_mode_on": state["sick_period"]["end_date"],
        "day_number": state["day_number"],
        "window_ends_on": state["ends_on"],
        "phase": state["phase_label"],
        "rpe_cap": state["rpe_cap"],
        "lingering_symptoms": state["lingering_symptoms"],
        "hard_sessions_in_window": [f"{item['date']} {item['name']} RPE {item['rpe']}" for item in state["hard_sessions"]],
        "guidance": (
            f"The athlete is back from illness until {state['ends_on']}. {state['guidance']} Do not plan intervals, "
            "tempo, quality rides, max lifts or 90+ minute sessions before that date; the anchor lift goal stays, "
            "as lighter sessions. If hard_sessions_in_window is not empty, say so plainly and keep the next days easy."
        ),
    }
