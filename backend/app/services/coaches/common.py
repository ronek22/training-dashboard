"""Shared, deterministic observations; these are not fitness predictions."""
from datetime import date, timedelta
from math import isfinite

SPORT_TYPES = {
    "running": {"Run", "VirtualRun", "TrailRun"},
    "cycling": {"Ride", "VirtualRide", "EBikeRide", "EMountainBikeRide"},
    "strength": {"WeightTraining"},
}
DEMANDING_INTENTS = {"tempo", "interval", "race_specific", "long", "strength_lower", "strength_general"}
EASY_INTENTS = {"easy", "recovery", "mobility"}


def number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) and value >= 0:
        return float(value)
    return None


def total(rows, field):
    values = [number(row.get(field)) for row in rows]
    known = [value for value in values if value is not None]
    return {"value": round(sum(known), 1) if known else None, "recorded": len(known), "sessions": len(rows)}


def report(sport, activities, start, cutoff):
    relevant = [row for row in activities if row["type"] in SPORT_TYPES[sport]]
    current = [row for row in relevant if start.isoformat() <= row["date"][:10] <= cutoff.isoformat()]
    duration = total(current, "duration_min")
    distance = total(current, "distance_km")
    elapsed = max(0, (cutoff - start).days + 1)
    baseline_windows = []
    for offset in range(1, 5):
        previous_start = start - timedelta(weeks=offset)
        previous_end = previous_start + timedelta(days=elapsed - 1)
        rows = [row for row in relevant if previous_start.isoformat() <= row["date"][:10] <= previous_end.isoformat()]
        baseline_windows.append(total(rows, "duration_min"))
    observed = [item["value"] for item in baseline_windows if item["sessions"] and item["recorded"] == item["sessions"]]
    baseline = round(sum(observed) / len(observed), 1) if observed else None
    comparable = len(observed) == 4 and duration["recorded"] == len(current) and bool(current) and baseline > 0
    delta = round((duration["value"] / baseline - 1) * 100, 1) if comparable else None
    unknown = sum(not row.get("workout_intent") for row in current)
    demanding = [row for row in current if row.get("workout_intent") in DEMANDING_INTENTS]
    limits = []
    if not current:
        limits.append("No sessions recorded for this sport in this window; this does not prove no training occurred.")
    if duration["recorded"] < len(current):
        limits.append("Some durations are missing; the displayed total includes recorded durations only.")
    if sport != "strength" and distance["recorded"] < len(current):
        limits.append("Some distances are missing; the displayed total includes recorded distances only.")
    if unknown:
        limits.append(f"{unknown} sessions have no recorded workout intent; intensity distribution is incomplete.")
    if len(observed) < 4:
        limits.append("Four complete recorded comparison windows are unavailable; workload change is not assessed.")
    risks = []
    recommendations = []
    if delta is not None and delta >= 30:
        risks.append(f"Recorded duration is {delta:g}% above the prior four-week matching-weekday average. This is a workload flag, not a physiological risk estimate.")
        recommendations.append("Review this increase against your goal and recent recovery before adding more work.")
    if len(demanding) >= 3 and sport != "strength":
        risks.append(f"{len(demanding)} sessions have demanding intent (including long sessions); review their spacing.")
        recommendations.append("Coordinate demanding sessions with the other sports before adding intensity.")
    return {
        "sport": sport, "status": "no_data" if not current else "review" if risks else "recorded",
        "totals": {"sessions": len(current), "duration_min": duration, "distance_km": distance,
                   "demanding_sessions": len(demanding), "easy_sessions": sum(row.get("workout_intent") in EASY_INTENTS for row in current),
                   "unknown_intent_sessions": unknown},
        "baseline": {"weeks_observed": len(observed), "matching_weekday_duration_min": baseline, "change_pct": delta},
        "evidence": [{"activity_id": row["id"], "date": row["date"][:10], "name": row.get("name") or row["type"],
                      "intent": row.get("workout_intent"), "demanding": row.get("workout_intent") in DEMANDING_INTENTS} for row in current],
        "observations": [f"{len(current)} {sport} sessions recorded in this window."] if current else [],
        "risks": risks, "recommendations": recommendations, "limitations": limits,
        "data_quality": "limited" if not current else "partial" if limits else "available",
    }
