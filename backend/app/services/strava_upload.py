"""Strength and rehab workouts recorded by TrainLog on the Apple Watch, uploaded to Strava.

Strava imports Apple Health workouts from Apple's own Workout app only, so a workout the TrainLog
Watch app saved never reaches it. Once the phone has pushed the workout (``health_workouts``) and
it's linked to the strength session or rehab routine it recorded, this uploads it with Strava's
JSON format: the sets (exercise, reps, weight, hold) and the heart-rate stream. Strava shows them
as its own exercise list.

The upload's Strava id is stored as the activity's ``strava`` source ref straight away, so the
next Strava import updates the same row instead of adding a second one. Needs the
``activity:write`` scope (reconnect Strava once); without it nothing is sent.
"""

import json
import logging
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

import httpx

from .activity_sources import upsert_source_ref
from .strava import get_strava_access_token

logger = logging.getLogger(__name__)

STRAVA_UPLOADS_URL = "https://www.strava.com/api/v3/uploads"
UPLOAD_SCOPE = "activity:write"
TRAINLOG_BUNDLE = "com.ronek22.trainlog"
# Older workouts are left alone: they were before this existed, or Strava has them another way.
LOOKBACK_DAYS = 3
MAX_ATTEMPTS = 4
POLL_SECONDS = 1.5
POLL_TRIES = 8

# TrainLog exercise names to Strava's exercise_type, first match wins: every word of the key in
# the name. The specific ones come before their family's generic one.
EXERCISE_RULES: tuple[tuple[str, str], ...] = (
    ("incline barbell bench", "INCLINE_BARBELL_BENCH_PRESS"),
    ("barbell incline bench", "INCLINE_BARBELL_BENCH_PRESS"),
    ("incline dumbbell bench", "INCLINE_DUMBBELL_BENCH_PRESS"),
    ("dumbbell bench", "DUMBBELL_BENCH_PRESS"),
    ("barbell bench", "BARBELL_BENCH_PRESS"),
    ("bench press", "BENCH_PRESS_GENERIC"),
    ("seated calf", "SEATED_CALF_RAISE"),
    ("standing calf", "STANDING_CALF_RAISE"),
    ("calf", "CALF_RAISE_GENERIC"),
    ("incline curl", "INCLINE_DUMBBELL_BICEPS_CURL"),
    ("incline dumbbell curl", "INCLINE_DUMBBELL_BICEPS_CURL"),
    ("hammer curl", "DUMBBELL_HAMMER_CURL"),
    ("barbell curl", "BARBELL_BICEPS_CURL"),
    ("dumbbell curl", "STANDING_DUMBBELL_BICEPS_CURL"),
    ("curl", "CURL_GENERIC"),
    ("romanian deadlift", "ROMANIAN_DEADLIFTS"),
    ("rdl", "ROMANIAN_DEADLIFTS"),
    ("deadlift", "DEADLIFT_GENERIC"),
    ("rear delt", "DUMBBELL_REAR_DELT_FLY"),
    ("fly", "FLYE_GENERIC"),
    ("flye", "FLYE_GENERIC"),
    ("glute bridge", "GLUTE_BRIDGE"),
    ("hip thrust", "HIP_THRUST"),
    ("bridge", "HIP_RAISE_GENERIC"),
    ("clam", "CLAMS"),
    ("side lying hip abduction", "SIDE_LYING_LEG_RAISE"),
    ("hip abduction", "STANDING_HIP_ABDUCTION"),
    ("hanging leg raise", "HANGING_LEG_RAISE"),
    ("leg raise", "LEG_RAISE_GENERIC"),
    ("lateral raise", "LATERAL_RAISE_GENERIC"),
    ("front raise", "FRONT_RAISE"),
    ("bulgarian split squat", "DUMBBELL_BULGARIAN_SPLIT_SQUATS"),
    ("split squat", "DUMBBELL_SPLIT_SQUAT"),
    ("lunge", "LUNGE_GENERIC"),
    ("pike push", "PIKE_PUSH_UP"),
    ("push up", "PUSH_UP_GENERIC"),
    ("pushup", "PUSH_UP_GENERIC"),
    ("chin up", "CLOSE_GRIP_CHIN_UP"),
    ("pull up", "PULL_UP_GENERIC"),
    ("pulldown", "LAT_PULLDOWN"),
    ("inverted row", "INVERTED_ROW"),
    ("upright row", "BARBELL_UPRIGHT_ROW"),
    ("bent over barbell row", "BENT_OVER_BARBELL_ROW"),
    ("barbell row", "BENT_OVER_BARBELL_ROW"),
    ("dumbbell row", "DUMBBELL_ROW"),
    ("row", "ROW_GENERIC"),
    ("shoulder press", "OVERHEAD_DUMBBELL_PRESS"),
    ("overhead press", "OVERHEAD_BARBELL_PRESS"),
    ("military press", "OVERHEAD_BARBELL_PRESS"),
    ("shrug", "SHRUG_GENERIC"),
    ("skullcrusher", "DUMBBELL_SKULLCRUSHER"),
    ("skull crusher", "SKULL_CRUSHER"),
    ("chest dip", "CHEST_DIP"),
    ("chair dip", "CHAIR_DIPS"),
    ("sofa dip", "CHAIR_DIPS"),
    ("triceps dip", "TRICEP_DIP"),
    ("dip", "BODY_WEIGHT_DIP"),
    ("pushdown", "TRICEPS_PRESSDOWN"),
    ("triceps", "TRICEPS_EXTENSION_GENERIC"),
    ("side plank", "SIDE_PLANK"),
    ("plank", "PLANK_GENERIC"),
    ("dead bug", "DEADBUG"),
    ("bird dog", "BIRD_DOG"),
    ("crunch", "CRUNCH"),
    ("wall sit", "WALL_SIT"),
    ("goblet squat", "GOBLET_SQUAT"),
    ("front squat", "BARBELL_FRONT_SQUAT"),
    ("back squat", "BARBELL_BACK_SQUAT"),
    ("sit to stand", "AIR_SQUAT"),
    ("squat", "SQUAT_GENERIC"),
    ("step up", "STEP_UP"),
    ("leg extension", "MACHINE_LEG_EXTENSION"),
    ("quad", "QUAD"),
    ("hamstring stretch", "STANDING_HAMSTRING_STRETCH"),
    ("stretch", "STRETCH"),
    ("good morning", "GOOD_MORNING"),
    ("nordic", "NORDIC_CURL"),
    ("swing", "KETTLEBELL_SWING"),
    ("carry", "CARRY_GENERIC"),
    ("burpee", "BURPEE"),
)
FALLBACK_EXERCISE = "TOTAL_BODY_GENERIC"


def exercise_type(name: str) -> str:
    """Strava's exercise_type for a TrainLog exercise name ("Push-ups" → PUSH_UP_GENERIC)."""
    text = re.sub(r"\(.*?\)", " ", (name or "").lower())
    words = re.findall(r"[a-z]+", text.replace("-", " "))
    # Plurals and spelling variants: "curls", "push-ups", "bicep".
    normal = {word[:-1] if word.endswith("s") and len(word) >= 3 and not word.endswith("ss") else word for word in words}
    normal |= {"triceps" for word in words if word in {"tricep", "triceps"}}
    for key, value in EXERCISE_RULES:
        if all(part in normal or part in words for part in key.split()):
            return value
    return FALLBACK_EXERCISE


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS strava_uploads (
            activity_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            upload_id TEXT,
            strava_activity_id TEXT,
            error TEXT,
            attempts INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def can_upload(get_setting_fn: Callable[[str], Optional[str]]) -> bool:
    return UPLOAD_SCOPE in (get_setting_fn("strava_scope") or "").split(",")


# MARK: Building the upload


def _strength_sets(conn: sqlite3.Connection, session_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT exercise.exercise_name, sets.actual_reps, sets.target_reps, sets.actual_weight_kg,
               sets.actual_seconds, sets.target_seconds
        FROM strength_session_sets sets
        JOIN strength_session_exercises exercise ON exercise.id = sets.session_exercise_id
        WHERE exercise.session_id = ? AND sets.status = 'completed'
        ORDER BY sets.completed_at, exercise.exercise_order, sets.set_order
        """,
        (session_id,),
    ).fetchall()
    sets = []
    for row in rows:
        item: dict[str, Any] = {"exercise_type": exercise_type(row["exercise_name"])}
        seconds = row["actual_seconds"] or row["target_seconds"]
        if seconds:
            item["duration"] = int(seconds)
        else:
            item["repetitions"] = int(row["actual_reps"] if row["actual_reps"] is not None else row["target_reps"])
        if row["actual_weight_kg"]:
            item["weight"] = float(row["actual_weight_kg"])
        sets.append(item)
    return sets


def _rehab_sets(session: dict) -> list[dict]:
    sets = []
    for exercise in session.get("exercises") or []:
        item: dict[str, Any] = {"exercise_type": exercise_type(exercise.get("name") or "")}
        if exercise.get("seconds"):
            item["duration"] = int(exercise["seconds"])
        elif exercise.get("reps"):
            item["repetitions"] = int(exercise["reps"])
        sets.extend(dict(item) for _ in range(max(1, int(exercise.get("sets") or 1))))
    return sets


def _heart_rate(conn: sqlite3.Connection, activity_id: str) -> Optional[dict]:
    row = conn.execute("SELECT streams_json FROM activity_details WHERE activity_id = ?", (activity_id,)).fetchone()
    if not row or not row["streams_json"]:
        return None
    streams = json.loads(row["streams_json"])
    times = (streams.get("time") or {}).get("data") or []
    beats = (streams.get("heartrate") or {}).get("data") or []
    points = [(int(t), int(round(b))) for t, b in zip(times, beats) if t is not None and b is not None]
    if not points:
        return None
    # Strava wants the timeline to begin at the start: the first reading stands in for second 0.
    if points[0][0] > 0:
        points.insert(0, (0, points[0][1]))
    return {"time": [t for t, _ in points], "heartrate": [b for _, b in points]}


def build_upload(conn: sqlite3.Connection, activity_id: str, started_at: str, end: Optional[str]) -> Optional[dict]:
    """The Strava upload (``file`` JSON plus form fields) for a linked Watch workout, or None when it
    isn't linked to a strength session or rehab routine with something done yet."""
    activity = conn.execute("SELECT name, duration_min, calories FROM activities WHERE id = ?", (activity_id,)).fetchone()
    if not activity:
        return None
    session = conn.execute(
        "SELECT id, template_name FROM strength_workout_sessions WHERE linked_activity_id = ?", (activity_id,)
    ).fetchone()
    if session:
        sets = _strength_sets(conn, session["id"])
        name, sport, description = session["template_name"], "WeightTraining", None
    else:
        completion = conn.execute(
            "SELECT session_json FROM sick_session_completions WHERE activity_id = ? AND session_json IS NOT NULL "
            "ORDER BY started_at DESC LIMIT 1",
            (activity_id,),
        ).fetchone()
        if not completion:
            return None
        routine = json.loads(completion["session_json"])
        sets = _rehab_sets(routine)
        issues = routine.get("issues") or []
        name, sport = "Rehab", "Workout"
        description = issues[0] if issues else None
    if not sets:
        return None

    start = datetime.fromisoformat(started_at)
    elapsed = None
    if end:
        elapsed = int((datetime.fromisoformat(end) - start).total_seconds())
    if not elapsed and activity["duration_min"]:
        elapsed = int(round(activity["duration_min"] * 60))
    body: dict[str, Any] = {
        "version": "1.0",
        # In UTC: Strava fails the upload ("Error Processing Data") for a start with an offset.
        "start_time": start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "utc_offset": int(start.utcoffset().total_seconds()) if start.utcoffset() else 0,
        "elapsed_time": max(1, elapsed or 1),
        "creator": {"name": "TrainLog"},
        "sets": sets,
    }
    if activity["calories"]:
        body["total_calories"] = int(activity["calories"])
    heart_rate = _heart_rate(conn, activity_id)
    if heart_rate:
        body["streams"] = heart_rate
    return {
        "file": body,
        "form": {
            "data_type": "json",
            "sport_type": sport,
            "name": name,
            "description": "\n".join(filter(None, [description, "Recorded with TrainLog on Apple Watch."])),
            "external_id": f"trainlog-{activity_id.replace(':', '-')}",
        },
    }


# MARK: Uploading


def _candidates(conn: sqlite3.Connection, now: datetime) -> list[sqlite3.Row]:
    since = (now - timedelta(days=LOOKBACK_DAYS)).date().isoformat()
    return conn.execute(
        """
        SELECT ref.activity_id, ref.started_at, json_extract(ref.metadata_json, '$.end') AS ended_at
        FROM activity_source_refs ref
        LEFT JOIN strava_uploads upload ON upload.activity_id = ref.activity_id
        WHERE ref.source = 'healthkit' AND ref.activity_id IS NOT NULL
          AND substr(ref.started_at, 1, 10) >= ?
          AND (json_extract(ref.metadata_json, '$.source_bundle') = ?
               OR json_extract(ref.metadata_json, '$.source_bundle') LIKE ?)
          AND NOT EXISTS (
              SELECT 1 FROM activity_source_refs strava
              WHERE strava.source = 'strava' AND strava.activity_id = ref.activity_id
          )
          AND (upload.activity_id IS NULL OR (upload.status = 'failed' AND upload.attempts < ?))
        ORDER BY ref.started_at
        """,
        (since, TRAINLOG_BUNDLE, f"{TRAINLOG_BUNDLE}.%", MAX_ATTEMPTS),
    ).fetchall()


def _record(conn: sqlite3.Connection, activity_id: str, status: str, **fields: Any) -> None:
    conn.execute(
        """
        INSERT INTO strava_uploads (activity_id, status, upload_id, strava_activity_id, error, attempts)
        VALUES (?, ?, ?, ?, ?, 1)
        ON CONFLICT(activity_id) DO UPDATE SET
            status = excluded.status,
            upload_id = COALESCE(excluded.upload_id, upload_id),
            strava_activity_id = COALESCE(excluded.strava_activity_id, strava_activity_id),
            error = excluded.error,
            attempts = attempts + 1,
            updated_at = CURRENT_TIMESTAMP
        """,
        (activity_id, status, fields.get("upload_id"), fields.get("strava_activity_id"), fields.get("error")),
    )
    conn.commit()


def _duplicate_of(error: str) -> Optional[str]:
    match = re.search(r"/activities/(\d+)", error or "")
    return match.group(1) if match else None


def _send(
    client: httpx.Client, token: str, upload: dict, sleep: Callable[[float], None]
) -> tuple[str, dict]:
    """Posts one upload and waits for Strava to process it: ("uploaded" | "duplicate" | "failed", fields)."""
    headers = {"Authorization": f"Bearer {token}"}
    file_name = upload["form"]["external_id"] + ".json"
    response = client.post(
        STRAVA_UPLOADS_URL,
        headers=headers,
        data=upload["form"],
        files={"file": (file_name, json.dumps(upload["file"]).encode(), "application/json")},
    )
    if response.status_code >= 400:
        return "failed", {"error": f"{response.status_code}: {response.text[:300]}"}
    status = response.json()
    for _ in range(POLL_TRIES):
        if status.get("activity_id") or status.get("error"):
            break
        sleep(POLL_SECONDS)
        polled = client.get(f"{STRAVA_UPLOADS_URL}/{status['id']}", headers=headers)
        if polled.status_code >= 400:
            break
        status = polled.json()
    fields = {"upload_id": str(status.get("id") or "")}
    if status.get("activity_id"):
        return "uploaded", {**fields, "strava_activity_id": str(status["activity_id"])}
    error = status.get("error") or "Strava was still processing the upload."
    if "duplicate" in error.lower():
        return "duplicate", {**fields, "strava_activity_id": _duplicate_of(error), "error": error}
    return "failed", {**fields, "error": error}


def upload_watch_workouts(
    conn: sqlite3.Connection,
    get_setting_fn: Callable[[str], Optional[str]],
    set_setting_fn: Callable[[str, str], None],
    *,
    now: Optional[datetime] = None,
    client: Optional[httpx.Client] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict]:
    """Uploads every recent TrainLog Watch workout that's linked and not on Strava yet."""
    ensure_table(conn)
    if not can_upload(get_setting_fn):
        return []
    uploads = []
    for row in _candidates(conn, now or datetime.now()):
        upload = build_upload(conn, row["activity_id"], row["started_at"], row["ended_at"])
        if upload:
            uploads.append((row, upload))
    if not uploads:
        return []

    token = get_strava_access_token(get_setting_fn, set_setting_fn)
    results = []
    with (client or httpx.Client(timeout=30)) as http:
        for row, upload in uploads:
            activity_id = row["activity_id"]
            try:
                status, fields = _send(http, token, upload, sleep)
            except httpx.HTTPError as error:
                status, fields = "failed", {"error": str(error)}
            _record(conn, activity_id, status, **fields)
            if fields.get("strava_activity_id"):
                upsert_source_ref(
                    conn, source="strava", external_id=fields["strava_activity_id"], activity_id=activity_id,
                    started_at=row["started_at"], status="linked", match_reason="Uploaded from the TrainLog Watch workout.",
                )
                conn.commit()
            results.append({"activity_id": activity_id, "status": status, **fields})
    return results


def run_watch_uploads() -> None:
    """For background tasks and the Strava loop: never raises."""
    from ..db import get_db
    from .settings import get_setting, set_setting

    conn = get_db()
    try:
        from .guided_sessions import reconcile_guided_session_activities

        # A rehab finished before its workout synced is linked here first.
        reconcile_guided_session_activities(conn)
        for result in upload_watch_workouts(conn, get_setting, set_setting):
            logger.info("Strava upload %s: %s", result["activity_id"], result["status"])
    except Exception:
        logger.exception("Uploading Watch workouts to Strava failed")
    finally:
        conn.close()
