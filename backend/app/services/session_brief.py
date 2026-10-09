"""Pre-session brief: purpose, how it should feel (RPE) and when to bail.

Deterministic, coach-style guidance for a planned session. Numbers come from
the athlete's own data: watt targets from the structured workout and stored
FTP, heart-rate caps from the configured zones, and a personal "usual HR at
this power" from recent rides so the drift rule is anchored to what is normal
for this athlete rather than a textbook value. Nothing here changes the plan.
"""

from __future__ import annotations

import json
import re
import sqlite3
import statistics
from datetime import date, timedelta
from typing import Any, Optional

from .checkins import get_daily_checkin
from .cycling_workouts import get_cycling_workout, latest_ftp
from .heart_rate_zones import HR_ZONE_DEFINITIONS
from .power_trends import _finite_number, _stream_values

DRIFT_BPM = 10
BASELINE_DAYS = 90
BASELINE_MAX_RIDES = 15
BASELINE_MIN_SAMPLES = 120
BASELINE_MIN_RIDES = 3
POWER_BAND = 0.08
WARMUP_SKIP_S = 600
ROLLING_S = 30


def _zone_top(modality: str, key: str) -> Optional[int]:
    return next((zone["upper_bpm"] for zone in HR_ZONE_DEFINITIONS[modality] if zone["key"] == key), None)


def _modality(session_type: Optional[str], title: Optional[str] = None) -> str:
    value = (session_type or "").lower()
    if value == "recovery":
        # Plans use a generic recovery type; the title says whether it is on the bike.
        return "ride" if re.search(r"cycl|ride|spin|bike|zwift", title or "", re.IGNORECASE) else "mobility"
    if "ride" in value or "cycl" in value or "bike" in value:
        return "ride"
    if "run" in value:
        return "run"
    if "weight" in value or "strength" in value:
        return "strength"
    if "yoga" in value or "mobility" in value:
        return "mobility"
    if "hike" in value:
        return "hike"
    return "other"


# ---------------------------------------------------------------------------
# Personal HR-at-power baseline
# ---------------------------------------------------------------------------


def usual_hr_at_power(conn: sqlite3.Connection, watts: float, today: date) -> Optional[dict[str, Any]]:
    """Median of per-ride median HR while 30 s power sits within ±8% of ``watts``.

    The first 10 minutes are skipped so warm-up HR lag does not drag the value
    down. Needs 3+ rides with 2+ minutes in the band.
    """
    since = (today - timedelta(days=BASELINE_DAYS)).isoformat()
    try:
        rows = conn.execute(
            """
            SELECT d.streams_json
            FROM activities AS a
            JOIN activity_details AS d ON d.activity_id = a.id
            WHERE a.type IN ('Ride', 'VirtualRide') AND a.date >= ? AND a.date < ?
              AND d.streams_json LIKE '%watts%' AND d.streams_json LIKE '%heartrate%'
            ORDER BY a.date DESC
            LIMIT ?
            """,
            (since, today.isoformat(), BASELINE_MAX_RIDES),
        ).fetchall()
    except sqlite3.OperationalError:
        return None
    per_ride = []
    low, high = watts * (1 - POWER_BAND), watts * (1 + POWER_BAND)
    for row in rows:
        try:
            streams = json.loads(row[0])
        except (TypeError, ValueError):
            continue
        power = _stream_values(streams, "watts")
        hr = _stream_values(streams, "heartrate")
        times = _stream_values(streams, "time")
        count = min(len(power), len(hr), len(times))
        prefix = [0.0]
        for index in range(count):
            prefix.append(prefix[-1] + (_finite_number(power[index]) or 0.0))
        values = []
        for index in range(ROLLING_S, count):
            elapsed = _finite_number(times[index])
            if elapsed is None or elapsed < WARMUP_SKIP_S:
                continue
            rolling = (prefix[index + 1] - prefix[index + 1 - ROLLING_S]) / ROLLING_S
            heart = _finite_number(hr[index])
            if heart and heart > 0 and low <= rolling <= high:
                values.append(heart)
        if len(values) >= BASELINE_MIN_SAMPLES:
            per_ride.append(statistics.median(values))
    if len(per_ride) < BASELINE_MIN_RIDES:
        return None
    return {
        "watts": round(watts),
        "bpm": round(statistics.median(per_ride)),
        "low_bpm": round(min(per_ride)),
        "high_bpm": round(max(per_ride)),
        "rides": len(per_ride),
        "days": BASELINE_DAYS,
    }


# ---------------------------------------------------------------------------
# Brief templates
# ---------------------------------------------------------------------------


def _main_power_fraction(workout: dict) -> Optional[float]:
    """The work-step power: the highest steady/interval target in the workout."""
    fractions = []
    for step in workout.get("steps", []):
        if step["kind"] == "steady":
            fractions.append(step["power"])
        elif step["kind"] == "intervals":
            fractions.append(step["on_power"])
    return max(fractions) if fractions else None


def _endurance_fraction(workout: Optional[dict]) -> float:
    if workout:
        steady = [step["power"] for step in workout.get("steps", []) if step["kind"] == "steady"]
        if steady:
            return max(steady)
    return 0.68


RIDE_BRIEFS = {
    "Recovery": {
        "purpose": "Flush the legs and keep the daily habit without adding fatigue.",
        "rpe": "1–2", "feel": "Barely working. If you are wondering whether it is easy enough, go easier.",
    },
    "Endurance": {
        "purpose": "Aerobic base: more fat burning and durability for a low fatigue cost.",
        "rpe": "3–4", "feel": "Conversational. You could speak in full sentences the whole time.",
    },
    "Tempo": {
        "purpose": "Raise sustainable power and make race-pace riding feel routine.",
        "rpe": "5–6", "feel": "Comfortably hard. Short sentences only, steady breathing.",
    },
    "Sweet spot": {
        "purpose": "Lift FTP with a big chunk of work just under threshold, without a threshold-sized recovery bill.",
        "rpe": "6–7", "feel": "Hard but controlled. The last minutes of each block should take focus, not desperation.",
    },
    "Threshold": {
        "purpose": "Push FTP directly by holding the edge of what you can sustain.",
        "rpe": "7–8", "feel": "Hard. Breathing deep and rhythmic; talking is a few words at most.",
    },
    "VO2 max": {
        "purpose": "Raise your aerobic ceiling, which lifts every power below it.",
        "rpe": "9", "feel": "Very hard. The last 30 s of each rep should feel like you could not go much longer.",
    },
}

RUN_BRIEFS = {
    "recovery": ("Easy movement to recover and keep running in the routine.", "2–3", "Very easy. Slower than feels natural is right."),
    "easy": ("Aerobic running base and tissue tolerance for the return to running.", "3–4", "Conversational. You could chat the whole way."),
    "long": ("Time on feet: durability for legs, tendons and the aerobic system.", "3–4", "Easy and patient. The last third should still feel controlled."),
    "tempo": ("Raise the pace you can hold for longer.", "6–7", "Comfortably hard. A few words at a time."),
    "interval": ("Speed and running economy.", "8", "Hard reps, fully relaxed recoveries."),
    "race_specific": ("Practise goal pace, fuelling and pacing.", "6–8", "Goal effort. Start controlled; finish strong, not desperate."),
}

STRENGTH_PURPOSE = {
    "strength_upper": "Build upper-body muscle and keep the 3× a week lifting habit.",
    "strength_lower": "Build leg and hip strength that carries over to riding and running.",
    "strength_general": "Whole-body strength and muscle while keeping the 3× a week habit.",
}


def _recent_ftp_estimate(conn: sqlite3.Connection, today: date) -> Optional[int]:
    try:
        from .personal_records import build_personal_records

        estimate = build_personal_records(conn, today)["cycling_power"]["ftp_estimate"]
    except (sqlite3.OperationalError, KeyError):
        return None
    return estimate.get("watts") if estimate.get("available") else None


def _ride_brief(day: dict, conn: sqlite3.Connection, today: date) -> dict[str, Any]:
    workout = get_cycling_workout(day.get("cycling_workout_id")) if day.get("cycling_workout_id") else None
    intent = day.get("workout_intent") or (workout or {}).get("workout_intent") or "easy"
    if (day.get("session_type") or "").lower() == "recovery":
        intent = "recovery"
    category = (workout or {}).get("category") or {
        "recovery": "Recovery", "easy": "Endurance", "long": "Endurance", "tempo": "Tempo",
        "interval": "Threshold", "race_specific": "Threshold",
    }.get(intent, "Endurance")
    template = RIDE_BRIEFS.get(category, RIDE_BRIEFS["Endurance"])
    ftp = latest_ftp(conn, today)
    ftp_w = ftp.get("watts") if ftp.get("available") else None
    z1, z2, z3, z4 = (_zone_top("ride", key) for key in ("zone1", "zone2", "zone3", "zone4"))

    targets: list[dict[str, str]] = []
    bail: list[str] = []
    notes: list[str] = []
    basis: dict[str, Any] = {"ftp": ftp}

    work_fraction = _main_power_fraction(workout) if workout else None
    work_w = round(work_fraction * ftp_w) if work_fraction and ftp_w else None
    if work_w and category not in ("Recovery", "Endurance"):
        targets.append({"label": "Work", "value": f"{work_w} W"})

    if category == "Recovery":
        targets.append({"label": "HR cap", "value": f"≤ {z1} bpm"})
        bail.append(f"If HR passes {z1} bpm or the legs still feel heavy after 10 min, stop at 20 min. It still counts.")
    elif category == "Endurance":
        endurance_w = round(_endurance_fraction(workout) * ftp_w) if ftp_w else None
        if endurance_w:
            targets.append({"label": "Power", "value": f"~{endurance_w} W"})
        targets.append({"label": "HR cap", "value": f"≤ {z2} bpm"})
        baseline = usual_hr_at_power(conn, endurance_w, today) if endurance_w else None
        basis["usual_hr"] = baseline
        if baseline:
            limit = baseline["bpm"] + DRIFT_BPM
            bail.append(
                f"At {endurance_w} W your HR usually settles around {baseline['bpm']} bpm. "
                f"If it climbs past {limit} bpm at the same power, cut it short: that is fatigue or heat, not fitness."
            )
            if z2 and baseline["bpm"] > z2:
                notes.append(f"Your usual HR at {endurance_w} W is above zone 2 (≤ {z2}). Ride by HR today and let power drop.")
        else:
            bail.append(
                f"Note your HR 15 min in. If it drifts more than {DRIFT_BPM} bpm higher at the same power, cut it short."
            )
        if intent == "long":
            bail.append("If power falls 10% at the same effort in the last hour, eat, then head home on the shortest route.")
    elif category == "Tempo":
        bail.append(f"If you cannot hold {work_w or 'target'} W in the second block without HR passing {z3} bpm, ride the rest as endurance.")
    elif category == "Sweet spot":
        bail.append(f"If HR passes {z4} bpm before the last third of a block, or power sags more than 5%, end the set and spin easy.")
    elif category == "Threshold":
        bail.append("If the first rep already feels above RPE 8, or you cannot finish rep 2 on target, swap the rest for sweet spot.")
    elif category == "VO2 max":
        bail.append("If a rep's power drops more than 10% below your first rep, stop the set. Quality over count.")

    if ftp.get("stale") and work_w:
        note = f"Watt targets use your FTP of {round(ftp_w)} W from {ftp['date']}."
        estimate = _recent_ftp_estimate(conn, today)
        if estimate and estimate < ftp_w * 0.95:
            note += f" Recent rides suggest about {estimate} W, which would put this work at ~{round(work_fraction * estimate)} W."
        notes.append(f"{note} If the first block feels harder than RPE {template['rpe']}, lower the watts.")

    return {
        "sport": "ride",
        "kind": category,
        "purpose": (workout or {}).get("purpose") or template["purpose"],
        "feel": {"rpe": template["rpe"], "text": template["feel"]},
        "targets": targets,
        "bail": bail,
        "notes": notes,
        "basis": basis,
    }


def _run_brief(day: dict, conn: sqlite3.Connection, today: date) -> dict[str, Any]:
    intent = day.get("workout_intent") or "easy"
    purpose, rpe, feel = RUN_BRIEFS.get(intent, RUN_BRIEFS["easy"])
    z2 = _zone_top("run", "zone2")
    z3 = _zone_top("run", "zone3")
    targets = []
    bail = []
    if intent in ("recovery", "easy", "long"):
        targets.append({"label": "HR cap", "value": f"≤ {z2} bpm"})
        bail.append(f"If HR passes {z2} bpm at an easy pace, walk 1 min and restart slower. If it keeps happening, call it at 20–30 min.")
        if intent == "long":
            bail.append(f"If HR drifts more than {DRIFT_BPM} bpm at the same pace in the second half, add walk breaks every km.")
    else:
        targets.append({"label": "HR ceiling", "value": f"~{z3} bpm on reps"})
        bail.append("If you cannot match the first rep's pace by rep 3, finish with easy running instead.")
    bail.append("Any sharp pain or a change in your stride: stop and walk home.")
    notes = []
    try:
        from .return_to_run import FLARE_DURING, build_return_to_run

        program = build_return_to_run(conn, today)
    except sqlite3.OperationalError:
        program = {"active": False}
    if program.get("active"):
        stage = program["stage"]
        symptom = program["program"]["symptom"].lower()
        purpose = f"Return to run, stage {stage['stage']} of {len(program['stages'])}: {stage['name']}."
        notes.append(f"Stage prescription: {stage['prescription']}")
        bail.insert(0, f"Stop and walk home if {symptom} pain reaches {FLARE_DURING - 1}/10, then log it.")
        if program["next"]["status"] in ("rest", "needs_morning", "flare", "needs_score"):
            notes.insert(0, program["next"]["message"])
    return {
        "sport": "run",
        "kind": intent,
        "purpose": purpose,
        "feel": {"rpe": rpe, "text": feel},
        "targets": targets,
        "bail": bail,
        "notes": notes,
        "basis": {},
    }


def _session_plateaus(day: dict, conn: sqlite3.Connection, today: date) -> list[dict]:
    """Stalled lifts among today's saved-workout exercises, longest stall first."""
    from .strength_plateaus import find_plateaus
    from .strength_volume import _day_exercises, _templates_by_name

    names = [item["exercise_name"] for item in _day_exercises(day, _templates_by_name(conn))]
    names += [item.get("exercise_name") for item in day.get("lift_volume_additions") or [] if item.get("exercise_name")]
    if not names:
        return []
    try:
        return find_plateaus(conn, today, names)
    except sqlite3.OperationalError:
        return []


def _session_effort_notes(day: dict, conn: sqlite3.Connection) -> list[dict]:
    """How today's lifts felt last time, from the between-set effort taps."""
    from .set_effort import effort_carryover
    from .strength_volume import _day_exercises, _templates_by_name

    names = [item["exercise_name"] for item in _day_exercises(day, _templates_by_name(conn))]
    names += [item.get("exercise_name") for item in day.get("lift_volume_additions") or [] if item.get("exercise_name")]
    try:
        return effort_carryover(conn, names)
    except sqlite3.OperationalError:
        return []


_TRAVEL_KIT_RE = re.compile(r"travel kit", re.IGNORECASE)


def _travel_kit_brief(day: dict) -> dict[str, Any]:
    core = re.search(r"\bcore\b", day.get("title") or "", re.IGNORECASE)
    return {
        "sport": "strength",
        "kind": "travel_kit",
        "purpose": "Keep the lift habit and the upper-body stimulus on the road, with no equipment.",
        "feel": {"rpe": "7–8", "text": "Each set ends 1–3 reps short of failure. Slow the lowering phase if the reps get too easy."},
        "targets": [{"label": "Reps in reserve", "value": "1–3"}],
        "bail": ["Shoulder or elbow pain (not muscle burn): drop that exercise and add a round of the others."],
        "notes": ["Counts toward lifting 3× a week; the A/B/C/D rotation waits until you are home."],
        "guided_session_key": "travel_core" if core else "travel_upper",
        "basis": {},
    }


def _hike_brief(day: dict, conn: sqlite3.Connection, today: date) -> dict[str, Any]:
    return {
        "sport": "hike",
        "kind": day.get("workout_intent") or "easy",
        "purpose": "Time on feet in the mountains: aerobic base and leg work without the bike.",
        "feel": {"rpe": "3–5", "text": "Full sentences on the climbs. Slow down rather than stop; the descents are where legs and knees get tired."},
        "targets": [
            {"label": "Fuel", "value": "30–60 g carbs per hour after the first hour"},
            {"label": "Water", "value": "about 0.5 L per hour"},
        ],
        "bail": [
            "Knee pain above 3/10 on a descent: poles, short steps, and take the easier way down.",
            "Weather turning or daylight short: turn back at the planned time, not at the summit.",
        ],
        "notes": ["Hiking counts as leg work today: no lower-body lifting on top."],
        "basis": {},
    }


def _strength_brief(day: dict, conn: sqlite3.Connection, today: date) -> dict[str, Any]:
    if _TRAVEL_KIT_RE.search(day.get("title") or ""):
        return _travel_kit_brief(day)
    intent = day.get("workout_intent") or "strength_general"
    return {
        "sport": "strength",
        "kind": intent,
        "purpose": STRENGTH_PURPOSE.get(intent, STRENGTH_PURPOSE["strength_general"]),
        "feel": {"rpe": "7–8", "text": "Working sets end with 1–2 good reps left in the tank. Warm-ups should feel light."},
        "targets": [{"label": "Reps in reserve", "value": "1–2"}],
        "bail": [
            "If the first working set of the main lift feels like RPE 9 at last week's load, drop 5–10% and keep the reps.",
            "Joint pain (not muscle burn) on a lift: swap the exercise rather than push through.",
        ],
        "notes": [],
        "plateaus": _session_plateaus(day, conn, today),
        "effort_notes": _session_effort_notes(day, conn),
        "basis": {},
    }


def _mobility_brief(day: dict, conn: sqlite3.Connection, today: date) -> dict[str, Any]:
    return {
        "sport": "mobility",
        "kind": "mobility",
        "purpose": "Restore range of motion and help recovery between harder days.",
        "feel": {"rpe": "2", "text": "Gentle stretch tension, never pain. Breathe slowly."},
        "targets": [],
        "bail": ["Anything that pinches or hurts: ease off or skip that position."],
        "notes": [],
        "basis": {},
    }


# A plan sentence is a guardrail when it tells the athlete to stop or scale back,
# not merely when it mentions a symptom inside a prescription.
_GUARDRAIL_RE = re.compile(r"\b(stop|skip|abort|shorten|cut (it|the)|end the|bail|back off|ease off|switch to)\b", re.IGNORECASE)
GUARDRAIL_MAX_CHARS = 180


def _plan_guardrails(details: Optional[str]) -> list[str]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", details or "") if part.strip()]
    return [s for s in sentences if _GUARDRAIL_RE.search(s) and len(s) <= GUARDRAIL_MAX_CHARS][:2]


def build_session_brief(conn: sqlite3.Connection, day: dict, today: Optional[date] = None) -> Optional[dict[str, Any]]:
    today = today or date.today()
    modality = _modality(day.get("session_type"), day.get("title"))
    builder = {"ride": _ride_brief, "run": _run_brief, "strength": _strength_brief, "mobility": _mobility_brief, "hike": _hike_brief}.get(modality)
    if builder is None or (day.get("session_type") or "").lower() in ("rest", ""):
        return None
    brief = builder(day, conn, today)

    # Plan-specific guardrails (from the coach's wording) come first.
    plan_lines = _plan_guardrails(day.get("details"))
    for sentence in reversed(plan_lines):
        if sentence not in brief["bail"]:
            brief["bail"].insert(0, sentence)

    # Today's own signals: an active injury and the morning check-in.
    try:
        from .recovery import coaching_summary

        issues = coaching_summary(conn).get("issues", [])
    except sqlite3.OperationalError:
        issues = []
    plan_covers_pain = any(re.search(r"pain|knee|heel|injur|symptom", line, re.IGNORECASE) for line in plan_lines)
    for issue in ([] if plan_covers_pain else issues[:2]):
        area = " ".join(part for part in (issue.get("side"), issue.get("body_area")) if part) or issue.get("title")
        brief["bail"].append(f"Active issue ({area}): stop if it goes above 3/10 or changes how you move.")
    try:
        checkin = get_daily_checkin(conn, day.get("date") or today.isoformat())
    except sqlite3.OperationalError:
        checkin = None
    if checkin:
        low = [
            label
            for label, value in (("energy", checkin.get("energy")), ("sleep", checkin.get("sleep_quality")))
            if value is not None and value <= 2
        ]
        if (checkin.get("muscle_soreness") or 0) >= 4:
            low.append("soreness")
        if low:
            brief["notes"].insert(0, f"Check-in shows low {' and '.join(low)} today. Hold the bottom of the targets, and use the bail rule early.")

    # Back from illness: the cap overrides the session's own effort target.
    try:
        from .illness_return import build_illness_return

        illness = build_illness_return(conn, today)
    except sqlite3.OperationalError:
        illness = None
    if illness and brief["sport"] in ("ride", "run", "strength", "hike"):
        brief["illness_return"] = {"headline": illness["headline"], "phase": illness["phase"], "rpe_cap": illness["rpe_cap"]}
        brief["notes"].insert(0, f"{illness['headline']}. {illness['guidance']}")
        brief["feel"] = {**brief["feel"], "rpe": f"≤{illness['rpe_cap']}"}
        if brief["sport"] == "strength":
            reserve = "3+" if illness["phase"] == "easy" else "2+"
            brief["targets"] = [item for item in brief["targets"] if item["label"] != "Reps in reserve"] + [{"label": "Reps in reserve", "value": reserve}]
        brief["bail"].insert(0, "Headache, chest tightness or a racing heart: stop, it is too soon.")

    family = {"ride": "ride_quality" if brief["kind"] in ("Tempo", "Sweet spot", "Threshold", "VO2 max") else "ride_easy",
              "run": "run", "strength": "strength"}.get(brief["sport"])
    if family:
        try:
            from .what_worked import patterns_for_family

            for pattern in patterns_for_family(conn, family, today)[:1]:
                brief["notes"].append(f"From your history: {pattern['statement']}")
        except sqlite3.OperationalError:
            pass

    brief["bail"] = brief["bail"][:3]
    brief["session_id"] = day.get("session_id")
    brief["date"] = day.get("date")
    brief["title"] = day.get("title")
    return brief


def build_briefs_for_date(conn: sqlite3.Connection, plan: Optional[dict], target: date) -> list[dict[str, Any]]:
    """Briefs for every planned session on ``target`` in a serialized weekly plan."""
    if not plan:
        return []
    from .sick_mode import sick_dates

    try:
        if target.isoformat() in sick_dates(conn):
            # Sick days get guided home sessions instead of the planned one.
            return []
    except sqlite3.OperationalError:
        pass
    briefs = []
    for day in plan.get("days", []):
        if day.get("date") != target.isoformat():
            continue
        brief = build_session_brief(conn, day, target)
        if brief:
            briefs.append(brief)
    return briefs
