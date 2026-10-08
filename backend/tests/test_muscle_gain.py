import sqlite3
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from backend.app.services import muscle_gain
from backend.app.services.muscle_gain import build_muscle_gain_check, muscle_groups_for

TODAY = date(2026, 10, 7)
WINDOW_START = TODAY - timedelta(days=27)


def _session(day, exercises, activity_id=None):
    return {
        "workout_date": day.isoformat(),
        "title": "Lift",
        "matched_activity": {"id": activity_id or f"lift-{day}", "name": "Weight Training"},
        "exercises": [
            {"exercise_name": name, "sets": [{"reps": reps, "weight_kg": kg, "is_warmup": False} for reps, kg in sets]}
            for name, sets in exercises
        ],
    }


class MuscleGroupMappingTests(unittest.TestCase):
    def test_specific_names_win_over_broad_ones(self):
        self.assertEqual(muscle_groups_for("Lying Leg Curl"), ("legs",))
        self.assertEqual(muscle_groups_for("Dumbbell Rear Delt Raise"), ("shoulders",))
        self.assertEqual(muscle_groups_for("Bent Over Barbell Row"), ("back",))
        self.assertEqual(muscle_groups_for("Hammer Curls"), ("arms",))
        self.assertEqual(muscle_groups_for("Chest Dip"), ("chest",))
        self.assertEqual(muscle_groups_for("Hanging Leg Raise"), ("core",))
        self.assertEqual(muscle_groups_for("Dumbbell Bulgarian Split Squat"), ("legs",))

    def test_stretches_and_unknown_names_are_unmapped(self):
        self.assertEqual(muscle_groups_for("Hamstring Stretch"), ())
        self.assertEqual(muscle_groups_for("Turkish Get-Up"), ())


class MuscleGainCheckTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE metrics (id INTEGER PRIMARY KEY, date TEXT, metric TEXT, value REAL);
            CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT, type TEXT, workout_intent TEXT);
            CREATE TABLE daily_nutrition (date TEXT PRIMARY KEY, protein_hit INTEGER NOT NULL);
            """
        )
        self.sessions = []
        self.sick = set()
        self.patches = [
            patch.object(muscle_gain, "_session_index", lambda conn: self.sessions),
            patch.object(muscle_gain, "sick_dates", lambda conn: self.sick),
            patch.object(muscle_gain, "get_health_metric_history", lambda conn, metric, days: []),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.conn.close()

    def _lift(self, day, exercises, intent=None):
        self.conn.execute("INSERT INTO activities VALUES (?, ?, 'WeightTraining', ?)", (f"lift-{day}", day.isoformat(), intent))
        self.sessions.append(_session(day, exercises))

    def _full_month(self, legs_sets=3, squat_kg=60):
        # Three sessions a week for four weeks, every lift progressing week on week.
        for week in range(4):
            for offset in (0, 2, 4):
                day = WINDOW_START + timedelta(days=week * 7 + offset)
                self._lift(
                    day,
                    [
                        ("Back Squat", [(8, squat_kg + week * 2.5)] * legs_sets),
                        ("Dumbbell Row", [(8 + week, 20)] * 3),
                        ("Dumbbell Bench Press", [(8 + week, 20)] * 3),
                        ("Dumbbell Shoulder Press", [(8 + week, 14)] * 3),
                        ("Dumbbell Curl", [(8 + week, 10)] * 3),
                    ],
                )

    def _check(self):
        return build_muscle_gain_check(self.conn, TODAY)

    def _group(self, result, key):
        return next(group for group in result["hard_sets"]["groups"] if group["key"] == key)

    def test_hard_sets_skip_warmups_and_name_their_sessions(self):
        day = WINDOW_START + timedelta(days=1)
        self._lift(day, [("Back Squat", [(8, 60)] * 4)])
        self.sessions[-1]["exercises"][0]["sets"].insert(0, {"reps": 10, "weight_kg": 20, "is_warmup": True})
        legs = self._group(self._check(), "legs")
        self.assertEqual(legs["total_sets"], 4)
        self.assertEqual(legs["sets_per_week"], 1.0)
        self.assertEqual(legs["status"], "low")
        self.assertEqual(legs["sessions"], [{"date": day.isoformat(), "activity_id": f"lift-{day}", "title": "Lift", "sets": 4}])

    def test_sessions_outside_the_window_are_ignored(self):
        self._lift(WINDOW_START - timedelta(days=1), [("Back Squat", [(8, 60)] * 4)])
        self.assertEqual(self._group(self._check(), "legs")["total_sets"], 0)

    def test_progression_compares_against_the_last_session_before_the_window(self):
        self._lift(WINDOW_START - timedelta(days=3), [("Back Squat", [(8, 60)] * 3), ("Pull Up", [(10, None)] * 3)])
        self._lift(WINDOW_START + timedelta(days=5), [("Back Squat", [(8, 65)] * 3), ("Pull Up", [(10, None)] * 3)])
        self._lift(WINDOW_START + timedelta(days=9), [("Dumbbell Curl", [(12, 10)] * 3)])
        progression = self._check()["progression"]
        directions = {lift["exercise_name"]: lift["direction"] for lift in progression["lifts"]}
        self.assertEqual(directions, {"Back Squat": "up", "Pull Up": "same", "Dumbbell Curl": "first"})
        self.assertEqual((progression["progressed"], progression["compared"], progression["share"]), (1, 2, 0.5))
        squat = next(lift for lift in progression["lifts"] if lift["exercise_name"] == "Back Squat")
        self.assertEqual(squat["baseline"]["date"], (WINDOW_START - timedelta(days=3)).isoformat())

    def test_protein_adherence_counts_lift_days_only(self):
        lift_day = WINDOW_START + timedelta(days=2)
        self._lift(lift_day, [("Back Squat", [(8, 60)] * 3)])
        self._lift(WINDOW_START + timedelta(days=4), [("Back Squat", [(8, 60)] * 3)])
        self._lift(WINDOW_START + timedelta(days=6), [("Mobility flow", [(1, None)])], intent="mobility")
        self.conn.execute("INSERT INTO daily_nutrition VALUES (?, 1)", (lift_day.isoformat(),))
        self.conn.execute("INSERT INTO daily_nutrition VALUES (?, 1)", ((WINDOW_START + timedelta(days=3)).isoformat(),))
        protein = self._check()["protein"]
        self.assertEqual((protein["lift_days"], protein["answered"], protein["hits"], protein["share"]), (2, 1, 1, 0.5))
        self.assertEqual(protein["days"][0]["activity_id"], f"lift-{lift_day}")

    def test_weekly_checkin_fills_unticked_lift_days_of_its_week(self):
        self.conn.execute("CREATE TABLE weekly_body_checkins (week_start TEXT PRIMARY KEY, protein_most_days INTEGER, weight_kg REAL, skipped INTEGER)")
        ticked = TODAY - timedelta(days=TODAY.weekday() + 7)  # last Monday
        covered = ticked + timedelta(days=2)
        uncovered = ticked - timedelta(days=5)  # the week before, no check-in
        for day in (ticked, covered, uncovered):
            self._lift(day, [("Back Squat", [(8, 60)] * 3)])
        self.conn.execute("INSERT INTO daily_nutrition VALUES (?, 0)", (ticked.isoformat(),))
        self.conn.execute("INSERT INTO weekly_body_checkins VALUES (?, 1, NULL, 0)", (ticked.isoformat(),))
        protein = self._check()["protein"]
        by_date = {day["date"]: (day["hit"], day["source"]) for day in protein["days"]}
        self.assertEqual(by_date[ticked.isoformat()], (False, "daily"))
        self.assertEqual(by_date[covered.isoformat()], (True, "weekly"))
        self.assertEqual(by_date[uncovered.isoformat()], (None, None))
        self.assertEqual((protein["answered"], protein["hits"]), (2, 1))

    def test_weight_trend_is_unavailable_with_too_few_weigh_ins(self):
        for offset in (2, 10, 20):
            self.conn.execute("INSERT INTO metrics (date, metric, value) VALUES (?, 'weight', 79)", ((TODAY - timedelta(days=offset)).isoformat(),))
        weight = self._check()["weight"]
        self.assertFalse(weight["available"])
        self.assertIn("found 3", weight["reason"])

    def test_weight_trend_uses_a_smoothed_average(self):
        for offset, kg in ((35, 79.0), (28, 79.2), (21, 79.3), (14, 79.5), (7, 79.6), (0, 79.8)):
            self.conn.execute("INSERT INTO metrics (date, metric, value) VALUES (?, 'weight', ?)", ((TODAY - timedelta(days=offset)).isoformat(), kg))
        weight = self._check()["weight"]
        self.assertTrue(weight["available"])
        self.assertEqual(weight["status"], "gentle_gain")
        self.assertAlmostEqual(weight["kg_per_week"], 0.16, places=2)

    def test_low_group_suggests_adding_a_set_of_a_lift_already_done(self):
        self._full_month(legs_sets=1)
        result = self._check()
        self.assertEqual(result["frequency"]["sessions_per_week"], 3.0)
        self.assertEqual(result["suggestion"]["lever"], "volume")
        self.assertEqual(result["suggestion"]["group"], "legs")
        self.assertIn("Back Squat", result["suggestion"]["headline"])

    def test_missing_sessions_suggest_more_lifting_never_less(self):
        for week in range(4):
            self._lift(WINDOW_START + timedelta(days=week * 7), [("Back Squat", [(8, 60)] * 3)])
        suggestion = self._check()["suggestion"]
        self.assertEqual(suggestion["lever"], "frequency")
        self.assertIn("3 lift sessions a week", suggestion["headline"])

    def test_sick_days_without_a_lift_shrink_the_frequency_window(self):
        for week in range(3):
            for offset in (0, 2, 4):
                self._lift(WINDOW_START + timedelta(days=week * 7 + offset), [("Back Squat", [(8, 60)] * 3)])
        self.sick = {(WINDOW_START + timedelta(days=21 + offset)).isoformat() for offset in range(7)}
        frequency = self._check()["frequency"]
        self.assertEqual((frequency["sessions_per_week"], frequency["sick_days_excluded"]), (3.0, 7))

    def test_high_volume_never_suggests_cutting_back(self):
        self._full_month(legs_sets=8)
        for day in self.sessions:
            self.conn.execute("INSERT INTO daily_nutrition VALUES (?, 1)", (day["workout_date"],))
        for offset, kg in ((35, 79.0), (28, 79.6), (21, 80.2), (14, 80.8), (7, 81.4), (0, 82.0)):
            self.conn.execute("INSERT INTO metrics (date, metric, value) VALUES (?, 'weight', ?)", ((TODAY - timedelta(days=offset)).isoformat(), kg))
        result = self._check()
        self.assertEqual(self._group(result, "legs")["status"], "high")
        suggestion = result["suggestion"]
        self.assertEqual(suggestion["lever"], "weight")
        text = f"{suggestion['headline']} {suggestion['detail']}".lower()
        for phrase in ("fewer", "skip", "drop a session", "less often", "cut a session"):
            self.assertNotIn(phrase, text)
        self.assertIn("keep all 3 lift sessions", text)

    def test_all_signals_good_reads_as_working(self):
        self._full_month(legs_sets=3)
        for day in self.sessions:
            self.conn.execute("INSERT INTO daily_nutrition VALUES (?, 1)", (day["workout_date"],))
        # Lifts done three per week with 3 sets each give 9 sets per group.
        result = self._check()
        self.assertEqual(self._group(result, "back")["sets_per_week"], 9.0)
        self.assertEqual(result["verdict"]["status"], "working")
        self.assertEqual(result["suggestion"]["lever"], "keep")


if __name__ == "__main__":
    unittest.main()
