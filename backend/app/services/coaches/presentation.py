"""Athlete-facing interpretation of facts and existing plan recommendations."""
from .common import SPORT_TYPES


def duration_label(minutes):
    if minutes is None:
        return "Time not recorded"
    minutes = round(minutes)
    hours, remainder = divmod(minutes, 60)
    return f"{hours}h {remainder:02d}m" if hours else f"{minutes} min"


def session_action(session):
    suggestion = session.get("suggestion", "keep")
    instructions = {
        "keep": "Follow the planned session.",
        "lighten": "Keep this session easy and remove the demanding efforts.",
        "swap_to_recovery": "Replace this session with recovery or rest.",
        "substitute": "Choose an allowed activity instead of this session.",
        "avoid": "Skip this session while the restriction is active.",
        "limit": "Stay within your current restriction for this session.",
        "review": "Review this session before starting; the week needs adjustment.",
    }
    return {"date": session["date"], "title": session.get("title") or session.get("session_type"),
            "instruction": session.get("restriction_summary") or instructions.get(suggestion, instructions["review"]),
            "suggestion": suggestion, "session_type": session.get("session_type"),
            "duration_min": session.get("target_duration_min") if suggestion == "keep" else None,
            "distance_km": session.get("target_distance_km") if suggestion == "keep" else None}


def specialist_takeaways(specialists, next_sessions):
    for sport, report in specialists.items():
        totals = report["totals"]
        count = totals["sessions"]
        distance = totals["distance_km"]["value"]
        delta = report["baseline"]["change_pct"]
        upcoming = next((item for item in next_sessions if item.get("session_type") in SPORT_TYPES[sport]), None)
        next_action = session_action(upcoming) if upcoming else None
        report["next_session"] = next_action
        report["display"] = {"time": duration_label(totals["duration_min"]["value"])}
        if not count:
            report["takeaway"] = "No sessions to assess yet"
            report["meaning"] = "Sync or log this week's training to bring this coach into the review."
        elif sport == "running":
            easy = totals["easy_sessions"]
            report["takeaway"] = "One run on the board" if count == 1 else "Your running week at a glance"
            report["meaning"] = (
                "Your recorded run was easy or recovery-focused." if count == easy == 1 else
                f"{easy} of {count} runs were tagged easy or recovery." if easy else
                "Use the next planned run to guide the rest of the week.")
            if delta is not None and delta >= 30:
                report["takeaway"] = "Running time has stepped up"
                report["meaning"] = f"Time on your feet is up {delta:g}% against the same weekdays in the last four weeks. Check recovery before adding another demanding run."
        elif sport == "cycling":
            if delta is not None and abs(delta) <= 15:
                report["takeaway"] = "Close to your usual riding volume"
                report["meaning"] = f"Riding time is {abs(delta):.0f}% {'above' if delta >= 0 else 'below'} your usual volume by this point in the week. This comparison describes volume, not whether those rides supported your goals."
            elif delta is not None and delta >= 30:
                report["takeaway"] = "A bigger riding week"
                report["meaning"] = f"Riding time is up {delta:g}% against your recent matching-weekday average. Account for that extra work when choosing the next run or leg session."
            else:
                report["takeaway"] = "Your riding contribution"
                report["meaning"] = f"{duration_label(totals['duration_min']['value'])} across {count} {'ride' if count == 1 else 'rides'}. Include this workload when planning the remaining run and strength sessions."
        else:
            report["takeaway"] = f"{count} strength {'session' if count == 1 else 'sessions'} completed"
            lower = totals.get("lower_body_work_sets")
            report["meaning"] = (f"{lower} lower-body work sets are part of this week's load. Consider leg soreness before your next demanding run or ride." if lower else
                                 "Use the next planned workout to continue your strength rotation.")
        if next_action:
            report["recommendations"] = [next_action["instruction"]]


def weekly_balance(specialists):
    timed = [(sport, report["totals"]["duration_min"]["value"]) for sport, report in specialists.items()]
    timed = [(sport, value) for sport, value in timed if value is not None and value > 0]
    if not timed:
        return "There is not enough recorded training time to assess the balance of the week."
    sport, value = max(timed, key=lambda item: item[1])
    return f"{sport.title()} accounts for the largest share of recorded training time this week: {duration_label(value)}."
