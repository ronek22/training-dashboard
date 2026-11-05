"""The week brief: one ordered contract for a week, built from everything that steers a plan.

Season (winter arc block, anchor and outcome goals), limits (injuries, illness, trips, busy days)
and habits (long-ride days, reliable weekdays) used to reach the planner as separate pieces that
could contradict each other. The brief resolves them in one fixed order:

    safety > anchors > block > outcomes > habits

and says where each line comes from. The planner plans to it, the save step fits rides to the
block and lifts to the weekly slots, and Plan shows it so the week explains itself.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date, timedelta
from typing import Optional

PRIORITY = ("safety", "anchor", "block", "outcome", "habit")
PRIORITY_LABELS = {"safety": "Safety", "anchor": "Anchor", "block": "Block", "outcome": "Outcome", "habit": "Habit"}
# A protected area here takes the week's lower-body lift out.
LOWER_AREAS = {"knee", "heel", "hip"}
QUALITY_METRICS = {"quality_sessions"}
RIDE_VOLUME_METRICS = {"ride_km", "ride_hours", "ride_minutes"}
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
WEEKDAY_LABELS = dict(zip(WEEKDAYS, ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")))
SLOT_NAMES = {"upper": "Upper", "lower": "Lower", "full_body": "Full body", "mobility": "Mobility"}


def _monday(value: str) -> str:
    day = date.fromisoformat(value)
    return (day - timedelta(days=day.weekday())).isoformat()


def _short(iso: str) -> str:
    day = date.fromisoformat(iso)
    return f"{WEEKDAY_LABELS[WEEKDAYS[day.weekday()]]} {day.day}"


def _line(priority: str, text: str, source: str, key: str) -> dict:
    return {"priority": priority, "priority_label": PRIORITY_LABELS[priority], "text": text, "source": source, "key": key}


def _week_dates(week_start: str) -> list[str]:
    start = date.fromisoformat(week_start)
    return [(start + timedelta(days=n)).isoformat() for n in range(7)]


def _goals(conn: sqlite3.Connection, week_start: str) -> list[dict]:
    from ..repositories.goals import ACTIVE_GOAL_CONDITION

    try:
        rows = conn.execute(
            "SELECT id, title, metric_type, period_type, target_value, activity_type, commitment, end_date FROM goals "
            f"WHERE {ACTIVE_GOAL_CONDITION} AND COALESCE(lifecycle_status, 'active') = 'active' "
            # Weekly goals repeat; others count until they end.
            "AND (period_type = 'week' OR end_date >= ?) ORDER BY commitment = 'anchor' DESC, id",
            (week_start, week_start),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(row) for row in rows]


def _limits(conn: sqlite3.Connection, week_start: str, today: date) -> tuple[list[dict], set[str]]:
    """Safety lines and the protected body areas that change the lifts."""
    from .illness_return import illness_return_dates
    from .mountain_reentry import mountain_reentry_dates
    from .recovery import coaching_summary, leg_comeback
    from .sick_mode import sick_dates

    dates = set(_week_dates(week_start))
    lines, areas = [], set()
    for issue in coaching_summary(conn)["issues"]:
        protected = set(issue["protected_areas"])
        areas |= protected
        rule = "no lower-body lifts, rides easy and flat with a pain check (go if 0-2/10 at rest)" if protected & LOWER_AREAS else (
            f"nothing that loads the {', '.join(sorted(protected))}" if protected else "keep sessions from aggravating it")
        pain = f", pain {issue['current_pain']}/10" if issue.get("current_pain") is not None else ""
        lines.append(_line("safety", f"{issue['label']}: {rule}", f"Recovery: {issue['title']}{pain}", f"injury:{issue['issue_id']}"))
    comeback = leg_comeback(conn, today)
    if comeback:
        healed = date.fromisoformat(comeback["healed_on"]).strftime("%-d %b")
        lines.append(_line("safety", f"{comeback['label']} healed {healed}: first lower-body lift at about 80% of last loads, 2+ reps in reserve",
                           "Recovery, healed", f"comeback:{comeback['issue_id']}"))
    for key, label, rule, read in (
        ("sick", "Sick", "no training beyond an easy walk", lambda: sick_dates(conn)),
        ("illness_return", "Back from illness", "easy sessions only", lambda: illness_return_dates(conn, today)),
        ("mountain_reentry", "Back from the mountains", "easy rides, first lower-body lift at old loads", lambda: mountain_reentry_dates(conn, today)),
    ):
        try:
            hit = sorted(dates & set(read()))
        except sqlite3.OperationalError:
            hit = []
        if hit:
            lines.append(_line("safety", f"{label} {_span(hit)}: {rule}", label, key))
    return lines, areas


def _span(days: list[str]) -> str:
    return _short(days[0]) if len(days) == 1 else f"{_short(days[0])}–{_short(days[-1])}"


def lift_slots(conn: sqlite3.Connection, protected_areas: set[str]) -> dict:
    """The week's lifts: the fixed slots, with a lower-body slot swapped while a leg area is protected."""
    from .settings import get_workout_template_settings_for_conn

    program = get_workout_template_settings_for_conn(conn)["programs"]["strength"]
    templates = {template["id"]: template for template in program["templates"]}
    slot_ids = program["rules"].get("weekly_slots") or []
    if not program.get("enabled", True) or not slot_ids:
        return {"mode": "rotation", "slots": [], "next": program["rotation_state"].get("next_template_label")}
    blocked = sorted(protected_areas & LOWER_AREAS)
    spare = [template for template in program["templates"] if template["id"] not in slot_ids and template["focus_area"] != "lower"]
    counts: dict[str, int] = {}
    slots = []
    for template_id in slot_ids:
        template = templates[template_id]
        name = SLOT_NAMES.get(template["focus_area"], "Lift")
        counts[name] = counts.get(name, 0) + 1
        slot = {"slot": name, "template_id": template_id, "label": template["display_name"], "focus_area": template["focus_area"],
                "swapped_from": None, "reason": None}
        if template["focus_area"] == "lower" and blocked and spare:
            swap = spare.pop(0)
            slot.update(template_id=swap["id"], label=swap["display_name"], focus_area=swap["focus_area"],
                        swapped_from=template["display_name"], reason=f"{', '.join(blocked).capitalize()} protected")
        slots.append(slot)
    # Number repeated slot names (Upper 1, Upper 2) only when they repeat.
    seen: dict[str, int] = {}
    for slot in slots:
        if counts[slot["slot"]] > 1:
            seen[slot["slot"]] = seen.get(slot["slot"], 0) + 1
            slot["slot"] = f"{slot['slot']} {seen[slot['slot']]}"
    return {"mode": "slots", "slots": slots, "next": None}


def _habits(conn: sqlite3.Connection, today: date) -> dict:
    from .plan_follow_through import build_plan_follow_through
    from .settings import get_athlete_profile_for_conn

    try:
        profile = get_athlete_profile_for_conn(conn)
    except sqlite3.OperationalError:
        profile = {}
    long_days = [item["value"] for item in profile.get("preferred_long_session_days") or [] if isinstance(item, dict)]
    try:
        follow = build_plan_follow_through(conn, today=today)
    except sqlite3.OperationalError:
        follow = {}
    return {"long_days": long_days, "reliable_weekdays": follow.get("reliable_weekdays") or [], "shaky_weekdays": follow.get("shaky_weekdays") or []}


def _days_label(days: list[str]) -> str:
    return "/".join(str(day)[:3].capitalize() for day in days)


def build_week_brief(conn: sqlite3.Connection, week_start: str, today: Optional[date] = None) -> dict:
    from .life_load import get_life_load_days
    from .winter_arc import MIX_LABELS, arc_week

    today = today or date.today()
    week_start = _monday(week_start)
    dates = _week_dates(week_start)
    lines: list[dict] = []

    safety, protected = _limits(conn, week_start, today)
    lines += safety

    goals = _goals(conn, week_start)
    lifts = lift_slots(conn, protected)
    for goal in goals:
        if goal["commitment"] != "anchor":
            continue
        text = goal["title"]
        if goal["metric_type"] == "strength_sessions" and lifts["mode"] == "slots":
            text += ": " + ", ".join(slot["label"] if not slot["swapped_from"] else f"{slot['label']} (for {slot['swapped_from']})" for slot in lifts["slots"])
        lines.append(_line("anchor", text, "Anchor goal", f"goal:{goal['id']}"))

    block = arc_week(conn, week_start)
    if block:
        mix = block["ride_mix"]
        rides = " + ".join(f"{mix[key]}× {MIX_LABELS[key]}" for key in ("z2", "sweet_spot", "vo2") if mix[key])
        no_quality = not (mix["sweet_spot"] or mix["vo2"])
        text = f"Rides about {block['ride_hours']:g} h: {rides}" + (", no sweet spot or VO2" if no_quality else "") + (
            " (lighter week)" if block["lighter"] else "")
        lines.append(_line("block", text, f"Winter arc: {block['label']} wk {block['week_number']}/{block['weeks_in_block']}", "arc"))
    else:
        no_quality = False

    for goal in goals:
        if goal["commitment"] == "anchor":
            continue
        text, source = goal["title"], "Goal"
        if block and no_quality and (goal["metric_type"] in QUALITY_METRICS or goal["metric_type"] == "benchmark_power"):
            text += f": waits for a quality block ({block['label']} has none)"
            source = "Goal, after the block"
        elif block and goal["metric_type"] in RIDE_VOLUME_METRICS:
            text += f": the block's {block['ride_hours']:g} h sets the week"
            source = "Goal, within the block"
        lines.append(_line("outcome", text, source, f"goal:{goal['id']}"))

    habits = _habits(conn, today)
    if habits["long_days"]:
        lines.append(_line("habit", f"Long ride {_days_label(habits['long_days'])}", "Athlete settings", "long_days"))
    if habits["reliable_weekdays"]:
        shaky = f", not {_days_label(habits['shaky_weekdays'])}" if habits["shaky_weekdays"] else ""
        lines.append(_line("habit", f"Key sessions {_days_label(habits['reliable_weekdays'])}{shaky}", "Plan follow-through", "key_days"))
    try:
        busy = get_life_load_days(conn, dates[0], dates[-1])
    except sqlite3.OperationalError:
        busy = {}
    for day, value in busy.items():
        lines.append(_line("habit", f"{_short(day)} busy ({', '.join(value['tags'])}): no hard session", "Life load", f"busy:{day}"))

    lines.sort(key=lambda line: PRIORITY.index(line["priority"]))
    return {
        "week_start": week_start,
        "headline": _headline(block, lifts, protected),
        "lines": lines,
        "block": block,
        "lifts": lifts,
        "protected_areas": sorted(protected),
        "priority": [PRIORITY_LABELS[key] for key in PRIORITY],
    }


def _headline(block: Optional[dict], lifts: dict, protected: set[str]) -> str:
    parts = []
    if block:
        quality = [label for key, label in (("sweet_spot", "SS"), ("vo2", "VO2")) if block["ride_mix"][key]]
        parts.append(f"{block['label']} wk {block['week_number']}/{block['weeks_in_block']}")
        parts.append(f"{block['ride_hours']:g} h rides")
        parts.append(" + ".join(f"{block['ride_mix'][key]}× {label}" for key, label in (("sweet_spot", "SS"), ("vo2", "VO2")) if block["ride_mix"][key]) if quality else "Z2 only")
    if lifts["mode"] == "slots" and lifts["slots"]:
        parts.append(f"{len(lifts['slots'])} lifts")
    if protected:
        parts.append(f"{', '.join(sorted(protected))} protected")
    return " · ".join(parts)


def week_brief_context(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    """This week's and next week's brief for the planner's recent context."""
    today = today or date.today()
    this_week = _monday(today.isoformat())
    next_week = (date.fromisoformat(this_week) + timedelta(weeks=1)).isoformat()
    compact = lambda brief: {key: brief[key] for key in ("week_start", "headline", "lifts", "protected_areas")} | {
        "rules": [f"[{line['priority_label']}] {line['text']} ({line['source']})" for line in brief["lines"]]}
    return {
        "instruction": "The ordered contract for each week. Follow the rules top to bottom: a higher line wins over a lower one. "
                       "When lifts.mode is slots, plan exactly those workouts by label; the rotation pointer does not apply.",
        "this_week": compact(build_week_brief(conn, this_week, today)),
        "next_week": compact(build_week_brief(conn, next_week, today)),
    }


def fit_week_to_lift_slots(
    conn: Optional[sqlite3.Connection], days: list[dict], week_start: str, today: Optional[date] = None,
) -> tuple[list[dict], list[dict]]:
    """Give the week's lift days the slot workouts in order. Done and past lifts use up their slot;
    bodyweight and travel days are left alone. A gym day the coach wrote out exercise by exercise
    gets its slot workout too: the slot already accounts for any protected area."""
    if conn is None:
        return days, []
    from .bodyweight_lifts import is_no_equipment_lift
    from .lift_ride_clash import locked_dates
    from .plans import normalize_plan_session_type
    from .recovery import coaching_summary

    protected = {area for issue in coaching_summary(conn)["issues"] for area in issue["protected_areas"]}
    lifts = lift_slots(conn, protected)
    if lifts["mode"] != "slots":
        return days, []
    days = [dict(day) for day in days]
    locked = locked_dates(conn, days, today)
    lift_days = sorted(
        (day for day in days if normalize_plan_session_type(day.get("session_type")) == "WeightTraining" and not is_no_equipment_lift(day)),
        key=lambda day: day["date"],
    )
    remaining = list(lifts["slots"])
    open_days = []
    for day in lift_days:
        if day["date"] in locked:
            done = next((slot for slot in remaining if slot["template_id"] == day.get("template_id")), remaining[0] if remaining else None)
            if done:
                remaining.remove(done)
        else:
            open_days.append(day)
    from .settings import get_workout_template_settings_for_conn

    templates = {item["id"]: item for item in get_workout_template_settings_for_conn(conn)["programs"]["strength"]["templates"]}
    changes = []
    for day, slot in zip(open_days, remaining):
        if day.get("template_id") == slot["template_id"] and day.get("title") == slot["label"] and not day.get("exercises"):
            continue
        template = templates[slot["template_id"]]
        index = days.index(day)
        reason = f"Weekly lifts: {slot['slot']}" + (f" ({slot['reason']}: {slot['label']} instead of {slot['swapped_from']})" if slot["swapped_from"] else "")
        days[index] = {
            **day,
            "template_id": template["id"],
            "template_label": template["display_name"],
            "template_summary": template.get("summary"),
            "workout_intent": template["workout_intent"],
            "title": template["display_name"],
            "details": template.get("summary") or day.get("details"),
            "exercises": [],
            "planning_rule_reason": reason,
        }
        changes.append({"date": day["date"], "kind": "lift_slot", "slot": slot["slot"], "from": day.get("title"), "to": template["display_name"]})
    return days, changes


def fit_week_to_safety(
    conn: Optional[sqlite3.Connection], days: list[dict], week_start: str, today: Optional[date] = None,
) -> tuple[list[dict], list[dict]]:
    """Safety outranks the block: while a knee, hip or heel is protected, and on sick, illness-return
    and mountain-return days, a quality ride is ridden as Z2 for the same time. Done and past days
    stay as they were."""
    if conn is None:
        return days, []
    from .illness_return import illness_return_dates
    from .lift_ride_clash import locked_dates
    from .mountain_reentry import mountain_reentry_dates
    from .recovery import coaching_summary
    from .sick_mode import sick_dates
    from .winter_arc import QUALITY_TYPES, _ride_minutes, ride_type

    blocked = sorted({area for issue in coaching_summary(conn)["issues"] for area in issue["protected_areas"]} & LOWER_AREAS)
    easy_days: dict[str, str] = {}
    for reason, read in (("sick", lambda: sick_dates(conn)), ("back from illness", lambda: illness_return_dates(conn, today)),
                         ("back from the mountains", lambda: mountain_reentry_dates(conn, today))):
        try:
            for day in read():
                easy_days.setdefault(day, reason)
        except sqlite3.OperationalError:
            pass
    if not blocked and not easy_days:
        return days, []
    days = [dict(day) for day in days]
    locked = locked_dates(conn, days, today)
    changes = []
    for index, day in enumerate(days):
        if day["date"] in locked or ride_type(day) not in QUALITY_TYPES or not (blocked or day["date"] in easy_days):
            continue
        why = f"{', '.join(blocked)} protected" if blocked else easy_days[day["date"]]
        minutes = _ride_minutes(day) or 60
        days[index] = {
            **day,
            "workout_intent": "easy",
            "cycling_workout_id": "endurance-60" if minutes == 60 else None,
            "title": f"Endurance {minutes}",
            "details": f"Easy Z2, flat and low resistance, smooth cadence{f'; stop if the {blocked[0]} hurts' if blocked else ''}. Replaces {day.get('title') or 'a quality ride'}.",
            "target_duration_min": minutes,
            "target_distance_km": None,
            "planning_rule_reason": f"Week brief: {why}, so no hard rides",
        }
        changes.append({"date": day["date"], "kind": "safety", "from": day.get("title"), "to": days[index]["title"]})
    return days, changes


QUALITY_WORDS = re.compile(r"quality|sweet[- ]?spot|tempo|threshold|vo2|interval", re.IGNORECASE)


def _without_quality(text: Optional[str], sentences: bool) -> Optional[str]:
    """Drop the clauses (or sentences) that promise a hard ride."""
    if not text or not QUALITY_WORDS.search(text):
        return text
    if sentences:
        # Sentence by sentence; inside one, only the clause that promises the ride goes.
        kept = []
        for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
            if not QUALITY_WORDS.search(sentence):
                kept.append(sentence)
                continue
            end = sentence[-1] if sentence[-1] in ".!?" else ""
            rest = _without_quality(sentence.rstrip(".!?"), sentences=False)
            if rest:
                kept.append(rest + end)
        return " ".join(kept) or None
    parts = re.split(r",\s*|;\s*|\s+and\s+", text.strip())
    kept = [part for part in parts if part and not QUALITY_WORDS.search(part)]
    if not kept:
        return None
    joined = ", ".join(kept)
    return joined[0].upper() + joined[1:]


def reconcile_summary(fields: dict, days: list[dict], changes: list[dict]) -> dict:
    """The coach's title, focus and overview after the save rules: once a hard ride was taken out
    and none is left, text that still promises one is dropped so the headline matches the week."""
    from .winter_arc import QUALITY_TYPES, ride_type

    removed = any(change["kind"] in ("too_hard", "safety") for change in changes)
    if not removed or any(ride_type(day) in QUALITY_TYPES for day in days):
        return {}
    update = {
        "title": _without_quality(fields.get("title"), sentences=False),
        "focus": _without_quality(fields.get("focus"), sentences=True),
        "overview": _without_quality(fields.get("overview"), sentences=True),
    }
    return {key: value for key, value in update.items() if value != fields.get(key)}
