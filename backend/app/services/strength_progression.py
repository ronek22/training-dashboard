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


def _increment(name: str, load: float) -> float:
    normalized = _normalize(name)
    if "dumbbell" in normalized or "kettlebell" in normalized:
        return 1.0 if load < 10 else 2.0
    return 2.5


def _fmt(value: float) -> str:
    return f"{value:g}"


def _next_hint(name: str, sets: list[dict], previous: Optional[dict]) -> Optional[str]:
    if not sets:
        return None
    reps = [int(item["reps"]) for item in sets]
    weighted = [item for item in sets if (item.get("weight_kg") or 0) > 0]
    if not weighted:
        return f"Add a rep per set — aim for {max(reps) + 1} on every set."
    top = max(float(item["weight_kg"]) for item in weighted)
    top_sets = [item for item in weighted if float(item["weight_kg"]) == top]
    top_reps = [int(item["reps"]) for item in top_sets]
    targets = [item.get("target_reps") for item in top_sets if item.get("target_reps")]
    if previous and previous["metric_value"] is not None and previous["direction"] == "down":
        return f"Below last time — repeat {_fmt(top)} kg before adding load."
    if targets and min(top_reps) < max(targets):
        return f"Stay at {_fmt(top)} kg until every set reaches {max(targets)} reps."
    if min(top_reps) < max(top_reps):
        return f"Stay at {_fmt(top)} kg and match {max(top_reps)} reps on every set."
    if len(top_sets) < len(weighted):
        return f"Do every working set at {_fmt(top)} kg next time."
    return f"Every set at {_fmt(top)} kg × {top_reps[0]} — try {_fmt(top + _increment(name, top))} kg next time."


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
            last_metric, last_value = _metric(last_summary)
            # Compare like with like: fall back to top load / reps when metrics differ.
            if last_metric != metric:
                metric = "top_load" if summary["weighted"] and last_summary["weighted"] else "reps"
                value = summary["top_load_kg"] if metric == "top_load" else float(summary["best_reps"])
                last_value = last_summary["top_load_kg"] if metric == "top_load" else float(last_summary["best_reps"])
                entry["metric"], entry["metric_value"] = metric, value
            prior_values = [
                v for v in (
                    _value_for(_summary(item_sets), metric) for _, item_sets in prior
                ) if v is not None
            ]
            best_before = max(prior_values) if prior_values else None
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
