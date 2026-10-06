"""Deterministic "session read" for the activity detail page.

Every signal compares this session with the athlete's own earlier sessions
(never later ones, so the read does not change after the fact) or with the
state they went in with. A verdict, one "next time" instruction and one thing
to watch are derived from those signals by plain rules; the LLM is only used
when the athlete asks a question about the session.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from statistics import median
from typing import Any, Optional

from .aerobic_decoupling import COMPARABLE_POWER_PCT, COUPLED_DECOUPLING_PCT, build_aerobic_decoupling
from .checkins import get_daily_checkin
from .goals import goal_period_window, goal_value_for_window
from .life_load import get_life_load_days
from .return_to_run import build_return_to_run
from .strength_progression import _metric, _normalize, _session_index, _summary, _value_for, _working_sets

RIDE_TYPES = {"Ride", "VirtualRide"}
EASY_INTENTS = {None, "easy", "recovery", "long"}
HARD_INTENTS = {"tempo", "interval", "race_specific"}
STEADY_DRIFT_PCT = 3.5
HOT_EASY_ABOVE_Z2_PCT = 15
OFF_EASY_ABOVE_Z2_PCT = 30
SAME_HR_BPM = 5
SAME_DURATION_SHARE = 0.30
PACE_CHANGE_S = 5
STALL_SESSIONS = 4
MAIN_LIFT_WORDS = ("squat", "deadlift", "benchpress", "row", "shoulderpress", "overheadpress", "pullup", "chinup", "hipthrust", "dip")
ACCESSORY_WORDS = ("upright", "goblet", "pikepush")
SERIES_LENGTH = 6
LOAD_LOOKBACK_DAYS = 42
QUALITY_LABELS = {
    "matched": "Matched",
    "partial": "Partly matched",
    "drifted": "Changed",
    "completed_without_evidence": "Done",
    "insufficient_evidence": "Done",
}


def _short_date(value: str) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).strftime("%-d %b")
    except ValueError:
        return str(value)[:10]


def _signal(key: str, label: str, value: str, detail: Optional[str] = None, tone: str = "neutral",
            series: Optional[list[float]] = None, better: Optional[str] = None) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "detail": detail,
        "tone": tone,
        "series": [round(float(point), 2) for point in series] if series and len(series) >= 2 else None,
        "better": better,
    }


def _verdict(tone: str, headline: str) -> dict[str, str]:
    badge = {"good": "On intent", "warn": "Mixed", "bad": "Off intent", "neutral": "Logged"}[tone]
    return {"tone": tone, "badge": badge, "headline": headline}


def _win(score: int, headline: str, detail: str) -> dict[str, Any]:
    """Something that went well, for the encouraging win card; higher scores are stronger wins."""
    return {"score": score, "headline": headline, "detail": detail}


def _round_to(value: float, step: int = 5) -> int:
    return int(round(value / step) * step)


def _pace_label(seconds: float) -> str:
    seconds = int(round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}/km"


def _above_zone2_pct(detail_payload: dict) -> Optional[int]:
    zones = detail_payload.get("heart_rate_zones") or {}
    if not zones.get("available"):
        return None
    return sum(int(zone.get("pct") or 0) for zone in zones.get("zones") or [] if zone.get("key") in {"zone3", "zone4", "zone5"})


# ---------------------------------------------------------------------------
# Shared signals
# ---------------------------------------------------------------------------


def _plan_signal(detail_payload: dict) -> Optional[dict]:
    quality = detail_payload.get("execution_quality")
    planned = detail_payload.get("linked_planned_session")
    if not quality or not planned:
        return None
    label = QUALITY_LABELS.get(quality.get("status"), "Compared")
    tone = {"matched": "good", "partial": "warn", "drifted": "warn"}.get(quality.get("status"), "neutral")
    planned_label = planned.get("title") or planned.get("workout_intent_label") or "Planned session"
    ratio = (quality.get("evidence") or {}).get("duration_ratio")
    detail = f"{planned_label} · {round(ratio * 100)}% of planned time" if ratio else planned_label
    return _signal("plan", "Planned vs done", label, detail, tone)


def _going_in_signal(conn: sqlite3.Connection, day: str) -> Optional[dict]:
    checkin = get_daily_checkin(conn, day) if _table_exists(conn, "daily_checkins") else None
    tagged = get_life_load_days(conn, day, day).get(day)
    if not checkin and not tagged:
        return None
    parts = []
    tone = "neutral"
    value = "No check-in"
    if checkin:
        energy, stress, sleep = checkin.get("energy"), checkin.get("stress"), checkin.get("sleep_quality")
        value = f"Energy {energy}/5" if energy is not None else "Checked in"
        if stress is not None:
            parts.append(f"stress {stress}/5")
        if sleep is not None:
            parts.append(f"sleep {sleep}/5")
        if (energy is not None and energy <= 2) or (stress is not None and stress >= 4) or (sleep is not None and sleep <= 2):
            tone = "warn"
    if tagged:
        parts.append(", ".join(label.lower() for label in tagged["labels"]))
        tone = "warn"
    return _signal("going_in", "Going in", value, " · ".join(parts) or None, tone)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone())


def _load_signal(conn: sqlite3.Connection, activity: dict, detail_payload: dict, types: set[str]) -> Optional[dict]:
    """HR load against the median of the same sport over the previous six weeks."""
    load = (detail_payload.get("source_stream_summary") or {}).get("hr_trimp")
    if not load:
        return None
    day = str(activity["date"])[:10]
    start = (date.fromisoformat(day) - timedelta(days=LOAD_LOOKBACK_DAYS)).isoformat()
    placeholders = ",".join("?" for _ in types)
    rows = conn.execute(
        f"""
        SELECT s.hr_trimp FROM activities AS a
        JOIN activity_stream_summaries AS s ON s.activity_id = a.id
        WHERE a.type IN ({placeholders}) AND a.id != ? AND substr(a.date, 1, 10) >= ? AND substr(a.date, 1, 10) < ?
          AND s.hr_trimp > 0
        """,
        (*types, activity["id"], start, day),
    ).fetchall()
    if len(rows) < 3:
        return None
    typical = median(float(row["hr_trimp"]) for row in rows)
    ratio = float(load) / typical if typical else None
    if not ratio:
        return None
    tone = "warn" if ratio >= 1.5 else "neutral"
    detail = "about your usual" if 0.8 <= ratio <= 1.2 else f"{ratio:.1f}× your usual"
    return _signal("load", "Heart-rate load", f"{round(float(load))}", detail, tone)


def _watch(detail_payload: dict, conn: sqlite3.Connection, extra: list[tuple[str, str]]) -> Optional[dict]:
    """The single most important thing to keep an eye on, or ``None``."""
    feedback = detail_payload.get("feedback") or {}
    activity = detail_payload["activity"]
    pain, rpe, soreness = feedback.get("pain_level"), feedback.get("rpe"), feedback.get("muscle_soreness")
    candidates: list[tuple[str, str]] = []
    if pain is not None and pain >= 3:
        candidates.append(("bad", f"Pain {pain}/5 after this session. Keep the next 48 h easy and see if it settles."))
    candidates.extend(extra)
    if feedback.get("fuelling") == "bonked":
        candidates.append(("warn", "You bonked. Eat earlier and more on the next long session."))
    if rpe is not None and soreness is not None and rpe >= 9 and soreness >= 3:
        candidates.append(("warn", f"RPE {rpe} with soreness {soreness}/5. Keep the next day easy."))
    day = str(activity["date"])[:10]
    if activity.get("workout_intent") in HARD_INTENTS and get_life_load_days(conn, day, day).get(day):
        candidates.append(("warn", "A hard session on a busy day. Check how you sleep tonight."))
    if not candidates:
        return None
    order = {"bad": 0, "warn": 1}
    tone, text = sorted(candidates, key=lambda item: order.get(item[0], 2))[0]
    return {"tone": tone, "text": text}


# ---------------------------------------------------------------------------
# Rides
# ---------------------------------------------------------------------------


def _ride_history(conn: sqlite3.Connection, activity: dict, environment: str) -> tuple[Optional[dict], list[dict]]:
    """This ride's steady-ride analysis (if it qualifies) and earlier qualifying rides indoors/outdoors alike."""
    day = date.fromisoformat(str(activity["date"])[:10])
    rides = [ride for ride in build_aerobic_decoupling(conn, today=day)["rides"] if ride["environment"] == environment]
    position = next((index for index, ride in enumerate(rides) if ride["activity_id"] == str(activity["id"])), None)
    if position is None:
        return None, [ride for ride in rides if ride["date"] < str(activity["date"])[:10]]
    return rides[position], rides[:position]


def _ride_read(conn: sqlite3.Connection, detail_payload: dict) -> dict[str, Any]:
    activity = detail_payload["activity"]
    cycling = detail_payload.get("cycling") or {}
    intent = activity.get("workout_intent")
    feedback = detail_payload.get("feedback") or {}
    signals: list[dict] = []
    wins: list[dict] = []
    steady, earlier = (None, [])
    if cycling.get("power_source") == "measured":
        steady, earlier = _ride_history(conn, activity, cycling.get("environment") or "outdoor")

    drift = steady["decoupling_pct"] if steady else None
    hr_change = None
    if steady:
        recent = earlier[-(SERIES_LENGTH - 1):]
        # Closest to zero is best: heart rate falling late on is not "cleaner" than flat.
        best_before = min((abs(ride["decoupling_pct"]) for ride in recent), default=None)
        if best_before is not None and len(recent) >= 2 and abs(drift) <= best_before:
            detail, tone = f"best of last {len(recent) + 1}", "good"
            wins.append(_win(75, f"Least heart-rate drift of your last {len(recent) + 1} steady rides",
                             f"Drift was {drift:.1f}%. Your heart rate held up better than on any recent steady ride."))
        elif drift <= -STEADY_DRIFT_PCT:
            detail, tone = "heart rate fell in the second half", "neutral"
        elif drift < COUPLED_DECOUPLING_PCT:
            detail, tone = "steady, under 5%", "good"
        else:
            detail, tone = "drifted, 5% or more", "warn"
        signals.append(_signal("decoupling", "Heart-rate drift", f"{drift:.1f}%", detail, tone,
                               [ride["decoupling_pct"] for ride in recent] + [drift], "down"))

        watts = steady["avg_watts"]
        comparable = [ride for ride in earlier if abs(ride["avg_watts"] - watts) <= watts * COMPARABLE_POWER_PCT / 100]
        if comparable:
            reference = comparable[0]
            hr_change = steady["avg_hr"] - reference["avg_hr"]
            tone = "good" if hr_change <= -2 else ("warn" if hr_change >= 2 else "neutral")
            if hr_change <= -2:
                wins.append(_win(90, f"{abs(round(hr_change))} bpm lower at {round(watts)} W than on {_short_date(reference['date'])}",
                                 "Same power for less heart rate: your aerobic base is getting stronger."))
            detail = f"{hr_change:+.0f} bpm vs {_short_date(reference['date'])}" if abs(hr_change) >= 1 else f"same as {_short_date(reference['date'])}"
            series = [ride["avg_hr"] for ride in comparable[-(SERIES_LENGTH - 1):]] + [steady["avg_hr"]]
            signals.append(_signal("hr_at_power", f"Heart rate at {round(watts)} W", f"{round(steady['avg_hr'])} bpm",
                                   detail, tone, series, "down"))

    efforts = [effort for effort in cycling.get("power_efforts") or [] if effort["duration_s"] >= 60 and effort.get("pct_of_best")]
    top_effort = max(efforts, key=lambda effort: (effort.get("is_record"), effort["pct_of_best"]), default=None)
    if top_effort and top_effort.get("is_record"):
        wins.append(_win(100, f"New {top_effort['label']} power best: {round(top_effort['watts'])} W",
                         "Nothing you've ridden before beats it."))
    elif top_effort and top_effort["pct_of_best"] >= 97:
        wins.append(_win(60, f"{top_effort['label']} at {top_effort['pct_of_best']}% of your best",
                         f"{round(top_effort['watts'])} W, right up against your all-time best."))
    if top_effort and (intent in HARD_INTENTS or not steady):
        record = top_effort.get("is_record")
        signals.append(_signal(
            "power_best", f"Best {top_effort['label']}", f"{round(top_effort['watts'])} W",
            "new all-time best" if record else f"{top_effort['pct_of_best']}% of your best",
            "good" if record or top_effort["pct_of_best"] >= 97 else "neutral",
        ))

    above = _above_zone2_pct(detail_payload)
    if intent in EASY_INTENTS and above is not None and not steady:
        tone = "good" if above <= HOT_EASY_ABOVE_Z2_PCT else ("bad" if above > OFF_EASY_ABOVE_Z2_PCT else "warn")
        signals.append(_signal("above_z2", "Time above Zone 2", f"{above}%", "easy rides stay under 15%", tone))

    for extra in (_plan_signal(detail_payload), _going_in_signal(conn, str(activity["date"])[:10])):
        if extra:
            signals.append(extra)
    if len(signals) < 4:
        load = _load_signal(conn, activity, detail_payload, RIDE_TYPES)
        if load:
            signals.append(load)

    # Verdict and next step.
    next_time = None
    if intent in HARD_INTENTS:
        if top_effort and top_effort.get("is_record"):
            verdict = _verdict("good", f"New {top_effort['label']} power best: {round(top_effort['watts'])} W")
        elif top_effort and top_effort["pct_of_best"] >= 95:
            verdict = _verdict("good", f"Quality work: {top_effort['label']} at {top_effort['pct_of_best']}% of your best")
        else:
            verdict = _verdict("neutral", "Hard ride logged")
        next_time = "Keep the next 24–48 h easy before the next quality ride."
    elif steady:
        watts = round(steady["avg_watts"])
        minutes = _round_to(steady["duration_min"], 5)
        if drift < STEADY_DRIFT_PCT:
            better = next((signal for signal in signals if signal["key"] == "decoupling" and signal["detail"].startswith("best")), None)
            headline = f"Steady ride: least drift of your last {better['detail'].split()[-1]}" if better else f"Steady ride: heart rate held at {watts} W"
            verdict = _verdict("good", headline)
            wins.append(_win(50, f"Heart rate held steady at {watts} W", f"{minutes} min with only {drift:.1f}% drift."))
            next_time = f"Heart rate stayed flat at {watts} W. Next steady ride, try {_round_to(watts + 5)}–{_round_to(watts + 10)} W for about {minutes} min."
        elif drift < COUPLED_DECOUPLING_PCT:
            verdict = _verdict("good", f"Steady ride with a little drift ({drift:.1f}%)")
            next_time = f"Repeat {watts} W for about {minutes} min until drift is under {STEADY_DRIFT_PCT:g}%."
        else:
            verdict = _verdict("warn", f"Heart rate drifted {drift:.1f}% in the second half")
            if feedback.get("fuelling") == "bonked":
                next_time = f"Same {watts} W, but eat from the first 30 min. Drift should drop once fuelling is fixed."
            else:
                next_time = f"Drop to about {_round_to(watts - 10)} W, or eat and drink earlier, and aim for drift under 5%."
    elif above is not None and intent in EASY_INTENTS:
        if above > OFF_EASY_ABOVE_Z2_PCT:
            verdict = _verdict("bad", f"Easy ride ran hot: {above}% of the time above Zone 2")
            next_time = "On easy rides, cap heart rate at the top of Zone 2 and let speed drop on climbs."
        elif above > HOT_EASY_ABOVE_Z2_PCT:
            verdict = _verdict("warn", f"Mostly easy, but {above}% of the time above Zone 2")
            next_time = "Keep climbs in Zone 2 next time, even if it means spinning slower."
        else:
            verdict = _verdict("good", "Easy ride stayed easy")
            wins.append(_win(40, "Easy ride stayed easy", f"Only {above}% of the time above Zone 2. That's the discipline that builds the base."))
    else:
        verdict = _verdict("neutral", "Ride logged")

    if cycling.get("power_source") != "measured" and not efforts:
        method = "No power meter on this ride, so the read uses heart rate only."
    else:
        method = "Drift and heart rate at the same power use your steady rides from the last 12 weeks, same environment."
    return {"signals": signals[:4], "verdict": verdict, "next_time": next_time, "watch": _watch(detail_payload, conn, []),
            "method": method, "wins": wins}


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


def _pace_seconds(row: dict) -> Optional[float]:
    if not row.get("distance_km") or not row.get("duration_min") or row["distance_km"] < 0.5:
        return None
    return row["duration_min"] * 60 / row["distance_km"]


def _run_read(conn: sqlite3.Connection, detail_payload: dict) -> dict[str, Any]:
    activity = detail_payload["activity"]
    intent = activity.get("workout_intent")
    day = str(activity["date"])[:10]
    signals: list[dict] = []
    wins: list[dict] = []
    watch_extra: list[tuple[str, str]] = []

    program = build_return_to_run(conn, today=date.fromisoformat(day))
    entry = next((run for run in program.get("history") or [] if str(run["activity_id"]) == str(activity["id"])), None)
    if entry:
        outcome = entry["outcome"]
        score = f"{entry['during']}/10 during" if entry["during"] is not None else "not scored yet"
        tone = {"clean": "good", "hold": "warn", "flare": "bad"}.get(outcome, "neutral")
        stage_name = program["stages"][entry["stage"] - 1]["name"]
        signals.append(_signal("return_to_run", "Return to run", f"Stage {entry['stage']}", f"{stage_name} · {score}", tone))

    hr_cap = program.get("hr_cap_bpm")
    avg_hr = activity.get("avg_hr")
    if avg_hr and hr_cap and intent in EASY_INTENTS:
        over = avg_hr > hr_cap
        signals.append(_signal("hr_cap", "Average heart rate", f"{round(avg_hr)} bpm",
                               f"{'over' if over else 'under'} the {hr_cap} bpm easy cap", "warn" if over else "good"))
        if not over:
            wins.append(_win(40, f"Kept it under the {hr_cap} bpm easy cap", f"Average {round(avg_hr)} bpm. Patient running is how the comeback sticks."))
        if over:
            watch_extra.append(("warn", f"Average heart rate {round(avg_hr)} bpm is over the {hr_cap} bpm easy cap. Slow down or walk more."))

    pace = _pace_seconds(activity)
    if pace and avg_hr:
        rows = conn.execute(
            """
            SELECT id, date, distance_km, duration_min, avg_hr FROM activities
            WHERE type = 'Run' AND id != ? AND substr(date, 1, 10) < ? AND substr(date, 1, 10) >= ?
            ORDER BY date ASC
            """,
            (activity["id"], day, (date.fromisoformat(day) - timedelta(days=180)).isoformat()),
        ).fetchall()
        similar = [
            dict(row) for row in rows
            if row["avg_hr"] and abs(row["avg_hr"] - avg_hr) <= SAME_HR_BPM
            and abs(row["duration_min"] / activity["duration_min"] - 1) <= SAME_DURATION_SHARE
            and _pace_seconds(dict(row))
        ][-(SERIES_LENGTH - 1):]
        if similar:
            paces = [_pace_seconds(row) for row in similar]
            change = pace - median(paces)
            tone = "good" if change <= -PACE_CHANGE_S else ("warn" if change >= PACE_CHANGE_S else "neutral")
            if change <= -PACE_CHANGE_S:
                wins.append(_win(90, f"{abs(round(change))} s/km faster at the same heart rate",
                                 f"{_pace_label(pace)} at about {round(avg_hr)} bpm, against {len(similar)} similar runs."))
            detail = f"{abs(round(change))} s/km {'faster' if change < 0 else 'slower'} than {len(similar)} similar runs" if abs(change) >= 1 else "same as similar runs"
            signals.append(_signal("pace_at_hr", f"Pace at ~{round(avg_hr)} bpm", _pace_label(pace), detail, tone, paces + [pace], "down"))

    for extra in (_plan_signal(detail_payload), _going_in_signal(conn, day)):
        if extra:
            signals.append(extra)
    if len(signals) < 4:
        load = _load_signal(conn, activity, detail_payload, {"Run"})
        if load:
            signals.append(load)

    above = _above_zone2_pct(detail_payload)
    next_time = None
    if entry:
        latest = (program.get("history") or [None])[0]
        stage = entry["stage"]
        if entry["outcome"] == "flare":
            verdict = _verdict("bad", f"Flare at stage {stage}: {entry['during']}/10 during")
        elif entry["outcome"] == "hold":
            verdict = _verdict("warn", f"Stage {stage} run with some symptoms ({entry['during']}/10)")
        elif entry["outcome"] == "clean" and (entry["above_hr_cap"] or entry["longer_than_stage"]):
            reason = "above the HR cap" if entry["above_hr_cap"] else "longer than the stage asks"
            verdict = _verdict("warn", f"Clean stage {stage} run, but {reason}")
        elif entry["outcome"] == "clean":
            verdict = _verdict("good", f"Clean stage {stage} run" + (", stage up" if entry["stage_change"] == "up" else ""))
            if entry["stage_change"] == "up":
                wins.append(_win(95, f"Up to stage {stage} of the return to run", "A clean run moved you up a stage."))
            else:
                wins.append(_win(80, f"Clean stage {stage} run", "No flare. Each clean run is a step back to normal running."))
        else:
            verdict = _verdict("neutral", f"Stage {stage} run, symptoms not scored yet")
        if latest and str(latest["activity_id"]) == str(activity["id"]) and program.get("next"):
            next_time = program["next"]["message"]
        else:
            next_time = f"Stage {stage}: {program['stages'][stage - 1]['prescription']}"
    elif intent in EASY_INTENTS and above is not None:
        if above > OFF_EASY_ABOVE_Z2_PCT:
            verdict = _verdict("bad", f"Easy run ran hot: {above}% above Zone 2")
            next_time = "Slow down until heart rate stays in Zone 2, and walk the hills."
        elif above > HOT_EASY_ABOVE_Z2_PCT:
            verdict = _verdict("warn", f"Mostly easy, {above}% above Zone 2")
            next_time = "Start slower: the first 10 min set the heart rate for the rest of the run."
        else:
            verdict = _verdict("good", "Easy run stayed easy")
            wins.append(_win(40, "Easy run stayed easy", f"Only {above}% of the time above Zone 2."))
    else:
        verdict = _verdict("neutral", "Run logged")

    method = "Pace is compared with runs of similar duration at an average heart rate within 5 bpm, from the last 6 months."
    return {"signals": signals[:4], "verdict": verdict, "next_time": next_time, "watch": _watch(detail_payload, conn, watch_extra),
            "method": method, "wins": wins}


# ---------------------------------------------------------------------------
# Strength
# ---------------------------------------------------------------------------


def _lift_history(conn: sqlite3.Connection, activity_id: str) -> dict[str, list[float]]:
    """Per lift, its headline value (e1RM, top load or reps) in every session up to and including this one."""
    sessions = _session_index(conn)
    position = next(
        (index for index, session in enumerate(sessions) if str((session.get("matched_activity") or {}).get("id")) == str(activity_id)),
        None,
    )
    if position is None:
        return {}
    history: dict[str, list[tuple[str, Optional[float]]]] = {}
    for session in sessions[: position + 1]:
        for exercise in session.get("exercises", []):
            sets = _working_sets(exercise)
            if not sets:
                continue
            summary = _summary(sets)
            metric, _ = _metric(summary)
            history.setdefault(_normalize(exercise["exercise_name"]), []).append((metric, _value_for(summary, metric)))
    # Keep only the values measured the same way as the latest session.
    result = {}
    for key, values in history.items():
        metric = values[-1][0]
        result[key] = [value for item_metric, value in values if item_metric == metric and value is not None]
    return result


def _sessions_without_increase(values: list[float]) -> int:
    """Sessions in a row, ending now, where the lift did not go up on the session before."""
    count = 0
    for index in range(len(values) - 1, 0, -1):
        if values[index] > values[index - 1]:
            break
        count += 1
    return count


def _is_main_lift(name: str) -> bool:
    normalized = _normalize(name)
    return any(word in normalized for word in MAIN_LIFT_WORDS) and not any(word in normalized for word in ACCESSORY_WORDS)


def _weekly_goal_signal(conn: sqlite3.Connection, day: str, metric_type: str) -> Optional[dict]:
    goal = conn.execute(
        "SELECT * FROM goals WHERE is_active = 1 AND COALESCE(lifecycle_status, 'active') = 'active' AND period_type = 'week' AND metric_type = ? "
        "ORDER BY CASE commitment WHEN 'anchor' THEN 0 ELSE 1 END, id LIMIT 1",
        (metric_type,),
    ).fetchone()
    if not goal:
        return None
    start, end, _ = goal_period_window("week", date.fromisoformat(day))
    done = goal_value_for_window(conn, goal, start_date=start.isoformat(), end_date=day)
    target = float(goal["target_value"])
    left = max(0, int(target - done))
    detail = "done for the week" if left == 0 else f"{left} left by {end.strftime('%a')}"
    return _signal("weekly_goal", goal["title"], f"{int(done)} / {int(target)}", detail, "good" if left == 0 else "neutral")


def _strength_read(conn: sqlite3.Connection, detail_payload: dict) -> dict[str, Any]:
    activity = detail_payload["activity"]
    day = str(activity["date"])[:10]
    progression = (detail_payload.get("strength_detail") or {}).get("progression") or {}
    exercises = list((progression.get("exercises") or {}).items())
    history = _lift_history(conn, activity["id"]) if exercises else {}
    signals: list[dict] = []
    watch_extra: list[tuple[str, str]] = []

    compared = [(key, item) for key, item in exercises if item.get("previous")]
    # Compound lifts first, then the heaviest; accessories at fixed loads are not judged for stalls.
    main = sorted(
        compared,
        key=lambda pair: (_is_main_lift(pair[1]["exercise_name"]), pair[1]["metric"] == "e1rm", pair[1]["current"].get("top_load_kg") or 0),
        reverse=True,
    )
    flat = {key: _sessions_without_increase(history.get(key, [])) for key, _ in compared}
    stalled = [(item, flat[key]) for key, item in main if _is_main_lift(item["exercise_name"]) and flat[key] >= STALL_SESSIONS]

    unit = {"e1rm": "kg", "top_load": "kg", "reps": "reps"}
    for key, item in main[:2]:
        if item["is_pr"]:
            detail, tone = "new best", "good"
        elif item["delta"]:
            detail = f"{item['delta']:+g} vs {_short_date(item['previous']['date'])}"
            tone = "good" if item["delta"] > 0 else "warn"
        elif flat[key] >= STALL_SESSIONS:
            detail, tone = f"no increase in {flat[key]} sessions", "warn" if _is_main_lift(item["exercise_name"]) else "neutral"
        else:
            detail, tone = f"same as {_short_date(item['previous']['date'])}", "neutral"
        label = item["exercise_name"] + (" e1RM" if item["metric"] == "e1rm" else "")
        signals.append(_signal(f"lift_{key}", label, f"{item['metric_value']:g} {unit[item['metric']]}", detail, tone,
                               history.get(key, [])[-SERIES_LENGTH:], "up"))

    up = [item for _, item in compared if item["direction"] == "up"]
    down = [item for _, item in compared if item["direction"] == "down"]
    if compared:
        tone = "good" if len(up) > len(down) else ("warn" if len(down) > len(up) else "neutral")
        same = len(compared) - len(up) - len(down)
        signals.append(_signal("lifts_moving", "Lifts up on last time", f"{len(up)} of {len(compared)}", f"{same} same · {len(down)} down", tone))

    goal = _weekly_goal_signal(conn, day, "strength_sessions")
    if goal:
        signals.append(goal)
    for extra in (_plan_signal(detail_payload), _going_in_signal(conn, day)):
        if extra and len(signals) < 4:
            signals.append(extra)

    prs = [item for _, item in compared if item["is_pr"]]
    wins: list[dict] = []
    if prs:
        names = " and ".join(item["exercise_name"] for item in prs[:2])
        wins.append(_win(100, f"New best on {names}", "Heavier than you've ever logged it. The work is paying off."))
    if up and len(up) >= len(down):
        wins.append(_win(70, f"{len(up)} of {len(compared)} lifts up on last time",
                         ", ".join(item["exercise_name"] for item in up[:3]) + " moved up."))
    if goal and goal["tone"] == "good":
        wins.append(_win(65, f"{goal['label']}: done for the week", f"{goal['value']} sessions. Goal hit."))
    if not compared:
        verdict = _verdict("neutral", "First time logging these lifts here" if exercises else "Strength session logged")
    elif prs:
        verdict = _verdict("good", "New best on " + " and ".join(item["exercise_name"] for item in prs[:2]))
    elif len(down) * 2 > len(compared):
        verdict = _verdict("warn", f"{len(down)} of {len(compared)} lifts came in below last time")
    elif stalled:
        item, count = stalled[0]
        verdict = _verdict("warn", f"{item['exercise_name']} hasn't gone up in {count} sessions")
    elif up:
        verdict = _verdict("good", f"{len(up)} of {len(compared)} lifts up on last time")
    else:
        verdict = _verdict("neutral", "Same loads as last time")

    # One instruction: the stalled main lift first, else the top lift's double-progression step.
    focus = stalled[0][0] if stalled else next((item for _, item in main if item.get("next_hint")), None)
    next_time = f"{focus['exercise_name']}: {focus['next_hint']}" if focus and focus.get("next_hint") else None
    if down and len(down) * 2 > len(compared):
        watch_extra.append(("warn", "Most lifts were down on last time. If that repeats next session, take a lighter week."))

    method = (progression.get("method") or "Each lift is compared with the most recent earlier session of the same lift.") + \
        f" A main lift is flagged when it hasn't gone up in {STALL_SESSIONS}+ sessions."
    return {"signals": signals[:4], "verdict": verdict, "next_time": next_time, "watch": _watch(detail_payload, conn, watch_extra),
            "method": method, "wins": wins}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_session_read(conn: sqlite3.Connection, detail_payload: dict) -> dict[str, Any]:
    activity = detail_payload["activity"]
    activity_type = activity.get("type")
    if detail_payload.get("sick_session"):
        return {"available": False, "reason": "Sick-mode sessions are not compared with training."}
    if activity_type in RIDE_TYPES:
        kind, builder = "ride", _ride_read
    elif activity_type == "Run":
        kind, builder = "run", _run_read
    elif activity_type == "WeightTraining" and (detail_payload.get("strength_detail") or {}).get("status") == "enriched":
        kind, builder = "strength", _strength_read
    else:
        return {"available": False, "reason": "No comparisons for this activity type yet."}
    try:
        read = builder(conn, detail_payload)
    except sqlite3.Error as exc:
        return {"available": False, "reason": f"The session read could not be built: {exc}"}
    return {"available": True, "kind": kind, **read}
