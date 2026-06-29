import json


MCP_SERVER_INFO = {"name": "training-dashboard", "version": "1.2.0"}
MCP_SECURITY_SCHEMES = [{"type": "noauth"}]

MCP_TOOLS = [
    {
        "name": "log_activity",
        "description": "Log a training activity to the dashboard (run, ride, strength session)",
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Unique ID (use strava ID if available)"},
                "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                "type": {"type": "string", "enum": ["Run", "Ride", "VirtualRide", "WeightTraining", "Walk", "Hike"]},
                "workout_intent": {"type": "string", "description": "Optional structured intent like easy, long, tempo, interval, recovery, strength_lower"},
                "name": {"type": "string"},
                "distance_km": {"type": "number"},
                "duration_min": {"type": "number"},
                "avg_hr": {"type": "integer"},
                "max_hr": {"type": "integer"},
                "avg_pace": {"type": "string", "description": "e.g. 5:46"},
                "avg_watts": {"type": "number"},
                "elevation_m": {"type": "integer"},
                "calories": {"type": "integer"},
                "zone2": {"type": "boolean", "description": "Was this a Zone 2 session?"},
                "notes": {"type": "string"},
            },
            "required": ["id", "date", "type"],
        },
    },
    {
        "name": "add_coach_note",
        "description": "Add a coaching observation or analysis note to the dashboard",
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": False,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                "category": {"type": "string", "enum": ["running", "cycling", "strength", "heel", "nutrition", "general"]},
                "content": {"type": "string", "description": "The coaching note content"},
            },
            "required": ["date", "category", "content"],
        },
    },
    {
        "name": "log_metric",
        "description": "Log a personal metric like weight, resting HR, Z2 pace, FTP, or streak",
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": False,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                "metric": {"type": "string", "enum": ["weight", "resting_hr", "z2_pace", "ftp", "streak"]},
                "value": {"type": "number", "description": "For z2_pace use seconds per km."},
                "unit": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["date", "metric", "value"],
        },
    },
    {
        "name": "update_weekly_summary",
        "description": "Update or create a weekly training summary",
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "week_start": {"type": "string", "description": "Monday date YYYY-MM-DD"},
                "run_km": {"type": "number"},
                "ride_km": {"type": "number"},
                "strength_sessions": {"type": "integer"},
                "total_elevation": {"type": "integer"},
                "avg_hr": {"type": "number"},
                "notes": {"type": "string"},
            },
            "required": ["week_start"],
        },
    },
    {
        "name": "set_weekly_plan",
        "description": "Create or update a structured weekly training plan for the dashboard",
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "week_start": {"type": "string", "description": "Monday date YYYY-MM-DD"},
                "title": {"type": "string"},
                "focus": {"type": "string", "description": "Main focus of the week"},
                "overview": {"type": "string", "description": "Short summary of the week's intent"},
                "days": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                            "label": {"type": "string", "description": "Mon, Tue, etc."},
                            "session_type": {"type": "string", "description": "run, ride, strength, recovery, rest"},
                            "workout_intent": {"type": "string", "description": "Optional structured intent like easy, long, tempo, interval, recovery"},
                            "title": {"type": "string"},
                            "details": {"type": "string"},
                            "target_duration_min": {"type": "integer"},
                            "target_distance_km": {"type": "number"},
                        },
                        "required": ["date", "label", "title"],
                    },
                },
                "notes": {"type": "string"},
            },
            "required": ["week_start", "days"],
        },
    },
    {
        "name": "adjust_weekly_plan",
        "description": "Adjust the remaining part of an existing weekly plan while preserving past or completed days",
        "annotations": {
            "readOnlyHint": False,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": False,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "week_start": {"type": "string", "description": "Monday date YYYY-MM-DD for the plan to adjust"},
                "effective_from": {"type": "string", "description": "First date that may be changed; defaults to today"},
                "title": {"type": "string", "description": "Optional replacement title for the week"},
                "focus": {"type": "string", "description": "Optional replacement focus"},
                "overview": {"type": "string", "description": "Optional replacement overview"},
                "notes": {"type": "string", "description": "Optional full replacement notes"},
                "adaptation_reason": {"type": "string", "description": "Short explanation appended to plan notes when notes are not replaced"},
                "days": {
                    "type": "array",
                    "description": "Only include days you want to change on or after effective_from",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                            "label": {"type": "string", "description": "Mon, Tue, etc."},
                            "session_type": {"type": "string", "description": "run, ride, strength, recovery, rest"},
                            "workout_intent": {"type": "string", "description": "Optional structured intent like easy, long, tempo, interval, recovery"},
                            "title": {"type": "string"},
                            "details": {"type": "string"},
                            "target_duration_min": {"type": "integer"},
                            "target_distance_km": {"type": "number"},
                        },
                        "required": ["date", "label", "title"],
                    },
                },
            },
            "required": ["week_start", "days"],
        },
    },
    {
        "name": "get_dashboard_summary",
        "description": "Get current dashboard data to see what's already logged",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_recent_context",
        "description": "Get a compact coaching context bundle with recent load, latest activities, notes, metrics, weekly mix, streak, and active plan",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "lookback_days": {"type": "integer", "description": "Primary analysis window, defaults to 14 days"},
                "context_days": {"type": "integer", "description": "Broader context window, defaults to 30 days"},
                "recent_activity_limit": {"type": "integer", "description": "How many recent activities to include"},
                "recent_note_limit": {"type": "integer", "description": "How many recent notes to include"},
            },
        },
    },
    {
        "name": "coach_this_week",
        "description": "Get a one-shot weekly coaching read that combines execution, recovery, goal, and recommendation context in one response",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "lookback_days": {"type": "integer", "description": "Primary analysis window, defaults to 14 days"},
                "context_days": {"type": "integer", "description": "Broader context window, defaults to 30 days"},
                "recent_activity_limit": {"type": "integer", "description": "How many recent activities to include"},
                "recent_note_limit": {"type": "integer", "description": "How many recent notes to include"},
                "include_proposed_adjustment": {
                    "type": "boolean",
                    "description": "Whether to include a preview-only adjustment payload when the recommendation suggests reducing or adjusting the week",
                },
            },
        },
    },
    {
        "name": "get_activities",
        "description": "Read activities already stored in the training dashboard",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of activities to return"},
                "type": {"type": "string", "description": "Optional activity type filter like Run, Ride, WeightTraining"},
                "days": {"type": "integer", "description": "Optional lookback window in days"},
            },
        },
    },
    {
        "name": "get_activity_stats",
        "description": "Read aggregated activity stats from the dashboard",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Lookback window in days"},
            },
        },
    },
    {
        "name": "get_coach_notes",
        "description": "Read coach notes already stored in the dashboard",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of notes to return"},
                "category": {"type": "string", "description": "Optional note category filter"},
            },
        },
    },
    {
        "name": "get_metric_history",
        "description": "Read metric history from the dashboard",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "metric_name": {
                    "type": "string",
                    "enum": ["weight", "resting_hr", "z2_pace", "ftp", "streak"],
                },
                "limit": {"type": "integer", "description": "Maximum number of entries to return"},
            },
            "required": ["metric_name"],
        },
    },
    {
        "name": "get_metrics_catalog",
        "description": "Discover supported metrics, expected units, and whether each metric is manual or computed",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_weekly_plans",
        "description": "Read saved weekly training plans from the dashboard",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of weekly plans to return"},
            },
        },
    },
    {
        "name": "get_calendar_weeks",
        "description": "Read weekly calendar summaries and day-by-day activities from the dashboard",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "openWorldHint": False,
            "idempotentHint": True,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "weeks": {"type": "integer", "description": "Number of recent weeks to return"},
            },
        },
    },
]


def make_mcp_response(msg_id, result=None, error=None):
    response = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        response["error"] = error
    else:
        response["result"] = result
    return response


def build_mcp_tools():
    tools = []
    for tool in MCP_TOOLS:
        meta = dict(tool.get("_meta", {}))
        meta["securitySchemes"] = MCP_SECURITY_SCHEMES
        enriched = dict(tool)
        enriched["securitySchemes"] = MCP_SECURITY_SCHEMES
        enriched["_meta"] = meta
        tools.append(enriched)
    return tools


def call_mcp_tool(
    name: str,
    args: dict,
    *,
    get_db_fn,
    activity_model,
    coach_note_model,
    metric_model,
    weekly_summary_model,
    weekly_plan_model,
    weekly_plan_adjustment_model,
    upsert_activity_fn,
    upsert_weekly_plan_row_fn,
    adjust_weekly_plan_data_fn,
    dashboard_fn,
    recent_context_fn,
    weekly_coaching_fn,
    list_activities_fn,
    activity_stats_fn,
    list_notes_fn,
    get_metric_fn,
    list_weekly_plans_data_fn,
    calendar_weeks_fn,
    metric_catalog,
) -> dict:
    conn = get_db_fn()
    try:
        if name == "log_activity":
            activity = activity_model(**args)
            upsert_activity_fn(conn, activity.model_dump())
            conn.commit()
            message = f"Activity logged: {activity.name or activity.type} on {activity.date}"
            data = {"status": "ok", "id": activity.id, "message": message}

        elif name == "add_coach_note":
            note = coach_note_model(**args)
            conn.execute(
                "INSERT INTO coach_notes (date, category, content) VALUES (?, ?, ?)",
                (note.date, note.category, note.content),
            )
            conn.commit()
            message = f"Coach note added for {note.date}"
            data = {"status": "ok", "message": message}

        elif name == "log_metric":
            metric = metric_model(**args)
            conn.execute(
                "INSERT INTO metrics (date, metric, value, unit, notes) VALUES (?, ?, ?, ?, ?)",
                (metric.date, metric.metric, metric.value, metric.unit, metric.notes),
            )
            conn.commit()
            message = f"Metric logged: {metric.metric} = {metric.value} on {metric.date}"
            data = {"status": "ok", "message": message}

        elif name == "update_weekly_summary":
            summary = weekly_summary_model(**args)
            conn.execute(
                """
                INSERT INTO weekly_summary
                (week_start, run_km, ride_km, strength_sessions, total_elevation, avg_hr, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(week_start) DO UPDATE SET
                    run_km=excluded.run_km,
                    ride_km=excluded.ride_km,
                    strength_sessions=excluded.strength_sessions,
                    total_elevation=excluded.total_elevation,
                    avg_hr=excluded.avg_hr,
                    notes=excluded.notes
                """,
                (
                    summary.week_start,
                    summary.run_km,
                    summary.ride_km,
                    summary.strength_sessions,
                    summary.total_elevation,
                    summary.avg_hr,
                    summary.notes,
                ),
            )
            conn.commit()
            message = f"Weekly summary updated for {summary.week_start}"
            data = {"status": "ok", "message": message}

        elif name == "set_weekly_plan":
            plan = weekly_plan_model(**args)
            upsert_weekly_plan_row_fn(conn, plan)
            conn.commit()
            message = f"Weekly plan saved for {plan.week_start}"
            data = {"status": "ok", "message": message}

        elif name == "adjust_weekly_plan":
            adjustment = weekly_plan_adjustment_model(**args)
            data = adjust_weekly_plan_data_fn(conn, adjustment)
            message = f"Weekly plan adjusted for {adjustment.week_start} from {data['effective_from']}"

        elif name == "get_dashboard_summary":
            data = dashboard_fn()
            message = json.dumps(data, indent=2)

        elif name == "get_recent_context":
            data = recent_context_fn(
                lookback_days=int(args.get("lookback_days", 14)),
                context_days=int(args.get("context_days", 30)),
                recent_activity_limit=int(args.get("recent_activity_limit", 12)),
                recent_note_limit=int(args.get("recent_note_limit", 5)),
            )
            message = json.dumps(data, indent=2)

        elif name == "coach_this_week":
            data = weekly_coaching_fn(
                lookback_days=int(args.get("lookback_days", 14)),
                context_days=int(args.get("context_days", 30)),
                recent_activity_limit=int(args.get("recent_activity_limit", 12)),
                recent_note_limit=int(args.get("recent_note_limit", 5)),
                include_proposed_adjustment=bool(args.get("include_proposed_adjustment", True)),
            )
            message = json.dumps(data, indent=2)

        elif name == "get_activities":
            data = list_activities_fn(
                limit=int(args.get("limit", 50)),
                type=args.get("type"),
                days=args.get("days"),
            )
            message = json.dumps(data, indent=2)

        elif name == "get_activity_stats":
            data = activity_stats_fn(days=int(args.get("days", 30)))
            message = json.dumps(data, indent=2)

        elif name == "get_coach_notes":
            data = list_notes_fn(
                limit=int(args.get("limit", 50)),
                category=args.get("category"),
            )
            message = json.dumps(data, indent=2)

        elif name == "get_metric_history":
            data = get_metric_fn(
                metric_name=args["metric_name"],
                limit=int(args.get("limit", 100)),
            )
            message = json.dumps(data, indent=2)

        elif name == "get_metrics_catalog":
            data = {"metrics": metric_catalog}
            message = json.dumps(data, indent=2)

        elif name == "get_weekly_plans":
            data = list_weekly_plans_data_fn(conn, limit=int(args.get("limit", 12)))
            message = json.dumps(data, indent=2)

        elif name == "get_calendar_weeks":
            data = calendar_weeks_fn(weeks=int(args.get("weeks", 8)))
            message = json.dumps(data, indent=2)

        else:
            raise ValueError(f"Unknown tool: {name}")

        return {
            "structuredContent": data,
            "content": [{"type": "text", "text": message}],
        }
    finally:
        conn.close()
