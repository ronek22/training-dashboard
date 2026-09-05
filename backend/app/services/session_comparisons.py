"""Transparent, outcome-independent matching of recorded session summaries."""
from collections import defaultdict
from datetime import date, timedelta
import math
import re

from .strength import _load_strength_rows


def positive(value):
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def pace_seconds(value):
    match = re.fullmatch(r"(\d+):([0-5]\d)", str(value or "").strip())
    return int(match[1]) * 60 + int(match[2]) if match else None


def snapshot(row, value, context):
    return {"activity_id": row["id"], "date": row["date"], "name": row["name"],
            "value": value, "context": context}


def endurance_comparison(rows, kind):
    running = kind == "running"
    sport_types = {"Run"} if running else {"Ride", "VirtualRide"}
    control = "avg_hr" if running else "avg_watts"
    candidates = [dict(r) for r in rows if r["type"] in sport_types]
    valid = []
    for row in candidates:
        row["value"] = pace_seconds(row.get("avg_pace")) if running else row.get("avg_hr")
        if all(positive(row.get(key)) for key in (control, "value", "duration_min")):
            valid.append(row)
    valid.sort(key=lambda r: (r["date"], r["id"]), reverse=True)
    result = {"kind": kind, "title": "Pace at similar heart rate" if running else "Heart rate at similar power",
              "unit": "sec/km" if running else "bpm", "excluded": len(candidates) - len(valid), "comparison": None,
              "rule": "Same activity type, compatible known workout intents; duration within 20%; " +
                      ("average HR within 5 bpm." if running else "average power within 5%."),
              "empty_reason": "No pair meets the matching rules in this window. Two sessions need duration, heart rate and " + ("pace." if running else "power.")}
    for recent in valid:
        matches = [old for old in valid if old["date"] < recent["date"] and old["type"] == recent["type"]
                   and not (old.get("workout_intent") and recent.get("workout_intent") and old["workout_intent"] != recent["workout_intent"])
                   and abs(old["duration_min"] / recent["duration_min"] - 1) <= .20
                   and abs(old[control] - recent[control]) <= (5 if running else recent[control] * .05)]
        if not matches:
            continue
        old = min(matches, key=lambda r: (abs(r[control] - recent[control]), abs(r["duration_min"] - recent["duration_min"]), -date.fromisoformat(r["date"][:10]).toordinal()))
        flags = ["Session averages only; intervals and sensor coverage are not verified.",
                 "Weather, wind, route and surface are not verified."]
        if not old.get("workout_intent") or not recent.get("workout_intent"):
            flags.append("Workout intent is missing; effort structure may differ.")
        elevations = [r.get("elevation_m") for r in (old, recent)]
        if any(v is None for v in elevations):
            flags.append("Elevation data is incomplete.")
        elif elevations[0] != elevations[1]:
            flags.append(f"Elevation gain differs: {elevations[0]} → {elevations[1]} m.")
        def context(r):
            return f'{r[control]:g} {"bpm" if running else "W"} · {r["duration_min"]:g} min · {r["type"]}'
        result["comparison"] = {"earlier": snapshot(old, old["value"], context(old)),
                                "recent": snapshot(recent, recent["value"], context(recent)),
                                "delta": round(recent["value"] - old["value"], 2), "flags": flags}
        break
    return result


def strength_comparisons(conn, start, end):
    sessions, exercises, sets = _load_strength_rows(conn, start)
    sessions = {r["id"]: dict(r) for r in sessions if r["workout_date"] <= end}
    exercises = {r["id"]: dict(r) for r in exercises if r["session_id"] in sessions}
    groups = defaultdict(lambda: defaultdict(list))
    excluded = 0
    for item in sets:
        exercise = exercises.get(item["exercise_id"])
        if not exercise or item["is_warmup"]:
            continue
        if not positive(item["weight_kg"]) or not positive(item["reps"]):
            excluded += 1
            continue
        # Exact exercise name and recorded weight avoid merging equipment/variants.
        groups[(exercise["exercise_name"], item["weight_kg"])][exercise["session_id"]].append(item["reps"])
    comparisons = []
    for (name, weight), by_session in groups.items():
        ordered = sorted(by_session, key=lambda sid: (sessions[sid]["workout_date"], sid), reverse=True)
        if len(ordered) < 2:
            continue
        recent_id = ordered[0]
        old_id = next((sid for sid in ordered[1:] if sessions[sid]["workout_date"] < sessions[recent_id]["workout_date"]), None)
        if old_id is None:
            continue
        def point(sid):
            s = sessions[sid]
            reps = by_session[sid]
            return {"activity_id": s["activity_id"], "date": s["workout_date"], "name": s["title"] or s["activity_name"],
                    "value": max(reps), "context": f'{weight:g} kg · reps by working set: {", ".join(str(r) for r in reps)}'}
        old, recent = point(old_id), point(recent_id)
        flags = ["Best recorded working set at this exact weight; warmups excluded.",
                 "Rest, technique, range of motion and effort are not verified; missing sets cannot be ruled out."]
        if len(by_session[old_id]) != len(by_session[recent_id]):
            flags.append(f'Working-set count differs: {len(by_session[old_id])} → {len(by_session[recent_id])}.')
        if sessions[old_id]["source"] != sessions[recent_id]["source"]:
            flags.append("Recording source differs between sessions.")
        comparisons.append({"kind": "strength", "title": f'{name} · {weight:g} kg', "unit": "reps", "excluded": 0,
                            "comparison": {"earlier": old, "recent": recent, "delta": recent["value"] - old["value"], "flags": flags}})
    comparisons.sort(key=lambda c: (c["comparison"]["recent"]["date"], c["title"]), reverse=True)
    return {"items": comparisons[:6], "excluded_sets": excluded,
            "note": "Same exercise name and exact recorded kg. Latest two distinct dates per lift/weight; showing up to six pairs. Only linked completed TrainLog or matched Fitbod sessions are included. Unlinked workouts and workouts without set detail are excluded."}


def get_session_comparisons(conn, days=180):
    end = date.today()
    start = end - timedelta(days=days - 1)
    rows = conn.execute("SELECT * FROM activities WHERE date >= ? AND date <= ? ORDER BY date DESC, id DESC", (start.isoformat(), end.isoformat())).fetchall()
    return {"window": {"days": days, "start": start.isoformat(), "end": end.isoformat()},
            "endurance": [endurance_comparison(rows, kind) for kind in ("running", "cycling")],
            "strength": strength_comparisons(conn, start.isoformat(), end.isoformat())}
