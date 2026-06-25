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
    """)
    conn.commit()
    conn.close()
