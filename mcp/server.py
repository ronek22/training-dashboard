#!/usr/bin/env python3
"""
Training Dashboard MCP Server
Allows Claude to push activities, notes and metrics to the dashboard.
Run with: python server.py
"""
import json
import sys
import httpx

API_BASE = "http://localhost:8000"

def call_api(method: str, path: str, data: dict = None):
    with httpx.Client(timeout=10) as client:
        if method == "POST":
            r = client.post(f"{API_BASE}{path}", json=data)
        elif method == "GET":
            r = client.get(f"{API_BASE}{path}", params=data)
        else:
            return {"error": f"Unknown method {method}"}
        r.raise_for_status()
        return r.json()

TOOLS = [
    {
        "name": "log_activity",
        "description": "Log a training activity to the dashboard (run, ride, strength session)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Unique ID (use strava ID if available)"},
                "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                "type": {"type": "string", "enum": ["Run", "Ride", "VirtualRide", "WeightTraining", "Walk", "Hike"]},
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
                "notes": {"type": "string"}
            },
            "required": ["id", "date", "type"]
        }
    },
    {
        "name": "add_coach_note",
        "description": "Add a coaching observation or analysis note to the dashboard",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                "category": {"type": "string", "enum": ["running", "cycling", "strength", "heel", "nutrition", "general"]},
                "content": {"type": "string", "description": "The coaching note content"}
            },
            "required": ["date", "category", "content"]
        }
    },
    {
        "name": "log_metric",
        "description": "Log a personal metric like weight, resting HR, Z2 pace, FTP, heel pain level, or streak",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                "metric": {"type": "string", "enum": ["weight", "resting_hr", "z2_pace", "ftp", "heel_pain", "streak"]},
                "value": {"type": "number", "description": "For z2_pace use seconds per km. For heel_pain use 0-10 scale."},
                "unit": {"type": "string"},
                "notes": {"type": "string"}
            },
            "required": ["date", "metric", "value"]
        }
    },
    {
        "name": "update_weekly_summary",
        "description": "Update or create a weekly training summary",
        "inputSchema": {
            "type": "object",
            "properties": {
                "week_start": {"type": "string", "description": "Monday date YYYY-MM-DD"},
                "run_km": {"type": "number"},
                "ride_km": {"type": "number"},
                "strength_sessions": {"type": "integer"},
                "total_elevation": {"type": "integer"},
                "avg_hr": {"type": "number"},
                "notes": {"type": "string"}
            },
            "required": ["week_start"]
        }
    },
    {
        "name": "set_weekly_plan",
        "description": "Create or update a structured weekly training plan for the dashboard",
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
                            "title": {"type": "string"},
                            "details": {"type": "string"},
                            "target_duration_min": {"type": "integer"},
                            "target_distance_km": {"type": "number"}
                        },
                        "required": ["date", "label", "title"]
                    }
                },
                "notes": {"type": "string"}
            },
            "required": ["week_start", "days"]
        }
    },
    {
        "name": "adjust_weekly_plan",
        "description": "Adjust the remaining part of an existing weekly plan while preserving past or completed days",
        "inputSchema": {
            "type": "object",
            "properties": {
                "week_start": {"type": "string", "description": "Monday date YYYY-MM-DD for the plan to adjust"},
                "effective_from": {"type": "string", "description": "First date that may be changed; defaults to today"},
                "title": {"type": "string"},
                "focus": {"type": "string"},
                "overview": {"type": "string"},
                "notes": {"type": "string", "description": "Optional full replacement notes"},
                "adaptation_reason": {"type": "string", "description": "Short explanation appended to notes if notes are not replaced"},
                "days": {
                    "type": "array",
                    "description": "Only include days you want to change on or after effective_from",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "Date YYYY-MM-DD"},
                            "label": {"type": "string", "description": "Mon, Tue, etc."},
                            "session_type": {"type": "string", "description": "run, ride, strength, recovery, rest"},
                            "title": {"type": "string"},
                            "details": {"type": "string"},
                            "target_duration_min": {"type": "integer"},
                            "target_distance_km": {"type": "number"}
                        },
                        "required": ["date", "label", "title"]
                    }
                }
            },
            "required": ["week_start", "days"]
        }
    },
    {
        "name": "get_dashboard_summary",
        "description": "Get current dashboard data to see what's already logged",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_recent_context",
        "description": "Get a compact coaching context bundle with recent load, activities, notes, metrics, weekly mix, streak, and active plan",
        "inputSchema": {
            "type": "object",
            "properties": {
                "lookback_days": {"type": "integer", "description": "Primary analysis window, defaults to 14 days"},
                "context_days": {"type": "integer", "description": "Broader context window, defaults to 30 days"},
                "recent_activity_limit": {"type": "integer", "description": "How many recent activities to include"},
                "recent_note_limit": {"type": "integer", "description": "How many recent notes to include"}
            }
        }
    },
    {
        "name": "get_activities",
        "description": "Read activities already stored in the training dashboard",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of activities to return"},
                "type": {"type": "string", "description": "Optional activity type filter like Run, Ride, WeightTraining"},
                "days": {"type": "integer", "description": "Optional lookback window in days"}
            }
        }
    },
    {
        "name": "get_activity_stats",
        "description": "Read aggregated activity stats from the dashboard",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Lookback window in days"}
            }
        }
    },
    {
        "name": "get_coach_notes",
        "description": "Read coach notes already stored in the dashboard",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of notes to return"},
                "category": {"type": "string", "description": "Optional note category filter"}
            }
        }
    },
    {
        "name": "get_metric_history",
        "description": "Read metric history from the dashboard",
        "inputSchema": {
            "type": "object",
            "properties": {
                "metric_name": {
                    "type": "string",
                    "enum": ["weight", "resting_hr", "z2_pace", "ftp", "heel_pain", "streak"]
                },
                "limit": {"type": "integer", "description": "Maximum number of entries to return"}
            },
            "required": ["metric_name"]
        }
    },
    {
        "name": "get_weekly_plans",
        "description": "Read saved weekly training plans from the dashboard",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Maximum number of weekly plans to return"}
            }
        }
    },
    {
        "name": "get_calendar_weeks",
        "description": "Read weekly calendar summaries and day-by-day activities from the dashboard",
        "inputSchema": {
            "type": "object",
            "properties": {
                "weeks": {"type": "integer", "description": "Number of recent weeks to return"}
            }
        }
    },
    {
        "name": "draft_goal",
        "description": "Preview a structured goal draft from natural-language text without saving it",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Natural-language goal idea to parse"}
            },
            "required": ["text"]
        }
    }
]

def handle_tool(name: str, args: dict) -> str:
    try:
        if name == "log_activity":
            result = call_api("POST", "/activities", args)
            return f"✅ Activity logged: {args.get('name', args['type'])} on {args['date']}"

        elif name == "add_coach_note":
            result = call_api("POST", "/notes", args)
            return f"✅ Note added ({args['category']}): {args['content'][:80]}..."

        elif name == "log_metric":
            result = call_api("POST", "/metrics", args)
            return f"✅ Metric logged: {args['metric']} = {args['value']} on {args['date']}"

        elif name == "update_weekly_summary":
            result = call_api("POST", "/weekly", args)
            return f"✅ Weekly summary updated for week of {args['week_start']}"

        elif name == "set_weekly_plan":
            result = call_api("POST", "/plans/weekly", args)
            return f"✅ Weekly plan saved for week of {args['week_start']}"

        elif name == "adjust_weekly_plan":
            result = call_api("POST", "/plans/weekly/adjust", args)
            changed_dates = ", ".join(result.get("changed_dates", [])) or "no dates"
            return f"✅ Weekly plan adjusted for week of {args['week_start']} ({changed_dates})"

        elif name == "get_dashboard_summary":
            result = call_api("GET", "/dashboard")
            return json.dumps(result, indent=2)

        elif name == "get_recent_context":
            result = call_api("GET", "/context/recent", args)
            return json.dumps(result, indent=2)

        elif name == "get_activities":
            result = call_api("GET", "/activities", args)
            return json.dumps(result, indent=2)

        elif name == "get_activity_stats":
            result = call_api("GET", "/activities/stats", args)
            return json.dumps(result, indent=2)

        elif name == "get_coach_notes":
            result = call_api("GET", "/notes", args)
            return json.dumps(result, indent=2)

        elif name == "get_metric_history":
            metric_name = args["metric_name"]
            params = {k: v for k, v in args.items() if k != "metric_name"}
            result = call_api("GET", f"/metrics/{metric_name}", params)
            return json.dumps(result, indent=2)

        elif name == "get_weekly_plans":
            result = call_api("GET", "/plans/weekly", args)
            return json.dumps(result, indent=2)

        elif name == "get_calendar_weeks":
            result = call_api("GET", "/calendar/weeks", args)
            return json.dumps(result, indent=2)

        elif name == "draft_goal":
            result = call_api("POST", "/goals/draft", args)
            return json.dumps(result, indent=2)

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        return f"❌ Error: {str(e)}"

def make_response(msg_id, result=None, error=None):
    response = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        response["error"] = error
    else:
        response["result"] = result
    return response

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = msg.get("method")
        msg_id = msg.get("id")

        # Notifications do not have an ID and must not receive a response.
        if msg_id is None:
            if method == "notifications/initialized":
                continue
            continue

        if method == "initialize":
            response = make_response(
                msg_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "training-dashboard", "version": "1.0.1"}
                }
            )

        elif method == "ping":
            response = make_response(msg_id, {})

        elif method == "tools/list":
            response = make_response(msg_id, {"tools": TOOLS})

        elif method == "tools/call":
            tool_name = msg["params"]["name"]
            tool_args = msg["params"].get("arguments", {})
            result_text = handle_tool(tool_name, tool_args)
            response = make_response(
                msg_id,
                {"content": [{"type": "text", "text": result_text}]}
            )

        else:
            response = make_response(
                msg_id,
                error={"code": -32601, "message": f"Method not found: {method}"}
            )

        print(json.dumps(response), flush=True)

if __name__ == "__main__":
    main()
