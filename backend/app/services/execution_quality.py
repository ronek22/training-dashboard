from __future__ import annotations

from typing import Optional


UPPER_BODY_PARTS = {"push", "pull"}
LOWER_BODY_PARTS = {"lower"}
SUPPORTED_INTENTS = {"easy", "long", "tempo", "interval", "race_specific", "strength_general", "strength_lower", "strength_upper"}

BODY_PART_KEYWORDS = {
    "lower": (
        "deadlift",
        "squat",
        "lunge",
        "legpress",
        "legcurl",
        "legextension",
        "hipthrust",
        "calfraise",
        "stepup",
        "glutebridge",
        "rdl",
        "romaniandeadlift",
    ),
    "push": (
        "benchpress",
        "chestpress",
        "inclinebench",
        "dip",
        "pushup",
        "shoulderpress",
        "overheadpress",
        "lateralraise",
        "tricep",
    ),
    "pull": (
        "row",
        "pulldown",
        "pullup",
        "chinup",
        "curl",
        "facepull",
        "shrug",
    ),
}


def _normalize_name(value: Optional[str]) -> str:
    if not value:
        return ""
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _classify_strength_body_part(exercise_name: Optional[str]) -> str:
    normalized = _normalize_name(exercise_name)
    if not normalized:
        return "other"
    for body_part, keywords in BODY_PART_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return body_part
    return "other"


def _build_result(
    status: str,
    headline: str,
    *,
    reasons: Optional[list[str]] = None,
    limitations: Optional[list[str]] = None,
    evidence: Optional[dict] = None,
) -> dict:
    return {
        "status": status,
        "headline": headline,
        "reasons": reasons or [],
        "limitations": limitations or [],
        "evidence": evidence or {},
    }


def _zone_lookup(heart_rate_zones: Optional[dict]) -> dict[str, dict]:
    zones = {}
    for item in (heart_rate_zones or {}).get("zones") or []:
        key = item.get("key")
        if key:
            zones[key] = item
    return zones


def _evaluate_easy_or_long(
    planned_session: dict,
    activity: dict,
    *,
    heart_rate_zones: Optional[dict],
) -> dict:
    planned_intent = planned_session.get("workout_intent")
    target_duration = planned_session.get("target_duration_min")
    duration_min = activity.get("duration_min")
    duration_ratio = None
    if target_duration and duration_min:
        try:
            duration_ratio = float(duration_min) / float(target_duration)
        except (TypeError, ValueError, ZeroDivisionError):
            duration_ratio = None

    evidence = {}
    if duration_ratio is not None:
        evidence["duration_ratio"] = round(duration_ratio, 2)
    if heart_rate_zones and heart_rate_zones.get("available"):
        evidence["zone2_pct"] = heart_rate_zones.get("zone2_pct")
        zones = _zone_lookup(heart_rate_zones)
        higher_zone_pct = sum(int((zones.get(key) or {}).get("pct") or 0) for key in ("zone3", "zone4", "zone5"))
        evidence["higher_zone_pct"] = higher_zone_pct

        if planned_intent == "easy":
            if higher_zone_pct <= 30 and int(heart_rate_zones.get("zone2_pct") or 0) >= 35:
                return _build_result("matched", "Matched intended effort", reasons=["The session stayed mostly aerobic without much higher-zone drift."], evidence=evidence)
            if higher_zone_pct <= 45:
                return _build_result("partial", "Partly matched intended effort", reasons=["Aerobic control was present, but the session drifted upward more than ideal for easy work."], evidence=evidence)
            return _build_result("drifted", "Drifted harder than planned", reasons=["Higher-zone time was too prominent for an easy aerobic session."], evidence=evidence)

        if duration_ratio is not None and duration_ratio < 0.6:
            return _build_result("partial", "Long-session intent was only partly met", reasons=["The linked session finished well short of the planned duration."], evidence=evidence)
        if higher_zone_pct <= 35:
            return _build_result("matched", "Matched long-run intent", reasons=["Duration and aerobic emphasis were broadly preserved."], evidence=evidence)
        if higher_zone_pct <= 50:
            return _build_result("partial", "Long-session intent was only partly met", reasons=["The session kept enough duration, but intensity drifted up for long aerobic work."], evidence=evidence)
        return _build_result("drifted", "Drifted away from long aerobic intent", reasons=["The session carried too much higher-zone work to read as preserved long aerobic intent."], evidence=evidence)

    limitations = ["Heart-rate stream detail is missing, so workout quality cannot be judged from intensity distribution."]
    if planned_intent == "long" and duration_ratio is not None:
        if duration_ratio >= 0.8:
            return _build_result("completed_without_evidence", "Completed with limited evidence", reasons=["Duration was close to the planned long-session target."], limitations=limitations, evidence=evidence)
        if duration_ratio >= 0.6:
            return _build_result("partial", "Long-session intent was only partly met", reasons=["The session captured some planned duration, but finished short."], limitations=limitations, evidence=evidence)
        return _build_result("drifted", "Long-session duration fell short", reasons=["The linked session was much shorter than planned."], limitations=limitations, evidence=evidence)
    return _build_result("completed_without_evidence", "Completed with limited evidence", reasons=["A linked session exists, but there is not enough intensity detail to judge aerobic execution quality."], limitations=limitations, evidence=evidence)


def _evaluate_quality_session(
    planned_session: dict,
    *,
    heart_rate_zones: Optional[dict],
) -> dict:
    planned_intent = planned_session.get("workout_intent")
    if not heart_rate_zones or not heart_rate_zones.get("available"):
        return _build_result(
            "completed_without_evidence",
            "Completed with limited evidence",
            reasons=["A linked quality session exists, but there is not enough intensity detail to verify the intended work."],
            limitations=["Heart-rate stream detail is missing, so the intended intensity band cannot be checked."],
        )

    zones = _zone_lookup(heart_rate_zones)
    zone3_pct = int((zones.get("zone3") or {}).get("pct") or 0)
    zone4_pct = int((zones.get("zone4") or {}).get("pct") or 0)
    zone5_pct = int((zones.get("zone5") or {}).get("pct") or 0)
    quality_band_pct = zone3_pct + zone4_pct if planned_intent in {"tempo", "race_specific"} else zone4_pct + zone5_pct
    evidence = {
        "zone3_pct": zone3_pct,
        "zone4_pct": zone4_pct,
        "zone5_pct": zone5_pct,
        "quality_band_pct": quality_band_pct,
    }

    if quality_band_pct >= 20:
        return _build_result("matched", "Matched quality-session intent", reasons=["Enough time landed in the intended harder intensity band."], evidence=evidence)
    if quality_band_pct >= 10:
        return _build_result("partial", "Quality-session intent was only partly met", reasons=["Some work reached the intended harder band, but not enough to read as a clean quality hit."], evidence=evidence)
    return _build_result("drifted", "Quality-session intent was missed", reasons=["Very little time landed in the intended harder intensity band."], evidence=evidence)


def _evaluate_strength_session(
    planned_session: dict,
    *,
    strength_detail: Optional[dict],
) -> dict:
    planned_intent = planned_session.get("workout_intent")
    if not strength_detail or strength_detail.get("status") != "enriched":
        return _build_result(
            "completed_without_evidence",
            "Completed with limited evidence",
            reasons=["The strength session is logged, but no linked Fitbod enrichment is available for template-aware review."],
            limitations=["Exercise-level strength detail is missing."],
        )

    session = strength_detail.get("session") or {}
    exercises = session.get("exercises") or []
    work_sets = sum(int(item.get("work_set_count") or 0) for item in exercises)
    exercise_count = len(exercises)
    body_part_sets = {"push": 0, "pull": 0, "lower": 0, "other": 0}
    for exercise in exercises:
        body_part = _classify_strength_body_part(exercise.get("exercise_name"))
        body_part_sets[body_part] = body_part_sets.get(body_part, 0) + int(exercise.get("work_set_count") or exercise.get("set_count") or 0)

    total_classified_sets = max(sum(body_part_sets.values()), 1)
    lower_share = round((body_part_sets["lower"] / total_classified_sets) * 100)
    upper_share = round(((body_part_sets["push"] + body_part_sets["pull"]) / total_classified_sets) * 100)
    evidence = {
        "exercise_count": exercise_count,
        "work_set_count": work_sets,
        "lower_share_pct": lower_share,
        "upper_share_pct": upper_share,
        "total_volume_kg": session.get("total_volume_kg"),
    }

    focus_matched = True
    if planned_intent == "strength_lower":
        focus_matched = lower_share >= 35
    elif planned_intent == "strength_upper":
        focus_matched = upper_share >= 55

    if not focus_matched:
        return _build_result("drifted", "Strength focus drifted from plan", reasons=["The exercise mix did not match the planned upper- or lower-body emphasis."], evidence=evidence)
    if work_sets >= 12 and exercise_count >= 4:
        return _build_result("matched", "Matched planned strength work", reasons=["Set count and exercise coverage were strong enough to read as a complete strength session."], evidence=evidence)
    if work_sets >= 8 and exercise_count >= 3:
        return _build_result("partial", "Strength work was only partly covered", reasons=["The session included meaningful work, but template coverage looked thinner than planned."], evidence=evidence)
    return _build_result("drifted", "Strength work fell short of plan", reasons=["Too little exercise or set coverage was logged to read as the planned strength session."], evidence=evidence)


def evaluate_execution_quality(
    planned_session: dict,
    activity: Optional[dict],
    *,
    heart_rate_zones: Optional[dict] = None,
    strength_detail: Optional[dict] = None,
) -> dict:
    planned_intent = planned_session.get("workout_intent")
    if not activity:
        return _build_result("unavailable", "No completed session to judge", reasons=["Execution quality is only available for completed linked sessions."])
    if not planned_intent:
        return _build_result("unavailable", "Not enough planned intent to judge workout quality", reasons=["The planned session did not define a supported workout intent."])
    if planned_intent not in SUPPORTED_INTENTS:
        return _build_result("unavailable", "Workout quality is not supported for this intent yet", reasons=[f"Intent `{planned_intent}` is outside the first supported evaluation set."])

    if planned_intent in {"easy", "long"}:
        return _evaluate_easy_or_long(planned_session, activity, heart_rate_zones=heart_rate_zones)
    if planned_intent in {"tempo", "interval", "race_specific"}:
        return _evaluate_quality_session(planned_session, heart_rate_zones=heart_rate_zones)
    return _evaluate_strength_session(planned_session, strength_detail=strength_detail)
