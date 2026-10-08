"""Compact projection of build_recent_context for the MCP get_recent_context tool.

The full bundle runs to ~200k characters, mostly from per-day plan link candidates,
goal objects repeated in three places, the training-load chart and cycling power
tables. The compact view keeps every section's summary and points at the detail
tools; detail="full" still returns the original bundle.
"""

DETAIL_TOOLS = {
    "full_bundle": "get_recent_context with detail='full'",
    "activities": "get_activities, get_activity_analysis_context",
    "weekly_plan": "get_weekly_plans",
    "goals": "get_goals, get_goal_review",
    "cycling_power": "get_cycling_power_profile",
    "aerobic_fitness": "get_aerobic_fitness_trend",
    "strength": "get_strength_context, get_strength_workout_history",
    "personal_records": "get_personal_records",
}

PLAN_DAY_KEYS = (
    "session_id",
    "date",
    "label",
    "session_type",
    "workout_intent_label",
    "title",
    "details",
    "target_duration_min",
    "target_distance_km",
    "cycling_workout_name",
    "benchmark_label",
    "template_label",
    "modality_restriction",
    "lift_volume_additions",
)

GOAL_KEYS = (
    "id",
    "title",
    "period_label",
    "metric_label",
    "status",
    "lifecycle_status",
    "current_value",
    "target_value",
    "unit",
    "progress_pct",
    "expected_pct",
    "days_remaining",
    "compact_summary",
    "weekly_requirement_summary",
    "is_constrained",
    "constraint_summary",
    "purpose",
    "commitment",
)


def _empty(value) -> bool:
    return value is None or value == [] or value == {} or value == ""


def _prune(value):
    """Drop null and empty values recursively; they are most of the noise in the bundle."""
    if isinstance(value, dict):
        pruned = {key: _prune(item) for key, item in value.items()}
        return {key: item for key, item in pruned.items() if not _empty(item)}
    if isinstance(value, list):
        return [_prune(item) for item in value if not _empty(item)]
    return value


def _pick(source, keys) -> dict:
    if not isinstance(source, dict):
        return {}
    return {key: source[key] for key in keys if key in source}


def _goal_ref(goal: dict) -> dict:
    return _pick(goal, ("id", "title", "status")) | {
        "risk": (goal.get("risk_summary") or {}).get("label"),
    }


def _plan_day(day: dict) -> dict:
    slim = _pick(day, PLAN_DAY_KEYS)
    if (slim.get("modality_restriction") or {}).get("status") == "allowed":
        slim.pop("modality_restriction")
    comparison = day.get("comparison")
    if isinstance(comparison, dict):
        slim["comparison"] = _pick(comparison, ("status", "label", "intent_alignment")) | {
            "execution_quality": _pick(comparison.get("execution_quality"), ("status", "headline")),
            "completed": [
                _pick(activity, ("id", "type", "name", "duration_min", "distance_km"))
                for activity in comparison.get("completed_activities") or []
            ],
        }
    slim["goal_links"] = [
        _pick(link, ("goal_id", "goal_title", "support_level")) for link in day.get("goal_links") or []
    ]
    return slim


def _active_plan(plan):
    if not isinstance(plan, dict):
        return plan
    slim = _pick(plan, ("week_start", "title", "focus", "overview", "notes", "created_at"))
    slim["latest_revision"] = _pick(
        plan.get("latest_revision"),
        ("effective_from", "adaptation_reason", "changed_dates", "source", "created_at"),
    )
    slim["days"] = [_plan_day(day) for day in plan.get("days") or []]
    lift_volume = plan.get("lift_volume")
    if isinstance(lift_volume, dict):
        slim["lift_volume"] = _pick(lift_volume, ("target_min", "target_max")) | {
            "groups": [
                _pick(group, ("label", "total_sets", "status", "shortfall"))
                for group in lift_volume.get("groups") or []
            ],
        }
    return slim


def _goal_summary(summary, list_key: str):
    if not isinstance(summary, dict):
        return summary
    slim = {key: value for key, value in summary.items() if key != list_key}
    slim[list_key] = [_goal_ref(goal) for goal in summary.get(list_key) or []]
    return slim


def _training_load(load, days: int = 7):
    if not isinstance(load, dict):
        return load
    slim = _pick(load, ("current", "ratio", "focus"))
    slim["model"] = _pick(load.get("model"), ("name", "ftp"))
    slim["recent_days"] = [
        _pick(point, ("date", "load", "ctl", "atl", "tsb")) for point in (load.get("chart") or [])[-days:]
    ]
    return slim


def _cycling_power(power):
    if not isinstance(power, dict):
        return power
    record_keys = ("duration_seconds", "watts", "date", "level_name")
    slim = _pick(power, ("category_levels", "coverage"))
    slim["recent_records"] = [_pick(record, record_keys) for record in power.get("recent_records") or []]
    slim["records"] = [_pick(record, record_keys) for record in power.get("records") or []]
    return slim


def _daily_recommendation(recommendation):
    if not isinstance(recommendation, dict):
        return recommendation
    slim = {key: value for key, value in recommendation.items() if key not in ("today_plan", "signals")}
    if isinstance(recommendation.get("today_plan"), dict):
        slim["today_plan"] = _plan_day(recommendation["today_plan"])
    signals = recommendation.get("signals")
    if isinstance(signals, dict):
        # modality_restrictions is already a top-level section.
        slim["signals"] = {key: value for key, value in signals.items() if key != "modality_restrictions"}
    return slim


def _activity(activity: dict) -> dict:
    slim = {key: value for key, value in activity.items() if key not in ("feedback", "session_tags")}
    feedback = activity.get("feedback")
    if isinstance(feedback, dict):
        slim["feedback"] = _pick(
            feedback, ("rpe", "energy", "muscle_soreness", "pain_level", "fuelling", "note", "verdict", "pre_fuel")
        )
    return slim


def _strength_detail(detail):
    if not isinstance(detail, dict):
        return detail
    slim = _pick(detail, ("available", "summary"))
    slim["recent_sessions"] = [
        _pick(
            session,
            ("workout_date", "title", "duration_min", "exercise_count", "set_count", "total_volume_kg", "major_exercises"),
        )
        for session in detail.get("recent_sessions") or []
    ]
    return slim


def _aerobic_fitness(fitness, rides: int = 3):
    if not isinstance(fitness, dict):
        return fitness
    slim = {key: value for key, value in fitness.items() if key not in ("interpretation_limits", "recent_rides")}
    slim["recent_rides"] = (fitness.get("recent_rides") or [])[:rides]
    return slim


def _readiness(readiness):
    if not isinstance(readiness, dict):
        return readiness
    slim = {key: value for key, value in readiness.items() if key != "latest_feedback"}
    score = readiness.get("score")
    if isinstance(score, dict):
        # Each factor's nested summary repeats score.sleep_debt.
        slim["score"] = dict(score) | {
            "factors": [_pick(factor, ("label", "detail", "tone")) for factor in score.get("factors") or []],
        }
    return slim


def compact_recent_context(context: dict) -> dict:
    compact = dict(context)
    # Pointers only: these sections have their own tools.
    compact.pop("workout_template_settings", None)
    compact["active_plan"] = _active_plan(context.get("active_plan"))
    compact["active_goals"] = [_pick(goal, GOAL_KEYS) for goal in context.get("active_goals") or []]
    compact["goal_planning_summary"] = _goal_summary(context.get("goal_planning_summary"), "most_urgent")
    compact["goal_risk_summary"] = _goal_summary(context.get("goal_risk_summary"), "most_pressured")
    compact["training_load"] = _training_load(context.get("training_load"))
    compact["cycling_power"] = _cycling_power(context.get("cycling_power"))
    compact["daily_recommendation"] = _daily_recommendation(context.get("daily_recommendation"))
    compact["recent_activities"] = [_activity(activity) for activity in context.get("recent_activities") or []]
    compact["recent_strength_detail"] = _strength_detail(context.get("recent_strength_detail"))
    compact["aerobic_fitness"] = _aerobic_fitness(context.get("aerobic_fitness"))
    compact["recent_feedback"] = [
        {key: value for key, value in item.items() if key not in ("created_at", "updated_at")}
        for item in context.get("recent_feedback") or []
    ]
    if isinstance(context.get("athlete_profile"), dict):
        # athlete_brief is already a top-level section.
        compact["athlete_profile"] = {
            key: value for key, value in context["athlete_profile"].items() if key != "athlete_brief"
        }
    compact["readiness"] = _readiness(context.get("readiness"))
    compact = _prune(compact)
    # Keep null sections (sick_mode, minimum_week, ...) so "off" stays explicit.
    for key, value in context.items():
        if value is None:
            compact[key] = None
    compact["detail"] = "compact"
    compact["detail_tools"] = DETAIL_TOOLS
    return compact
