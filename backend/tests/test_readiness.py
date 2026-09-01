import sqlite3
import unittest
from datetime import datetime, timedelta

from backend.app.services.readiness import build_readiness_summary


class ReadinessSummaryTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE activities (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                type TEXT NOT NULL,
                name TEXT,
                workout_intent TEXT,
                duration_min REAL,
                distance_km REAL,
                avg_hr REAL,
                zone2 INTEGER,
                created_at TEXT NOT NULL
            );
            CREATE TABLE activity_feedback (
                activity_id TEXT PRIMARY KEY,
                rpe INTEGER,
                energy INTEGER,
                muscle_soreness INTEGER,
                pain_level INTEGER,
                note TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

    def tearDown(self):
        self.conn.close()

    def test_consistent_easy_training_is_not_strain_by_itself(self):
        today = datetime.now().date()
        now = datetime.now().isoformat()
        for offset in range(6):
            self.conn.execute(
                """
                INSERT INTO activities
                (id, date, type, workout_intent, duration_min, distance_km, avg_hr, zone2, created_at)
                VALUES (?, ?, 'Ride', 'easy', 90, 40, 138, 0, ?)
                """,
                (f"easy-{offset}", (today - timedelta(days=offset)).isoformat(), now),
            )
        self.conn.execute(
            """
            INSERT INTO activity_feedback
            (activity_id, rpe, energy, muscle_soreness, pain_level, note, created_at, updated_at)
            VALUES ('easy-0', 5, 4, 1, 0, 'Feeling normal', ?, ?)
            """,
            (now, now),
        )
        self.conn.commit()

        result = build_readiness_summary(
            self.conn,
            training_load_summary={
                "current": {"fitness": 102, "fatigue": 91, "form": 11},
                "ratio": {"status": "recovery"},
                "model": {"coverage": {"detailed_pct": 80, "overall_pct": 80}},
            },
        )

        self.assertEqual(result["state"], "ready")
        self.assertEqual(result["label"], "Balanced")
        self.assertEqual(result["metrics"]["active_days_7d"], 6)
        self.assertEqual(result["metrics"]["hard_sessions_7d"], 0)


if __name__ == "__main__":
    unittest.main()
