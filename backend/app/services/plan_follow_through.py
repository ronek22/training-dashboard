"""What happens to planned sessions, by kind and weekday, over recent planned weeks.

Built on the per-day plan comparison (matched / moved / replaced / skipped). It answers
two questions the single-week view can't: which kinds of session keep getting dropped
(and what replaces them), and whether a goal's sessions were ever planned at all.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Optional

from ..repositories.goals import ACTIVE_GOAL_CONDITION
from ..repositories.plans import list_weekly_plan_rows
from .plans import normalize_plan_session_type, serialize_weekly_plan

KINDS = {
    "quality_ride": "Quality rides",
    "long_ride": "Long rides",
    "easy_ride": "Easy rides",
    "recovery": "Recovery sessions",
    "lift_lower": "Lower-body lifts",
    "lift_upper": "Upper-body lifts",
    "lift_general": "Full-body lifts",
    "run": "Runs",
}
QUALITY_INTENTS = {"tempo", "interval", "race_specific"}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

OUTCOMES = {
    "linked": "done",
    "matched": "done",
    "moved": "done",
    "partially_matched": "changed",
    "replaced": "replaced",
    "rest_day_changed": "replaced",
    "skipped": "skipped",
}
REPLACEMENT_SPORTS = {
    "Ride": "ride",
    "VirtualRide": "ride",
    "WeightTraining": "lift",
    "Run": "run",
    "Walk": "walk",
    "Hike": "walk",
}
MIN_SAMPLES = 3
RELIABLE_PCT = 80
SHAKY_PCT = 50


def classify_planned_day(day: dict) -> Optional[str]:
    session_type = normalize_plan_session_type(day.get("session_type"))
    intent = day.get("workout_intent")
    if session_type == "Ride":
        if day.get("cycling_workout_id") or intent in QUALITY_INTENTS:
            return "quality_ride"
        if intent == "long":
            return "long_ride"
        if intent == "recovery":
            return "recovery"
        return "easy_ride"
    if session_type == "Recovery":
        return "recovery"
    if session_type == "WeightTraining":
        if intent == "strength_lower":
            return "lift_lower"
        if intent == "strength_upper":
            return "lift_upper"
        return "lift_general"
    if session_type == "Run":
        return "run"
    return None


def _replacement_sport(activities: list[dict]) -> str:
    if not activities:
        return "other"
    longest = max(activities, key=lambda item: item.get("duration_min") or 0)
    return REPLACEMENT_SPORTS.get(longest.get("type"), "other")


def _pct(part: int, whole: int) -> Optional[int]:
    return round(part / whole * 100) if whole else None


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def _times(count: int) -> str:
    return "once" if count == 1 else "twice" if count == 2 else f"{count} times"


def _weekly_quality_ride_target(goals: list[dict]) -> Optional[float]:
    for goal in goals:
        if (
            goal.get("metric_type") == "quality_sessions"
            and goal.get("period_type") == "week"
            and (goal.get("activity_type") or "Ride") in {"Ride", "VirtualRide"}
        ):
            return float(goal.get("target_value") or 0) or None
    return None


def summarize_follow_through(plans: list[dict], goals: Optional[list[dict]] = None) -> dict[str, Any]:
    """plans: serialized weekly plans (oldest first) whose days carry a `comparison`."""
    kinds: dict[str, dict] = {}
    weekdays = [{"weekday": name, "planned": 0, "done": 0} for name in WEEKDAYS]
    quality_weeks: set[str] = set()

    for plan in plans:
        for day in plan.get("days", []):
            kind = classify_planned_day(day)
            if not kind:
                continue
            if kind == "quality_ride":
                quality_weeks.add(plan["week_start"])
            outcome = OUTCOMES.get((day.get("comparison") or {}).get("status"))
            if not outcome:
                continue
            entry = kinds.setdefault(kind, {
                "kind": kind, "label": KINDS[kind], "planned": 0,
                "done": 0, "changed": 0, "replaced": 0, "skipped": 0, "replaced_by": {},
            })
            entry["planned"] += 1
            entry[outcome] += 1
            if outcome == "replaced":
                sport = _replacement_sport(day["comparison"].get("completed_activities") or [])
                entry["replaced_by"][sport] = entry["replaced_by"].get(sport, 0) + 1
            try:
                weekday = weekdays[datetime.strptime(day["date"], "%Y-%m-%d").weekday()]
            except (KeyError, TypeError, ValueError):
                continue
            weekday["planned"] += 1
            weekday["done"] += outcome == "done"

    kind_rows = []
    for kind in KINDS:
        entry = kinds.get(kind)
        if not entry:
            continue
        entry["done_pct"] = _pct(entry["done"], entry["planned"])
        entry["replaced_by"] = [
            {"sport": sport, "count": count}
            for sport, count in sorted(entry["replaced_by"].items(), key=lambda item: -item[1])
        ]
        kind_rows.append(entry)
    for weekday in weekdays:
        weekday["done_pct"] = _pct(weekday["done"], weekday["planned"])

    weeks = len(plans)
    quality_target = _weekly_quality_ride_target(goals or [])
    quality = {
        "weeks_planned": len(quality_weeks),
        "weeks": weeks,
        "weekly_target": quality_target,
    }
    sampled = [day for day in weekdays if day["planned"] >= MIN_SAMPLES]
    reliable = [day for day in sampled if day["done_pct"] >= RELIABLE_PCT]
    shaky = [day for day in sampled if day["done_pct"] <= SHAKY_PCT]

    return {
        "weeks": weeks,
        "from_week": plans[0]["week_start"] if plans else None,
        "to_week": plans[-1]["week_start"] if plans else None,
        "kinds": kind_rows,
        "weekdays": weekdays,
        "reliable_weekdays": [day["weekday"] for day in reliable],
        "shaky_weekdays": [day["weekday"] for day in shaky],
        "quality_rides": quality,
        "findings": _findings(kind_rows, reliable, shaky, quality),
    }


def _findings(kinds: list[dict], reliable: list[dict], shaky: list[dict], quality: dict) -> list[dict]:
    findings = []
    target, weeks = quality["weekly_target"], quality["weeks"]
    under_planned = bool(target and weeks >= MIN_SAMPLES and quality["weeks_planned"] < weeks / 2)
    if under_planned:
        findings.append({
            "key": "quality_not_planned",
            "tone": "warn",
            "text": (
                f"Quality rides were planned in only {quality['weeks_planned']} of {weeks} weeks. "
                f"Your goal asks for {target:g} a week, so the plan is the gap, not skipping."
            ),
        })

    dropped = [
        kind for kind in kinds
        if kind["planned"] >= MIN_SAMPLES and kind["replaced"] + kind["skipped"] >= 2 and kind["done_pct"] < 70
    ]
    dropped.sort(key=lambda kind: (kind["done_pct"], -kind["planned"]))
    for kind in dropped[:2]:
        text = f"{kind['label']} happened as planned {kind['done']} of {kind['planned']} times."
        if kind["replaced_by"]:
            top = kind["replaced_by"][0]
            text += f" Replaced by a {top['sport']} {_times(top['count'])}"
            text += f", skipped {_times(kind['skipped'])}." if kind["skipped"] else "."
        elif kind["skipped"]:
            text += f" Skipped {_times(kind['skipped'])}."
        findings.append({"key": f"dropped_{kind['kind']}", "tone": "warn", "text": text})

    if reliable:
        low, high = min(day["done_pct"] for day in reliable), max(day["done_pct"] for day in reliable)
        share = f"{high}%" if low == high else f"{low}–{high}%"
        names = _join([day["weekday"] for day in reliable])
        text = f"{names} {'is your most reliable day' if len(reliable) == 1 else 'are your most reliable days'} ({share} done)."
        if under_planned:
            text += " Put the quality ride there." if len(reliable) == 1 else " Put the quality ride on one of them."
        findings.append({"key": "reliable_weekdays", "tone": "good", "text": text})
    if shaky:
        done, planned = sum(day["done"] for day in shaky), sum(day["planned"] for day in shaky)
        findings.append({
            "key": "shaky_weekdays",
            "tone": "warn",
            "text": f"Plans for {_join([day['weekday'] for day in shaky])} held only {done} of {planned} times. Keep key sessions off them.",
        })

    if not findings:
        steady = [kind for kind in kinds if kind["planned"] >= 4 and kind["done_pct"] >= 85]
        if steady:
            kind = max(steady, key=lambda item: item["planned"])
            findings.append({
                "key": f"steady_{kind['kind']}",
                "tone": "good",
                "text": f"{kind['label']} happen: {kind['done']} of {kind['planned']} done as planned.",
            })
    return findings[:5]


def _active_goals(conn: sqlite3.Connection, today: date) -> list[dict]:
    try:
        rows = conn.execute(
            f"SELECT metric_type, period_type, activity_type, target_value FROM goals WHERE {ACTIVE_GOAL_CONDITION}",
            (today.isoformat(),),
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(row) for row in rows]


def build_plan_follow_through(conn: sqlite3.Connection, weeks: int = 12, today: Optional[date] = None) -> dict[str, Any]:
    weeks = max(2, min(weeks, 26))
    today = today or date.today()
    this_monday = (today - timedelta(days=today.weekday())).isoformat()
    rows = [row for row in list_weekly_plan_rows(conn, weeks + 4) if row["week_start"] <= this_monday][:weeks]
    plans = [serialize_weekly_plan(row, conn) for row in reversed(rows)]
    return summarize_follow_through(plans, _active_goals(conn, today))


def plan_follow_through_coaching_context(conn: sqlite3.Connection) -> Optional[dict]:
    """Small slice for the coach and planner: findings plus per-kind counts."""
    try:
        summary = build_plan_follow_through(conn)
    except sqlite3.OperationalError:
        return None
    if not summary["kinds"]:
        return None
    return {
        "weeks": summary["weeks"],
        "findings": [item["text"] for item in summary["findings"]],
        "reliable_weekdays": summary["reliable_weekdays"],
        "shaky_weekdays": summary["shaky_weekdays"],
        "quality_rides": summary["quality_rides"],
        "kinds": [
            {key: kind[key] for key in ("label", "planned", "done", "changed", "replaced", "skipped", "replaced_by")}
            for kind in summary["kinds"]
        ],
    }
