"""Deterministic review of whether each goal is still worth chasing.

A verdict combines the goal's own period history (Step 2), the outcome it is
meant to improve and the cost of training (Step 3), and the athlete's intent
(anchor goals, purpose). Recommendations carry ready-to-apply payloads for the
goal lifecycle endpoints; nothing is applied without the athlete's click.
"""

import re
import sqlite3
from datetime import date, datetime, timedelta
from math import ceil
from typing import Any, Optional

from ..repositories.goals import insert_goal_review_decision, latest_goal_review_decisions
from .goal_history import attach_goal_histories
from .goal_outcomes import attach_goal_outcomes, build_cost_signals
from .goal_portfolio import build_portfolio_check
from .goals import get_goal_data, list_goals_data
from .seasons import DEFAULT_OFF_SEASON_MONTHS, off_season_end
from .settings import get_athlete_profile_for_conn

MIN_REVIEW_PERIODS = 4
MIN_VERDICT_PERIODS = 8
OUT_OF_REACH_HIT_RATE = 0.25
OUT_OF_REACH_RATE_MULTIPLIER = 1.5
TOO_EASY_HIT_RATE = 0.9
TOO_EASY_MARGIN = 1.4
ON_TRACK_HIT_RATE = 0.6
PLATEAU_HIT_RATE = 0.7
CROWDING_HIT_RATE_DROP = 0.3
CROWDING_VOLUME_RISE_PCT = 5.0
CALIBRATION_PERCENTILE_UPLIFT = 1.05
# A lowered target below this share of the current one is a different goal, not a recalibration.
MIN_LOWERED_TARGET_SHARE = 0.25
DEFAULT_REVIEW_WEEKS = 8
# Next year's goal is only worth setting when the year is nearly over.
NEXT_YEAR_PLANNING_DAYS = 60
NEXT_YEAR_TITLES = {
    "ride_km": "Ride {target} km in {year}",
    "run_km": "Run {target} km in {year}",
    "strength_sessions": "{target} strength sessions in {year}",
    "zone2_hours": "{target} zone 2 hours in {year}",
    "activities_count": "{target} activities in {year}",
}
DECISION_DEFAULT_DAYS = {"snoozed": 28, "kept": 56, "applied": 0}
MAINTENANCE_PURPOSE = re.compile(r"\b(maint\w*|keep\w*|hold\w*|preserv\w*|retain\w*)\b", re.IGNORECASE)

# label, needs attention, urgency (lower sorts first)
VERDICTS: dict[str, tuple[str, bool, int]] = {
    "done": ("Done", True, 1),
    "out_of_reach": ("Out of reach", True, 2),
    "crowding_out": ("Crowding out", True, 3),
    "review_due": ("Review due", True, 4),
    "too_easy": ("Too easy", True, 5),
    "plateaued": ("Plateaued", True, 6),
    "inconsistent": ("Inconsistent", True, 7),
    "anchor_under_pressure": ("Anchor under pressure", False, 8),
    "season_change": ("Season changing", False, 9),
    "on_track_unproven": ("On track, unproven", False, 9),
    "productive": ("Productive", False, 10),
    "anchor_steady": ("Anchor steady", False, 11),
    "insufficient_evidence": ("Too early to judge", False, 12),
    "not_applicable": ("Tracked by readiness", False, 13),
}


def _format(value: Optional[float], unit: str = "") -> str:
    if value is None:
        return "–"
    number = f"{round(value):,}" if abs(value) >= 100 else f"{round(value, 1):g}"
    return f"{number} {unit}".strip()


def calibrated_target(metric_type: str, value: float) -> float:
    """A round, reachable number near ``value`` (counts round up to whole sessions)."""
    if metric_type in {"strength_sessions", "quality_sessions", "activities_count"}:
        return float(max(1, ceil(value - 1e-9)))
    for threshold, step in ((1000, 100), (100, 10), (10, 5)):
        if value >= threshold:
            return float(round(value / step) * step)
    return max(0.5, round(value * 2) / 2)


def _completed_entries(history: dict) -> list[dict]:
    return [entry for entry in history.get("entries", []) if not entry.get("partial")]


def _hit_rate_change(history: dict) -> Optional[float]:
    entries = _completed_entries(history)
    if history.get("kind") != "recurring" or len(entries) < MIN_VERDICT_PERIODS:
        return None
    half = len(entries) // 2
    earlier = sum(entry["hit"] for entry in entries[:half]) / half
    later = sum(entry["hit"] for entry in entries[-half:]) / half
    return round(later - earlier, 2)


def _outcome_state(goal: dict) -> dict[str, Any]:
    outcomes = goal.get("outcomes") or {}
    signals = outcomes.get("signals") or []
    if not signals:
        return {"state": "none_linked", "signals": [], "lines": []}
    judged = [signal for signal in signals if signal["trend"] != "insufficient"]
    lines = []
    for signal in signals:
        if signal["trend"] == "insufficient":
            lines.append(f"{signal['label']}: not enough data yet.")
        else:
            change = f" ({signal['change_pct']:+g}%)" if signal.get("change_pct") is not None else ""
            word = {"improving": "improving", "flat": "holding", "declining": "declining"}[signal["trend"]]
            lines.append(f"{signal['label']}: {word}{change}.")
    if not judged:
        state = "insufficient"
    elif any(signal["trend"] == "improving" for signal in judged):
        state = "improving"
    elif any(signal["trend"] == "declining" for signal in judged):
        state = "declining"
    else:
        state = "holding"
    return {"state": state, "signals": signals, "lines": lines}


def _worsening_costs(costs: list[dict]) -> list[dict]:
    return [cost for cost in costs if not cost.get("stale") and cost.get("trend") == "declining"]


def _is_maintenance(goal: dict) -> bool:
    return bool(goal.get("purpose") and MAINTENANCE_PURPOSE.search(goal["purpose"]))


def _goal_path(goal: dict) -> str:
    return f"/goals/{goal['id']}"


def _action(action_type: str, label: str, *, method: Optional[str] = None, path: Optional[str] = None,
            body: Optional[dict] = None, detail: Optional[str] = None) -> dict[str, Any]:
    return {"type": action_type, "label": label, "method": method, "path": path, "body": body, "detail": detail}


def _status_action(goal: dict, status: str, label: str, reason: str) -> dict[str, Any]:
    return _action(status_action_type(status), label, method="POST", path=f"{_goal_path(goal)}/status",
                   body={"status": status, "reason": reason})


def status_action_type(status: str) -> str:
    return {"completed": "complete", "retired": "retire", "paused": "pause", "active": "reactivate"}[status]


def _target_action(goal: dict, action_type: str, target: float) -> dict[str, Any]:
    unit = goal.get("unit") or ""
    verb = "Raise" if action_type == "raise_target" else "Lower"
    return _action(action_type, f"{verb} target to {_format(target, unit)}", method="PATCH", path=_goal_path(goal),
                   body={"target_value": target})


def _worth_lowering(goal: dict, lowered: float) -> bool:
    current = float(goal.get("target_value") or 0)
    return 0 < lowered < current and lowered >= current * MIN_LOWERED_TARGET_SHARE


def _review_action(goal: dict, today: date, weeks: int = DEFAULT_REVIEW_WEEKS) -> dict[str, Any]:
    review_on = (today + timedelta(weeks=weeks)).isoformat()
    return _action("set_review", f"Review again in {weeks} weeks", method="PATCH", path=_goal_path(goal),
                   body={"review_on": review_on})


def _season_action(goal: dict, today: date, off_months: list[int]) -> Optional[dict[str, Any]]:
    season_end = off_season_end(today, off_months)
    if season_end is None:
        return None
    return _action("set_season", f"Limit it to the off season (ends {season_end.day} {season_end.strftime('%b')})",
                   method="PATCH", path=_goal_path(goal), body={"season_end": season_end.isoformat()})


def _effective_stats(goal: dict, history: dict, today: date) -> tuple[dict, list[str], Optional[tuple]]:
    """Stats to judge a recurring goal by, allowing for a change of season.

    Returns (stats, evidence lines, season_change result). When the coming
    season differs from the one the recent weeks come from, the same season
    last year is the yardstick; without enough of it there is no fair verdict.
    """
    stats = history.get("stats") or {}
    season = history.get("season") or {}
    if not season.get("shift"):
        return stats, [], None
    label = season["upcoming_label"]
    reference = season.get("reference")
    noun = "weeks" if history.get("period_type") == "week" else "months"
    if not reference or reference["periods"] < MIN_REVIEW_PERIODS:
        check = date.fromisoformat(season["next_change"]) + timedelta(weeks=4)
        weeks = max(1, round((check - today).days / 7))
        line = f"The {label} starts {season['next_change']}; there is not enough {label} history to judge this target against."
        return stats, [line], ("season_change", [line], [_review_action(goal, today, weeks)])
    unit = history.get("unit") or ""
    line = (
        f"Recent {noun} are from a different season. Judged against last {label} ({reference['label']}): "
        f"hit {reference['hit_count']} of {reference['periods']} {noun}, median {_format(reference['median'], unit)}."
    )
    return {**stats, **{key: reference[key] for key in ("periods", "hit_count", "hit_rate", "median", "p75", "margin")}}, [line], None


def next_year_planning_open(today: date) -> bool:
    return (date(today.year, 12, 31) - today).days <= NEXT_YEAR_PLANNING_DAYS


def _next_year_draft(goal: dict, stats: dict, today: date) -> dict[str, Any]:
    projected = stats.get("projected_total") or stats.get("year_to_date") or goal.get("target_value") or 0
    target = calibrated_target(goal["metric_type"], projected * CALIBRATION_PERCENTILE_UPLIFT)
    next_year = today.year + 1
    template = NEXT_YEAR_TITLES.get(goal["metric_type"], "{target} in {year}")
    title = template.format(target=_format(target), year=next_year)
    return {
        "title": title,
        "period_type": "year",
        "goal_family": goal.get("goal_family"),
        "metric_type": goal["metric_type"],
        "activity_type": goal.get("activity_type"),
        "target_value": target,
        "start_date": date(next_year, 1, 1).isoformat(),
        "end_date": date(next_year, 12, 31).isoformat(),
        "purpose": goal.get("purpose"),
        "commitment": goal.get("commitment"),
    }


def _month_name(year_month: Optional[str]) -> str:
    return datetime.strptime(year_month, "%Y-%m").strftime("%B") if year_month else "this period"


def _history_lines(goal: dict, history: dict) -> list[str]:
    stats = history.get("stats") or {}
    unit = history.get("unit") or ""
    if history.get("kind") == "yearly":
        if stats.get("reached_in"):
            return [f"Target reached in {_month_name(stats['reached_in'])}; {_format(stats.get('year_to_date'), unit)} so far this year."]
        return [
            f"{_format(stats.get('year_to_date'), unit)} of {_format(history.get('target'), unit)} so far; "
            f"{_format(stats.get('remaining'), unit)} left with {stats.get('days_left')} days to go.",
            f"Needs {_format(stats.get('required_rate_per_week'), unit)}/week; recent pace {_format(stats.get('recent_rate_per_week'), unit)}/week, "
            f"best 4 weeks {_format(stats.get('best_4_week_rate'), unit)}/week.",
        ]
    noun = "weeks" if history.get("period_type") == "week" else "months"
    return [
        f"Hit {stats.get('hit_count')} of the last {stats.get('periods')} {noun}; "
        f"median {_format(stats.get('median'), unit)} against a target of {_format(history.get('target'), unit)}."
    ]


def _crowding(goal: dict, others: list[dict], costs: list[dict]) -> Optional[str]:
    stats = (goal.get("history") or {}).get("stats") or {}
    rising = (stats.get("trend_slope_pct") or 0) >= CROWDING_VOLUME_RISE_PCT
    if not rising:
        return None
    for other in others:
        change = _hit_rate_change(other.get("history") or {})
        if change is not None and change <= -CROWDING_HIT_RATE_DROP:
            return f"Volume here is rising while '{other['title']}' fell from hitting its target {round(-change * 100)} points more often."
    worsening = _worsening_costs(costs)
    if worsening:
        labels = ", ".join(cost["label"].lower() for cost in worsening)
        return f"Volume here is rising while {labels} {'is' if len(worsening) == 1 else 'are'} getting worse."
    return None


def _confidence(history: dict, outcome: dict) -> str:
    periods = (history.get("stats") or {}).get("periods") or 0
    if history.get("kind") == "yearly":
        periods = MIN_VERDICT_PERIODS if len(_completed_entries(history)) >= 3 else 0
    if periods >= MIN_VERDICT_PERIODS and outcome["state"] in {"improving", "holding", "declining"}:
        return "high"
    if periods >= MIN_VERDICT_PERIODS:
        return "medium"
    return "low"


def _base_verdict(
    goal: dict,
    history: dict,
    outcome: dict,
    others: list[dict],
    costs: list[dict],
    today: date,
    off_months: list[int],
) -> tuple[str, list[str], list[dict]]:
    """Pick the verdict for a flexible goal. Returns (verdict, extra evidence, actions)."""
    stats = history.get("stats") or {}
    metric_type = goal["metric_type"]

    if history.get("kind") == "yearly":
        if stats.get("remaining") == 0:
            complete = _status_action(goal, "completed", "Mark completed", f"Target reached in {_month_name(stats.get('reached_in'))}")
            if not next_year_planning_open(today):
                return "done", [], [complete]
            draft = _next_year_draft(goal, stats, today)
            unit = goal.get("unit") or ""
            basis = (
                f"Your recent pace projects about {_format(stats.get('projected_total'), unit)} this year; "
                f"the draft adds {round((CALIBRATION_PERCENTILE_UPLIFT - 1) * 100)}%. Edit it before saving."
            )
            # Creating the next goal first: completing removes this one from review.
            return "done", [], [
                _action("create_next", f"Start '{draft['title']}'", method="POST", path="/goals", body=draft, detail=basis),
                complete,
            ]
        required = stats.get("required_rate_per_week") or 0
        best = stats.get("best_4_week_rate") or 0
        if required > OUT_OF_REACH_RATE_MULTIPLIER * best:
            weeks_left = (stats.get("days_left") or 0) / 7
            realistic = (stats.get("year_to_date") or 0) + (stats.get("recent_rate_per_week") or 0) * weeks_left * 1.1
            actions = [_status_action(goal, "retired", "Retire it", "Out of reach at the current training mix")]
            if realistic > (stats.get("year_to_date") or 0):
                actions.insert(0, _target_action(goal, "lower_target", calibrated_target(metric_type, realistic)))
            return "out_of_reach", [f"The pace it needs is more than {OUT_OF_REACH_RATE_MULTIPLIER:g}× your best 4 weeks."], actions
        # The projection already accounts for the coming season's usual pace.
        if (stats.get("projected_total") or 0) < float(goal.get("target_value") or 0):
            return "inconsistent", ["Reachable, but only above your usual pace for the rest of the year."], [_review_action(goal, today, 4)]
        return _outcome_verdict(goal, outcome, today)

    stats, season_lines, season_change = _effective_stats(goal, history, today)
    if season_change:
        return season_change
    verdict, extra, actions = _recurring_verdict(goal, history, stats, outcome, others, costs, today, off_months)
    return verdict, [*season_lines, *extra], actions


def _started_lines(goal: dict, since_created: Optional[int], history: dict) -> list[str]:
    noun = "week" if history.get("period_type") == "week" else "month"
    done = since_created or 0
    return [f"Just started: {done} full {noun}{'' if done == 1 else 's'} since {goal['title']} was set. A fair verdict needs a few more."]


def _recurring_verdict(
    goal: dict,
    history: dict,
    stats: dict,
    outcome: dict,
    others: list[dict],
    costs: list[dict],
    today: date,
    off_months: list[int],
) -> tuple[str, list[str], list[dict]]:
    metric_type = goal["metric_type"]
    periods = stats.get("periods") or 0
    if periods < MIN_REVIEW_PERIODS:
        return "insufficient_evidence", [], [_review_action(goal, today, 4)]
    hit_rate = stats.get("hit_rate") or 0
    # Weeks before the goal existed prove nothing about a target that is meant to
    # change behaviour, so failing verdicts wait for the goal's own track record.
    since_created = history.get("stats", {}).get("periods_since_created")
    started_lines = _started_lines(goal, since_created, history)

    if periods >= MIN_VERDICT_PERIODS and hit_rate < OUT_OF_REACH_HIT_RATE:
        if since_created is not None and since_created < MIN_VERDICT_PERIODS:
            return "insufficient_evidence", started_lines, [_review_action(goal, today, MIN_VERDICT_PERIODS - since_created)]
        median_target = calibrated_target(metric_type, max(stats.get("median") or 0, stats.get("p75") or 0))
        actions = [_status_action(goal, "retired", "Retire it", "Rarely reached at the current training mix")]
        if _worth_lowering(goal, median_target):
            actions.insert(0, _target_action(goal, "lower_target", median_target))
        return "out_of_reach", [], actions

    crowding = _crowding(goal, others, costs)
    if crowding:
        return "crowding_out", [crowding], [_review_action(goal, today, 4), _status_action(goal, "paused", "Pause it", "Crowding out other training")]

    if periods >= MIN_VERDICT_PERIODS and hit_rate >= TOO_EASY_HIT_RATE and (stats.get("margin") or 0) >= TOO_EASY_MARGIN:
        raised = calibrated_target(metric_type, (stats.get("p75") or 0) * CALIBRATION_PERCENTILE_UPLIFT)
        actions = [_target_action(goal, "raise_target", raised)]
        season_action = _season_action(goal, today, off_months) if goal.get("period_type") == "week" and not goal.get("season_end") else None
        if season_action:
            actions.append(season_action)
        actions.append(_status_action(goal, "retired", "Retire it — you do this anyway", "Habit is established without the goal"))
        return "too_easy", [f"You typically do {stats.get('margin'):g}× the target, so it no longer changes what you do."], actions

    if hit_rate < ON_TRACK_HIT_RATE:
        if since_created is not None and since_created < MIN_REVIEW_PERIODS:
            return "insufficient_evidence", started_lines, [_review_action(goal, today, MIN_REVIEW_PERIODS - since_created)]
        lowered = calibrated_target(metric_type, stats.get("median") or 0)
        actions = [_review_action(goal, today, 4)]
        if _worth_lowering(goal, lowered):
            actions.insert(0, _target_action(goal, "lower_target", lowered))
        return "inconsistent", [], actions

    if hit_rate >= PLATEAU_HIT_RATE or outcome["state"] == "improving":
        return _outcome_verdict(goal, outcome, today)
    return "on_track_unproven", [], [_review_action(goal, today)]


def _outcome_verdict(goal: dict, outcome: dict, today: date) -> tuple[str, list[str], list[dict]]:
    state = outcome["state"]
    if state == "improving" or (state == "holding" and _is_maintenance(goal)):
        return "productive", [], []
    if state in {"holding", "declining"}:
        return "plateaued", ["You hit the target, but the result it should improve isn't moving."], [
            _review_action(goal, today),
            _status_action(goal, "paused", "Pause it", "Target is met but the outcome is not moving"),
        ]
    return "on_track_unproven", [], [_review_action(goal, today)]


def _anchor_verdict(goal: dict, history: dict, outcome: dict, today: date) -> tuple[str, list[str], list[dict], str]:
    stats, season_lines, _ = _effective_stats(goal, history, today) if history.get("kind") == "recurring" else (history.get("stats") or {}, [], None)
    hit_rate = stats.get("hit_rate")
    if history.get("kind") == "yearly":
        under_pressure = (stats.get("required_rate_ratio") or 0) > 1.1
    else:
        under_pressure = hit_rate is not None and hit_rate < ON_TRACK_HIT_RATE
    state = outcome["state"]
    maintenance = _is_maintenance(goal)
    if state == "improving" or (state == "holding" and maintenance):
        purpose_status = "served"
    elif state == "declining" or (state == "holding" and not maintenance):
        purpose_status = "at_risk" if state == "declining" else "not_improving"
    else:
        purpose_status = "unknown"

    extra = list(season_lines)
    purpose = (goal.get("purpose") or "").rstrip(".")
    if purpose_status == "served":
        purpose_note = f" ({purpose})" if purpose else ""
        movement = "improving" if state == "improving" else "holding"
        extra.append(f"Purpose served{purpose_note}: the linked outcome is {movement}.")
    elif purpose_status == "at_risk":
        extra.append("The outcome this goal protects is declining; the missed weeks may be starting to cost you.")
    elif purpose_status == "unknown":
        extra.append("Not enough outcome data yet to tell whether the purpose is served.")

    actions = [_action("keep", "Keep the standard as is")]
    if under_pressure:
        noun = "sessions" if goal["metric_type"] in {"strength_sessions", "activities_count"} else "work"
        actions.append(_action(
            "plan_support",
            "Protect the slots in your weekly plan",
            detail=f"Put the {noun} in the plan first; a short, minimum-effective session still counts toward the standard.",
        ))
    actions.append(_review_action(goal, today))
    verdict = "anchor_under_pressure" if under_pressure else "anchor_steady"
    return verdict, extra, actions, purpose_status


def build_goal_verdict(
    goal: dict,
    *,
    others: list[dict],
    costs: list[dict],
    decision: Optional[sqlite3.Row] = None,
    today: Optional[date] = None,
    off_season_months: Optional[list[int]] = None,
) -> dict[str, Any]:
    """Verdict for a goal that already carries ``history`` and ``outcomes``."""
    current = today or datetime.now().date()
    off_months = list(DEFAULT_OFF_SEASON_MONTHS) if off_season_months is None else off_season_months
    history = goal.get("history") or {}
    outcome = _outcome_state(goal)
    purpose_status = None

    yearly_done = history.get("kind") == "yearly" and (history.get("stats") or {}).get("remaining") == 0
    if not history.get("available"):
        verdict, extra, actions = "not_applicable", [history.get("reason") or "No period history for this goal."], []
    elif goal.get("commitment") == "anchor" and not yearly_done:
        verdict, extra, actions, purpose_status = _anchor_verdict(goal, history, outcome, current)
    else:
        verdict, extra, actions = _base_verdict(goal, history, outcome, others, costs, current, off_months)

    review_on = goal.get("review_on")
    if verdict not in {"done", "out_of_reach"} and (goal.get("season_ended") or (review_on and review_on <= current.isoformat())):
        extra = ["Your season has ended." if goal.get("season_ended") else f"You asked to review this goal on {review_on}.", *extra]
        actions = [
            _action("keep", "Keep it going", method="PATCH", path=_goal_path(goal), body={"review_on": None, "season_end": None}),
            _status_action(goal, "paused", "Pause it", "Season or review period ended"),
            _status_action(goal, "retired", "Retire it", "Season or review period ended"),
        ]
        verdict = "review_due"

    label, needs_attention, urgency = VERDICTS[verdict]
    evidence = [*(_history_lines(goal, history) if history.get("available") else []), *extra, *outcome["lines"]]
    worsening = _worsening_costs(costs)
    if worsening and verdict not in {"done", "not_applicable"}:
        evidence.append("Recovery cost: " + ", ".join(f"{cost['label']} {cost['change_pct']:+g}%" for cost in worsening) + " vs baseline.")

    snoozed_until = None
    if decision is not None and decision["verdict"] == verdict and decision["until"] and decision["until"] > current.isoformat():
        snoozed_until = decision["until"]
    # A future review date is the athlete's own "look again then"; only a finished goal interrupts it.
    if verdict != "done" and review_on and review_on > current.isoformat():
        snoozed_until = max(snoozed_until or "", review_on)

    return {
        "verdict": verdict,
        "label": label,
        "headline": _headline(goal, verdict, history, outcome, purpose_status),
        "needs_attention": needs_attention and snoozed_until is None,
        "urgency": urgency,
        "confidence": _confidence(history, outcome) if history.get("available") else "low",
        "purpose_status": purpose_status,
        "evidence": evidence,
        "actions": actions,
        "snoozed_until": snoozed_until,
        "last_decision": dict(decision) if decision is not None else None,
    }


def _headline(goal: dict, verdict: str, history: dict, outcome: dict, purpose_status: Optional[str]) -> str:
    stats = history.get("stats") or {}
    title = goal["title"]
    if verdict == "done":
        return f"{title} is achieved. Close it and set the next target."
    if verdict == "out_of_reach":
        return f"{title} is out of reach at your current training mix."
    if verdict == "crowding_out":
        return f"{title} may be squeezing out other training."
    if verdict == "review_due":
        return f"Time to decide whether {title} still earns its place."
    if verdict == "too_easy":
        return f"{title} no longer challenges you: you beat it {round((stats.get('hit_rate') or 0) * 100)}% of the time."
    if verdict == "plateaued":
        return f"{title} is being hit, but the result it should improve is not moving."
    if verdict == "inconsistent":
        season = history.get("season") or {}
        if season.get("shift") and season.get("reference"):
            return f"Last {season['upcoming_label']} you reached {title} less often than not."
        return f"{title} is hit less often than not."
    if verdict in {"anchor_under_pressure", "anchor_steady"}:
        rate = stats.get("hit_rate")
        cadence = f"Hit {round(rate * 100)}% of weeks" if rate is not None and history.get("kind") == "recurring" else "Tracking"
        purpose = {
            "served": "and its purpose is served. It stays your standard.",
            "at_risk": "and the outcome it protects is slipping.",
            "not_improving": "and the linked outcome is flat.",
            "unknown": "; the outcome evidence is still thin.",
        }.get(purpose_status or "unknown")
        return f"{cadence} {purpose}".replace(" ;", ";")
    if verdict == "productive":
        return f"{title} is working: you hit it and the result is {'improving' if outcome['state'] == 'improving' else 'holding'}."
    if verdict == "on_track_unproven":
        season = history.get("season") or {}
        reference = season.get("reference") if season.get("shift") else None
        if reference:
            noun = "weeks" if history.get("period_type") == "week" else "months"
            return (
                f"{title} is a realistic {season['upcoming_label']} target: last {season['upcoming_label']} you hit it "
                f"{reference['hit_count']} of {reference['periods']} {noun}. Outcome data is still too thin to prove it pays off."
            )
        return f"{title} is being hit; there is not enough outcome data yet to prove it pays off."
    if verdict == "insufficient_evidence":
        return f"{title} is too new to judge."
    if verdict == "season_change":
        return f"The season is changing; {title} will be judged once there is enough history from this season."
    return f"{title} is reviewed through its readiness summary."


def _scheduled_goal_review(goal: dict, decision: Optional[sqlite3.Row], current: date) -> dict[str, Any]:
    """A paused goal whose review date arrived, e.g. next year's goal created early."""
    label, needs_attention, urgency = VERDICTS["review_due"]
    snoozed_until = None
    if decision is not None and decision["verdict"] == "review_due" and decision["until"] and decision["until"] > current.isoformat():
        snoozed_until = decision["until"]
    return {
        "verdict": "review_due",
        "label": label,
        "headline": f"{goal['title']} is paused and was due back on {goal['review_on']}.",
        "needs_attention": needs_attention and snoozed_until is None,
        "urgency": urgency,
        "confidence": "high",
        "purpose_status": None,
        "evidence": [goal["status_reason"]] if goal.get("status_reason") else [],
        "actions": [
            _status_action(goal, "active", "Start it now", "Scheduled start"),
            _status_action(goal, "retired", "Retire it", "No longer planned"),
        ],
        "snoozed_until": snoozed_until,
        "last_decision": dict(decision) if decision is not None else None,
    }


def _review_item(goal: dict, review: dict) -> dict[str, Any]:
    return {
        "goal_id": goal["id"],
        "title": goal["title"],
        "lifecycle_status": goal.get("lifecycle_status"),
        "commitment": goal.get("commitment"),
        "purpose": goal.get("purpose"),
        "period_type": goal.get("period_type"),
        "metric_type": goal.get("metric_type"),
        "unit": goal.get("unit"),
        "target_value": goal.get("target_value"),
        "season_end": goal.get("season_end"),
        "review_on": goal.get("review_on"),
        "review": review,
    }


def build_goal_review(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, Any]:
    current = today or datetime.now().date()
    goals = list_goals_data(conn, lifecycle_status="active", limit=48)
    goals = attach_goal_outcomes(conn, attach_goal_histories(conn, goals, today=current), today=current)
    costs = list(build_cost_signals(conn, today=current).values())
    decisions = latest_goal_review_decisions(conn)
    off_months = get_athlete_profile_for_conn(conn)["off_season_months"]

    reviewed = []
    for goal in goals:
        others = [other for other in goals if other["id"] != goal["id"]]
        review = build_goal_verdict(
            goal, others=others, costs=costs, decision=decisions.get(goal["id"]), today=current, off_season_months=off_months,
        )
        reviewed.append(_review_item(goal, review))
    for goal in list_goals_data(conn, lifecycle_status="paused", limit=48):
        if goal.get("review_on") and goal["review_on"] <= current.isoformat():
            reviewed.append(_review_item(goal, _scheduled_goal_review(goal, decisions.get(goal["id"]), current)))
    reviewed.sort(key=lambda item: (not item["review"]["needs_attention"], item["review"]["urgency"], item["title"]))
    return {
        "generated_on": current.isoformat(),
        "attention_count": sum(1 for item in reviewed if item["review"]["needs_attention"]),
        "costs": costs,
        "portfolio": build_portfolio_check(conn, goals, today=current, off_season_months=off_months),
        "goals": reviewed,
    }


def record_review_decision(
    conn: sqlite3.Connection,
    goal_id: int,
    *,
    verdict: str,
    decision: str,
    days: Optional[int] = None,
    note: Optional[str] = None,
    today: Optional[date] = None,
) -> dict[str, Any]:
    get_goal_data(conn, goal_id)  # raises LookupError for unknown goals
    if verdict not in VERDICTS:
        raise ValueError(f"Unknown verdict '{verdict}'.")
    if decision not in DECISION_DEFAULT_DAYS:
        raise ValueError(f"decision must be one of: {', '.join(DECISION_DEFAULT_DAYS)}.")
    length = DECISION_DEFAULT_DAYS[decision] if days is None else int(days)
    if length < 0 or length > 365:
        raise ValueError("days must be between 0 and 365.")
    current = today or datetime.now().date()
    until = (current + timedelta(days=length)).isoformat() if length else None
    note = (note or "").strip()[:280] or None
    decision_id = insert_goal_review_decision(conn, goal_id, verdict, decision, until, note)
    conn.commit()
    return {"id": decision_id, "goal_id": goal_id, "verdict": verdict, "decision": decision, "until": until, "note": note}
