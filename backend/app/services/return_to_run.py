"""Return-to-run tracker: staged progression driven by symptom scores.

The athlete switches the program on with a starting stage. Every run since the
start date is replayed in order against simple, conservative rules:

* flare (during >= 4/10, or next morning >= 3/10): drop one stage;
* clean (during <= 2/10 and, when logged, next morning <= 2/10): counts
  toward the stage; two clean runs in a row advance, but only once the latest
  run's next-morning score is in, because morning stiffness is the signal that
  matters most for heel (plantar fascia) pain;
* anything else: hold the stage and restart the clean count.

Runs without a "during" score do not count either way. The feedback form's
generic pain score stands in for "during" when no symptom score was logged.
Nothing here edits the plan: the stage and its prescription are context for
the athlete, the pre-session brief and the weekly planner.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from typing import Any, Optional

from ..repositories.settings import get_setting_value, set_setting_value
from .heart_rate_zones import HR_ZONE_DEFINITIONS

SETTINGS_KEY = "return_to_run"
CLEAN_MAX = 2
FLARE_DURING = 4
FLARE_MORNING = 3
CLEAN_RUNS_TO_ADVANCE = 2
CLEAN_RUNS_TO_GRADUATE = 3  # at the final stage: symptoms look resolved
LONG_GAP_DAYS = 21  # a break this long costs one stage when choosing where to start
EARLY_STAGE_REST_DAYS = 2  # stages 1-3: at least one full day between runs
RUN_HR_CAP = next(zone["upper_bpm"] for zone in HR_ZONE_DEFINITIONS["run"] if zone["key"] == "zone2")
DISTANCE_INCREASE = 1.10  # +10% over the previous week counts as "more distance"
DISTANCE_MIN_DELTA_MIN = 10
FAST_INTENTS = ("tempo", "interval", "race_specific")

STAGES = (
    {"stage": 1, "name": "Run/walk 1:2", "minutes": 25,
     "prescription": "5 min brisk walk, then 6–8 × (1 min easy jog / 2 min walk), easy cool-down. Flat route, no pace target."},
    {"stage": 2, "name": "Run/walk 2:1", "minutes": 25,
     "prescription": "5 min brisk walk, then 6–8 × (2 min easy jog / 1 min walk). Flat route, no pace target."},
    {"stage": 3, "name": "Run/walk 5:1", "minutes": 30,
     "prescription": "5 min brisk walk, then 4–5 × (5 min easy jog / 1 min walk). Conversational pace."},
    {"stage": 4, "name": "Continuous 20 min", "minutes": 25,
     "prescription": "20 min continuous easy running plus a short walk warm-up. Stay under the HR cap."},
    {"stage": 5, "name": "Continuous 30–40 min", "minutes": 40,
     "prescription": "30–40 min continuous easy running, up to 3 runs a week. Raise distance or pace, never both in one week."},
    {"stage": 6, "name": "Back to normal running", "minutes": 60,
     "prescription": "Easy runs up to 60 min. Add one quality session only after two clean weeks here."},
)


# ---------------------------------------------------------------------------
# Settings and scores
# ---------------------------------------------------------------------------


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS run_symptom_checks (
            activity_id TEXT PRIMARY KEY,
            during INTEGER CHECK (during BETWEEN 0 AND 10),
            next_morning INTEGER CHECK (next_morning BETWEEN 0 AND 10),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE
        )
        """
    )


def get_program(conn: sqlite3.Connection) -> dict[str, Any]:
    raw = get_setting_value(conn, SETTINGS_KEY)
    try:
        program = json.loads(raw) if raw else {}
    except (TypeError, ValueError):
        program = {}
    return {
        "active": bool(program.get("active")),
        "symptom": program.get("symptom") or "Heel",
        "started_on": program.get("started_on"),
        "start_stage": int(program.get("start_stage") or 1),
    }


def save_program(conn: sqlite3.Connection, payload: dict[str, Any], today: Optional[date] = None) -> dict[str, Any]:
    today = today or date.today()
    program = get_program(conn)
    if payload.get("active") is False:
        program["active"] = False
    else:
        program.update(
            {
                "active": True,
                "symptom": (payload.get("symptom") or program["symptom"]).strip()[:40] or "Heel",
                "started_on": payload.get("started_on") or today.isoformat(),
                "start_stage": min(max(int(payload.get("start_stage") or 1), 1), len(STAGES)),
            }
        )
    set_setting_value(conn, SETTINGS_KEY, json.dumps(program))
    conn.commit()
    return program


def save_symptom_check(conn: sqlite3.Connection, activity_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Upsert only the fields present; ``None`` clears one."""
    _ensure_table(conn)
    row = conn.execute("SELECT type FROM activities WHERE id = ?", (activity_id,)).fetchone()
    if not row:
        raise LookupError("Activity not found")
    if row["type"] != "Run":
        raise ValueError("Symptom checks are for runs")
    current = conn.execute("SELECT during, next_morning FROM run_symptom_checks WHERE activity_id = ?", (activity_id,)).fetchone()
    during = payload["during"] if "during" in payload else (current["during"] if current else None)
    morning = payload["next_morning"] if "next_morning" in payload else (current["next_morning"] if current else None)
    conn.execute(
        """
        INSERT INTO run_symptom_checks (activity_id, during, next_morning) VALUES (?, ?, ?)
        ON CONFLICT(activity_id) DO UPDATE SET
            during = excluded.during, next_morning = excluded.next_morning, updated_at = CURRENT_TIMESTAMP
        """,
        (activity_id, during, morning),
    )
    conn.commit()
    return {"activity_id": activity_id, "during": during, "next_morning": morning}


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


def _runs_since(conn: sqlite3.Connection, started_on: str) -> list[dict[str, Any]]:
    _ensure_table(conn)
    rows = conn.execute(
        """
        SELECT a.id, a.date, a.name, a.distance_km, a.duration_min, a.avg_hr,
               c.during, c.next_morning, f.pain_level AS feedback_pain
        FROM activities AS a
        LEFT JOIN run_symptom_checks AS c ON c.activity_id = a.id
        LEFT JOIN activity_feedback AS f ON f.activity_id = a.id
        WHERE a.type = 'Run' AND a.date >= ?
        ORDER BY a.date, a.id
        """,
        (started_on,),
    ).fetchall()
    return [dict(row) for row in rows]


def _classify(during: Optional[int], morning: Optional[int]) -> str:
    if during is None:
        return "unscored"
    if during >= FLARE_DURING or (morning is not None and morning >= FLARE_MORNING):
        return "flare"
    if during <= CLEAN_MAX and (morning is None or morning <= CLEAN_MAX):
        return "clean"
    return "hold"


def build_return_to_run(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, Any]:
    today = today or date.today()
    program = get_program(conn)
    base = {"program": program, "stages": list(STAGES), "hr_cap_bpm": RUN_HR_CAP}
    if not program["active"] or not program["started_on"]:
        return {**base, "active": False, "suggested_start": suggest_start_stage(conn, today)}

    stage = program["start_stage"]
    clean_streak = 0
    history = []
    previous_day: Optional[date] = None
    for run in _runs_since(conn, program["started_on"]):
        run_day = date.fromisoformat(run["date"])
        after_break = previous_day is not None and (run_day - previous_day).days >= LONG_GAP_DAYS
        if after_break and stage > 1:
            # A long break costs one stage, as when choosing where to start.
            stage -= 1
            clean_streak = 0
        previous_day = run_day
        during = run["during"] if run["during"] is not None else run["feedback_pain"]
        source = "symptom" if run["during"] is not None else ("feedback" if run["feedback_pain"] is not None else None)
        outcome = _classify(during, run["next_morning"])
        stage_at_run = stage
        change = None
        if outcome == "flare":
            if stage > 1:
                stage -= 1
                change = "down"
            clean_streak = 0
        elif outcome == "clean":
            clean_streak += 1
            if clean_streak >= CLEAN_RUNS_TO_ADVANCE and run["next_morning"] is not None and stage < len(STAGES):
                stage += 1
                change = "up"
                clean_streak = 0
        elif outcome == "hold":
            clean_streak = 0
        planned_minutes = STAGES[stage_at_run - 1]["minutes"]
        history.append(
            {
                "activity_id": run["id"],
                "date": run["date"],
                "name": run["name"],
                "distance_km": run["distance_km"],
                "duration_min": run["duration_min"],
                "avg_hr": run["avg_hr"],
                "above_hr_cap": bool(run["avg_hr"] and run["avg_hr"] > RUN_HR_CAP),
                "longer_than_stage": bool(run["duration_min"] and run["duration_min"] > planned_minutes * 1.3),
                "stage": stage_at_run,
                "during": during,
                "during_source": source,
                "next_morning": run["next_morning"],
                "outcome": outcome,
                "stage_change": change,
                "after_break": after_break,
            }
        )

    break_days = (today - previous_day).days if previous_day else None
    if break_days is not None and break_days >= LONG_GAP_DAYS and stage > 1:
        stage -= 1
        clean_streak = 0

    current = STAGES[stage - 1]
    last = history[-1] if history else None
    next_step = _next_step(last, stage, clean_streak, today)
    if break_days is not None and break_days >= LONG_GAP_DAYS and last and next_step["status"] == "ready":
        next_step["message"] = f"{break_days} days since your last run, so back one stage: {current['name']}."
    return {
        **base,
        "active": True,
        "stage": current,
        "clean_streak": clean_streak,
        "clean_runs_to_advance": CLEAN_RUNS_TO_ADVANCE,
        "next": next_step,
        "history": list(reversed(history)),
        "rules": [
            f"Clean run: {program['symptom'].lower()} ≤ {CLEAN_MAX}/10 during and the next morning.",
            f"{CLEAN_RUNS_TO_ADVANCE} clean runs in a row move you up a stage (the latest needs its next-morning score).",
            f"Flare: ≥ {FLARE_DURING}/10 during or ≥ {FLARE_MORNING}/10 the next morning drops one stage.",
            f"A break of {LONG_GAP_DAYS}+ days between runs also drops one stage.",
            "Never raise distance and pace in the same week.",
            f"Easy runs stay under {RUN_HR_CAP} bpm.",
        ],
    }


def _next_step(last: Optional[dict], stage: int, clean_streak: int, today: date) -> dict[str, Any]:
    prescription = STAGES[stage - 1]
    if last is None:
        return {"status": "ready", "message": f"Start with {prescription['name']}.", "earliest": today.isoformat()}
    last_day = date.fromisoformat(last["date"])
    rest_days = EARLY_STAGE_REST_DAYS if stage <= 3 else 1
    earliest = last_day + timedelta(days=rest_days)
    if last["during"] is None:
        return {"status": "needs_score", "message": "Log how the last run felt before the next one.", "activity_id": last["activity_id"], "earliest": earliest.isoformat()}
    if last["outcome"] == "flare":
        return {"status": "flare", "message": f"Flare after the last run. Rest it, then repeat {prescription['name']} once symptoms settle.", "earliest": earliest.isoformat()}
    if last["next_morning"] is None and today > last_day:
        return {"status": "needs_morning", "message": "Log the morning-after score for the last run.", "activity_id": last["activity_id"], "earliest": earliest.isoformat()}
    if stage == len(STAGES) and clean_streak >= CLEAN_RUNS_TO_GRADUATE:
        return {
            "status": "graduated",
            "message": f"{CLEAN_RUNS_TO_GRADUATE} clean full runs in a row: symptoms look resolved. You can end the program.",
            "earliest": earliest.isoformat(),
        }
    if earliest > today:
        return {"status": "rest", "message": f"Rest day first. Next run from {earliest.isoformat()}: {prescription['name']}.", "earliest": earliest.isoformat()}
    if last["stage_change"] == "up":
        return {"status": "ready", "message": f"Moved up: next run is {prescription['name']}.", "earliest": earliest.isoformat()}
    remaining = CLEAN_RUNS_TO_ADVANCE - clean_streak
    return {"status": "ready", "message": f"Ready: {prescription['name']}. {remaining} more clean run{'s' if remaining != 1 else ''} to move up.", "earliest": earliest.isoformat()}


def suggest_start_stage(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, Any]:
    """Pick a cautious starting stage from the most recent runs.

    The last pain-free run sets the level (its duration maps to a stage); a
    break of 3+ weeks costs one stage, and recent pain above 2/10 starts at 1.
    """
    today = today or date.today()
    _ensure_table(conn)
    rows = conn.execute(
        """
        SELECT a.date, a.duration_min, COALESCE(c.during, f.pain_level) AS pain
        FROM activities AS a
        LEFT JOIN run_symptom_checks AS c ON c.activity_id = a.id
        LEFT JOIN activity_feedback AS f ON f.activity_id = a.id
        WHERE a.type = 'Run' AND a.date >= ?
        ORDER BY a.date DESC
        LIMIT 3
        """,
        ((today - timedelta(days=120)).isoformat(),),
    ).fetchall()
    if not rows:
        return {"stage": 1, "reason": "No runs in the last four months, so start from the beginning."}
    last = rows[0]
    if any(row["pain"] is not None and row["pain"] > CLEAN_MAX for row in rows):
        return {"stage": 1, "reason": "A recent run scored above 2/10 for pain, so start from the beginning."}
    minutes = float(last["duration_min"] or 0)
    stage = 4 if minutes >= 20 else 3 if minutes >= 15 else 1
    if minutes >= 30:
        stage = 5
    gap = (today - date.fromisoformat(last["date"])).days
    reason = f"Last run {last['date']}: {round(minutes)} min"
    if last["pain"] is not None:
        reason += f", pain {last['pain']}/10"
    if gap >= LONG_GAP_DAYS and stage > 1:
        stage -= 1
        reason += f". {gap} days since then, so one stage lower"
    return {"stage": stage, "reason": f"{reason}.", "days_since_last_run": gap}


# ---------------------------------------------------------------------------
# Plan check: never raise distance and pace in the same week
# ---------------------------------------------------------------------------


def check_run_progression(conn: sqlite3.Connection, days: list[dict], week_start: str) -> Optional[dict[str, Any]]:
    """Flag a plan whose runs raise both volume and pace versus last week's actual runs."""
    run_days = [day for day in days if "run" in (day.get("session_type") or "").lower()]
    if not run_days:
        return None
    start = date.fromisoformat(week_start)
    previous = conn.execute(
        """
        SELECT COALESCE(SUM(duration_min), 0) AS minutes, COUNT(*) AS runs
        FROM activities WHERE type = 'Run' AND date >= ? AND date < ?
        """,
        ((start - timedelta(days=7)).isoformat(), start.isoformat()),
    ).fetchone()
    previous_fast = conn.execute(
        """
        SELECT COUNT(*) FROM activities
        WHERE type = 'Run' AND date >= ? AND date < ? AND workout_intent IN ('tempo', 'interval', 'race_specific')
        """,
        ((start - timedelta(days=7)).isoformat(), start.isoformat()),
    ).fetchone()[0]
    planned_minutes = sum(float(day.get("target_duration_min") or 0) for day in run_days)
    planned_fast = sum(1 for day in run_days if day.get("workout_intent") in FAST_INTENTS)
    previous_minutes = float(previous["minutes"] or 0)
    more_distance = planned_minutes > previous_minutes * DISTANCE_INCREASE and planned_minutes - previous_minutes >= DISTANCE_MIN_DELTA_MIN
    more_pace = planned_fast > previous_fast
    if not (more_distance and more_pace):
        return None
    return {
        "type": "run_distance_and_pace",
        "label": "Distance and pace both rise",
        "summary": (
            f"Planned running is {round(planned_minutes)} min with {planned_fast} faster session(s), against "
            f"{round(previous_minutes)} min and {previous_fast} last week. Raise one, not both."
        ),
    }


def build_return_to_run_context(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, Any]:
    data = build_return_to_run(conn, today)
    if not data["active"]:
        return {"active": False}
    return {
        "active": True,
        "symptom": data["program"]["symptom"],
        "stage": {key: data["stage"][key] for key in ("stage", "name", "prescription", "minutes")},
        "next": data["next"],
        "recent_runs": [
            {key: run[key] for key in ("date", "stage", "during", "next_morning", "outcome", "above_hr_cap")}
            for run in data["history"][:5]
        ],
        "rules": data["rules"],
        "guidance": "Plan run days from the current stage's prescription only. Do not progress the stage in the plan; the tracker moves it from symptom scores.",
    }
