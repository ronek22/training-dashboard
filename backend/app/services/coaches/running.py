from .common import report, number


def analyze(activities, start, cutoff, strength_sessions=None):
    result = report("running", activities, start, cutoff)
    ids = {item["activity_id"] for item in result["evidence"]}
    rows = [row for row in activities if row["id"] in ids]
    result["totals"]["heart_rate_sessions"] = sum(number(row.get("avg_hr")) is not None for row in rows)
    result["limitations"].append("Pace and heart rate are not used to infer fitness changes without comparable session conditions.")
    return result
