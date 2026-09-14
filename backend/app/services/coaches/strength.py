from .common import report


def analyze(activities, start, cutoff, strength_sessions=None):
    result = report("strength", activities, start, cutoff)
    evidence = {item["activity_id"]: item for item in result["evidence"]}
    details = [session for session in (strength_sessions or []) if session["matched_activity"]["id"] in evidence]
    exercises = [exercise for session in details for exercise in session["exercises"]]
    sets = sum(exercise["work_set_count"] for exercise in exercises) if details else None
    lower = sum(exercise["work_set_count"] for exercise in exercises if exercise["body_part"] == "lower") if details else None
    result["totals"].update({"detailed_sessions": len(details), "work_sets": sets, "lower_body_work_sets": lower})
    for session in details:
        if any(exercise["body_part"] == "lower" and exercise["work_set_count"] > 0 for exercise in session["exercises"]):
            evidence[session["matched_activity"]["id"]]["demanding"] = True
    result["totals"]["demanding_sessions"] = sum(item["demanding"] for item in evidence.values())
    if details:
        result["observations"].append(f"{sets} work sets recorded, including {lower} classified as lower body; warm-ups excluded.")
    if len(details) < len(evidence):
        result["limitations"].append("Some strength sessions have no linked exercise detail; set totals cover detailed sessions only.")
        result["data_quality"] = "partial"
    result["limitations"].append("Muscle groups use exercise-name heuristics. Sets do not measure fatigue; load progression and proximity to failure are not inferred.")
    return result
