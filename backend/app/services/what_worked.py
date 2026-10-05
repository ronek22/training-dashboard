""""What worked" memory: session tags plus the patterns they reveal.

Two outcomes are compared across training conditions:

* verdict: the athlete's own loved / fine / hated tag (+1 / 0 / -1);
* effort cost: post-workout RPE minus the target RPE for that kind of session,
  so an easy ride logged at RPE 6 counts as "cost more than intended". This
  uses the existing feedback, so the memory has data before any tagging.

Conditions come from data the app already has (local start time, indoor or
outdoor, the morning check-in, rest the day before) plus the pre-session fuel
tag. A pattern is only "confirmed" with 6+ sessions on each side and a clear
gap; with 3+ it is "emerging" and never presented as a rule. Everything is
deterministic and descriptive: it reports what happened, not why.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Any, Callable, Optional

from .activity_times import start_times, time_of_day
from .sick_mode import sick_dates

VERDICTS = {"loved": 1, "fine": 0, "hated": -1}
PRE_FUEL = ("fasted", "snack", "meal_recent", "meal_earlier")
PRE_FUEL_LABELS = {
    "fasted": "Fasted",
    "snack": "Snack < 1 h before",
    "meal_recent": "Meal 1–3 h before",
    "meal_earlier": "Meal 3+ h before",
}
CONFIRMED_MIN = 6
EMERGING_MIN = 3
VERDICT_GAP = 0.5  # on the -1..+1 scale
EFFORT_GAP = 1.0  # RPE points
WINDOW_DAYS = 365
RIDE_TYPES = ("Ride", "VirtualRide")

# Target RPE midpoints, matching the pre-session brief.
TARGET_RPE = {
    "recovery": 1.5,
    "easy": 3.5,
    "long": 3.5,
    "tempo": 5.5,
    "interval": 8.0,
    "race_specific": 7.0,
    "strength_upper": 7.5,
    "strength_lower": 7.5,
    "strength_general": 7.5,
    "mobility": 2.0,
}


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


def get_session_tags(conn: sqlite3.Connection, activity_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT activity_id, verdict, pre_fuel, updated_at FROM session_tags WHERE activity_id = ?", (activity_id,)
    ).fetchone()
    return dict(row) if row else {"activity_id": activity_id, "verdict": None, "pre_fuel": None, "updated_at": None}


def save_session_tags(conn: sqlite3.Connection, activity_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Upsert only the fields present in ``payload``; ``None`` clears a field."""
    if not conn.execute("SELECT 1 FROM activities WHERE id = ?", (activity_id,)).fetchone():
        raise LookupError("Activity not found")
    current = get_session_tags(conn, activity_id)
    verdict = payload["verdict"] if "verdict" in payload else current["verdict"]
    pre_fuel = payload["pre_fuel"] if "pre_fuel" in payload else current["pre_fuel"]
    conn.execute(
        """
        INSERT INTO session_tags (activity_id, verdict, pre_fuel)
        VALUES (?, ?, ?)
        ON CONFLICT(activity_id) DO UPDATE SET
            verdict = excluded.verdict,
            pre_fuel = excluded.pre_fuel,
            updated_at = CURRENT_TIMESTAMP
        """,
        (activity_id, verdict, pre_fuel),
    )
    conn.commit()
    return get_session_tags(conn, activity_id)


# ---------------------------------------------------------------------------
# Session facts
# ---------------------------------------------------------------------------


def _family(activity_type: str, intent: Optional[str]) -> Optional[str]:
    if activity_type in RIDE_TYPES:
        return "ride_quality" if intent in ("tempo", "interval", "race_specific") else "ride_easy"
    if activity_type == "Run":
        return "run"
    if activity_type == "WeightTraining":
        return "strength"
    return None


FAMILY_LABELS = {
    "ride_quality": "Hard rides",
    "ride_easy": "Easy rides",
    "run": "Runs",
    "strength": "Strength sessions",
    "all": "Sessions",
}


def _load_sessions(conn: sqlite3.Connection, today: date) -> list[dict[str, Any]]:
    since = (today - timedelta(days=WINDOW_DAYS)).isoformat()
    rows = conn.execute(
        """
        SELECT a.id, a.date, a.type, a.name, a.workout_intent, d.detail_json,
               f.rpe, t.verdict, t.pre_fuel
        FROM activities AS a
        LEFT JOIN activity_details AS d ON d.activity_id = a.id
        LEFT JOIN activity_feedback AS f ON f.activity_id = a.id
        LEFT JOIN session_tags AS t ON t.activity_id = a.id
        WHERE a.date >= ? AND (f.activity_id IS NOT NULL OR t.verdict IS NOT NULL OR t.pre_fuel IS NOT NULL)
        ORDER BY a.date
        """,
        (since,),
    ).fetchall()
    starts = start_times(conn, rows)
    active_days = {r[0] for r in conn.execute("SELECT DISTINCT date FROM activities WHERE date >= ?", ((today - timedelta(days=WINDOW_DAYS + 1)).isoformat(),))}
    try:
        checkins = {
            r["date"]: dict(r)
            for r in conn.execute("SELECT date, energy, sleep_quality FROM daily_checkins WHERE date >= ?", (since,))
        }
    except sqlite3.OperationalError:
        checkins = {}

    sick = sick_dates(conn)
    sessions = []
    for row in rows:
        if row["date"] in sick:
            # Sick days measure the illness, not the training conditions.
            continue
        family = _family(row["type"], row["workout_intent"])
        if family is None:
            continue
        target = TARGET_RPE.get(row["workout_intent"] or "")
        detail = row["detail_json"] or ""
        indoor = row["type"] == "VirtualRide" or '"trainer": true' in detail or '"trainer":true' in detail
        previous_day = (date.fromisoformat(row["date"]) - timedelta(days=1)).isoformat()
        checkin = checkins.get(row["date"]) or {}
        tod = time_of_day(starts.get(row["id"]))
        sessions.append(
            {
                "id": row["id"],
                "date": row["date"],
                "name": row["name"],
                "family": family,
                "verdict": VERDICTS.get(row["verdict"]) if row["verdict"] else None,
                "effort_gap": (row["rpe"] - target) if row["rpe"] is not None and target is not None else None,
                "period": tod["period"] if tod else None,
                "indoor": indoor if row["type"] in RIDE_TYPES else None,
                "pre_fuel": row["pre_fuel"],
                "sleep": checkin.get("sleep_quality"),
                "energy": checkin.get("energy"),
                "rested": previous_day not in active_days,
            }
        )
    return sessions


# ---------------------------------------------------------------------------
# Conditions: each splits sessions into a named side and the comparison side.
# ---------------------------------------------------------------------------

Split = tuple[str, str, Callable[[dict], Optional[bool]]]


def _period_split(period: str) -> Split:
    return (
        f"in the {period}",
        "at other times",
        lambda s: None if s["period"] is None else s["period"] == period,
    )


CONDITIONS: dict[str, list[Split]] = {
    "time_of_day": [_period_split(p) for p in ("morning", "afternoon", "evening", "night")],
    "venue": [("indoors", "outdoors", lambda s: s["indoor"])],
    "pre_fuel": [("fasted", "after eating", lambda s: None if s["pre_fuel"] is None else s["pre_fuel"] == "fasted")],
    "sleep": [("after good sleep (4–5)", "after poor sleep (1–2)", lambda s: None if s["sleep"] in (None, 3) else s["sleep"] >= 4)],
    "energy": [("on high-energy mornings (4–5)", "on low-energy mornings (1–2)", lambda s: None if s["energy"] in (None, 3) else s["energy"] >= 4)],
    "rest": [("the day after a rest day", "on back-to-back days", lambda s: s["rested"])],
}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _compare(sessions: list[dict], outcome: str, split: Split) -> Optional[dict[str, Any]]:
    label_on, label_off, predicate = split
    on, off = [], []
    for session in sessions:
        value = session[outcome]
        side = predicate(session)
        if value is None or side is None:
            continue
        (on if side else off).append(value)
    if min(len(on), len(off)) < EMERGING_MIN:
        return None
    gap = _mean(on) - _mean(off)
    threshold = VERDICT_GAP if outcome == "verdict" else EFFORT_GAP
    if abs(gap) < threshold:
        return None
    # For effort cost, lower is better: a negative gap means "on" went better.
    better_on = gap > 0 if outcome == "verdict" else gap < 0
    return {
        "on": label_on,
        "off": label_off,
        "n_on": len(on),
        "n_off": len(off),
        "mean_on": round(_mean(on), 2),
        "mean_off": round(_mean(off), 2),
        "gap": round(gap, 2),
        "better_on": better_on,
        "confirmed": min(len(on), len(off)) >= CONFIRMED_MIN,
    }


def _describe(family: str, outcome: str, result: dict[str, Any]) -> str:
    subject = FAMILY_LABELS[family]
    good, bad = (result["on"], result["off"]) if result["better_on"] else (result["off"], result["on"])
    if outcome == "verdict":
        return f"{subject} were rated better {good} than {bad}."
    return f"{subject} felt easier for the same job {good} than {bad}."


def _evidence(outcome: str, result: dict[str, Any]) -> str:
    if outcome == "verdict":
        fmt = lambda v: f"{v:+.1f}"
        scale = "average rating on a −1 (hated) to +1 (loved) scale"
    else:
        fmt = lambda v: f"{v:+.1f}"
        scale = "RPE versus the session's target"
    return (
        f"{result['on']}: {fmt(result['mean_on'])} over {result['n_on']} sessions; "
        f"{result['off']}: {fmt(result['mean_off'])} over {result['n_off']} ({scale})."
    )


def build_what_worked(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, Any]:
    today = today or date.today()
    sessions = _load_sessions(conn, today)
    patterns = []
    for family in ("ride_quality", "ride_easy", "run", "strength", "all"):
        pool = sessions if family == "all" else [s for s in sessions if s["family"] == family]
        for outcome in ("verdict", "effort_gap"):
            for condition, splits in CONDITIONS.items():
                if condition == "venue" and family in ("run", "strength", "all"):
                    continue
                for split in splits:
                    result = _compare(pool, outcome, split)
                    if not result:
                        continue
                    patterns.append(
                        {
                            "family": family,
                            "outcome": outcome,
                            "condition": condition,
                            "statement": _describe(family, outcome, result),
                            "evidence": _evidence(outcome, result),
                            "status": "confirmed" if result["confirmed"] else "emerging",
                            "strength": round(abs(result["gap"]) / (VERDICT_GAP if outcome == "verdict" else EFFORT_GAP), 2),
                            **result,
                        }
                    )
    patterns = _dedupe(patterns)
    patterns.sort(key=lambda p: (p["status"] != "confirmed", -min(p["n_on"], p["n_off"]), -p["strength"]))

    tagged = [s for s in sessions if s["verdict"] is not None]
    recent_cutoff = (today - timedelta(days=13)).isoformat()
    untagged = conn.execute(
        """
        SELECT a.id, a.date, a.type, a.name
        FROM activities AS a
        LEFT JOIN session_tags AS t ON t.activity_id = a.id
        WHERE a.date >= ? AND a.type IN ('Ride', 'VirtualRide', 'Run', 'WeightTraining') AND (t.verdict IS NULL)
        ORDER BY a.date DESC
        LIMIT 16
        """,
        (recent_cutoff,),
    ).fetchall()
    sick = sick_dates(conn)
    untagged = [row for row in untagged if row["date"] not in sick][:8]
    return {
        "as_of": today.isoformat(),
        "sessions_considered": len(sessions),
        "tagged_sessions": len(tagged),
        "verdicts": {key: sum(1 for s in tagged if s["verdict"] == value) for key, value in VERDICTS.items()},
        "with_effort_data": sum(1 for s in sessions if s["effort_gap"] is not None),
        "confirmed": [p for p in patterns if p["status"] == "confirmed"],
        "emerging": [p for p in patterns if p["status"] == "emerging"][:8],
        "untagged_recent": [dict(r) for r in untagged],
        "thresholds": {"confirmed_min": CONFIRMED_MIN, "emerging_min": EMERGING_MIN, "verdict_gap": VERDICT_GAP, "effort_gap": EFFORT_GAP},
        "method": (
            "Compares your loved/fine/hated tags and RPE-versus-target across conditions. A pattern is confirmed with "
            f"{CONFIRMED_MIN}+ sessions on each side and a clear gap; with {EMERGING_MIN}+ it is emerging. "
            "These are observations from your history, not causes."
        ),
    }


def _dedupe(patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the most specific family per (outcome, condition, side) and drop
    the "all sessions" version when a family-level one says the same thing."""
    kept: dict[tuple, dict[str, Any]] = {}
    for pattern in patterns:
        key = (pattern["outcome"], pattern["condition"], pattern["on"], pattern["better_on"], pattern["family"])
        kept[key] = pattern
    specific = {(p["outcome"], p["condition"], p["on"], p["better_on"]) for p in patterns if p["family"] != "all"}
    return [p for p in kept.values() if not (p["family"] == "all" and (p["outcome"], p["condition"], p["on"], p["better_on"]) in specific)]


def build_what_worked_coaching_context(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, Any]:
    data = build_what_worked(conn, today)
    compact = lambda p: {"pattern": p["statement"], "evidence": p["evidence"]}
    return {
        "confirmed": [compact(p) for p in data["confirmed"][:6]],
        "emerging": [compact(p) for p in data["emerging"][:4]],
        "tagged_sessions": data["tagged_sessions"],
        "guidance": (
            "Confirmed patterns are the athlete's own history: when the schedule allows, place sessions where they "
            "went better (e.g. time of day, rest the day before). Treat emerging patterns as hints only and never as rules."
        ),
    }


def patterns_for_family(conn: sqlite3.Connection, family: str, today: Optional[date] = None) -> list[dict[str, Any]]:
    """Confirmed patterns relevant to one session family, for the pre-session brief."""
    data = build_what_worked(conn, today)
    return [p for p in data["confirmed"] if p["family"] in (family, "all")]
