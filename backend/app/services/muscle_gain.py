"""Monthly muscle-gain check: is Lift 3x turning into muscle?

Four signals over the last four weeks, each naming the sessions it came from:

* Hard sets per muscle group. A hard set is a completed working set (not a
  warm-up, at least one rep) of a mapped exercise. Each set counts once for
  the exercise's primary group(s) in ``MUSCLE_GROUP_RULES``; secondary muscles
  are not credited. The weekly average is compared with a moderate target
  range that fits lifting alongside endurance training.
* Share of lifts that progressed. Each lift's latest session in the window is
  compared with its most recent session before the window (or its first in the
  window), using the same like-for-like metric as strength progression.
* Protein adherence on lift days, from the daily protein tick.
* Body-weight trend, from a 7-day trailing average of weigh-ins, against a
  gentle gain rate. Fewer than ``MIN_WEIGH_INS`` weigh-ins means unavailable.

It ends with one deterministic suggestion that never proposes fewer lift
sessions per week.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta
from typing import Any, Optional

from .health_data import get_health_metric_history
from .protein import _logged_lift_dates
from .sick_mode import sick_dates
from .strength_progression import _metric, _normalize, _session_index, _summary, _value_for, _working_sets

WINDOW_DAYS = 28
WEEKS = WINDOW_DAYS / 7
LIFT_SESSIONS_PER_WEEK = 3
TARGET_SETS_MIN = 8
TARGET_SETS_MAX = 16
PROGRESSED_SHARE_GOOD = 0.5
PROTEIN_SHARE_GOOD = 0.7
WEIGHT_WINDOW_DAYS = 42
MIN_WEIGH_INS = 4
MIN_WEIGHT_SPAN_DAYS = 14
SMOOTHING_DAYS = 7
# Gentle lean gain, as % of body weight per week.
GAIN_PCT_MIN = 0.1
GAIN_PCT_MAX = 0.35

MUSCLE_GROUPS = [
    {"key": "legs", "label": "Legs", "targeted": True, "default_exercise": "Bulgarian split squat"},
    {"key": "back", "label": "Back", "targeted": True, "default_exercise": "dumbbell row"},
    {"key": "chest", "label": "Chest", "targeted": True, "default_exercise": "dumbbell bench press"},
    {"key": "shoulders", "label": "Shoulders", "targeted": True, "default_exercise": "dumbbell lateral raise"},
    {"key": "arms", "label": "Arms", "targeted": True, "default_exercise": "dumbbell curl"},
    {"key": "core", "label": "Core", "targeted": False, "default_exercise": "hanging leg raise"},
]
GROUP_BY_KEY = {group["key"]: group for group in MUSCLE_GROUPS}

# Exercise name (lower-case, words) -> primary muscle groups. Specific variants
# come before broad movement names (leg curl before curl, rear delt before row).
# Mirrors frontend/src/activity-detail/muscles.mjs at group level.
MUSCLE_GROUP_RULES: list[tuple[str, tuple[str, ...]]] = [
    (r"\b(?:calf|calves)\b", ("legs",)),
    (r"\b(?:leg|hamstring) curls?\b|\bnordic\b|\bleg extensions?\b|\b(?:hip|thigh) (?:ab|ad)ductions?\b|\badductor\b", ("legs",)),
    (r"\bhip thrusts?\b|\bglute (?:bridge|kickback)s?\b|\bdeadlifts?\b|\brdl\b|\bgood mornings?\b", ("legs",)),
    (r"\bsquats?\b|\blunges?\b|\bleg press\b|\bstep ups?\b|\bkettlebell swings?\b", ("legs",)),
    (r"\b(?:back|lumbar) extensions?\b|\bhyperextensions?\b", ("back",)),
    (r"\b(?:reverse|rear delt) (?:fly|flyes|flys|flies|raises?)\b|\bface pulls?\b", ("shoulders",)),
    (r"\bupright rows?\b", ("shoulders",)),
    (r"\bshrugs?\b|\bpull ?ups?\b|\bchin ?ups?\b|\bpull ?downs?\b|\bpullovers?\b|\brows?\b", ("back",)),
    (r"\bcurls?\b|\b(?:tricep|triceps)\b|\bskull ?crushers?\b|\bpush ?downs?\b|\bclose grip (?:bench )?press\b|\bbench dips?\b|\bfarmer", ("arms",)),
    (r"\b(?:shoulder|overhead|military|arnold|push) press\b|\b(?:lateral|front|scaption) raises?\b|\bpike push ups?\b", ("shoulders",)),
    (r"\bbench press\b|\bchest press\b|\bfloor press\b|\bpush ?ups?\b|\bdips?\b|\b(?:fly|flyes|flys|flies)\b|\bpec deck\b|\bcrossover\b", ("chest",)),
    (r"\bplank\b|\bcrunch(?:es)?\b|\bsit ?ups?\b|\b(?:leg|knee) raises?\b|\bdead bug\b|\bab (?:wheel|rollout)\b|\brussian twist\b|\bwood ?chop\b|\bpallof\b|\btoes to bar\b", ("core",)),
]
_COMPILED_RULES = [(re.compile(pattern), groups) for pattern, groups in MUSCLE_GROUP_RULES]


def muscle_groups_for(name: Optional[str]) -> tuple[str, ...]:
    words = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", re.sub(r"[-_–—]", " ", str(name or "").lower()))).strip()
    if re.search(r"\bstretch|\bwarm up\b|\bmobility\b", words):
        return ()
    for pattern, groups in _COMPILED_RULES:
        if pattern.search(words):
            return groups
    return ()


def _session_ref(session: dict) -> dict:
    matched = session.get("matched_activity") or {}
    return {
        "date": session["workout_date"][:10],
        "activity_id": matched.get("id"),
        "title": session.get("title") or matched.get("name") or "Strength session",
    }


def _hard_sets(window_sessions: list[dict]) -> tuple[list[dict], list[str]]:
    totals: dict[str, dict[str, Any]] = {
        group["key"]: {"sets": 0, "exercises": {}, "sessions": {}} for group in MUSCLE_GROUPS
    }
    unmapped: set[str] = set()
    for session in window_sessions:
        ref = _session_ref(session)
        for exercise in session.get("exercises", []):
            count = len(_working_sets(exercise))
            if not count:
                continue
            groups = muscle_groups_for(exercise["exercise_name"])
            if not groups:
                unmapped.add(exercise["exercise_name"])
                continue
            for key in groups:
                bucket = totals[key]
                bucket["sets"] += count
                bucket["exercises"][exercise["exercise_name"]] = bucket["exercises"].get(exercise["exercise_name"], 0) + count
                session_key = (ref["date"], str(ref["activity_id"]))
                entry = bucket["sessions"].setdefault(session_key, {**ref, "sets": 0})
                entry["sets"] += count

    result = []
    for group in MUSCLE_GROUPS:
        bucket = totals[group["key"]]
        per_week = round(bucket["sets"] / WEEKS, 1)
        if not group["targeted"]:
            status = "tracked"
        elif per_week < TARGET_SETS_MIN:
            status = "low"
        elif per_week > TARGET_SETS_MAX:
            status = "high"
        else:
            status = "in_range"
        result.append(
            {
                "key": group["key"],
                "label": group["label"],
                "targeted": group["targeted"],
                "total_sets": bucket["sets"],
                "sets_per_week": per_week,
                "status": status,
                "exercises": [
                    {"exercise_name": name, "sets": sets}
                    for name, sets in sorted(bucket["exercises"].items(), key=lambda item: (-item[1], item[0]))
                ],
                "sessions": sorted(bucket["sessions"].values(), key=lambda item: item["date"]),
            }
        )
    return result, sorted(unmapped)


def _compare(current_sets: list[dict], previous_sets: list[dict]) -> tuple[str, Optional[float], Optional[float], str]:
    current, previous = _summary(current_sets), _summary(previous_sets)
    metric, value = _metric(current)
    previous_metric, previous_value = _metric(previous)
    if previous_metric != metric:
        metric = "top_load" if current["weighted"] and previous["weighted"] else "reps"
        value, previous_value = _value_for(current, metric), _value_for(previous, metric)
    if value is None or previous_value is None:
        return "same", value, previous_value, metric
    if value > previous_value:
        return "up", value, previous_value, metric
    if value < previous_value:
        return "down", value, previous_value, metric
    more_reps = current["total_reps"] > previous["total_reps"] and current["top_load_kg"] == previous["top_load_kg"]
    return ("up" if more_reps else "same"), value, previous_value, metric


def _progression(all_sessions: list[dict], window_start: str, window_end: str) -> dict:
    performances: dict[str, list[tuple[dict, dict, list[dict]]]] = {}
    for session in all_sessions:
        day = session["workout_date"][:10]
        if day > window_end:
            continue
        for exercise in session.get("exercises", []):
            sets = _working_sets(exercise)
            if sets:
                performances.setdefault(_normalize(exercise["exercise_name"]), []).append((session, exercise, sets))

    lifts = []
    for history in performances.values():
        in_window = [item for item in history if item[0]["workout_date"][:10] >= window_start]
        if not in_window:
            continue
        before = [item for item in history if item[0]["workout_date"][:10] < window_start]
        latest = in_window[-1]
        baseline = before[-1] if before else (in_window[0] if len(in_window) > 1 else None)
        name = latest[1]["exercise_name"]
        if baseline is None:
            lifts.append({"exercise_name": name, "direction": "first", "latest": _session_ref(latest[0]), "baseline": None})
            continue
        direction, value, baseline_value, metric = _compare(latest[2], baseline[2])
        lifts.append(
            {
                "exercise_name": name,
                "direction": direction,
                "metric": metric,
                "value": value,
                "baseline_value": baseline_value,
                "latest": _session_ref(latest[0]),
                "baseline": _session_ref(baseline[0]),
            }
        )
    order = {"up": 0, "same": 1, "down": 2, "first": 3}
    lifts.sort(key=lambda item: (order[item["direction"]], item["exercise_name"]))
    compared = [item for item in lifts if item["direction"] != "first"]
    progressed = sum(1 for item in compared if item["direction"] == "up")
    return {
        "compared": len(compared),
        "progressed": progressed,
        "share": round(progressed / len(compared), 2) if compared else None,
        "lifts": lifts,
        "method": "Latest session in the window vs the most recent earlier session of the same lift (or its first session in the window). Estimated 1RM, top load or reps, like for like; more total reps at the same load counts as progress.",
    }


def _protein(conn: sqlite3.Connection, window_start: str, window_end: str) -> dict:
    lift_days = sorted(_logged_lift_dates(conn, window_start, window_end) - sick_dates(conn))
    try:
        ticks = {
            row["date"]: bool(row["protein_hit"])
            for row in conn.execute(
                "SELECT date, protein_hit FROM daily_nutrition WHERE date BETWEEN ? AND ?",
                (window_start, window_end),
            ).fetchall()
        }
    except sqlite3.OperationalError:
        ticks = {}
    activity_ids: dict[str, str] = {}
    for row in conn.execute(
        "SELECT id, date FROM activities WHERE type = 'WeightTraining' AND date BETWEEN ? AND ? ORDER BY date, id",
        (window_start, window_end),
    ).fetchall():
        activity_ids.setdefault(row["date"], row["id"])
    days = [{"date": day, "hit": ticks.get(day), "activity_id": activity_ids.get(day)} for day in lift_days]
    hits = sum(1 for day in days if day["hit"])
    answered = sum(1 for day in days if day["hit"] is not None)
    return {
        "lift_days": len(days),
        "answered": answered,
        "hits": hits,
        "share": round(hits / len(days), 2) if days and answered else None,
        "days": days,
    }


def _weigh_ins(conn: sqlite3.Connection, start: str, end: str) -> list[dict]:
    by_date: dict[str, dict] = {}
    try:
        for item in get_health_metric_history(conn, "weight", WEIGHT_WINDOW_DAYS + 30):
            if start <= item["date"] <= end and float(item["value"] or 0) > 0:
                by_date[item["date"]] = {"date": item["date"], "kg": float(item["value"]), "source": "health"}
    except sqlite3.OperationalError:
        pass
    # Manual weigh-ins win over Apple Health on the same day.
    for row in conn.execute(
        "SELECT date, value FROM metrics WHERE metric = 'weight' AND value > 0 AND date BETWEEN ? AND ? ORDER BY date, id",
        (start, end),
    ).fetchall():
        by_date[row["date"]] = {"date": row["date"], "kg": float(row["value"]), "source": "manual"}
    return [by_date[day] for day in sorted(by_date)]


def _weight(conn: sqlite3.Connection, today: date) -> dict:
    start = (today - timedelta(days=WEIGHT_WINDOW_DAYS - 1)).isoformat()
    weigh_ins = _weigh_ins(conn, start, today.isoformat())
    base = {
        "window_days": WEIGHT_WINDOW_DAYS,
        "min_weigh_ins": MIN_WEIGH_INS,
        "weigh_ins": weigh_ins,
        "gentle_gain_pct_per_week": [GAIN_PCT_MIN, GAIN_PCT_MAX],
    }
    span = (date.fromisoformat(weigh_ins[-1]["date"]) - date.fromisoformat(weigh_ins[0]["date"])).days if weigh_ins else 0
    if len(weigh_ins) < MIN_WEIGH_INS or span < MIN_WEIGHT_SPAN_DAYS:
        return {
            **base,
            "available": False,
            "status": "unavailable",
            "reason": f"Needs at least {MIN_WEIGH_INS} weigh-ins spread over {MIN_WEIGHT_SPAN_DAYS}+ days in the last {WEIGHT_WINDOW_DAYS // 7} weeks; found {len(weigh_ins)}.",
        }
    smoothed = []
    for item in weigh_ins:
        day = date.fromisoformat(item["date"])
        floor = (day - timedelta(days=SMOOTHING_DAYS - 1)).isoformat()
        values = [other["kg"] for other in weigh_ins if floor <= other["date"] <= item["date"]]
        smoothed.append({"date": item["date"], "kg": round(sum(values) / len(values), 2)})
    first, last = smoothed[0], smoothed[-1]
    days = (date.fromisoformat(last["date"]) - date.fromisoformat(first["date"])).days
    kg_per_week = (last["kg"] - first["kg"]) / days * 7
    pct_per_week = kg_per_week / first["kg"] * 100
    if pct_per_week > GAIN_PCT_MAX:
        status = "fast_gain"
    elif pct_per_week >= GAIN_PCT_MIN:
        status = "gentle_gain"
    elif pct_per_week > -GAIN_PCT_MIN:
        status = "flat"
    else:
        status = "losing"
    return {
        **base,
        "available": True,
        "status": status,
        "smoothed": smoothed,
        "start_kg": first["kg"],
        "end_kg": last["kg"],
        "kg_per_week": round(kg_per_week, 2),
        "pct_per_week": round(pct_per_week, 2),
        "gentle_gain_kg_per_week": [round(first["kg"] * GAIN_PCT_MIN / 100, 2), round(first["kg"] * GAIN_PCT_MAX / 100, 2)],
    }


def _fmt(value: float) -> str:
    return f"{value:g}"


def _suggestion(sessions_per_week: float, groups: list[dict], progression: dict, protein: dict, weight: dict) -> dict:
    if sessions_per_week < LIFT_SESSIONS_PER_WEEK - 0.25:
        return {
            "lever": "frequency",
            "headline": f"Get back to {LIFT_SESSIONS_PER_WEEK} lift sessions a week",
            "detail": f"You averaged {_fmt(round(sessions_per_week, 1))} sessions a week. Consistency is the biggest lever; a short 30-minute session still counts.",
        }
    low = sorted((group for group in groups if group["status"] == "low"), key=lambda group: group["sets_per_week"])
    if low:
        group = low[0]
        exercise = group["exercises"][0]["exercise_name"] if group["exercises"] else GROUP_BY_KEY[group["key"]]["default_exercise"]
        add = max(1, round(TARGET_SETS_MIN - group["sets_per_week"]))
        fewest, most = max(1, add // LIFT_SESSIONS_PER_WEEK), max(1, -(-add // LIFT_SESSIONS_PER_WEEK))
        per_session = f"{fewest}" if fewest == most else f"{fewest}–{most}"
        return {
            "lever": "volume",
            "group": group["key"],
            "headline": f"{group['label']} got {_fmt(group['sets_per_week'])} hard sets a week; add a set of {exercise}",
            "detail": f"The target is {TARGET_SETS_MIN}–{TARGET_SETS_MAX} a week. About {add} more a week closes the gap: {per_session} extra set{'' if per_session == '1' else 's'} of {exercise} in each lift session.",
        }
    if progression["share"] is not None and progression["share"] < PROGRESSED_SHARE_GOOD:
        stalled = next((lift for lift in progression["lifts"] if lift["direction"] in {"same", "down"}), None)
        name = stalled["exercise_name"] if stalled else "your main lift"
        return {
            "lever": "progression",
            "headline": f"Only {progression['progressed']} of {progression['compared']} lifts progressed; push {name}",
            "detail": f"Keep the load on {name} and add a rep per set until every set hits the top of its range, then add weight.",
        }
    if protein["lift_days"] and protein["answered"] == 0:
        return {
            "lever": "protein",
            "headline": "Tick protein on lift days",
            "detail": f"None of the {protein['lift_days']} lift days this month have a protein answer, so this check can't tell whether food is backing the lifting.",
        }
    if protein["share"] is not None and protein["share"] < PROTEIN_SHARE_GOOD:
        return {
            "lever": "protein",
            "headline": f"Protein hit on {protein['hits']} of {protein['lift_days']} lift days",
            "detail": "Plan one protein-rich meal or a shake after each lift so the target lands on training days.",
        }
    if weight["available"] and weight["status"] in {"flat", "losing"}:
        return {
            "lever": "weight",
            "headline": "Body weight isn't moving up; eat a little more",
            "detail": f"Trend is {_fmt(weight['kg_per_week'])} kg a week. A gentle gain is {_fmt(weight['gentle_gain_kg_per_week'][0])}–{_fmt(weight['gentle_gain_kg_per_week'][1])} kg a week; add a snack of around 200–300 kcal on lift days.",
        }
    if weight["available"] and weight["status"] == "fast_gain":
        return {
            "lever": "weight",
            "headline": "Weight is rising faster than a gentle gain",
            "detail": f"Trend is {_fmt(weight['kg_per_week'])} kg a week. Trim a snack on rest days; keep all {LIFT_SESSIONS_PER_WEEK} lift sessions as they are.",
        }
    return {
        "lever": "keep",
        "headline": "Keep going: Lift 3× is doing its job",
        "detail": "Same sessions, same sets. Add load when every set reaches its target reps.",
    }


def _verdict(sessions_per_week: float, session_count: int, groups: list[dict], progression: dict, protein: dict, weight: dict) -> dict:
    if session_count < 3:
        return {"status": "too_early", "label": "Too early to tell", "good": 0, "known": 0}
    signals = [
        sessions_per_week >= LIFT_SESSIONS_PER_WEEK - 0.25,
        all(group["status"] != "low" for group in groups if group["targeted"]),
    ]
    if progression["share"] is not None:
        signals.append(progression["share"] >= PROGRESSED_SHARE_GOOD)
    if protein["share"] is not None:
        signals.append(protein["share"] >= PROTEIN_SHARE_GOOD)
    if weight["available"]:
        signals.append(weight["status"] == "gentle_gain")
    good, known = sum(signals), len(signals)
    if good == known:
        status, label = "working", "Yes, it's working"
    elif good * 2 >= known:
        status, label = "partly", "Partly working"
    else:
        status, label = "not_yet", "Not yet"
    return {"status": status, "label": label, "good": good, "known": known}


def build_muscle_gain_check(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    today = today or datetime.now().date()
    window_start = (today - timedelta(days=WINDOW_DAYS - 1)).isoformat()
    window_end = today.isoformat()

    all_sessions = _session_index(conn)
    window_sessions = [item for item in all_sessions if window_start <= item["workout_date"][:10] <= window_end]
    # Lifts done while sick still count; sick days without a lift shrink the window instead of counting as missed.
    lift_days = sorted(_logged_lift_dates(conn, window_start, window_end))
    sick_days = sorted(day for day in sick_dates(conn) if window_start <= day <= window_end and day not in lift_days)
    available_weeks = max(WINDOW_DAYS - len(sick_days), 7) / 7
    sessions_per_week = round(len(lift_days) / available_weeks, 1)

    groups, unmapped = _hard_sets(window_sessions)
    progression = _progression(all_sessions, window_start, window_end)
    protein = _protein(conn, window_start, window_end)
    weight = _weight(conn, today)

    return {
        "window": {"start_date": window_start, "end_date": window_end, "weeks": int(WEEKS)},
        "verdict": _verdict(sessions_per_week, len(lift_days), groups, progression, protein, weight),
        "frequency": {
            "lift_days": len(lift_days),
            "sessions_per_week": sessions_per_week,
            "target_per_week": LIFT_SESSIONS_PER_WEEK,
            "sick_days_excluded": len(sick_days),
            "lift_dates": lift_days,
            "detailed_sessions": [_session_ref(item) for item in window_sessions],
        },
        "hard_sets": {
            "target_min": TARGET_SETS_MIN,
            "target_max": TARGET_SETS_MAX,
            "groups": groups,
            "unmapped_exercises": unmapped,
            "method": f"Completed working sets (no warm-ups) per primary muscle group, averaged over {int(WEEKS)} weeks. Secondary muscles are not credited. Target {TARGET_SETS_MIN}–{TARGET_SETS_MAX} hard sets a week for each main group.",
        },
        "progression": progression,
        "protein": protein,
        "weight": weight,
        "suggestion": _suggestion(sessions_per_week, groups, progression, protein, weight),
    }
