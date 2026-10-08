"""Per-exercise progression for a single strength session.

For each lift in the session linked to an activity, compare against the most
recent earlier session containing the same exercise, flag personal bests, and
suggest a simple double-progression next step.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any, Optional

from .personal_records import E1RM_MAX_REPS, epley_1rm
from .strength import _filtered_sessions


def _normalize(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def _working_sets(exercise: dict) -> list[dict]:
    return [item for item in exercise.get("sets", []) if not item.get("is_warmup") and (item.get("reps") or 0) > 0]


def _summary(sets: list[dict]) -> dict[str, Any]:
    weighted = [item for item in sets if (item.get("weight_kg") or 0) > 0]
    scored = [item for item in weighted if item["reps"] <= E1RM_MAX_REPS]
    e1rm = round(max(epley_1rm(item["weight_kg"], item["reps"]) for item in scored), 1) if scored else None
    top_load = max((float(item["weight_kg"]) for item in weighted), default=None)
    return {
        "sets": [{"reps": item["reps"], "weight_kg": item.get("weight_kg")} for item in sets],
        "e1rm": e1rm,
        "top_load_kg": top_load,
        "best_reps": max((int(item["reps"]) for item in sets), default=None),
        "total_reps": sum(int(item["reps"]) for item in sets),
        "volume_kg": round(sum(int(item["reps"]) * float(item.get("weight_kg") or 0) for item in sets), 1),
        "weighted": bool(weighted),
    }


def _metric(summary: dict) -> tuple[str, Optional[float]]:
    if summary["e1rm"] is not None:
        return "e1rm", summary["e1rm"]
    if summary["weighted"]:
        return "top_load", summary["top_load_kg"]
    return "reps", float(summary["best_reps"]) if summary["best_reps"] is not None else None


# Names that imply dumbbells even when the word itself is missing.
_DUMBBELL_HINTS = ("dumbbell", "hammercurl", "concentrationcurl", "lateralraise", "reardeltraise", "gobletsquat")
# Sets lighter than this share of the top load count as ramp-up sets, not working sets.
RAMP_UP_SHARE = 0.6


def _is_dumbbell(name: str) -> bool:
    normalized = _normalize(name)
    return any(hint in normalized for hint in _DUMBBELL_HINTS)


def _increment(name: str, load: float) -> float:
    if _is_dumbbell(name) or "kettlebell" in _normalize(name):
        return 1.0 if load < 10 else 2.0
    return 2.5


def _fmt(value: float) -> str:
    return f"{value:g}"


# Past this many reps on a capped dumbbell, keep the load and slow the lowering instead.
CAPPED_REP_CEILING = 15


def max_load_for(name: str, max_dumbbell_kg: Optional[float]) -> Optional[float]:
    """Heaviest load the athlete can use for this lift, when the equipment caps it."""
    if max_dumbbell_kg and _is_dumbbell(name):
        return float(max_dumbbell_kg)
    return None


def next_step(
    name: str,
    sets: list[dict],
    previous: Optional[dict],
    max_load: Optional[float] = None,
) -> Optional[dict[str, Any]]:
    """Double-progression step after ``sets``: the next target load/reps plus a one-line hint."""
    if not sets:
        return None
    reps = [int(item["reps"]) for item in sets]
    weighted = [item for item in sets if (item.get("weight_kg") or 0) > 0]
    if not weighted:
        return {"weight_kg": None, "reps": max(reps) + 1, "hint": f"Add a rep per set — aim for {max(reps) + 1} on every set."}
    top = max(float(item["weight_kg"]) for item in weighted)
    weighted = [item for item in weighted if float(item["weight_kg"]) >= top * RAMP_UP_SHARE]
    top_sets = [item for item in weighted if float(item["weight_kg"]) == top]
    top_reps = [int(item["reps"]) for item in top_sets]
    targets = [item.get("target_reps") for item in top_sets if item.get("target_reps")]
    if previous and previous["metric_value"] is not None and previous["direction"] == "down":
        return {"weight_kg": top, "reps": max(targets) if targets else max(top_reps), "hint": f"Below last time — repeat {_fmt(top)} kg before adding load."}
    if targets and min(top_reps) < max(targets):
        return {"weight_kg": top, "reps": max(targets), "hint": f"Stay at {_fmt(top)} kg until every set reaches {max(targets)} reps."}
    if min(top_reps) < max(top_reps):
        return {"weight_kg": top, "reps": max(top_reps), "hint": f"Stay at {_fmt(top)} kg and match {max(top_reps)} reps on every set."}
    if len(top_sets) < len(weighted):
        return {"weight_kg": top, "reps": max(top_reps), "hint": f"Do every working set at {_fmt(top)} kg next time."}
    heavier = top + _increment(name, top)
    if max_load is not None and heavier > max_load:
        if top_reps[0] < CAPPED_REP_CEILING:
            return {
                "weight_kg": top,
                "reps": top_reps[0] + 1,
                "hint": f"{_fmt(top)} kg is your heaviest dumbbell — aim for {top_reps[0] + 1} reps on every set.",
            }
        return {
            "weight_kg": top,
            "reps": top_reps[0],
            "hint": f"{_fmt(top)} kg × {top_reps[0]} is maxed out — lower each rep over 3 seconds to keep it hard.",
        }
    return {
        "weight_kg": heavier,
        "reps": top_reps[0],
        "hint": f"Every set at {_fmt(top)} kg × {top_reps[0]} — try {_fmt(heavier)} kg next time.",
    }


def _next_hint(name: str, sets: list[dict], previous: Optional[dict], max_load: Optional[float] = None) -> Optional[str]:
    step = next_step(name, sets, previous, max_load)
    return step["hint"] if step else None


def _compare(summary: dict, last_summary: dict) -> dict[str, Any]:
    """Compare a lift with its previous session like with like."""
    metric, value = _metric(summary)
    last_metric, last_value = _metric(last_summary)
    # Compare like with like: fall back to top load / reps when metrics differ.
    if last_metric != metric:
        metric = "top_load" if summary["weighted"] and last_summary["weighted"] else "reps"
        value = summary["top_load_kg"] if metric == "top_load" else float(summary["best_reps"])
        last_value = last_summary["top_load_kg"] if metric == "top_load" else float(last_summary["best_reps"])
    delta = round(value - last_value, 1) if value is not None and last_value is not None else None
    if delta is None:
        direction = "same"
    elif delta > 0:
        direction = "up"
    elif delta < 0:
        direction = "down"
    else:
        # Same headline number: more total reps still counts as progress.
        direction = "up" if summary["total_reps"] > last_summary["total_reps"] and summary["top_load_kg"] == last_summary["top_load_kg"] else "same"
    return {"metric": metric, "value": value, "last_value": last_value, "delta": delta, "direction": direction}


def _max_dumbbell_kg(conn: sqlite3.Connection) -> Optional[float]:
    from .settings import get_athlete_profile_for_conn

    if conn is None:
        return None
    try:
        return get_athlete_profile_for_conn(conn).get("max_dumbbell_kg")
    except sqlite3.OperationalError:
        return None


def _session_index(conn: sqlite3.Connection) -> list[dict]:
    try:
        _, sessions = _filtered_sessions(conn, window_start=date(2000, 1, 1), body_part="all")
    except sqlite3.OperationalError:
        return []
    return sessions


def build_strength_progression(
    conn: sqlite3.Connection,
    activity_id: str,
    target_reps: Optional[dict[str, list[Optional[int]]]] = None,
) -> Optional[dict[str, Any]]:
    """Return progression per exercise name for the session linked to ``activity_id``.

    ``target_reps`` optionally maps normalized exercise names to per-working-set
    rep targets (first-party sessions record them) so hints can respect the plan.
    """
    sessions = _session_index(conn)
    position = next(
        (index for index, session in enumerate(sessions) if str((session.get("matched_activity") or {}).get("id")) == str(activity_id)),
        None,
    )
    if position is None:
        return None
    current = sessions[position]
    earlier = sessions[:position]

    history: dict[str, list[tuple[dict, list[dict]]]] = {}
    for session in earlier:
        for exercise in session.get("exercises", []):
            sets = _working_sets(exercise)
            if sets:
                history.setdefault(_normalize(exercise["exercise_name"]), []).append((session, sets))

    max_dumbbell_kg = _max_dumbbell_kg(conn)
    exercises: dict[str, Any] = {}
    for exercise in current.get("exercises", []):
        sets = _working_sets(exercise)
        if not sets:
            continue
        key = _normalize(exercise["exercise_name"])
        targets = (target_reps or {}).get(key) or []
        hinted_sets = [{**item, "target_reps": targets[index] if index < len(targets) else None} for index, item in enumerate(sets)]
        summary = _summary(sets)
        metric, value = _metric(summary)
        prior = history.get(key, [])
        entry: dict[str, Any] = {
            "exercise_name": exercise["exercise_name"],
            "metric": metric,
            "metric_value": value,
            "current": summary,
            "previous": None,
            "delta": None,
            "direction": "first",
            "is_pr": False,
            "best_before": None,
            "session_count": len(prior) + 1,
        }
        if prior:
            last_session, last_sets = prior[-1]
            last_summary = _summary(last_sets)
            compared = _compare(summary, last_summary)
            metric, value, last_value = compared["metric"], compared["value"], compared["last_value"]
            delta, direction = compared["delta"], compared["direction"]
            entry["metric"], entry["metric_value"] = metric, value
            prior_values = [
                v for v in (
                    _value_for(_summary(item_sets), metric) for _, item_sets in prior
                ) if v is not None
            ]
            best_before = max(prior_values) if prior_values else None
            matched = (last_session.get("matched_activity") or {})
            entry.update(
                {
                    "previous": {
                        **last_summary,
                        "date": last_session["workout_date"][:10],
                        "activity_id": matched.get("id"),
                        "title": last_session.get("title") or matched.get("name"),
                        "metric_value": last_value,
                    },
                    "delta": delta,
                    "direction": direction,
                    "best_before": best_before,
                    "is_pr": value is not None and best_before is not None and value > best_before,
                }
            )
        entry["next_hint"] = _next_hint(
            exercise["exercise_name"],
            hinted_sets,
            {"metric_value": entry["metric_value"], "direction": entry["direction"]} if entry["previous"] else None,
            max_load_for(exercise["exercise_name"], max_dumbbell_kg),
        )
        exercises[key] = entry

    return {
        "exercises": exercises,
        "pr_count": sum(1 for item in exercises.values() if item["is_pr"]),
        "improved_count": sum(1 for item in exercises.values() if item["direction"] == "up"),
        "compared_count": sum(1 for item in exercises.values() if item["previous"]),
        "method": f"Compared with the most recent earlier session of the same lift. Estimated 1RM uses Epley on working sets up to {E1RM_MAX_REPS} reps.",
    }


def _value_for(summary: dict, metric: str) -> Optional[float]:
    if metric == "e1rm":
        return summary["e1rm"]
    if metric == "top_load":
        return summary["top_load_kg"]
    return float(summary["best_reps"]) if summary["best_reps"] is not None else None


def latest_next_steps(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    """Per lift, the latest logged working sets and how they compared, for planning the next session."""
    latest: dict[str, dict[str, Any]] = {}
    for session in _session_index(conn):
        for exercise in session.get("exercises", []):
            sets = _working_sets(exercise)
            if not sets:
                continue
            key = _normalize(exercise["exercise_name"])
            summary = _summary(sets)
            previous = latest.get(key)
            compared = _compare(summary, previous["summary"]) if previous else None
            latest[key] = {
                "exercise_name": exercise["exercise_name"],
                "date": session["workout_date"][:10],
                "sets": sets,
                "summary": summary,
                "previous": {"metric_value": compared["value"], "direction": compared["direction"]} if compared else None,
            }
    return latest


def plan_next_step(
    lift: Optional[dict[str, Any]],
    name: str,
    target_reps: Optional[int],
    max_dumbbell_kg: Optional[float],
) -> Optional[dict[str, Any]]:
    """Next target for a planned lift, respecting the saved rep target and equipment limits."""
    if not lift:
        return None
    sets = [{**item, "target_reps": target_reps} for item in lift["sets"]]
    step = next_step(name, sets, lift["previous"], max_load_for(name, max_dumbbell_kg))
    if not step:
        return None
    return {
        "target_weight_kg": step["weight_kg"],
        "target_reps": step["reps"],
        "hint": step["hint"],
        "based_on_date": lift["date"],
    }
