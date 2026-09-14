from .common import report, number


def analyze(activities, start, cutoff, strength_sessions=None):
    result = report("cycling", activities, start, cutoff)
    ids = {item["activity_id"] for item in result["evidence"]}
    rows = [row for row in activities if row["id"] in ids]
    result["totals"]["power_sessions"] = sum(number(row.get("avg_watts")) is not None for row in rows)
    result["totals"]["indoor_sessions"] = sum(row["type"] == "VirtualRide" for row in rows)
    result["limitations"].append("Average power alone does not establish time in zones; indoor and outdoor distances are not treated as equivalent performance tests.")
    return result
