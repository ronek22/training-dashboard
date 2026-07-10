#!/usr/bin/env python3
"""
Training Dashboard MCP Server
Allows Claude to push activities, notes and metrics to the dashboard.
Run with: python server.py
"""
import json
import sys
import httpx
from typing import Optional

API_BASE = "http://localhost:8000"
MCP_SERVER_INFO = {"name": "training-dashboard", "version": "1.3.0"}

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


def call_remote_mcp_tool(name: str, arguments: Optional[dict] = None):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments or {},
        },
    }
    with httpx.Client(timeout=20) as client:
        r = client.post(f"{API_BASE}/mcp", json=payload)
        r.raise_for_status()
        body = r.json()
    if "error" in body:
        raise RuntimeError(body["error"].get("message", "Unknown MCP error"))
    return body["result"]["structuredContent"]

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
        "name": "get_strength_context",
        "description": "Read Fitbod-enriched strength history with recent sessions, exercise-level set and rep detail, recurring lifts, selected exercise trend, and important PRs",
        "inputSchema": {
            "type": "object",
            "properties": {
                "weeks": {"type": "integer", "description": "Recent window to inspect; supported values normalize to 4, 8, or 12 weeks"},
                "body_part": {"type": "string", "description": "Optional body-part filter like all, push, pull, lower, core, or other"},
                "exercise": {"type": "string", "description": "Optional exact exercise name to focus the selected trend payload"}
            }
        }
    },
    {
        "name": "get_exercise_history",
        "description": "Read exercise-level strength workout history with exercises, sets, reps, weights, recent sessions, and lift trends",
        "inputSchema": {
            "type": "object",
            "properties": {
                "weeks": {"type": "integer", "description": "Recent window to inspect; supported values normalize to 4, 8, or 12 weeks"},
                "body_part": {"type": "string", "description": "Optional body-part filter like all, push, pull, lower, core, or other"},
                "exercise": {"type": "string", "description": "Optional exact exercise name to focus the selected trend payload"}
            }
        }
    },
    {
        "name": "get_strength_workout_history",
        "description": "Read recent strength workouts with full exercise breakdown including set-by-set reps and weights from linked Fitbod history",
        "inputSchema": {
            "type": "object",
            "properties": {
                "weeks": {"type": "integer", "description": "Recent window to inspect; supported values normalize to 4, 8, or 12 weeks"},
                "body_part": {"type": "string", "description": "Optional body-part filter like all, push, pull, lower, core, or other"},
                "exercise": {"type": "string", "description": "Optional exact exercise name to focus the selected trend payload"}
            }
        }
    },
    {
        "name": "analyze_activity",
        "description": "Request a compact workout analysis for one activity so an MCP-connected LLM client can generate and save it",
        "inputSchema": {
            "type": "object",
            "properties": {
                "activity_id": {"type": "string", "description": "Activity ID to analyze"},
                "force_refresh": {"type": "boolean", "description": "Regenerate analysis even if a current cached result exists"}
            },
            "required": ["activity_id"]
        }
    },
    {
        "name": "get_activity_analysis_context",
        "description": "Read the deterministic context bundle that an LLM should use to analyze one workout",
        "inputSchema": {
            "type": "object",
            "properties": {
                "activity_id": {"type": "string", "description": "Activity ID to inspect"}
            },
            "required": ["activity_id"]
        }
    },
    {
        "name": "save_activity_analysis",
        "description": "Write an LLM-generated structured workout analysis back into the dashboard for one activity",
        "inputSchema": {
            "type": "object",
            "properties": {
                "activity_id": {"type": "string"},
                "headline": {"type": "string"},
                "summary": {"type": "string"},
                "key_observations": {"type": "array", "items": {"type": "string"}},
                "limitations": {"type": "array", "items": {"type": "string"}},
                "confidence_note": {"type": "string"},
                "generator": {"type": "string"},
                "model_name": {"type": "string"}
            },
            "required": ["activity_id", "headline", "summary", "key_observations", "limitations", "confidence_note"]
        }
    },
    {
        "name": "fail_activity_analysis",
        "description": "Mark a requested workout analysis as failed when the external LLM client cannot complete it",
        "inputSchema": {
            "type": "object",
            "properties": {
                "activity_id": {"type": "string"},
                "error": {"type": "string"}
            },
            "required": ["activity_id", "error"]
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

        elif name in {"get_strength_context", "get_exercise_history", "get_strength_workout_history"}:
            result = call_remote_mcp_tool(name, args)
            return json.dumps(result, indent=2)

        elif name == "analyze_activity":
            result = call_api("POST", f"/activities/{args['activity_id']}/analysis", {"force_refresh": bool(args.get("force_refresh", False))})
            return json.dumps(result, indent=2)

        elif name == "get_activity_analysis_context":
            result = call_api("GET", f"/activities/{args['activity_id']}/analysis/context")
            return json.dumps(result, indent=2)

        elif name == "save_activity_analysis":
            payload = {
                "headline": args["headline"],
                "summary": args["summary"],
                "key_observations": args.get("key_observations", []),
                "limitations": args.get("limitations", []),
                "confidence_note": args["confidence_note"],
                "generator": args.get("generator", "llm"),
                "model_name": args.get("model_name"),
            }
            result = call_api("POST", f"/activities/{args['activity_id']}/analysis/save", payload)
            return json.dumps(result, indent=2)

        elif name == "fail_activity_analysis":
            result = call_api("POST", f"/activities/{args['activity_id']}/analysis/fail", {"error": args["error"]})
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
                    "serverInfo": MCP_SERVER_INFO
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
