import json
import sqlite3
import unittest
from datetime import date, timedelta

from backend.app.services.life_load import (
    build_plan_life_load,
    get_life_load_days,
    life_load_coaching_context,
    life_load_readiness_factor,
    missed_on_tagged_days,
    mountain_dates,
    session_load_reason,
    set_life_load_day,
    tagged_days_between,
)

SCHEMA = """
CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT NOT NULL, type TEXT NOT NULL, name TEXT);
CREATE TABLE weekly_plans (week_start TEXT PRIMARY KEY, title TEXT, days_json TEXT NOT NULL);
CREATE TABLE life_load_days (
    date TEXT PRIMARY KEY, tags_json TEXT NOT NULL, note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

MONDAY = date(2026, 10, 5)


def day(offset: int) -> str:
    return (MONDAY + timedelta(days=offset)).isoformat()


def session(offset: int, session_type: str, intent=None, minutes=None, title=None) -> dict:
    return {"date": day(offset), "session_type": session_type, "workout_intent": intent, "target_duration_min": minutes, "title": title or session_type}


class LifeLoadTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def tearDown(self):
        self.conn.close()

    def test_set_orders_tags_and_clearing_removes_the_day(self):
        saved = set_life_load_day(self.conn, day(2), ["late_night", "deadline"], " big launch ")
        self.assertEqual(saved["tags"], ["deadline", "late_night"])
        self.assertEqual(saved["labels"], ["Deadline", "Late night"])
        self.assertEqual(saved["note"], "big launch")
        self.assertIsNone(set_life_load_day(self.conn, day(2), []))
        self.assertEqual(get_life_load_days(self.conn), {})
        with self.assertRaises(ValueError):
            set_life_load_day(self.conn, day(2), ["vacation"])

    def test_missing_table_fails_soft(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        self.assertEqual(get_life_load_days(conn), {})
        self.assertEqual(tagged_days_between(conn, MONDAY, MONDAY), 0)
        conn.close()

    def test_only_intensity_and_long_sessions_clash_with_a_tagged_day(self):
        self.assertEqual(session_load_reason(session(0, "Ride", "interval")), "hard intensity")
        self.assertEqual(session_load_reason(session(0, "Run", "tempo")), "hard intensity")
        self.assertEqual(session_load_reason(session(0, "Ride", "easy", 120)), "long session")
        self.assertEqual(session_load_reason(session(0, "Ride", "long")), "long session")
        self.assertIsNone(session_load_reason(session(0, "Ride", "easy", 45)))
        self.assertIsNone(session_load_reason(session(0, "WeightTraining", "strength_general", 60)))
        self.assertIsNone(session_load_reason(session(0, "Rest")))
        self.assertIsNone(session_load_reason(session(0, "rest", None, 120)))
        self.assertIsNone(session_load_reason(session(0, "recovery", "recovery", 95)))
        self.assertEqual(session_load_reason(session(0, "ride", "tempo")), "hard intensity")

    def test_plan_flags_hard_session_on_tagged_day_and_suggests_calm_neighbour(self):
        days = [
            session(0, "WeightTraining", "strength_general"),
            session(1, "Ride", "interval", 60, "VO2 intervals"),
            session(2, "Rest"),
            session(3, "Ride", "easy", 45),
            session(4, "WeightTraining", "strength_general"),
            session(5, "Ride", "long", 150),
            session(6, "Rest"),
        ]
        set_life_load_day(self.conn, day(1), ["deadline"])
        set_life_load_day(self.conn, day(0), ["family"])
        result = build_plan_life_load(self.conn, days, day(0), today=MONDAY)
        self.assertEqual(set(result["days"]), {day(0), day(1)})
        self.assertEqual(len(result["conflicts"]), 1)
        conflict = result["conflicts"][0]
        self.assertEqual((conflict["date"], conflict["reason"], conflict["labels"]), (day(1), "hard intensity", ["Deadline"]))
        # Monday is tagged, Wednesday is next to nothing hard once Tuesday moves: nearest calm day.
        self.assertEqual(conflict["suggested_date"], day(2))

    def test_plan_skips_past_and_done_days_and_avoids_hard_neighbours(self):
        days = [session(1, "Ride", "interval"), session(3, "Run", "tempo"), session(4, "Ride", "easy", 40), session(5, "Rest")]
        set_life_load_day(self.conn, day(3), ["travel"])
        set_life_load_day(self.conn, day(1), ["travel"])
        result = build_plan_life_load(self.conn, days, day(0), today=MONDAY + timedelta(days=2))
        self.assertEqual([item["date"] for item in result["conflicts"]], [day(3)])
        # Wednesday is today but sits next to Tuesday's intervals; Friday's easy ride can trade places.
        self.assertEqual(result["conflicts"][0]["suggested_date"], day(4))
        self.conn.execute("INSERT INTO activities (id, date, type) VALUES ('a', ?, 'Run')", (day(3),))
        self.assertEqual(build_plan_life_load(self.conn, days, day(0), today=MONDAY)["conflicts"][0]["date"], day(1))
        self.assertIsNone(build_plan_life_load(self.conn, days, day(7), today=MONDAY))

    def test_review_counts_misses_on_tagged_days(self):
        days = [session(0, "WeightTraining"), session(1, "Ride", "easy"), session(2, "rest"), session(3, "Ride", "interval"), session(4, "WeightTraining")]
        self.conn.execute("INSERT INTO weekly_plans (week_start, days_json) VALUES (?, ?)", (day(0), json.dumps(days)))
        self.conn.execute("INSERT INTO activities (id, date, type) VALUES ('a', ?, 'WeightTraining'), ('b', ?, 'WeightTraining')", (day(0), day(4)))
        set_life_load_day(self.conn, day(1), ["deadline"])
        set_life_load_day(self.conn, day(3), ["deadline"])
        result = missed_on_tagged_days(self.conn, MONDAY, today=MONDAY + timedelta(days=7))
        self.assertEqual(result["missed"], 2)
        self.assertEqual([item["date"] for item in result["missed_on_tagged"]], [day(1), day(3)])
        self.assertEqual(result["summary"], "Missed 2 sessions, both on deadline days.")
        # Mid-week only the days already over are judged.
        self.assertEqual(missed_on_tagged_days(self.conn, MONDAY, today=MONDAY + timedelta(days=2))["summary"], "Missed 1 session, on a deadline day.")

    def test_readiness_factor_from_poor_sleep_today_or_late_night_yesterday(self):
        self.assertIsNone(life_load_readiness_factor(self.conn, MONDAY))
        set_life_load_day(self.conn, day(-1), ["late_night"])
        factor = life_load_readiness_factor(self.conn, MONDAY)
        self.assertEqual((factor["points"], factor["detail"]), (1, "late night yesterday"))
        set_life_load_day(self.conn, day(0), ["poor_sleep"])
        self.assertEqual(life_load_readiness_factor(self.conn, MONDAY)["detail"], "poor sleep tagged, late night yesterday")

    def test_coaching_context_splits_recent_and_upcoming(self):
        self.assertIsNone(life_load_coaching_context(self.conn, MONDAY))
        set_life_load_day(self.conn, day(-2), ["family"])
        set_life_load_day(self.conn, day(3), ["travel"], "Berlin")
        context = life_load_coaching_context(self.conn, MONDAY)
        self.assertEqual(context["recent"], [{"date": day(-2), "tags": ["Family"]}])
        self.assertEqual(context["upcoming"], [{"date": day(3), "tags": ["Travel"], "note": "Berlin"}])


    def test_hikes_on_mountain_days_are_not_conflicts_but_rides_still_are(self):
        for offset in (1, 2):
            set_life_load_day(self.conn, day(offset), ["travel", "mountains"])
        days = [session(1, "hike", "long", 300, "Hike"), session(2, "ride", "long", 120, "Long ride")]
        result = build_plan_life_load(self.conn, days, day(0), today=MONDAY)
        self.assertEqual([item["date"] for item in result["conflicts"]], [day(2)])
        self.assertEqual(mountain_dates(self.conn, day(0), day(6)), {day(1), day(2)})

    def test_coaching_context_adds_mountain_guidance_only_ahead_of_a_trip(self):
        set_life_load_day(self.conn, day(-2), ["mountains"])
        self.assertNotIn("mountains_guidance", life_load_coaching_context(self.conn, MONDAY))
        set_life_load_day(self.conn, day(3), ["mountains"])
        self.assertIn("Travel kit", life_load_coaching_context(self.conn, MONDAY)["mountains_guidance"])


if __name__ == "__main__":
    unittest.main()
