from datetime import date
from .presentation import specialist_takeaways, session_action, weekly_balance


def coordinate(specialists, context=None, recommendation=None, next_sessions=None):
    context = context or {}
    recommendation = recommendation or {}
    next_sessions = next_sessions or []
    specialist_takeaways(specialists, next_sessions)
    sessions = sorted([
        {**item, "sport": sport} for sport, report in specialists.items()
        for item in report["evidence"] if item["demanding"]
    ], key=lambda item: (item["date"], item["activity_id"]))
    conflicts = []
    for index, first in enumerate(sessions):
        for second in sessions[index + 1:]:
            gap = (date.fromisoformat(second["date"]) - date.fromisoformat(first["date"])).days
            if gap > 1:
                break
            if first["sport"] == second["sport"]:
                continue
            conflicts.append({
                "kind": "adjacent_demanding_sessions", "sessions": [first, second],
                "message": f"{first['sport'].title()} on {first['date']} and {second['sport']} on {second['date']} place demanding work on the same or adjacent days.",
            })
    restrictions = (context.get("modality_restrictions") or {}).get("active", [])
    daily = context.get("daily_recommendation") or {}
    recovery_action = daily.get("status")
    constrained = recovery_action in {"recover", "reduce", "adjust"} or recommendation.get("status") in {"recover", "reduce", "adjust"} or bool(restrictions)
    priorities = []
    if constrained:
        priorities.append(daily.get("action") if recovery_action in {"recover", "reduce", "adjust"} and daily.get("action") else "Respect current recovery guidance and active sport restrictions before adding training.")
    if conflicts:
        priorities.append("Review the spacing of demanding work across sports; protect the next priority session when arranging the remaining week.")
    risks = [risk for report in specialists.values() for risk in report["risks"]]
    if risks:
        priorities.append("Review the specialist workload flags before increasing next week's volume or intensity.")
    goal_context = context.get("goal_planning_summary") or {}
    if recommendation.get("focus_for_next_48h") and not constrained:
        priorities.append(recommendation["focus_for_next_48h"])
    count = sum(report["totals"]["sessions"] for report in specialists.values())
    status = "review" if constrained or conflicts or risks else "steady" if count else "insufficient_data"
    headline = {
        "review": "Review the combined week before adding more work",
        "steady": "No cross-sport scheduling flags in the recorded sessions",
        "insufficient_data": "Record training to build your team review",
    }[status]
    action = daily.get("action") if constrained else None
    reason = next(iter(daily.get("reasons") or []), None) if constrained else None
    if reason and "Training form is suppressed" in reason:
        reason = "Recent training load is running above your longer-term baseline."
    if constrained:
        # A weekly adjustment must not reuse an unrelated daily 'keep' instruction.
        headline = "Give recovery room this week"
        action = daily.get('action') if recovery_action in {'recover', 'reduce', 'adjust'} else None
        action = action or "Keep the next session within your current recovery and sport restrictions."
    elif conflicts:
        headline = "Give your demanding sessions more space"
        pair = conflicts[0]["sessions"]
        reason = f"{pair[0]['name']} and {pair[1]['name']} landed on the same or adjacent days."
        action = "Avoid adding another demanding session immediately after this cluster."
    elif risks:
        headline = "Hold the extra workload for now"
        action = "Check how you recover from this week before increasing next week's training."
    elif count:
        headline = "Keep following the week you planned" if context.get("active_plan") else "No session clashes flagged this week"
        action = "No change is suggested by the recorded cross-sport scheduling pattern." if context.get("active_plan") else "Set out your next sessions in the plan to turn this review into a training decision."
    else:
        headline = "Your coaching week starts with your training"
        action = "Sync or log a session to get a useful weekly assessment."
    if not priorities:
        priorities.append("Continue checking recovery and recording workout intent." if count else "Sync or log your sessions, then return to review the week.")
    return {
        "status": status, "headline": headline, "priorities": list(dict.fromkeys(priorities)),
        "action": action, "reason": reason, "balance": weekly_balance(specialists),
        "next_session": session_action(next((item for item in next_sessions if item.get("session_type") not in {"Rest", "Recovery"}), next_sessions[0])) if next_sessions else None,
        "conflicts": conflicts, "risks": risks,
        "limitations": ["This is a rules-based review of recorded training, not a prediction of adaptation or injury.",
                         "No scheduling flag does not establish adequate recovery; missing intent can hide demanding sessions."],
        "context_used": {"recovery": bool(daily), "restrictions": bool(restrictions), "goals": bool(goal_context)},
    }
