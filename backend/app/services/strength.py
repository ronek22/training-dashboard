import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional


BODY_PART_LABELS = {
    "push": "Push",
    "pull": "Pull",
    "lower": "Lower",
    "core": "Core",
    "other": "Other",
}
BODY_PART_KEYWORDS = {
    "core": (
        "abwheel",
        "bicyclecrunch",
        "cablecrunch",
        "crunch",
        "deadbug",
        "hangingkneeraise",
        "hanginglegraise",
        "legraise",
        "pallof",
        "plank",
        "russiantwist",
        "situp",
        "toestobar",
        "woodchop",
    ),
    "lower": (
        "backextension",
        "bulgariansplitsquat",
        "calfraise",
        "deadlift",
        "frontsquat",
        "glutebridge",
        "glutehamraise",
        "goodmorning",
        "hacksquat",
        "hipthrust",
        "kettlebellswing",
        "legcurl",
        "legextension",
        "legpress",
        "lunge",
        "rdl",
        "romaniandeadlift",
        "singlelegdeadlift",
        "splitsquat",
        "squat",
        "stepup",
        "stifflegdeadlift",
        "sumodeadlift",
    ),
    "push": (
        "arnoldpress",
        "benchpress",
        "chestfly",
        "chestpress",
        "dip",
        "inclinebench",
        "inclinedumbbellpress",
        "lateralraise",
        "overheadpress",
        "pecdeck",
        "pushdown",
        "pushpress",
        "pushup",
        "shoulderpress",
        "skullcrusher",
        "tricep",
        "uprightrow",
    ),
    "pull": (
        "bicep",
        "chinup",
        "curl",
        "facepull",
        "highrow",
        "latpulldown",
        "pulldown",
        "pullover",
        "pullup",
        "rackpull",
        "reardelt",
        "row",
        "seatedrow",
        "shrug",
    ),
}
IMPORTANT_PR_PATTERNS = [
    {"key": "bench_press", "label": "Bench Press", "tokens": ("benchpress",)},
    {"key": "back_squat", "label": "Back Squat", "tokens": ("backsquat",)},
    {"key": "front_squat", "label": "Front Squat", "tokens": ("frontsquat",)},
    {"key": "deadlift", "label": "Deadlift", "tokens": ("deadlift", "sumodeadlift", "trapbardeadlift")},
    {"key": "romanian_deadlift", "label": "Romanian Deadlift", "tokens": ("romaniandeadlift", "rdl")},
    {"key": "overhead_press", "label": "Overhead Press", "tokens": ("overheadpress", "shoulderpress", "militarypress")},
    {"key": "barbell_row", "label": "Barbell Row", "tokens": ("barbellrow", "bentoverrow", "pendlayrow")},
    {"key": "pull_up", "label": "Pull Up", "tokens": ("pullup", "chinup")},
]


def _normalize_name(value: Optional[str]) -> str:
    if not value:
        return ""
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _classify_body_part(exercise_name: Optional[str]) -> str:
    normalized = _normalize_name(exercise_name)
    if not normalized:
        return "other"
    for body_part in ("core", "lower", "push", "pull"):
        if any(keyword in normalized for keyword in BODY_PART_KEYWORDS[body_part]):
            return body_part
    return "other"


def _parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def _round_number(value: Optional[float], digits: int = 1) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


def _week_start_for(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _window_start_for_weeks(weeks: int) -> date:
    current_week_start = _week_start_for(date.today())
    return current_week_start - timedelta(weeks=max(weeks - 1, 0))


def _load_strength_rows(conn: sqlite3.Connection, window_start: str) -> tuple[list[sqlite3.Row], list[sqlite3.Row], list[sqlite3.Row]]:
    sessions = conn.execute(
        """
        SELECT
            s.id,
            s.workout_timestamp,
            s.workout_date,
            s.title,
            s.match_status,
            s.match_provenance,
            s.match_reason,
            s.total_duration_seconds,
            s.calories,
            a.id AS activity_id,
            a.name AS activity_name,
            a.date AS activity_date,
            a.duration_min AS activity_duration_min,
            'fitbod' AS source
        FROM fitbod_workout_sessions s
        JOIN activities a ON a.id = s.matched_activity_id
        WHERE s.match_status = 'matched'
          AND a.type = 'WeightTraining'
          AND s.workout_date >= ?
          AND NOT EXISTS (
              SELECT 1 FROM strength_workout_sessions recorded
              WHERE recorded.linked_activity_id = a.id
                AND recorded.status = 'completed'
          )

        UNION ALL

        SELECT
            -s.id AS id,
            s.started_at AS workout_timestamp,
            substr(s.started_at, 1, 10) AS workout_date,
            s.template_name AS title,
            'matched' AS match_status,
            'trainlog_link' AS match_provenance,
            'Recorded in TrainLog and linked to the activity.' AS match_reason,
            CASE
                WHEN s.completed_at IS NOT NULL
                THEN ROUND((julianday(s.completed_at) - julianday(s.started_at)) * 86400)
                ELSE NULL
            END AS total_duration_seconds,
            a.calories AS calories,
            a.id AS activity_id,
            a.name AS activity_name,
            a.date AS activity_date,
            a.duration_min AS activity_duration_min,
            'trainlog' AS source
        FROM strength_workout_sessions s
        JOIN activities a ON a.id = s.linked_activity_id
        WHERE s.status = 'completed'
          AND a.type = 'WeightTraining'
          AND substr(s.started_at, 1, 10) >= ?
          AND EXISTS (
              SELECT 1
              FROM strength_session_exercises e
              JOIN strength_session_sets workout_set ON workout_set.session_exercise_id = e.id
              WHERE e.session_id = s.id AND workout_set.status = 'completed'
          )
        ORDER BY workout_date ASC, workout_timestamp ASC, id ASC
        """,
        (window_start, window_start),
    ).fetchall()
    exercises = conn.execute(
        """
        SELECT
            e.id,
            e.session_id,
            e.exercise_order,
            e.exercise_name,
            e.set_count,
            e.rep_count,
            e.total_volume_kg,
            e.work_set_count,
            e.warmup_set_count
        FROM fitbod_workout_exercises e
        JOIN fitbod_workout_sessions s ON s.id = e.session_id
        JOIN activities a ON a.id = s.matched_activity_id
        WHERE s.match_status = 'matched'
          AND a.type = 'WeightTraining'
          AND s.workout_date >= ?
          AND NOT EXISTS (
              SELECT 1 FROM strength_workout_sessions recorded
              WHERE recorded.linked_activity_id = a.id
                AND recorded.status = 'completed'
          )

        UNION ALL

        SELECT
            -e.id AS id,
            -s.id AS session_id,
            e.exercise_order,
            e.exercise_name,
            COUNT(workout_set.id) AS set_count,
            COALESCE(SUM(workout_set.actual_reps), 0) AS rep_count,
            COALESCE(SUM(workout_set.actual_reps * COALESCE(workout_set.actual_weight_kg, 0)), 0) AS total_volume_kg,
            COUNT(workout_set.id) AS work_set_count,
            0 AS warmup_set_count
        FROM strength_session_exercises e
        JOIN strength_workout_sessions s ON s.id = e.session_id
        JOIN activities a ON a.id = s.linked_activity_id
        JOIN strength_session_sets workout_set
          ON workout_set.session_exercise_id = e.id
         AND workout_set.status = 'completed'
        WHERE s.status = 'completed'
          AND a.type = 'WeightTraining'
          AND substr(s.started_at, 1, 10) >= ?
        GROUP BY e.id, s.id, e.exercise_order, e.exercise_name
        ORDER BY session_id ASC, exercise_order ASC, id ASC
        """,
        (window_start, window_start),
    ).fetchall()
    sets = conn.execute(
        """
        SELECT
            fs.id,
            fs.exercise_id,
            fs.set_order,
            fs.reps,
            fs.weight_kg,
            fs.is_warmup
        FROM fitbod_workout_sets fs
        JOIN fitbod_workout_exercises e ON e.id = fs.exercise_id
        JOIN fitbod_workout_sessions s ON s.id = e.session_id
        JOIN activities a ON a.id = s.matched_activity_id
        WHERE s.match_status = 'matched'
          AND a.type = 'WeightTraining'
          AND s.workout_date >= ?
          AND NOT EXISTS (
              SELECT 1 FROM strength_workout_sessions recorded
              WHERE recorded.linked_activity_id = a.id
                AND recorded.status = 'completed'
          )

        UNION ALL

        SELECT
            -workout_set.id AS id,
            -e.id AS exercise_id,
            workout_set.set_order,
            workout_set.actual_reps AS reps,
            workout_set.actual_weight_kg AS weight_kg,
            0 AS is_warmup
        FROM strength_session_sets workout_set
        JOIN strength_session_exercises e ON e.id = workout_set.session_exercise_id
        JOIN strength_workout_sessions s ON s.id = e.session_id
        JOIN activities a ON a.id = s.linked_activity_id
        WHERE workout_set.status = 'completed'
          AND s.status = 'completed'
          AND a.type = 'WeightTraining'
          AND substr(s.started_at, 1, 10) >= ?
        ORDER BY exercise_id ASC, set_order ASC, id ASC
        """,
        (window_start, window_start),
    ).fetchall()
    return sessions, exercises, sets


def _build_session_index(
    session_rows: list[sqlite3.Row],
    exercise_rows: list[sqlite3.Row],
    set_rows: list[sqlite3.Row],
) -> list[dict]:
    sessions_by_id: dict[int, dict] = {}
    exercises_by_id: dict[int, dict] = {}

    for row in session_rows:
        sessions_by_id[int(row["id"])] = {
            "id": int(row["id"]),
            "workout_timestamp": row["workout_timestamp"],
            "workout_date": row["workout_date"],
            "title": row["title"],
            "match_provenance": row["match_provenance"],
            "match_reason": row["match_reason"],
            "total_duration_seconds": row["total_duration_seconds"],
            "calories": row["calories"],
            "source": row["source"],
            "matched_activity": {
                "id": row["activity_id"],
                "name": row["activity_name"],
                "date": row["activity_date"],
                "duration_min": row["activity_duration_min"],
            },
            "exercises": [],
        }

    for row in exercise_rows:
        exercise = {
            "id": int(row["id"]),
            "session_id": int(row["session_id"]),
            "exercise_order": row["exercise_order"],
            "exercise_name": row["exercise_name"],
            "set_count": int(row["set_count"] or 0),
            "rep_count": int(row["rep_count"] or 0),
            "total_volume_kg": _round_number(row["total_volume_kg"]),
            "work_set_count": int(row["work_set_count"] or 0),
            "warmup_set_count": int(row["warmup_set_count"] or 0),
            "body_part": _classify_body_part(row["exercise_name"]),
            "sets": [],
        }
        sessions_by_id[exercise["session_id"]]["exercises"].append(exercise)
        exercises_by_id[exercise["id"]] = exercise

    for row in set_rows:
        exercise = exercises_by_id.get(int(row["exercise_id"]))
        if not exercise:
            continue
        exercise["sets"].append(
            {
                "id": int(row["id"]),
                "set_order": int(row["set_order"]),
                "reps": row["reps"],
                "weight_kg": _round_number(row["weight_kg"]),
                "is_warmup": bool(row["is_warmup"]),
            }
        )

    return list(sessions_by_id.values())


def _serialize_session_slice(session: dict, body_part: str) -> Optional[dict]:
    predicate = (lambda exercise: True) if body_part == "all" else (lambda exercise: exercise["body_part"] == body_part)
    exercises = [exercise for exercise in session["exercises"] if predicate(exercise)]
    if not exercises:
        return None
    total_volume = sum(exercise["total_volume_kg"] or 0 for exercise in exercises)
    return {
        "id": session["id"],
        "workout_timestamp": session["workout_timestamp"],
        "workout_date": session["workout_date"],
        "title": session["title"],
        "match_provenance": session["match_provenance"],
        "match_reason": session["match_reason"],
        "total_duration_seconds": session["total_duration_seconds"],
        "calories": session["calories"],
        "source": session.get("source"),
        "matched_activity": session["matched_activity"],
        "exercise_count": len(exercises),
        "set_count": sum(exercise["set_count"] for exercise in exercises),
        "rep_count": sum(exercise["rep_count"] for exercise in exercises),
        "total_volume_kg": _round_number(total_volume),
        "exercises": exercises,
    }


def _body_part_breakdown(sessions: list[dict]) -> list[dict]:
    breakdown = []
    all_option = {
        "value": "all",
        "label": "All lifts",
        "session_count": len(sessions),
        "total_volume_kg": _round_number(sum(sum(exercise["total_volume_kg"] or 0 for exercise in session["exercises"]) for session in sessions)),
    }
    breakdown.append(all_option)
    for value, label in BODY_PART_LABELS.items():
        filtered = [_serialize_session_slice(session, value) for session in sessions]
        filtered = [session for session in filtered if session]
        if not filtered:
            continue
        breakdown.append(
            {
                "value": value,
                "label": label,
                "session_count": len(filtered),
                "total_volume_kg": _round_number(sum(session["total_volume_kg"] or 0 for session in filtered)),
            }
        )
    return breakdown


def _filtered_sessions(
    conn: sqlite3.Connection,
    *,
    window_start: date,
    body_part: str,
) -> tuple[list[dict], list[dict]]:
    session_rows, exercise_rows, set_rows = _load_strength_rows(conn, window_start.isoformat())
    sessions = _build_session_index(session_rows, exercise_rows, set_rows)
    filtered = [
        serialized
        for serialized in (_serialize_session_slice(session, body_part) for session in sessions)
        if serialized
    ]
    filtered.sort(key=lambda item: (item["workout_date"], item["workout_timestamp"], item["id"]))
    return sessions, filtered


def _weekly_trend(filtered_sessions: list[dict], weeks: int, window_start: date) -> list[dict]:
    trend_by_week = {
        (window_start + timedelta(weeks=index)).isoformat(): {
            "week_start": (window_start + timedelta(weeks=index)).isoformat(),
            "session_count": 0,
            "total_volume_kg": 0.0,
            "total_sets": 0,
            "total_reps": 0,
        }
        for index in range(weeks)
    }
    for session in filtered_sessions:
        week_start = _week_start_for(_parse_iso_date(session["workout_date"])).isoformat()
        bucket = trend_by_week.get(week_start)
        if not bucket:
            continue
        bucket["session_count"] += 1
        bucket["total_volume_kg"] += session["total_volume_kg"] or 0.0
        bucket["total_sets"] += session["set_count"]
        bucket["total_reps"] += session["rep_count"]
    return [
        {
            **bucket,
            "total_volume_kg": _round_number(bucket["total_volume_kg"]),
        }
        for bucket in trend_by_week.values()
    ]


def _build_exercise_aggregates(filtered_sessions: list[dict], weeks: int) -> tuple[list[dict], dict[str, list[dict]]]:
    aggregates: dict[str, dict] = {}
    trends: dict[str, list[dict]] = defaultdict(list)

    for session in filtered_sessions:
        for exercise in session["exercises"]:
            name = exercise["exercise_name"]
            aggregate = aggregates.setdefault(
                name,
                {
                    "exercise_name": name,
                    "body_part": exercise["body_part"],
                    "appearance_count": 0,
                    "session_dates": set(),
                    "total_sets": 0,
                    "total_reps": 0,
                    "total_volume_kg": 0.0,
                    "last_performed_date": None,
                    "recent_best_load_kg": None,
                },
            )
            aggregate["appearance_count"] += 1
            aggregate["session_dates"].add(session["workout_date"])
            aggregate["total_sets"] += exercise["set_count"]
            aggregate["total_reps"] += exercise["rep_count"]
            aggregate["total_volume_kg"] += exercise["total_volume_kg"] or 0.0
            aggregate["last_performed_date"] = session["workout_date"]

            top_load = max((set_row["weight_kg"] or 0) for set_row in exercise["sets"]) if exercise["sets"] else 0
            if top_load > 0 and (aggregate["recent_best_load_kg"] is None or top_load > aggregate["recent_best_load_kg"]):
                aggregate["recent_best_load_kg"] = _round_number(top_load)

            trends[name].append(
                {
                    "workout_date": session["workout_date"],
                    "workout_timestamp": session["workout_timestamp"],
                    "total_volume_kg": exercise["total_volume_kg"],
                    "set_count": exercise["set_count"],
                    "rep_count": exercise["rep_count"],
                    "top_load_kg": _round_number(top_load) if top_load > 0 else None,
                    "matched_activity": session["matched_activity"],
                }
            )

    ranked = []
    for aggregate in aggregates.values():
        active_weeks = len({_week_start_for(_parse_iso_date(day)).isoformat() for day in aggregate["session_dates"]})
        frequency_ratio = active_weeks / max(weeks, 1)
        ranked.append(
            {
                "exercise_name": aggregate["exercise_name"],
                "body_part": aggregate["body_part"],
                "appearance_count": aggregate["appearance_count"],
                "active_weeks": active_weeks,
                "frequency_ratio": round(frequency_ratio, 2),
                "total_sets": aggregate["total_sets"],
                "total_reps": aggregate["total_reps"],
                "total_volume_kg": _round_number(aggregate["total_volume_kg"]),
                "last_performed_date": aggregate["last_performed_date"],
                "recent_best_load_kg": aggregate["recent_best_load_kg"],
            }
        )
    ranked.sort(
        key=lambda item: (
            -item["appearance_count"],
            -(item["total_volume_kg"] or 0),
            item["exercise_name"].lower(),
        )
    )
    return ranked, trends


def _progression_summary(trend: list[dict], weeks: int) -> dict:
    if not trend:
        return {
            "headline": "No recurring history yet",
            "detail": "This lift has not appeared inside the selected window.",
            "tone": "flat",
        }
    first = trend[0]
    last = trend[-1]
    first_load = first.get("top_load_kg")
    last_load = last.get("top_load_kg")
    first_volume = first.get("total_volume_kg") or 0
    last_volume = last.get("total_volume_kg") or 0
    active_weeks = len({_week_start_for(_parse_iso_date(item["workout_date"])).isoformat() for item in trend})
    frequency_ratio = active_weeks / max(weeks, 1)

    if first_load is not None and last_load is not None and last_load > first_load:
        return {
            "headline": "Load is trending up",
            "detail": f"Top load moved from {_round_number(first_load)} kg to {_round_number(last_load)} kg in the selected window.",
            "tone": "up",
        }
    if last_volume > first_volume:
        return {
            "headline": "Volume is trending up",
            "detail": f"Per-session volume moved from {_round_number(first_volume)} kg to {_round_number(last_volume)} kg.",
            "tone": "up",
        }
    if frequency_ratio >= 0.6 and len(trend) >= 2:
        return {
            "headline": "Frequency is stable",
            "detail": f"This lift appeared in {active_weeks} of the last {weeks} tracked weeks.",
            "tone": "steady",
        }
    return {
        "headline": "Trend is mostly flat",
        "detail": "Load, volume, and frequency are present but not clearly rising in the selected window.",
        "tone": "flat",
    }


def _selected_exercise_payload(exercise_name: Optional[str], ranked_exercises: list[dict], trends: dict[str, list[dict]], weeks: int) -> Optional[dict]:
    if not ranked_exercises:
        return None
    selected = next((item for item in ranked_exercises if item["exercise_name"] == exercise_name), None) if exercise_name else None
    if not selected:
        selected = ranked_exercises[0]
    trend = trends.get(selected["exercise_name"], [])
    return {
        **selected,
        "trend": trend,
        "progression": _progression_summary(trend, weeks),
    }


def _recent_sessions(filtered_sessions: list[dict], limit: int = 8) -> list[dict]:
    latest = sorted(
        filtered_sessions,
        key=lambda item: (item["workout_timestamp"], item["id"]),
        reverse=True,
    )[:limit]
    payload = []
    for session in latest:
        payload.append(
            {
                "id": session["id"],
                "workout_timestamp": session["workout_timestamp"],
                "workout_date": session["workout_date"],
                "title": session["title"],
                "total_duration_seconds": session["total_duration_seconds"],
                "calories": session["calories"],
                "source": session.get("source"),
                "matched_activity": session["matched_activity"],
                "exercise_count": session["exercise_count"],
                "set_count": session["set_count"],
                "rep_count": session["rep_count"],
                "total_volume_kg": session["total_volume_kg"],
                "major_exercises": [exercise["exercise_name"] for exercise in session["exercises"][:3]],
            }
        )
    return payload


def _recent_sessions_with_detail(filtered_sessions: list[dict], limit: int = 8) -> list[dict]:
    latest = sorted(
        filtered_sessions,
        key=lambda item: (item["workout_timestamp"], item["id"]),
        reverse=True,
    )[:limit]
    payload = []
    for session in latest:
        payload.append(
            {
                "id": session["id"],
                "workout_timestamp": session["workout_timestamp"],
                "workout_date": session["workout_date"],
                "title": session["title"],
                "total_duration_seconds": session["total_duration_seconds"],
                "calories": session["calories"],
                "source": session.get("source"),
                "matched_activity": session["matched_activity"],
                "exercise_count": session["exercise_count"],
                "set_count": session["set_count"],
                "rep_count": session["rep_count"],
                "total_volume_kg": session["total_volume_kg"],
                "major_exercises": [exercise["exercise_name"] for exercise in session["exercises"][:3]],
                "exercises": [
                    {
                        "id": exercise["id"],
                        "exercise_order": exercise["exercise_order"],
                        "exercise_name": exercise["exercise_name"],
                        "body_part": exercise["body_part"],
                        "set_count": exercise["set_count"],
                        "rep_count": exercise["rep_count"],
                        "total_volume_kg": exercise["total_volume_kg"],
                        "work_set_count": exercise["work_set_count"],
                        "warmup_set_count": exercise["warmup_set_count"],
                        "sets": [
                            {
                                "id": set_row["id"],
                                "set_order": set_row["set_order"],
                                "reps": set_row["reps"],
                                "weight_kg": set_row["weight_kg"],
                                "is_warmup": set_row["is_warmup"],
                            }
                            for set_row in exercise["sets"]
                        ],
                    }
                    for exercise in session["exercises"]
                ],
            }
        )
    return payload


def _match_pr_pattern(exercise_name: str) -> Optional[dict]:
    normalized = _normalize_name(exercise_name)
    for pattern in IMPORTANT_PR_PATTERNS:
        if any(token in normalized for token in pattern["tokens"]):
            return pattern
    return None


def _important_prs(trends: dict[str, list[dict]]) -> list[dict]:
    prs: dict[str, dict] = {}
    for exercise_name, trend in trends.items():
        pattern = _match_pr_pattern(exercise_name)
        if not pattern:
            continue
        best_point = None
        for point in trend:
            top_load = point.get("top_load_kg")
            if top_load is None:
                continue
            if best_point is None or top_load > best_point["top_load_kg"]:
                best_point = {
                    "exercise_name": exercise_name,
                    "label": pattern["label"],
                    "key": pattern["key"],
                    "top_load_kg": top_load,
                    "workout_date": point["workout_date"],
                    "workout_timestamp": point["workout_timestamp"],
                    "matched_activity": point.get("matched_activity"),
                }
        if not best_point:
            continue
        current = prs.get(pattern["key"])
        if current is None or best_point["top_load_kg"] > current["top_load_kg"]:
            prs[pattern["key"]] = best_point
    ordered = []
    for pattern in IMPORTANT_PR_PATTERNS:
        item = prs.get(pattern["key"])
        if item:
            ordered.append(item)
    return ordered


def get_strength_overview_data(
    conn: sqlite3.Connection,
    *,
    weeks: int = 8,
    body_part: Optional[str] = None,
    exercise: Optional[str] = None,
) -> dict:
    normalized_weeks = weeks if weeks in {4, 8, 12} else 8
    selected_body_part = body_part if body_part in {"all", *BODY_PART_LABELS.keys()} else "all"
    window_start = _window_start_for_weeks(normalized_weeks)

    sessions, filtered_sessions = _filtered_sessions(
        conn,
        window_start=window_start,
        body_part=selected_body_part,
    )
    body_part_options = _body_part_breakdown(sessions)

    ranked_exercises, trends = _build_exercise_aggregates(filtered_sessions, normalized_weeks)
    selected_exercise = _selected_exercise_payload(exercise, ranked_exercises, trends, normalized_weeks)

    summary = {
        "session_count": len(filtered_sessions),
        "total_volume_kg": _round_number(sum(session["total_volume_kg"] or 0 for session in filtered_sessions)),
        "total_sets": sum(session["set_count"] for session in filtered_sessions),
        "total_reps": sum(session["rep_count"] for session in filtered_sessions),
        "unique_exercises": len(ranked_exercises),
    }

    return {
        "window": {
            "weeks": normalized_weeks,
            "start_date": window_start.isoformat(),
            "end_date": date.today().isoformat(),
        },
        "filters": {
            "body_part": selected_body_part,
            "exercise": selected_exercise["exercise_name"] if selected_exercise else None,
            "body_part_options": body_part_options,
            "exercise_options": [
                {
                    "exercise_name": item["exercise_name"],
                    "body_part": item["body_part"],
                    "appearance_count": item["appearance_count"],
                }
                for item in ranked_exercises[:32]
            ],
        },
        "summary": summary,
        "weekly": _weekly_trend(filtered_sessions, normalized_weeks, window_start),
        "important_prs": _important_prs(trends),
        "exercises": ranked_exercises[:12],
        "selected_exercise": selected_exercise,
        "sessions": _recent_sessions_with_detail(filtered_sessions),
        "heuristics": {
            "body_part_mapping_version": "strength_view_v1",
            "note": "Body-part filters use explicit keyword heuristics over recorded exercise names and may not classify every variant cleanly.",
        },
    }


def get_strength_context_data(
    conn: sqlite3.Connection,
    *,
    weeks: int = 8,
    body_part: Optional[str] = None,
    exercise: Optional[str] = None,
) -> dict:
    overview = get_strength_overview_data(
        conn,
        weeks=weeks,
        body_part=body_part,
        exercise=exercise,
    )
    _, filtered_sessions = _filtered_sessions(
        conn,
        window_start=date.fromisoformat(overview["window"]["start_date"]),
        body_part=overview["filters"]["body_part"],
    )
    selected_exercise = overview.get("selected_exercise")
    recurring_lifts = overview.get("exercises", [])

    return {
        "window": overview["window"],
        "filters": {
            "body_part": overview["filters"]["body_part"],
            "exercise": overview["filters"]["exercise"],
        },
        "summary": overview["summary"],
        "recurring_lifts": recurring_lifts,
        "selected_exercise": selected_exercise,
        "important_prs": overview["important_prs"],
        "recent_sessions": _recent_sessions_with_detail(filtered_sessions),
        "weekly_trend": overview["weekly"],
        "body_part_options": overview["filters"]["body_part_options"],
        "exercise_options": overview["filters"]["exercise_options"],
        "data_source": {
            "kind": "linked_exercise_level_strength_history",
            "included_session_criteria": [
                "Completed TrainLog session explicitly linked to a WeightTraining activity, or matched Fitbod session",
                "completed exercise and set detail is present",
                "TrainLog is preferred when both sources refer to the same activity",
            ],
            "exclusion_note": "Unlinked sessions and generic WeightTraining activities without exercise-level detail are excluded.",
        },
        "heuristics": overview["heuristics"],
    }
