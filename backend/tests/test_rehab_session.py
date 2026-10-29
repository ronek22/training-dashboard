import sqlite3
import unittest
from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from backend.app.models.recovery import AIResult, IssueCreate, MessageCreate, RoutineTick
from backend.app.repositories.activities import upsert_activity_row
from backend.app.repositories.recovery import init_recovery_schema
from backend.app.services import recovery
from backend.app.services.guided_sessions import completions_on, guided_label_for_activity, guided_session_for_activity, public_session, save_guided_completion
from backend.app.services.rehab_session import build_rehab_today, parse_dose, todays_session
from backend.tests.test_sick_mode import SCHEMA

TODAY = date.today()
ROUTINE = [
    {"name": "Quad isometric", "dose": "5 x 30 sec, daily", "how": "Tighten the thigh."},
    {"name": "Side-lying hip abduction", "dose": "3 x 12/side, daily", "how": "Top leg slightly behind."},
    {"name": "Shallow wall sit isometric", "dose": "4 x 30 sec, every other day", "how": "Knees 30-45°."},
    {"name": "Glute bridge", "dose": "3 x 12, 4 days/week", "how": "Push through heels."},
    {"name": "Hamstring and glute stretch (gentle)", "dose": "2 x 30 sec, daily", "how": "Mild stretch only."},
]


class DoseParsingTests(unittest.TestCase):
    def test_sets_holds_reps_sides_and_ranges(self):
        self.assertEqual(parse_dose("5 x 30 sec, daily"), {"sets": 5, "seconds": 30, "per_side": False, "frequency": {"kind": "daily", "label": "daily"}})
        hips = parse_dose("3 x 12/side, daily")
        self.assertEqual((hips["sets"], hips["reps"], hips["per_side"]), (3, 12, True))
        plank = parse_dose("3 x 20-30 sec/side, 4 days/week")
        self.assertEqual((plank["seconds"], plank["range"], plank["per_side"], plank["frequency"]["times"]), (20, "20–30 s", True, 4))
        chair = parse_dose("3 x 8-10, every other day")
        self.assertEqual((chair["reps"], chair["range"], chair["frequency"]["kind"]), (8, "8–10", "every_other_day"))
        self.assertEqual(parse_dose("2 min walk")["seconds"], 120)
        loose = parse_dose("as tolerated")
        self.assertEqual((loose["sets"], "reps" in loose, "seconds" in loose), (1, False, False))
        self.assertEqual(parse_dose("3 x 12, 3x/week")["frequency"]["times"], 3)


class RehabSessionTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        init_recovery_schema(self.conn)
        patcher = patch.object(recovery, "training_context", return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.issue_id = recovery.create_issue(self.conn, IssueCreate(body_area="knee", side="left", pain=3))["id"]
        request = recovery.add_message(self.conn, self.issue_id, MessageCreate(content="Outer knee."))
        recovery.finish_request(self.conn, self.issue_id, request["request_id"], AIResult(reply="Ok.", plan={"summary": "Settle it.", "exercises": ROUTINE}))

    def tearDown(self):
        self.conn.close()

    def tick(self, index, day=TODAY):
        recovery.set_tick(self.conn, self.issue_id, RoutineTick(day=day.isoformat(), index=index))

    def test_inactive_without_a_routine(self):
        recovery.heal(self.conn, self.issue_id, "")
        self.assertEqual(build_rehab_today(self.conn, []), {"active": False})
        self.assertIsNone(public_session("rehab", self.conn))
        self.assertIsNone(public_session("rehab"))

    def test_session_is_straight_sets_of_what_is_due(self):
        session = public_session("rehab", self.conn, TODAY)
        self.assertEqual((session["layout"], session["context"], session["watch_workout"]), ("sets", "rehab", "Core Training"))
        self.assertEqual(session["issues"], ["Left knee"])
        self.assertEqual(len(session["exercises"]), 5)
        self.assertEqual(session["steps"][1], "Side-lying hip abduction 3 × 12/side")
        self.assertEqual(session["exercises"][0]["cue"], "Tighten the thigh.")
        self.assertGreater(session["duration_min"], 8)

    def test_frequency_decides_what_is_due_and_ticks_mark_done(self):
        yesterday = TODAY - timedelta(days=1)
        self.tick(2, yesterday)  # every other day: rests today
        for days_ago in range(1, 5):
            self.tick(3, TODAY - timedelta(days=days_ago))  # 4 days/week already reached
        self.tick(0)
        names = [item["name"] for item in todays_session(self.conn, TODAY)["exercises"]]
        self.assertEqual(names, ["Side-lying hip abduction", "Hamstring and glute stretch (gentle)"])
        card = build_rehab_today(self.conn, [], TODAY)
        self.assertEqual((card["due_count"], card["done_count"], card["pending_count"], card["rest_count"]), (3, 1, 2, 2))
        self.tick(1)
        self.assertEqual(todays_session(self.conn, TODAY)["watch_workout"], "Flexibility")  # only the stretch is left

    def test_finished_session_keeps_a_snapshot_and_links_only_a_non_training_workout(self):
        day = TODAY.isoformat()
        self.conn.execute("INSERT INTO activities (id, date, type, name, duration_min) VALUES ('ride', ?, 'VirtualRide', 'Zwift', 60)", (day,))
        self.conn.execute("INSERT INTO activity_source_refs (source, external_id, activity_id, started_at) VALUES ('strava', 'ride', 'ride', ?)", (f"{day}T18:00:00+00:00",))
        self.tick(0)
        self.tick(1)
        payload = {"session_key": "rehab", "started_at": f"{day}T18:30:00Z", "elapsed_seconds": 600}
        state = save_guided_completion(self.conn, payload, today=TODAY)
        self.assertIsNone(state["completed_today"][0]["activity_id"])  # the ride is never relabelled
        self.conn.execute("INSERT INTO activities (id, date, type, name, duration_min) VALUES ('core', ?, 'Workout', 'Evening Workout', 11)", (day,))
        self.conn.execute("INSERT INTO activity_source_refs (source, external_id, activity_id, started_at) VALUES ('strava', 'core', 'core', ?)", (f"{day}T18:31:00+00:00",))
        save_guided_completion(self.conn, payload, today=TODAY)
        [completion] = completions_on(self.conn, day, "rehab")
        self.assertEqual((completion["activity_id"], completion["title"]), ("core", "Rehab routine"))
        row = self.conn.execute("SELECT workout_intent, notes FROM activities WHERE id = 'core'").fetchone()
        self.assertEqual(row["workout_intent"], "mobility")
        self.assertIn("Rehab (Left knee): Quad isometric, Side-lying hip abduction", row["notes"])
        self.assertIsNone(self.conn.execute("SELECT workout_intent FROM activities WHERE id = 'ride'").fetchone()[0])
        linked = guided_session_for_activity(self.conn, "core")
        self.assertEqual(([item["name"] for item in linked["exercises"]], linked["guided_min"], linked["context_label"]),
                         (["Quad isometric", "Side-lying hip abduction"], 10.0, "Rehab"))

    def test_a_session_finished_after_midnight_belongs_to_the_day_it_started(self):
        evening = TODAY - timedelta(days=1)
        started = datetime.combine(evening, time(23, 54, 38)).astimezone()
        self.conn.execute("INSERT INTO activities (id, date, type, name, duration_min) VALUES ('core', ?, 'Workout', 'Core Training', 28)", (evening.isoformat(),))
        self.conn.execute("INSERT INTO activity_source_refs (source, external_id, activity_id, started_at) VALUES ('healthkit', 'core', 'core', ?)",
                          ((started - timedelta(seconds=6)).isoformat(),))
        self.tick(0, day=evening)
        payload = {"session_key": "rehab", "started_at": started.isoformat(), "elapsed_seconds": 1689}
        state = save_guided_completion(self.conn, payload, today=TODAY)  # finished the next day
        self.assertEqual(state["completed_today"][0]["activity_id"], "core")
        self.assertEqual(completions_on(self.conn, TODAY.isoformat(), "rehab"), [])
        self.assertEqual(self.conn.execute("SELECT workout_intent FROM activities WHERE id = 'core'").fetchone()[0], "mobility")
        self.assertEqual([item["name"] for item in guided_session_for_activity(self.conn, "core")["exercises"]], ["Quad isometric"])

    def test_a_lift_links_only_when_it_started_with_the_rehab_session(self):
        day = TODAY.isoformat()
        self.conn.execute("INSERT INTO activities (id, date, type, name, duration_min) VALUES ('lift', ?, 'WeightTraining', 'Morning Weights', 60)", (day,))
        self.conn.execute("INSERT INTO activity_source_refs (source, external_id, activity_id, started_at) VALUES ('strava', 'lift', 'lift', ?)", (f"{day}T11:00:00+00:00",))
        self.tick(0)
        payload = {"session_key": "rehab", "started_at": f"{day}T11:48:19Z", "elapsed_seconds": 2010}
        state = save_guided_completion(self.conn, payload, today=TODAY)
        self.assertIsNone(state["completed_today"][0]["activity_id"])  # the morning lift is a real lift
        # Core Training that reached Strava as WeightTraining, started two seconds before the guided session.
        self.conn.execute("INSERT INTO activities (id, date, type, name, duration_min) VALUES ('core', ?, 'WeightTraining', 'Lunch Workout', 34)", (day,))
        self.conn.execute("INSERT INTO activity_source_refs (source, external_id, activity_id, started_at) VALUES ('strava', 'core', 'core', ?)", (f"{day}T11:48:17+00:00",))
        save_guided_completion(self.conn, payload, today=TODAY)
        [completion] = completions_on(self.conn, day, "rehab")
        self.assertEqual(completion["activity_id"], "core")
        rows = {row["id"]: (row["type"], row["workout_intent"]) for row in self.conn.execute("SELECT id, type, workout_intent FROM activities")}
        self.assertEqual(rows, {"lift": ("WeightTraining", None), "core": ("Workout", "mobility")})
        # A Strava resync sends WeightTraining again; the rehab session stays a plain workout.
        upsert_activity_row(self.conn, {
            "id": "core", "date": day, "type": "WeightTraining", "name": "Lunch Workout", "distance_km": None, "duration_min": 34,
            "avg_hr": 116, "max_hr": 148, "avg_pace": None, "avg_watts": None, "elevation_m": None, "calories": None, "zone2": False, "notes": None,
        }, preserve_annotations=True)
        self.assertEqual(tuple(self.conn.execute("SELECT type, workout_intent FROM activities WHERE id = 'core'").fetchone()), ("Workout", "mobility"))
        self.assertEqual(guided_label_for_activity(self.conn, "core"), {"title": "Rehab routine", "context_label": "Rehab"})
        self.assertIsNone(guided_label_for_activity(self.conn, "lift"))


if __name__ == "__main__":
    unittest.main()
