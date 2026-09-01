import os
import sqlite3

DEFAULT_DB_PATH = "/data/training.db"
DB_PATH = os.getenv("TRAINING_DB_PATH", DEFAULT_DB_PATH)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


NON_STRENGTH_EXERCISES = {
    "bike",
    "biking",
    "cycling",
    "elliptical",
    "hike",
    "hiking",
    "ride",
    "row",
    "rowing",
    "run",
    "running",
    "stairclimber",
    "stairmaster",
    "swim",
    "swimming",
    "walk",
    "walking",
    "yoga",
}
NON_STRENGTH_PREFIXES = tuple(sorted(NON_STRENGTH_EXERCISES, key=len, reverse=True))


def _normalize_fitbod_exercise_name(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _looks_like_non_strength_fitbod_exercise(value: str | None) -> bool:
    normalized = _normalize_fitbod_exercise_name(value)
    if not normalized:
        return False
    if normalized in NON_STRENGTH_EXERCISES:
        return True
    return normalized.startswith(NON_STRENGTH_PREFIXES)


def _recompute_fitbod_batch_counters(conn: sqlite3.Connection, batch_id: int) -> None:
    row = conn.execute(
        """
        SELECT
            COUNT(*) AS raw_row_count,
            SUM(CASE WHEN row_kind = 'strength' THEN 1 ELSE 0 END) AS strength_row_count,
            SUM(CASE WHEN row_kind = 'ignored' THEN 1 ELSE 0 END) AS ignored_row_count,
            SUM(CASE WHEN row_kind = 'rejected' THEN 1 ELSE 0 END) AS rejected_row_count
        FROM fitbod_import_rows
        WHERE batch_id = ?
        """,
        (batch_id,),
    ).fetchone()
    session_row = conn.execute(
        """
        SELECT
            COUNT(*) AS session_count,
            SUM(CASE WHEN match_status = 'matched' THEN 1 ELSE 0 END) AS matched_count,
            SUM(CASE WHEN match_status = 'ambiguous' THEN 1 ELSE 0 END) AS ambiguous_count,
            SUM(CASE WHEN match_status = 'unmatched' THEN 1 ELSE 0 END) AS unmatched_count
        FROM fitbod_workout_sessions
        WHERE batch_id = ?
        """,
        (batch_id,),
    ).fetchone()
    conn.execute(
        """
        UPDATE fitbod_import_batches
        SET raw_row_count = ?,
            strength_row_count = ?,
            ignored_row_count = ?,
            rejected_row_count = ?,
            session_count = ?,
            matched_count = ?,
            ambiguous_count = ?,
            unmatched_count = ?
        WHERE id = ?
        """,
        (
            int(row["raw_row_count"] or 0),
            int(row["strength_row_count"] or 0),
            int(row["ignored_row_count"] or 0),
            int(row["rejected_row_count"] or 0),
            int(session_row["session_count"] or 0),
            int(session_row["matched_count"] or 0),
            int(session_row["ambiguous_count"] or 0),
            int(session_row["unmatched_count"] or 0),
            batch_id,
        ),
    )


def _cleanup_existing_fitbod_non_strength_sessions(conn: sqlite3.Connection) -> None:
    if not conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'fitbod_workout_sessions'"
    ).fetchone():
        return

    sessions = conn.execute(
        """
        SELECT id, batch_id, workout_timestamp
        FROM fitbod_workout_sessions
        ORDER BY id ASC
        """
    ).fetchall()
    affected_batches: set[int] = set()

    for session in sessions:
        exercise_rows = conn.execute(
            """
            SELECT id, exercise_name
            FROM fitbod_workout_exercises
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session["id"],),
        ).fetchall()
        if not exercise_rows:
            continue
        exercise_names = [row["exercise_name"] for row in exercise_rows]
        if not all(_looks_like_non_strength_fitbod_exercise(name) for name in exercise_names):
            continue

        affected_batches.add(int(session["batch_id"]))
        reason = f"Retrospective cleanup filtered non-strength modality rows: {', '.join(exercise_names)}."
        conn.execute(
            """
            UPDATE fitbod_import_rows
            SET row_kind = 'ignored',
                ignore_reason = ?
            WHERE batch_id = ? AND workout_timestamp = ? AND row_kind = 'strength'
            """,
            (reason, session["batch_id"], session["workout_timestamp"]),
        )

        exercise_ids = [row["id"] for row in exercise_rows]
        if exercise_ids:
            placeholders = ",".join("?" for _ in exercise_ids)
            conn.execute(
                f"DELETE FROM fitbod_workout_sets WHERE exercise_id IN ({placeholders})",
                exercise_ids,
            )
            conn.execute(
                f"DELETE FROM fitbod_workout_exercises WHERE id IN ({placeholders})",
                exercise_ids,
            )
        conn.execute(
            "DELETE FROM fitbod_workout_sessions WHERE id = ?",
            (session["id"],),
        )

    for batch_id in affected_batches:
        _recompute_fitbod_batch_counters(conn, batch_id)


def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS activities (
            id TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            type TEXT NOT NULL,
            workout_intent TEXT,
            name TEXT,
            distance_km REAL,
            duration_min REAL,
            avg_hr INTEGER,
            max_hr INTEGER,
            avg_pace TEXT,
            avg_watts REAL,
            elevation_m INTEGER,
            calories INTEGER,
            zone2 INTEGER DEFAULT 0,
            notes TEXT,
            linked_planned_session_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS activity_source_refs (
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            activity_id TEXT,
            started_at TEXT,
            file_name TEXT,
            file_hash TEXT,
            status TEXT NOT NULL DEFAULT 'linked',
            match_reason TEXT,
            metadata_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (source, external_id),
            FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_activity_source_refs_activity
        ON activity_source_refs(activity_id);

        CREATE INDEX IF NOT EXISTS idx_activity_source_refs_started
        ON activity_source_refs(source, started_at);

        CREATE TABLE IF NOT EXISTS coach_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS coach_chat_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT 'New conversation',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS coach_chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(conversation_id) REFERENCES coach_chat_conversations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS weekly_summary (
            week_start TEXT PRIMARY KEY,
            run_km REAL DEFAULT 0,
            ride_km REAL DEFAULT 0,
            strength_sessions INTEGER DEFAULT 0,
            total_elevation INTEGER DEFAULT 0,
            avg_hr REAL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            metric TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS health_data_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            file_hash TEXT NOT NULL UNIQUE,
            file_size INTEGER NOT NULL,
            file_modified_ns INTEGER NOT NULL,
            export_date TEXT,
            status TEXT NOT NULL DEFAULT 'imported',
            samples_seen INTEGER NOT NULL DEFAULT 0,
            samples_inserted INTEGER NOT NULL DEFAULT 0,
            import_version INTEGER NOT NULL DEFAULT 1,
            metadata_json TEXT,
            imported_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_health_data_import_file
        ON health_data_imports(file_name, file_size, file_modified_ns);

        CREATE TABLE IF NOT EXISTS health_metric_samples (
            sample_key TEXT PRIMARY KEY,
            metric TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            end_timestamp TEXT,
            date TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT,
            category_label TEXT,
            duration_seconds REAL,
            source_name TEXT,
            source_bundle TEXT,
            source_device TEXT,
            import_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(import_id) REFERENCES health_data_imports(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_health_metric_samples_metric_date
        ON health_metric_samples(metric, date DESC);

        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS weekly_plans (
            week_start TEXT PRIMARY KEY,
            title TEXT,
            focus TEXT,
            overview TEXT,
            days_json TEXT NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS plan_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start TEXT NOT NULL,
            effective_from TEXT NOT NULL,
            adaptation_reason TEXT,
            changed_dates_json TEXT NOT NULL,
            preserved_dates_json TEXT NOT NULL,
            previous_plan_json TEXT NOT NULL,
            updated_plan_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS coaching_snapshots (
            week_start TEXT PRIMARY KEY,
            week_end TEXT,
            summary_status TEXT NOT NULL,
            headline TEXT NOT NULL,
            rationale_summary TEXT,
            recommendation_status TEXT NOT NULL,
            recommendation_action TEXT,
            focus_for_next_48h TEXT,
            proposed_changed_dates_json TEXT NOT NULL,
            revision_count INTEGER DEFAULT 0,
            generated_at TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS activity_stream_summaries (
            activity_id TEXT PRIMARY KEY,
            fetched_at TEXT NOT NULL,
            source TEXT NOT NULL,
            hr_trimp REAL,
            power_tss REAL,
            normalized_power REAL,
            low_aerobic_seconds INTEGER DEFAULT 0,
            high_aerobic_seconds INTEGER DEFAULT 0,
            anaerobic_seconds INTEGER DEFAULT 0,
            has_heartrate INTEGER DEFAULT 0,
            has_watts INTEGER DEFAULT 0,
            stream_version TEXT DEFAULT 'v1'
        );

        CREATE TABLE IF NOT EXISTS activity_details (
            activity_id TEXT PRIMARY KEY,
            fetched_at TEXT NOT NULL,
            source_status TEXT NOT NULL,
            detail_json TEXT,
            streams_json TEXT,
            charts_json TEXT,
            best_efforts_json TEXT,
            derived_version TEXT,
            route_polyline TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS activity_analyses (
            activity_id TEXT PRIMARY KEY,
            context_signature TEXT NOT NULL,
            context_json TEXT NOT NULL,
            analysis_json TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            generator TEXT DEFAULT 'llm',
            model_name TEXT,
            requested_via TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS activity_analysis_requests (
            activity_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            requested_at TEXT NOT NULL,
            requested_via TEXT NOT NULL,
            context_signature TEXT NOT NULL,
            last_error TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            period_type TEXT NOT NULL,
            goal_family TEXT DEFAULT 'accumulation',
            metric_type TEXT NOT NULL,
            target_value REAL NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            activity_type TEXT,
            is_active INTEGER DEFAULT 1,
            target_config_json TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS activity_feedback (
            activity_id TEXT PRIMARY KEY,
            rpe INTEGER NOT NULL,
            energy INTEGER NOT NULL,
            muscle_soreness INTEGER NOT NULL,
            pain_level INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS fitbod_import_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            file_hash TEXT NOT NULL UNIQUE,
            parser_version TEXT NOT NULL,
            grouping_version TEXT NOT NULL,
            imported_at TEXT NOT NULL,
            raw_row_count INTEGER NOT NULL DEFAULT 0,
            strength_row_count INTEGER NOT NULL DEFAULT 0,
            ignored_row_count INTEGER NOT NULL DEFAULT 0,
            rejected_row_count INTEGER NOT NULL DEFAULT 0,
            session_count INTEGER NOT NULL DEFAULT 0,
            matched_count INTEGER NOT NULL DEFAULT 0,
            ambiguous_count INTEGER NOT NULL DEFAULT 0,
            unmatched_count INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS fitbod_import_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            row_index INTEGER NOT NULL,
            row_kind TEXT NOT NULL,
            workout_timestamp TEXT,
            exercise_name TEXT,
            ignore_reason TEXT,
            raw_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(batch_id) REFERENCES fitbod_import_batches(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS fitbod_workout_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id INTEGER NOT NULL,
            session_key TEXT NOT NULL,
            workout_timestamp TEXT NOT NULL,
            workout_date TEXT NOT NULL,
            title TEXT,
            exercise_count INTEGER NOT NULL DEFAULT 0,
            set_count INTEGER NOT NULL DEFAULT 0,
            rep_count INTEGER NOT NULL DEFAULT 0,
            total_volume_kg REAL,
            total_duration_seconds REAL,
            total_distance_m REAL,
            calories INTEGER,
            match_status TEXT NOT NULL DEFAULT 'unmatched',
            matched_activity_id TEXT,
            match_confidence REAL,
            match_provenance TEXT,
            match_reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(batch_id) REFERENCES fitbod_import_batches(id) ON DELETE CASCADE,
            FOREIGN KEY(matched_activity_id) REFERENCES activities(id) ON DELETE SET NULL,
            UNIQUE(batch_id, session_key)
        );

        CREATE TABLE IF NOT EXISTS fitbod_workout_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            exercise_order INTEGER NOT NULL,
            exercise_name TEXT NOT NULL,
            set_count INTEGER NOT NULL DEFAULT 0,
            rep_count INTEGER NOT NULL DEFAULT 0,
            total_volume_kg REAL,
            work_set_count INTEGER NOT NULL DEFAULT 0,
            warmup_set_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES fitbod_workout_sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS fitbod_workout_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id INTEGER NOT NULL,
            set_order INTEGER NOT NULL,
            reps INTEGER,
            weight_kg REAL,
            duration_seconds REAL,
            distance_m REAL,
            incline REAL,
            resistance REAL,
            is_warmup INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            multiplier REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(exercise_id) REFERENCES fitbod_workout_exercises(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS fitbod_session_decisions (
            workout_timestamp TEXT PRIMARY KEY,
            decision_type TEXT NOT NULL,
            activity_id TEXT,
            reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS strength_workout_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS strength_template_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER NOT NULL,
            exercise_order INTEGER NOT NULL,
            exercise_name TEXT NOT NULL,
            set_count INTEGER NOT NULL,
            target_reps INTEGER NOT NULL,
            target_weight_kg REAL,
            rest_seconds INTEGER NOT NULL DEFAULT 90,
            notes TEXT,
            FOREIGN KEY(template_id) REFERENCES strength_workout_templates(id) ON DELETE CASCADE,
            UNIQUE(template_id, exercise_order)
        );

        CREATE TABLE IF NOT EXISTS strength_workout_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER,
            template_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            started_at TEXT NOT NULL,
            completed_at TEXT,
            current_exercise_order INTEGER NOT NULL DEFAULT 1,
            current_set_order INTEGER NOT NULL DEFAULT 1,
            linked_activity_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(template_id) REFERENCES strength_workout_templates(id) ON DELETE SET NULL,
            FOREIGN KEY(linked_activity_id) REFERENCES activities(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_strength_sessions_status
        ON strength_workout_sessions(status, started_at DESC);

        CREATE TABLE IF NOT EXISTS strength_session_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            exercise_order INTEGER NOT NULL,
            exercise_name TEXT NOT NULL,
            notes TEXT,
            FOREIGN KEY(session_id) REFERENCES strength_workout_sessions(id) ON DELETE CASCADE,
            UNIQUE(session_id, exercise_order)
        );

        CREATE TABLE IF NOT EXISTS strength_session_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_exercise_id INTEGER NOT NULL,
            set_order INTEGER NOT NULL,
            target_reps INTEGER NOT NULL,
            target_weight_kg REAL,
            rest_seconds INTEGER NOT NULL DEFAULT 90,
            actual_reps INTEGER,
            actual_weight_kg REAL,
            status TEXT NOT NULL DEFAULT 'pending',
            completed_at TEXT,
            rest_ends_at TEXT,
            FOREIGN KEY(session_exercise_id) REFERENCES strength_session_exercises(id) ON DELETE CASCADE,
            UNIQUE(session_exercise_id, set_order)
        );
    """)

    feedback_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(activity_feedback)").fetchall()
    }
    activity_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(activities)").fetchall()
    }
    goal_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(goals)").fetchall()
    }
    activity_detail_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(activity_details)").fetchall()
    }
    activity_analysis_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(activity_analyses)").fetchall()
    }
    activity_analysis_request_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(activity_analysis_requests)").fetchall()
    }
    health_import_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(health_data_imports)").fetchall()
    }
    health_sample_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(health_metric_samples)").fetchall()
    }
    chat_message_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(coach_chat_messages)").fetchall()
    }
    if "conversation_id" not in chat_message_columns:
        conn.execute("ALTER TABLE coach_chat_messages ADD COLUMN conversation_id INTEGER")
    if conn.execute("SELECT 1 FROM coach_chat_messages WHERE conversation_id IS NULL LIMIT 1").fetchone():
        cursor = conn.execute(
            "INSERT INTO coach_chat_conversations (title) VALUES (?)",
            ("Previous conversation",),
        )
        conn.execute(
            "UPDATE coach_chat_messages SET conversation_id = ? WHERE conversation_id IS NULL",
            (cursor.lastrowid,),
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_coach_chat_messages_conversation ON coach_chat_messages(conversation_id, id)"
    )
    if "import_version" not in health_import_columns:
        conn.execute("ALTER TABLE health_data_imports ADD COLUMN import_version INTEGER NOT NULL DEFAULT 1")
    if "end_timestamp" not in health_sample_columns:
        conn.execute("ALTER TABLE health_metric_samples ADD COLUMN end_timestamp TEXT")
    if "category_label" not in health_sample_columns:
        conn.execute("ALTER TABLE health_metric_samples ADD COLUMN category_label TEXT")
    if "duration_seconds" not in health_sample_columns:
        conn.execute("ALTER TABLE health_metric_samples ADD COLUMN duration_seconds REAL")
    if "linked_planned_session_id" not in activity_columns:
        conn.execute("ALTER TABLE activities ADD COLUMN linked_planned_session_id TEXT")
    if "workout_intent" not in activity_columns:
        conn.execute("ALTER TABLE activities ADD COLUMN workout_intent TEXT")
    if "goal_family" not in goal_columns:
        conn.execute("ALTER TABLE goals ADD COLUMN goal_family TEXT DEFAULT 'accumulation'")
    if "target_config_json" not in goal_columns:
        conn.execute("ALTER TABLE goals ADD COLUMN target_config_json TEXT")
    if activity_detail_columns and "route_polyline" not in activity_detail_columns:
        conn.execute("ALTER TABLE activity_details ADD COLUMN route_polyline TEXT")
    if activity_detail_columns and "charts_json" not in activity_detail_columns:
        conn.execute("ALTER TABLE activity_details ADD COLUMN charts_json TEXT")
    if activity_detail_columns and "best_efforts_json" not in activity_detail_columns:
        conn.execute("ALTER TABLE activity_details ADD COLUMN best_efforts_json TEXT")
    if activity_detail_columns and "derived_version" not in activity_detail_columns:
        conn.execute("ALTER TABLE activity_details ADD COLUMN derived_version TEXT")
    if activity_analysis_columns and "generator" not in activity_analysis_columns:
        conn.execute("ALTER TABLE activity_analyses ADD COLUMN generator TEXT DEFAULT 'llm'")
    if activity_analysis_columns and "model_name" not in activity_analysis_columns:
        conn.execute("ALTER TABLE activity_analyses ADD COLUMN model_name TEXT")
    if activity_analysis_columns and "requested_via" not in activity_analysis_columns:
        conn.execute("ALTER TABLE activity_analyses ADD COLUMN requested_via TEXT")
    if not activity_analysis_request_columns:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_analysis_requests (
                activity_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                requested_at TEXT NOT NULL,
                requested_via TEXT NOT NULL,
                context_signature TEXT NOT NULL,
                last_error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE
            )
            """
        )

    if "heel_pain" in feedback_columns:
        pain_level_expr = "COALESCE(pain_level, heel_pain, 0)" if "pain_level" in feedback_columns else "COALESCE(heel_pain, 0)"
        conn.execute("ALTER TABLE activity_feedback RENAME TO activity_feedback_legacy")
        conn.execute(
            """
            CREATE TABLE activity_feedback (
                activity_id TEXT PRIMARY KEY,
                rpe INTEGER NOT NULL,
                energy INTEGER NOT NULL,
                muscle_soreness INTEGER NOT NULL,
                pain_level INTEGER NOT NULL DEFAULT 0,
                note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(activity_id) REFERENCES activities(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            f"""
            INSERT INTO activity_feedback
            (activity_id, rpe, energy, muscle_soreness, pain_level, note, created_at, updated_at)
            SELECT
                activity_id,
                rpe,
                energy,
                muscle_soreness,
                {pain_level_expr},
                note,
                created_at,
                updated_at
            FROM activity_feedback_legacy
            """
        )
        conn.execute("DROP TABLE activity_feedback_legacy")
    elif "pain_level" not in feedback_columns:
        conn.execute("ALTER TABLE activity_feedback ADD COLUMN pain_level INTEGER NOT NULL DEFAULT 0")

    _cleanup_existing_fitbod_non_strength_sessions(conn)

    conn.commit()
    conn.close()
