"""Evidence-based goal drafts. Reading suggestions never changes an athlete's goals."""

import sqlite3
from datetime import date, datetime, timedelta
from typing import Optional

from ..repositories.goals import insert_goal_suggestion_decision, latest_goal_suggestion_decisions
from .goal_history import _percentile, build_goal_period_history, recurring_period_windows
from .goal_outcomes import attach_goal_outcomes, build_cost_signals
from .goal_review import (
    CALIBRATION_PERCENTILE_UPLIFT,
    _next_year_draft,
    build_goal_verdict,
    calibrated_target,
    next_year_planning_open,
)
from .goals import goal_value_for_window
from .power_trends import get_cycling_power_trends_data
from .seasons import SEASON_LABELS, next_season_change, season_for
from .settings import get_athlete_profile_for_conn, get_modality_restrictions_for_conn, modality_for_goal

MAX_SUGGESTIONS = 3
SEASON_BOUNDARY_DAYS = 21
MIN_HISTORY_WEEKS = 4
NEGLECTED_DAYS = 56
REGULAR_USE_WEEKS = 8
MIN_REGULAR_WEEKS = 6
DEFAULT_DISMISS_DAYS = 28
MAX_DISMISS_DAYS = 365
BENCHMARK_LOOKBACK_DAYS = 180
QUALITY_VERDICTS = {"plateaued", "too_easy", "on_track_unproven"}
MODALITY_METRICS = {"ride": ("ride_km", "Ride"), "run": ("run_km", "Run"), "strength": ("strength_sessions", "WeightTraining")}


def _suggestion(source: str, identity: str, draft: dict, rationale: str, evidence: list[str]) -> dict:
    return {"key": f"{source}:{identity}", "title": draft["title"], "rationale": rationale,
            "evidence": evidence, "draft": draft, "source": source}


def _weekly_draft(metric: str, activity: str, target: float, title: str, start: date, end: date) -> dict:
    return {"title": title, "goal_family": "process" if metric.endswith("sessions") else "accumulation",
            "metric_type": metric, "period_type": "week", "activity_type": activity,
            "target_value": target, "start_date": start.isoformat(), "end_date": end.isoformat(),
            "season_end": end.isoformat(), "review_on": (start + timedelta(weeks=4)).isoformat(),
            "commitment": "flexible"}


def _reference(conn: sqlite3.Connection, goal: dict, today: date, off_months: list[int],
               season: Optional[str] = None) -> dict:
    history = build_goal_period_history(conn, goal, today=today, periods=52 if season else 12,
                                        off_season_months=off_months)
    entries = [entry for entry in history.get("entries", []) if not entry.get("partial")]
    if season:
        entries = [entry for entry in entries if season_for(
            date.fromisoformat(entry["period_start"]) + timedelta(days=3), off_months) == season]
    values = [entry["value"] for entry in entries]
    return {"periods": len(values), "p75": _percentile(values, 0.75)}


def replace_completed(goal: dict, today: date) -> Optional[dict]:
    if (goal.get("lifecycle_status") != "completed" or goal.get("period_type") != "year"
            or goal.get("goal_family") != "accumulation" or goal.get("commitment") == "anchor"):
        return None
    # Old completed years must not turn this year's activity into their replacement target.
    if not str(goal.get("end_date") or "").startswith(str(today.year)):
        return None
    if not next_year_planning_open(today):
        return None
    stats = (goal.get("history") or {}).get("stats") or {}
    if not stats.get("year_to_date"):
        return None
    draft = _next_year_draft(goal, stats, today)
    basis = "Season-aware" if stats.get("projection_basis") == "seasonal" else "Recent-pace"
    return _suggestion("replace_completed", f"{goal['id']}:{today.year + 1}", draft,
                       "Carry the completed goal into next year with a target based on your riding or running history.",
                       [f"Completed: {goal['title']}.",
                        f"{basis} projection: {stats.get('projected_total') or stats['year_to_date']:g}; the draft adds 5% before rounding."])


def plateau_to_quality(conn: sqlite3.Connection, goal: dict, today: date, off_months: list[int]) -> Optional[dict]:
    if (goal.get("commitment") == "anchor" or goal.get("metric_type") not in {"ride_km", "zone2_hours"}
            or (goal.get("review") or {}).get("verdict") not in QUALITY_VERDICTS
            or (goal["metric_type"] == "zone2_hours" and goal.get("activity_type") not in {"Ride", "VirtualRide"})):
        return None
    probe = {"goal_family": "process", "metric_type": "quality_sessions", "period_type": "week", "target_value": 1, "activity_type": "Ride"}
    change = next_season_change(today, off_months)
    changing = change and (change - today).days <= SEASON_BOUNDARY_DAYS
    reference = _reference(conn, probe, today, off_months, season_for(change, off_months) if changing else None)
    if reference["periods"] < MIN_HISTORY_WEEKS:
        return None
    target = calibrated_target("quality_sessions", (reference["p75"] or 0) * CALIBRATION_PERCENTILE_UPLIFT)
    start = change if changing else today
    end = (next_season_change(start, off_months) or (start + timedelta(weeks=12))) - timedelta(days=1)
    draft = _weekly_draft("quality_sessions", "Ride", target, f"{target:g} quality ride{'s' if target != 1 else ''} per week", start, end)
    draft["purpose"] = "Improve sustained cycling power with structured quality sessions"
    return _suggestion("plateau_to_quality", str(goal["id"]), draft,
                       "Try a structured quality target to give established volume a purpose. Review how it fits alongside your current goal.",
                       [f"{goal['title']}: {goal['review']['verdict'].replace('_', ' ')}.",
                        f"{'Same-season' if changing else 'Recent'} quality history: p75 {reference['p75']:g} sessions across {reference['periods']} weeks.",
                        "Count tempo, interval, sweet spot or race-specific rides; unlabelled rides need 20 measured minutes at 88% FTP or above. Use the cycling workout library for structured sessions."])


def profile_weakness(profile: dict, today: date) -> Optional[dict]:
    categories = [(name, entry) for name, entry in profile.get("category_levels", {}).items()
                  if entry and entry.get("level") is not None and entry.get("limiting_duration_seconds")]
    if not categories:
        return None
    name, category = min(categories, key=lambda item: (item[1]["level"], item[0]))
    seconds = category["limiting_duration_seconds"]
    earliest = (today - timedelta(days=BENCHMARK_LOOKBACK_DAYS)).isoformat()
    values = [float(effort["watts"]) for month in profile.get("monthly", []) for effort in month.get("efforts", [])
              if effort.get("duration_seconds") == seconds and earliest <= str(effort.get("date") or "")[:10] <= today.isoformat()]
    if len(values) < 3:
        return None
    p75 = _percentile(values, 0.75)
    target = calibrated_target("benchmark_power", p75 * CALIBRATION_PERCENTILE_UPLIFT)
    recorded = [float(record["watts"]) for record in profile.get("records", [])
                if record.get("duration_seconds") == seconds]
    # Benchmark progress uses recorded bests, so an already achieved target adds no objective.
    if target <= max([*values, *recorded]):
        return None
    minutes = seconds / 60
    draft = {"title": f"Build {name.lower()} power: {target:g} W for {minutes:g} min",
             "goal_family": "benchmark", "metric_type": "benchmark_power", "period_type": "month",
             "activity_type": "Ride", "target_value": target,
             "target_config": {"duration_min": minutes, "target_watts": target, "measurement": "power_stream"},
             "start_date": today.isoformat(), "end_date": (today + timedelta(weeks=12)).isoformat(),
             "purpose": "Improve the least-developed recorded power category", "commitment": "flexible"}
    return _suggestion("profile_weakness", f"{name.lower()}:{seconds}", draft,
                       "Explore your weakest recorded power category during normal rides; no dedicated FTP test is needed.",
                       [f"{name}: {category['name']} (level {category['level']}).",
                        f"{len(values)} monthly bests in the last six months: p75 {p75:g} W, plus 5% before rounding.",
                        "Category levels reflect recorded efforts and available coverage, not a diagnosis of ability."])


def season_template(conn: sqlite3.Connection, today: date, off_months: list[int]) -> list[dict]:
    change = next_season_change(today, off_months)
    if not change or (change - today).days > SEASON_BOUNDARY_DAYS:
        return []
    season = season_for(change, off_months)
    end = next_season_change(change, off_months) - timedelta(days=1)
    result = []
    for modality in (("strength", "ride") if season == "off" else ("ride", "run")):
        metric, activity = MODALITY_METRICS[modality]
        probe = _weekly_draft(metric, activity, 1, "Season history", today, end)
        reference = _reference(conn, probe, today, off_months, season)
        if reference["periods"] < MIN_HISTORY_WEEKS or not reference["p75"]:
            continue
        target = calibrated_target(metric, reference["p75"] * CALIBRATION_PERCENTILE_UPLIFT)
        unit = "sessions" if modality == "strength" else "km"
        draft = _weekly_draft(metric, activity, target, f"{SEASON_LABELS[season].capitalize()}: {target:g} {unit} of {modality} per week", change, end)
        result.append(_suggestion("season_template", f"{change.isoformat()}:{modality}", draft,
                                  f"Start the {SEASON_LABELS[season]} with a target grounded in the same season's history.",
                                  [f"Season starts {change.isoformat()} and ends {end.isoformat()}.",
                                   f"Same-season p75: {reference['p75']:g} {unit} across {reference['periods']} weeks; plus 5% before rounding."]))
    return result


def neglected_modality(conn: sqlite3.Connection, today: date) -> list[dict]:
    result = []
    for modality, (metric, activity) in MODALITY_METRICS.items():
        types = {"ride": ("Ride", "VirtualRide"), "run": ("Run",), "strength": ("WeightTraining",)}[modality]
        placeholders = ','.join('?' for _ in types)
        row = conn.execute(f"SELECT MAX(substr(date, 1, 10)) AS last_day FROM activities WHERE type IN ({placeholders}) AND date < ?",
                           (*types, (today + timedelta(days=1)).isoformat())).fetchone()
        if not row["last_day"]:
            continue
        last = date.fromisoformat(row["last_day"])
        if (today - last).days < NEGLECTED_DAYS:
            continue
        # Include the final week of regular use, then compare complete weeks before it.
        reference_end = last + timedelta(days=7 - last.weekday())
        windows, _ = recurring_period_windows("week", REGULAR_USE_WEEKS, reference_end)
        probe = {"goal_family": "process", "metric_type": "strength_sessions" if modality == "strength" else "activities_count", "activity_type": activity}
        values = [goal_value_for_window(conn, probe, start_date=start.isoformat(), end_date=end.isoformat()) for start, end in windows]
        if sum(value > 0 for value in values) < MIN_REGULAR_WEEKS:
            continue
        # Restarting after a long break is maintenance: cap the historical target at one session.
        target = min(1, calibrated_target(probe["metric_type"], _percentile(values, 0.75) * CALIBRATION_PERCENTILE_UPLIFT))
        draft = _weekly_draft(probe["metric_type"], activity, target, f"Optional: one {modality} session per week", today, today + timedelta(weeks=4))
        draft["purpose"] = f"Maintain a small amount of {modality} training"
        result.append(_suggestion("neglected_modality", f"{modality}:{last.isoformat()}", draft,
                                  "If this sport still matters to you, try a small maintenance goal and review it after four weeks.",
                                  [f"Last session: {last.isoformat()} ({(today - last).days // 7} weeks ago).",
                                   f"Previously used in {sum(value > 0 for value in values)} of {REGULAR_USE_WEEKS} weeks; restart capped at one session."]))
    return result


def _modality(draft: dict) -> Optional[str]:
    if draft["metric_type"] in {"quality_sessions", "benchmark_power"}:
        return "ride"
    return modality_for_goal(draft["metric_type"], draft.get("activity_type"))


def select_suggestions(candidates: list[dict], goals: list[dict], restrictions: dict,
                       decisions: dict, today: date) -> list[dict]:
    occupied = {(goal["metric_type"], goal["period_type"]) for goal in goals
                if goal.get("lifecycle_status") in {"active", "paused"}}
    selected = []
    for item in candidates:
        draft = item["draft"]
        pair = (draft["metric_type"], draft["period_type"])
        decision = decisions.get(item["key"])
        if decision and (decision["decision"] == "accepted" or (decision["until"] and decision["until"] > today.isoformat())):
            continue
        restriction = restrictions.get("modalities", {}).get(_modality(draft), {})
        if restriction.get("status", "allowed") != "allowed" or pair in occupied:
            continue
        occupied.add(pair)
        selected.append(item)
        if len(selected) == MAX_SUGGESTIONS:
            break
    return selected


def build_goal_suggestions(conn: sqlite3.Connection, today: Optional[date] = None) -> dict:
    current = today or datetime.now().date()
    off_months = get_athlete_profile_for_conn(conn)["off_season_months"]
    goals = [dict(row) for row in conn.execute("SELECT * FROM goals ORDER BY id")]
    relevant = [goal for goal in goals if goal["lifecycle_status"] in {"active", "completed"}]
    for goal in relevant:
        goal["history"] = build_goal_period_history(conn, goal, today=current, off_season_months=off_months)
    active = attach_goal_outcomes(conn, [goal for goal in relevant if goal["lifecycle_status"] == "active"], today=current)
    costs = list(build_cost_signals(conn, today=current).values()) if active else []
    candidates = [item for goal in relevant if (item := replace_completed(goal, current))]
    for goal in active:
        goal["season_ended"] = bool(goal.get("season_end") and goal["season_end"] < current.isoformat())
        goal["review"] = build_goal_verdict(goal, others=[other for other in active if other["id"] != goal["id"]],
                                            costs=costs, today=current, off_season_months=off_months)
        item = plateau_to_quality(conn, goal, current, off_months)
        if item:
            candidates.append(item)
    weakness = profile_weakness(get_cycling_power_trends_data(conn), current)
    if weakness:
        candidates.append(weakness)
    candidates.extend(season_template(conn, current, off_months))
    candidates.extend(neglected_modality(conn, current))
    return {"generated_on": current.isoformat(), "suggestions": select_suggestions(
        candidates, goals, get_modality_restrictions_for_conn(conn), latest_goal_suggestion_decisions(conn), current)}


def record_suggestion_decision(conn: sqlite3.Connection, key: str, *, decision: str,
                               until: Optional[str] = None, today: Optional[date] = None) -> dict:
    current = today or datetime.now().date()
    if decision not in {"accepted", "dismissed"}:
        raise ValueError("decision must be accepted or dismissed.")
    if not key or len(key) > 200 or key.split(":", 1)[0] not in {
        "replace_completed", "plateau_to_quality", "profile_weakness", "season_template", "neglected_modality",
    }:
        raise ValueError("Unknown suggestion key.")
    if decision == "dismissed":
        expiry = date.fromisoformat(until) if until else current + timedelta(days=DEFAULT_DISMISS_DAYS)
        if not current < expiry <= current + timedelta(days=MAX_DISMISS_DAYS):
            raise ValueError("until must be a future date within 365 days.")
        until = expiry.isoformat()
    elif until is not None:
        raise ValueError("Accepted decisions do not have an until date.")
    decision_id = insert_goal_suggestion_decision(conn, key, decision, until)
    conn.commit()
    return {"id": decision_id, "key": key, "decision": decision, "until": until}
