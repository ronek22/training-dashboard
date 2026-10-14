import json
import os
import sqlite3
import tempfile
import unittest
from datetime import date

from fastapi.testclient import TestClient

from backend.app import db
from backend.app.repositories import trails as trail_repo
from backend.app.services.mountain_trips import build_trip_recap, list_trips
from backend.app.services.season_review import build_season_review

TODAY = date(2030, 11, 1)


class MountainTripTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        previous = db.DB_PATH
        db.DB_PATH = os.path.join(temp.name, "training.db")
        self.addCleanup(setattr, db, "DB_PATH", previous)
        db.init_db()
        self.conn = sqlite3.connect(db.DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.addCleanup(self.conn.close)
        self.conn.executescript(trail_repo.SCHEMA)
        trail_repo.migrate(self.conn)

    def tag(self, *days, tag="mountains"):
        for day in days:
            self.conn.execute("INSERT INTO life_load_days (date, tags_json) VALUES (?, ?)", (day, json.dumps([tag])))
        self.conn.commit()

    def add(self, activity_id, day, kind="Hike", km=12.0, minutes=300, ascent=900):
        self.conn.execute(
            "INSERT INTO activities (id, date, type, name, distance_km, duration_min, elevation_m) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (activity_id, day, kind, f"{kind} {activity_id}", km, minutes, ascent),
        )
        self.conn.commit()

    def track(self, activity_id, day, points):
        self.conn.execute(
            "INSERT INTO mountain_tracks (activity_id, region, name, date, latlng_json) VALUES (?, 'tatras', 'x', ?, ?)",
            (activity_id, day, json.dumps(points)),
        )
        self.conn.commit()

    def test_consecutive_tagged_days_with_hikes_form_one_trip(self):
        self.tag("2030-08-01", "2030-08-02", "2030-08-03", "2030-08-10")
        self.tag("2030-08-04", tag="travel")
        self.add("h1", "2030-08-01")
        self.add("h2", "2030-08-03", km=8.0, minutes=240, ascent=600)
        self.add("r1", "2030-08-02", kind="Ride")  # Not on foot: not part of the recap.
        self.add("h3", "2030-07-31")  # The day before the trip.

        listing = list_trips(self.conn, TODAY)

        self.assertEqual(len(listing["trips"]), 1, "the lone tagged day has no hike")
        trip = listing["trips"][0]
        self.assertEqual((trip["start_date"], trip["end_date"], trip["days"], trip["hike_days"]), ("2030-08-01", "2030-08-03", 3, 2))
        self.assertEqual((trip["distance_km"], trip["ascent_m"], trip["hours"]), (20.0, 1500, 9.0))
        self.assertEqual(trip["url"], "/mountains/trips/2030-08-01")
        self.assertEqual(listing["upcoming"], [])

    def test_tagged_run_ahead_without_hikes_is_upcoming(self):
        self.tag("2030-11-05", "2030-11-06")
        listing = list_trips(self.conn, TODAY)
        self.assertEqual(listing["trips"], [])
        self.assertEqual(listing["upcoming"], [{"start_date": "2030-11-05", "end_date": "2030-11-06", "days": 2}])
        self.assertIsNone(build_trip_recap(self.conn, "2030-11-05", TODAY))

    def test_recap_counts_new_trail_summits_and_season_share(self):
        self.tag("2030-08-01", "2030-08-02", "2030-08-03")
        self.add("h1", "2030-08-01")
        self.add("h2", "2030-08-03", ascent=600)
        self.add("r1", "2030-03-01", kind="Ride", ascent=1500)
        self.track("h1", "2030-08-01", [[49.2, 19.9, 1000.0], [49.21, 19.91, 1500.0], [49.22, 19.92, 1987.0]])
        self.track("h2", "2030-08-03", [[49.2, 19.9, 1000.0], [49.2, 19.95, 1200.0]])
        for length, walked in ((2000.0, ["h1"]), (3000.0, ["old", "h2"]), (1500.0, ["h2", "h1"])):
            self.conn.execute(
                "INSERT INTO trail_sections (region, osm_key, park, colours_json, names_json, coords_json, length_m, status, walked_by_json, imported_at) "
                "VALUES ('tatras', 'w', 'TPN', '[]', '[]', '[]', ?, 'done', ?, '2030-01-01')",
                (length, json.dumps(walked)),
            )
        for name, ele, visited in (("Kasprowy Wierch", 1987, ["h1"]), ("Giewont", 1894, ["old", "h1"]), ("Hala", 1500, ["h2"])):
            self.conn.execute(
                "INSERT INTO trail_pois (region, osm_id, kind, name, ele, lat, lon, park, visited_by_json) VALUES ('tatras', ?, ?, ?, ?, 49.2, 19.9, 'TPN', ?)",
                (name, "hut" if name == "Hala" else "peak", name, ele, json.dumps(visited)),
            )
        self.conn.commit()

        recap = build_trip_recap(self.conn, "2030-08-02", TODAY)  # Any day of the trip finds it.

        trip = recap["trip"]
        self.assertEqual(trip["start_date"], "2030-08-01")
        self.assertEqual(trip["new_trail_km"], 3.5)
        self.assertEqual((trip["summits"], trip["new_summits"], trip["highest_m"]), (2, 1, 1987))
        self.assertEqual(recap["season"]["share_pct"], 50.0)
        self.assertEqual(recap["regions"][0]["key"], "tatras")
        first, rest, last = recap["days"]
        self.assertEqual(first["highlight"]["name"], "Kasprowy Wierch")
        self.assertTrue(first["highlight"]["first_time"])
        self.assertEqual([s["name"] for s in first["summits"]], ["Kasprowy Wierch", "Giewont"])
        self.assertEqual((first["new_trail_km"], last["new_trail_km"]), (2.0, 1.5))
        self.assertTrue(rest["rest"])
        self.assertEqual(last["highlight"]["name"], "Hala")
        self.assertEqual(len(first["activities"][0]["track"][0]), 3, "track keeps altitude for the profile")

    def test_recap_without_coverage_falls_back_to_streams_and_highlights_the_longest_outing(self):
        self.tag("2030-08-01")
        self.add("h1", "2030-08-01", km=14.0)
        self.add("w1", "2030-08-01", kind="Walk", km=2.0)
        streams = {"latlng": {"data": [[46.5, 8.0], [46.51, 8.01]]}, "altitude": {"data": [1800, 2100]}}
        self.conn.execute(
            "INSERT INTO activity_details (activity_id, fetched_at, source_status, streams_json) VALUES ('h1', '2030-08-02', 'ok', ?)",
            (json.dumps(streams),),
        )
        self.conn.commit()

        recap = build_trip_recap(self.conn, "2030-08-01", TODAY)

        self.assertIsNone(recap["trip"]["new_trail_km"])
        self.assertEqual(recap["regions"], [])
        [day] = recap["days"]
        self.assertEqual(day["highlight"]["name"], "Hike h1")
        self.assertEqual(day["activities"][0]["track"][-1], [46.51, 8.01, 2100])
        self.assertEqual(day["activities"][1]["track"], [])
        self.assertEqual(recap["trip"]["highest_m"], 2100)

    def test_api_and_season_review_link_trips(self):
        from backend.app.main import app

        self.tag("2030-08-01", "2030-08-02")
        self.add("h1", "2030-08-01")
        client = TestClient(app)

        self.assertEqual(client.get("/trails/trips").json()["trips"][0]["start_date"], "2030-08-01")
        self.assertEqual(client.get("/trails/trips/2030-08-01").json()["trip"]["hikes"], 1)
        self.assertEqual(client.get("/trails/trips/2030-09-01").status_code, 404)
        self.assertEqual(client.get("/trails/trips/not-a-date").status_code, 400)
        review = build_season_review(self.conn, 2030, today=date(2030, 12, 5))
        self.assertEqual([trip["start_date"] for trip in review["mountain_trips"]], ["2030-08-01"])


if __name__ == "__main__":
    unittest.main()
