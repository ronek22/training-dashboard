import os
import sqlite3

DEFAULT_DB_PATH = "/data/training.db"
DB_PATH = os.getenv("TRAINING_DB_PATH", DEFAULT_DB_PATH)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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

        CREATE TABLE IF NOT EXISTS coach_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
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

        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            period_type TEXT NOT NULL,
            metric_type TEXT NOT NULL,
            target_value REAL NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            activity_type TEXT,
            is_active INTEGER DEFAULT 1,
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
    """)

    feedback_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(activity_feedback)").fetchall()
    }
    activity_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(activities)").fetchall()
    }
    if "linked_planned_session_id" not in activity_columns:
        conn.execute("ALTER TABLE activities ADD COLUMN linked_planned_session_id TEXT")
    if "workout_intent" not in activity_columns:
        conn.execute("ALTER TABLE activities ADD COLUMN workout_intent TEXT")

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

    conn.commit()
    conn.close()
