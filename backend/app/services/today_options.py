""""Feeling flat" and "Short on time": concrete changes to today's planned session.

The athlete taps how they are going in and gets two or three ready-made versions of
today instead of a blank chat. Every option is an ordinary plan change (an
adjustment, so it becomes a plan revision, or a swap), and each one names what it
keeps: a lift stays a lift, because lifting three times a week is an anchor goal.
Resting is only offered for non-lift days; a flat lift day can be moved instead.
"""
import json
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import HTTPException

from ..models.plans import WeeklyPlanAdjustment, WeeklyPlanDay, WeeklyPlanSwap
from .life_load import get_life_load_days
from .minimum_week import minimum_week_state
from .plans import adjust_weekly_plan_data, swap_weekly_plan_days_data

REASONS = {"flat": "Feeling flat", "short": "Short on time"}
LIFT_TYPES = {"strength", "weighttraining"}
REST_TYPES = {"rest", ""}
ENDURANCE_FALLBACK_MIN = 45
FLAT_SHARE = 0.6
QUICK_MIN = {"lift": 25, "endurance": 30}
EASY_INTENTS = {None, "", "easy", "recovery", "long"}

FLAT_LIFT = ("Feeling flat: main lifts only, 2 working sets at last time's weights, stop 2-3 reps short of failure. "
             "No new loads today. It still counts as a lift.")
FLAT_ENDURANCE = ("Feeling flat: Zone 2 only, conversational the whole way. If you feel better after 15 min, "
                  "stay easy anyway; you'll bank the session without digging a hole.")
QUICK_LIFT = ("Short on time: main lifts only (first 2-3 exercises), 3 working sets, skip accessories and "
              "keep rests to 90 s. It still counts as a lift.")
QUICK_EASY = "Short on time: steady Zone 2. 5 min easy to start, then hold it; consistency beats length."
QUICK_HARD = "Short on time: 10 min easy, then half the main set at the planned effort, 5 min easy to finish."
REST_FLAT = "Feeling flat: rest. A walk or 10 minutes of mobility keeps the streak if you want it."


def _kind(day: dict) -> str:
    session_type = str(day.get("session_type") or "").strip().lower()
    if session_type in LIFT_TYPES:
        return "lift"
    if session_type in REST_TYPES:
        return "rest"
    return "endurance"


def _round5(value: float) -> int:
    return int(round(value / 5) * 5)


def _week_start(day: date) -> str:
    return (day - timedelta(days=day.weekday())).isoformat()


def _plan_days(conn: sqlite3.Connection, week_start: str) -> list[dict]:
    row = conn.execute("SELECT days_json FROM weekly_plans WHERE week_start = ?", (week_start,)).fetchone()
    return sorted(json.loads(row["days_json"]), key=lambda item: item["date"]) if row else []


def _training_done_on(conn: sqlite3.Connection, day: str) -> bool:
    """A recorded session other than a walk; the daily streak walk does not complete a planned session."""
    return bool(conn.execute(
        "SELECT 1 FROM activities WHERE substr(date, 1, 10) = ? AND type != 'Walk' LIMIT 1", (day,)
    ).fetchone())


def _changed(day: dict, **updates: Any) -> dict:
    """Today's session with new targets; a structured ride is dropped because its blocks no longer fit."""
    result = {key: value for key, value in day.items() if key in WeeklyPlanDay.model_fields}
    result.update(updates)
    if "cycling_workout_id" not in updates:
        result["cycling_workout_id"] = None
    return result


def _minutes(day: dict) -> Optional[int]:
    value = day.get("target_duration_min")
    return int(value) if value else None


def _easy_version(day: dict) -> dict:
    kind = _kind(day)
    planned = _minutes(day) or ENDURANCE_FALLBACK_MIN
    minutes = max(20 if kind == "lift" else 30, _round5(planned * FLAT_SHARE))
    if kind == "lift":
        proposed = _changed(day, title=f"{day.get('title') or 'Strength'} (light)", details=FLAT_LIFT,
                            target_duration_min=min(planned, minutes))
        summary = f"Same lifts, lighter: 2 working sets, no new loads, about {proposed['target_duration_min']} min."
    else:
        proposed = _changed(day, workout_intent="easy", title=f"Easy {_sport_word(day)}", details=FLAT_ENDURANCE,
                            target_duration_min=min(planned, minutes), target_distance_km=None)
        summary = f"{proposed['target_duration_min']} min in Zone 2 instead of {planned} min" + \
            ("" if (day.get("workout_intent") or "") in EASY_INTENTS else f" of {day.get('workout_intent')}") + "."
    already_easy = kind != "lift" and (day.get("workout_intent") or None) in EASY_INTENTS
    label = "Lighter version" if kind == "lift" or already_easy else "Easy version"
    return {"key": "easy", "label": label, "summary": summary, "action": "adjust", "day": proposed}


def _quick_version(day: dict) -> Optional[dict]:
    kind = _kind(day)
    target = QUICK_MIN[kind]
    planned = _minutes(day)
    if planned is not None and planned <= target:
        return None
    if kind == "lift":
        proposed = _changed(day, title=f"{day.get('title') or 'Strength'} (express)", details=QUICK_LIFT, target_duration_min=target)
        summary = f"Main lifts only, 3 working sets, {target} min. Still counts toward lifting three times this week."
    else:
        easy = (day.get("workout_intent") or None) in EASY_INTENTS
        proposed = _changed(day, details=QUICK_EASY if easy else QUICK_HARD, target_duration_min=target, target_distance_km=None)
        summary = f"{target} min instead of {planned or 'the planned'}{' min' if planned else ' session'}" + \
            ("." if easy else ", keeping a short version of the main set.")
    return {"key": "quick", "label": f"{target}-min version", "summary": summary, "action": "adjust", "day": proposed}


def _sport_word(day: dict) -> str:
    session_type = str(day.get("session_type") or "").lower()
    return {"run": "run", "walk": "walk", "swim": "swim"}.get(session_type, "ride" if "ride" in session_type or session_type in {"cycling", "bike"} else "session")


def _move_target(conn: sqlite3.Connection, today: dict, days: list[dict]) -> Optional[dict]:
    """The first later day this week that makes today lighter: a rest day, or an easy session in place
    of a lift. Never a tagged (busy) day, and a lift never lands next to another lift."""
    later = [day for day in days if day["date"] > today["date"]]
    if not later:
        return None
    tagged = get_life_load_days(conn, later[0]["date"], later[-1]["date"])
    kind = _kind(today)
    lift_dates = {day["date"] for day in days if _kind(day) == "lift" and day["date"] != today["date"]}
    for day in later:
        lighter = _kind(day) == "rest" or (
            kind == "lift" and _kind(day) == "endurance" and (day.get("workout_intent") or None) in EASY_INTENTS
        )
        if not lighter or day["date"] in tagged or _training_done_on(conn, day["date"]):
            continue
        if kind == "lift":
            # Keep lifts apart: not next to another lift day.
            neighbours = {(date.fromisoformat(day["date"]) + timedelta(days=step)).isoformat() for step in (-1, 1)}
            if neighbours & lift_dates:
                continue
        return day
    return None


def _move_option(conn: sqlite3.Connection, today: dict, days: list[dict]) -> Optional[dict]:
    target = _move_target(conn, today, days)
    if not target:
        return None
    weekday = date.fromisoformat(target["date"]).strftime("%A")
    swapped = "rest" if _kind(target) == "rest" else (target.get("title") or "that session").lower()
    return {
        "key": "move",
        "label": f"Move it to {weekday}",
        "summary": f"Swap with {weekday} ({swapped}), so today gets {weekday}'s plan." if _kind(target) != "rest"
        else f"Do it on {weekday} instead and rest today.",
        "action": "swap",
        "to_date": target["date"],
    }


def build_today_options(conn: sqlite3.Connection, reason: str, today: Optional[date] = None) -> dict[str, Any]:
    if reason not in REASONS:
        raise HTTPException(status_code=400, detail=f"reason must be one of: {', '.join(REASONS)}")
    day = today or datetime.now().date()
    week_start = _week_start(day)
    days = _plan_days(conn, week_start)
    planned = next((item for item in days if item["date"] == day.isoformat()), None)
    base = {"reason": reason, "label": REASONS[reason], "date": day.isoformat(), "week_start": week_start}
    if not planned or _kind(planned) == "rest":
        return {**base, "available": False, "message": "Nothing is planned today, so there's nothing to change.", "options": []}
    if _training_done_on(conn, day.isoformat()):
        return {**base, "available": False, "message": "Today's session is already done.", "options": []}

    options: list[dict] = []
    if reason == "flat":
        options.append(_easy_version(planned))
        move = _move_option(conn, planned, days)
        if move:
            options.append(move)
        if _kind(planned) != "lift":
            rest = _changed(planned, session_type="Rest", workout_intent=None, title="Rest", details=REST_FLAT,
                            target_duration_min=None, target_distance_km=None, template_id=None, template_label=None,
                            template_summary=None, benchmark_tag=None, benchmark_label=None)
            options.append({"key": "rest", "label": "Rest today", "summary": "Take the day. A walk keeps the streak.",
                            "action": "adjust", "day": rest})
        message = ("Flat days happen. Doing a lighter version still counts: it keeps the habit and the anchor without digging a hole."
                   if _kind(planned) == "lift" else
                   "Flat days happen. An easy version keeps the habit; resting is fine too when the week allows it.")
    else:
        quick = _quick_version(planned)
        if quick:
            options.append(quick)
        move = _move_option(conn, planned, days)
        if move:
            options.append(move)
        if not minimum_week_state(conn, week_start):
            options.append({"key": "minimum_week", "label": "Shrink the whole week",
                            "summary": "If the rest of the week is tight too: keep the anchors, make the rest short or rest.",
                            "action": "minimum_week"})
        message = ("A short session beats a skipped one. Pick the version that fits."
                   if quick else "Today is already short. If the whole week is squeezed, shrink it instead.")
    return {**base, "available": True, "message": message, "planned": planned, "options": options}


def apply_today_option(conn: sqlite3.Connection, reason: str, key: str, today: Optional[date] = None) -> dict[str, Any]:
    state = build_today_options(conn, reason, today)
    option = next((item for item in state["options"] if item["key"] == key), None)
    if not option or option["action"] not in {"adjust", "swap"}:
        raise HTTPException(status_code=400, detail=f"Option {key!r} is not available today")
    label = f"{state['label']}: {option['label'].lower()}"
    # Only walks can be recorded on an open day (see build_today_options); they don't lock the plan.
    unlocked = frozenset({state["date"], option.get("to_date") or state["date"]})
    if option["action"] == "swap":
        result = swap_weekly_plan_days_data(conn, WeeklyPlanSwap(from_date=state["date"], to_date=option["to_date"]),
                                            unprotected_dates=unlocked)
        undo = {"action": "swap", "from_date": state["date"], "to_date": option["to_date"]}
    else:
        result = adjust_weekly_plan_data(conn, WeeklyPlanAdjustment(
            week_start=state["week_start"], effective_from=state["date"],
            days=[WeeklyPlanDay(**option["day"])], adaptation_reason=label,
        ), unprotected_dates=unlocked)
        previous = {key: value for key, value in state["planned"].items() if key in WeeklyPlanDay.model_fields}
        undo = {"action": "adjust", "week_start": state["week_start"], "effective_from": state["date"], "days": [previous]}
    return {"status": "ok", "applied": label, "option": option["key"], "undo": undo, "plan": result.get("plan")}


def undo_today_option(conn: sqlite3.Connection, undo: dict, today: Optional[date] = None) -> dict[str, Any]:
    """Put back today's session as it was before ``apply_today_option``; only today's change can be undone."""
    day = (today or datetime.now().date()).isoformat()
    action = undo.get("action")
    if action == "swap" and undo.get("from_date") == day and undo.get("to_date"):
        unlocked = frozenset({day, undo["to_date"]})
        result = swap_weekly_plan_days_data(conn, WeeklyPlanSwap(from_date=undo["to_date"], to_date=day),
                                            unprotected_dates=unlocked)
    elif action == "adjust" and undo.get("effective_from") == day and [item.get("date") for item in undo.get("days") or []] == [day]:
        result = adjust_weekly_plan_data(conn, WeeklyPlanAdjustment(
            week_start=undo["week_start"], effective_from=day,
            days=[WeeklyPlanDay(**undo["days"][0])], adaptation_reason="Undid today's change",
        ), unprotected_dates=frozenset({day}))
    else:
        raise HTTPException(status_code=400, detail="Only today's change can be undone")
    return {"status": "ok", "plan": result.get("plan")}
