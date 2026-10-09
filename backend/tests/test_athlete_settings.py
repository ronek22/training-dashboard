import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.services.ftp import ftp_on, stored_ftp, working_ftp
from backend.app.services.settings import (
    normalize_athlete_profile,
    normalize_body_areas,
    normalize_modality_restrictions,
    protected_area_for_exercise,
)

TODAY = date(2026, 10, 9)


def _memory_conn(choice=None):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE metrics (id INTEGER PRIMARY KEY, date TEXT, metric TEXT, value REAL);
        CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO metrics (date, metric, value) VALUES ('2026-01-10', 'ftp', 250), ('2026-03-12', 'ftp', 242);
        """
    )
    if choice:
        conn.execute("INSERT INTO app_settings VALUES ('performance_settings', ?)", (json.dumps({"ftp": choice}),))
    return conn


class FtpSourceTests(unittest.TestCase):
    def test_logged_ftp_follows_metric_history(self):
        conn = _memory_conn()
        self.assertEqual(ftp_on(conn, "2026-02-01"), 250)
        self.assertEqual(ftp_on(conn, "2026-10-01"), 242)
        self.assertIsNone(ftp_on(conn, "2025-12-01"))
        working = working_ftp(conn, TODAY)
        self.assertEqual((working["watts"], working["source"], working["stale"]), (242, "stored", True))

    def test_working_ftp_applies_from_the_day_it_was_chosen(self):
        conn = _memory_conn({"source": "manual", "manual_watts": 230, "effective_from": "2026-10-01"})
        # Earlier rides keep the FTP they were ridden with.
        self.assertEqual(ftp_on(conn, "2026-09-30"), 242)
        self.assertEqual(ftp_on(conn, "2026-10-01"), 230)
        working = working_ftp(conn, TODAY)
        self.assertEqual((working["watts"], working["source"], working["date"]), (230, "manual", "2026-10-01"))
        # The logged value is still reported separately.
        self.assertEqual(stored_ftp(conn, TODAY)["watts"], 242)

    def test_estimate_source_uses_the_snapshot_and_never_goes_stale(self):
        conn = _memory_conn({
            "source": "estimate", "estimate_watts": 198, "estimate_date": "2026-06-01", "effective_from": "2026-06-01",
        })
        working = working_ftp(conn, TODAY)
        self.assertEqual((working["watts"], working["source"], working["stale"]), (198, "estimate", False))

    def test_unusable_choice_falls_back_to_the_logged_ftp(self):
        conn = _memory_conn({"source": "estimate", "estimate_watts": None, "effective_from": "2026-10-01"})
        self.assertEqual(ftp_on(conn, "2026-10-05"), 242)
        self.assertEqual(working_ftp(conn, TODAY)["source"], "stored")

    def test_missing_tables_mean_no_ftp(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        self.assertIsNone(ftp_on(conn, "2026-10-01"))
        self.assertFalse(working_ftp(conn, TODAY)["available"])


class BodyAreaTests(unittest.TestCase):
    def test_normalizes_and_dedupes_areas(self):
        areas = normalize_body_areas([
            {"area": "knee", "side": "left", "note": " outside of knee ", "recovery_issue_id": "1"},
            {"area": "knee", "side": "left"},
            {"area": "Lower back"},
            {"area": "spleen"},
        ])
        self.assertEqual([(item["area"], item["side"]) for item in areas], [("knee", "left"), ("lower_back", None)])
        self.assertEqual(areas[0]["summary_label"], "left knee")
        self.assertEqual(areas[0]["note"], "outside of knee")
        self.assertEqual(areas[0]["recovery_issue_id"], 1)

    def test_headline_names_protected_areas(self):
        payload = normalize_modality_restrictions({"body_areas": [{"area": "knee", "side": "left"}]})
        self.assertEqual(payload["summary"]["headline"], "Protecting left knee.")
        self.assertEqual(payload["summary"]["protected_count"], 1)
        blocked = normalize_modality_restrictions({
            "modalities": {"run": {"status": "blocked"}},
            "body_areas": [{"area": "heel"}],
        })
        self.assertEqual(blocked["summary"]["headline"], "1 modality blocked. Protecting heel / achilles.")

    def test_exercise_matching(self):
        knee = normalize_body_areas([{"area": "knee"}])
        self.assertTrue(protected_area_for_exercise("Dumbbell Bulgarian Split Squat", knee))
        self.assertTrue(protected_area_for_exercise("Back Squat", knee))
        self.assertIsNone(protected_area_for_exercise("Romanian Deadlift", knee))
        self.assertIsNone(protected_area_for_exercise("Standing Dumbbell Calf Raise", knee))
        elbow = normalize_body_areas([{"area": "elbow"}])
        self.assertTrue(protected_area_for_exercise("Dumbbell Bicep Curl", elbow))
        self.assertIsNone(protected_area_for_exercise("Lying Leg Curl", elbow))


class NoteReviewTests(unittest.TestCase):
    def test_notes_without_a_review_date_are_stale(self):
        profile = normalize_athlete_profile({"planning_notes": "Protect long rides", "current_block": None})
        self.assertTrue(profile["note_reviews"]["planning_notes"]["stale"])
        # An empty note has nothing to go stale.
        self.assertFalse(profile["note_reviews"]["current_block"]["stale"])

    def test_recent_review_is_fresh(self):
        recent = (date.today() - timedelta(days=3)).isoformat()
        old = (date.today() - timedelta(days=60)).isoformat()
        profile = normalize_athlete_profile({
            "planning_notes": "a", "weekly_availability_notes": "b",
            "notes_reviewed_at": {"planning_notes": recent, "weekly_availability_notes": old},
        })
        self.assertFalse(profile["note_reviews"]["planning_notes"]["stale"])
        self.assertEqual(profile["note_reviews"]["planning_notes"]["age_days"], 3)
        self.assertTrue(profile["note_reviews"]["weekly_availability_notes"]["stale"])


def _is_app_module(name):
    return name == "backend.app" or name.startswith("backend.app.")


class AthleteSettingsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["TRAINING_DB_PATH"] = os.path.join(cls.temp_dir.name, "athlete-settings.db")
        cls.replaced = {name: sys.modules.pop(name) for name in list(sys.modules) if _is_app_module(name)}
        import backend.app.main as main_module

        cls.client = TestClient(main_module.app, base_url="http://localhost:8000")
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        os.environ.pop("TRAINING_DB_PATH", None)
        for name in [name for name in sys.modules if _is_app_module(name)]:
            sys.modules.pop(name)
        sys.modules.update(cls.replaced)
        cls.temp_dir.cleanup()

    def test_choosing_a_working_ftp_drives_the_ride_anchor(self):
        self.client.post("/metrics", json={"date": "2026-03-12", "metric": "ftp", "value": 242})
        before = self.client.get("/settings/performance").json()
        self.assertEqual(before["ftp"]["source"], "stored")
        self.assertEqual(before["anchors"]["ride_threshold_power"]["value"], 242)
        self.assertEqual(before["ftp_options"]["stored"]["watts"], 242)

        updated = self.client.put("/settings/performance", json={"ftp": {"source": "manual", "manual_watts": 230}}).json()
        self.assertEqual(updated["ftp"]["source"], "manual")
        self.assertEqual(updated["ftp"]["effective_from"], date.today().isoformat())
        self.assertEqual(updated["anchors"]["ride_threshold_power"]["value"], 230)
        self.assertEqual(updated["ftp_options"]["working"]["watts"], 230)

        library = self.client.get("/cycling-workouts").json()
        self.assertEqual(library["ftp"]["watts"], 230)
        self.client.put("/settings/performance", json={"ftp": {"source": "stored"}})

    def test_body_areas_round_trip(self):
        response = self.client.put("/settings/modality-restrictions", json={
            "modalities": {},
            "body_areas": [{"area": "knee", "side": "left", "note": "outside of knee", "recovery_issue_id": 1}],
        })
        self.assertEqual(response.status_code, 200)
        saved = self.client.get("/settings/modality-restrictions").json()
        self.assertEqual(saved["body_areas"][0]["summary_label"], "left knee")
        self.assertEqual(saved["summary"]["headline"], "Protecting left knee.")
        self.client.put("/settings/modality-restrictions", json={"modalities": {}, "body_areas": []})

    def test_editing_or_confirming_a_note_stamps_today(self):
        today = date.today().isoformat()
        first = self.client.put("/settings/athlete-profile", json={"planning_notes": "Protect long rides"}).json()
        self.assertEqual(first["notes_reviewed_at"]["planning_notes"], today)
        self.assertIsNone(first["notes_reviewed_at"]["current_block"])

        # Saving other fields does not refresh an unchanged note's date.
        with patch("backend.app.services.settings.date") as fake_date:
            fake_date.today.return_value = date.today() + timedelta(days=50)
            fake_date.fromisoformat = date.fromisoformat
            later = self.client.put("/settings/athlete-profile", json={
                "planning_notes": "Protect long rides", "primary_focus": "hybrid",
            }).json()
            self.assertEqual(later["notes_reviewed_at"]["planning_notes"], today)
            confirmed = self.client.put("/settings/athlete-profile", json={
                "planning_notes": "Protect long rides",
                "notes_reviewed_at": {"planning_notes": (date.today() + timedelta(days=50)).isoformat()},
            }).json()
            self.assertEqual(confirmed["notes_reviewed_at"]["planning_notes"], (date.today() + timedelta(days=50)).isoformat())


if __name__ == "__main__":
    unittest.main()
