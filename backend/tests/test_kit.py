import json
import sqlite3
import unittest
from datetime import date
from unittest import mock

from fastapi import HTTPException

from backend.app.services.kit import (
    activity_kit,
    assign_activity_kit,
    create_item,
    import_strava_gear,
    kit_due,
    log_event,
    replace_item,
    gear_backfill_range,
    mark_gear_ids_known,
    list_kit,
    update_item,
)

from backend.app.services.strava import backfill_strava_gear_ids, build_strava_authorize_url, exchange_strava_code, fetch_strava_gear

TODAY = date(2026, 10, 26)
GEAR = [
    {"gear_id": "g1", "name": "Pegasus 41", "kind": "shoes", "distance_km": 512.3, "primary": True, "retired": False},
    {"gear_id": "b1", "name": "Tarmac", "kind": "bike", "distance_km": 8000.0, "primary": True, "retired": False},
    {"gear_id": "g0", "name": "Old Ghost", "kind": "shoes", "distance_km": 900.0, "primary": False, "retired": True},
]


class KitTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(
            """
            CREATE TABLE activities (id TEXT PRIMARY KEY, date TEXT, type TEXT, name TEXT,
                distance_km REAL, duration_min REAL);
            CREATE TABLE activity_source_refs (source TEXT, external_id TEXT, activity_id TEXT,
                metadata_json TEXT, PRIMARY KEY (source, external_id));
            """
        )
        self.addCleanup(self.conn.close)

    def add(self, activity_id, day, activity_type="Run", km=10.0, minutes=60.0, gear=None):
        self.conn.execute(
            "INSERT INTO activities VALUES (?, ?, ?, ?, ?, ?)",
            (activity_id, day, activity_type, activity_id, km, minutes),
        )
        if gear:
            self.conn.execute(
                "INSERT INTO activity_source_refs VALUES ('strava', ?, ?, ?)",
                (activity_id, activity_id, json.dumps({"gear_id": gear})),
            )

    def item(self, kit_id):
        return next(item for item in list_kit(self.conn, TODAY)["items"] if item["id"] == kit_id)

    def test_default_kit_collects_runs_since_its_start_date(self):
        self.add("old", "2026-07-01")
        self.add("r1", "2026-09-01")
        self.add("ride", "2026-09-02", activity_type="Ride", km=40)
        shoes = create_item(self.conn, {"kind": "shoes", "name": "Pegasus", "started_on": "2026-08-01", "threshold_km": 600}, TODAY)
        self.assertEqual(shoes["sport"], "Run")
        self.assertEqual(shoes["used_km"], 10.0)
        self.assertEqual(shoes["activity_count"], 1)
        # A run added later is picked up on the next read.
        self.add("r2", "2026-10-20", km=5)
        self.assertEqual(self.item(shoes["id"])["used_km"], 15.0)

    def test_delete_and_reassign_move_distance(self):
        self.add("r1", "2026-09-01")
        self.add("r2", "2026-09-03", km=8)
        first = create_item(self.conn, {"kind": "shoes", "name": "Old pair", "started_on": "2026-08-01", "threshold_km": 600}, TODAY)
        # The new default does not steal runs already assigned to the old pair.
        second = create_item(self.conn, {"kind": "shoes", "name": "New pair", "started_on": "2026-09-01", "threshold_km": 600}, TODAY)
        self.assertFalse(self.item(first["id"])["is_default"])
        self.assertEqual(self.item(first["id"])["used_km"], 18.0)
        self.assertEqual(second["used_km"], 0)

        assign_activity_kit(self.conn, "r2", "shoes", second["id"])
        self.assertEqual(self.item(first["id"])["used_km"], 10.0)
        self.assertEqual(self.item(second["id"])["used_km"], 8.0)

        self.conn.execute("DELETE FROM activities WHERE id = 'r2'")
        self.assertEqual(self.item(second["id"])["used_km"], 0)
        self.add("r3", "2026-10-01", km=6)
        self.assertEqual(self.item(second["id"])["used_km"], 6.0)

    def test_manual_none_is_kept(self):
        self.add("r1", "2026-09-01")
        shoes = create_item(self.conn, {"kind": "shoes", "started_on": "2026-08-01", "threshold_km": 600}, TODAY)
        data = assign_activity_kit(self.conn, "r1", "shoes", None)
        self.assertEqual(data["slots"][0]["kit_id"], None)
        self.assertEqual(data["slots"][0]["source"], "manual")
        self.assertEqual(self.item(shoes["id"])["used_km"], 0)

    def test_wrong_kind_is_rejected(self):
        self.add("r1", "2026-09-01")
        chain = create_item(self.conn, {"kind": "chain", "started_on": "2026-08-01"}, TODAY)
        with self.assertRaises(ValueError):
            assign_activity_kit(self.conn, "r1", "shoes", chain["id"])

    def test_nearly_due_at_ninety_percent_and_start_offset(self):
        self.add("r1", "2026-09-01", km=40)
        shoes = create_item(
            self.conn,
            {"kind": "shoes", "started_on": "2026-08-01", "threshold_km": 600, "start_km": 500},
            TODAY,
        )
        self.assertEqual(shoes["status"], "nearly_due")
        self.assertEqual(shoes["remaining_km"], 60.0)
        self.assertEqual([item["id"] for item in kit_due(self.conn, TODAY)], [shoes["id"]])
        self.add("r2", "2026-09-02", km=70)
        self.assertEqual(self.item(shoes["id"])["status"], "due")

    def test_time_threshold_for_trainer(self):
        self.add("v1", "2026-09-01", activity_type="VirtualRide", km=30, minutes=600)
        trainer = create_item(self.conn, {"kind": "trainer", "started_on": "2026-08-01", "threshold_hours": 11}, TODAY)
        self.assertEqual(trainer["sport"], "VirtualRide")
        self.assertEqual(trainer["used_hours"], 10.0)
        self.assertEqual(trainer["status"], "nearly_due")

    def test_retired_item_keeps_history_and_stops_claiming(self):
        self.add("r1", "2026-09-01")
        shoes = create_item(self.conn, {"kind": "shoes", "started_on": "2026-08-01", "threshold_km": 600}, TODAY)
        retired = update_item(self.conn, shoes["id"], {"retired_on": "2026-09-15"}, TODAY)
        self.assertEqual(retired["status"], "retired")
        self.assertFalse(retired["is_default"])
        self.add("r2", "2026-10-01")
        self.assertEqual(self.item(shoes["id"])["used_km"], 10.0)
        self.assertEqual(kit_due(self.conn, TODAY), [])

    def test_strava_gear_beats_the_default(self):
        self.add("ride1", "2026-09-01", activity_type="Ride", km=50, gear="b123")
        self.add("ride2", "2026-09-02", activity_type="Ride", km=30, gear="b999")
        road = create_item(self.conn, {"kind": "bike", "name": "Road", "started_on": "2026-01-01"}, TODAY)
        gravel = create_item(self.conn, {"kind": "bike", "name": "Gravel", "started_on": "2026-01-01", "is_default": False}, TODAY)
        self.assertEqual(self.item(road["id"])["used_km"], 80.0)
        update_item(self.conn, gravel["id"], {"strava_gear_id": "b123"}, TODAY)
        self.assertEqual(self.item(gravel["id"])["used_km"], 50.0)
        self.assertEqual(self.item(road["id"])["used_km"], 30.0)
        gear = list_kit(self.conn, TODAY)["strava_gear"]
        self.assertEqual({row["gear_id"] for row in gear}, {"b123", "b999"})

    def test_activity_slots_list_options_for_its_sport(self):
        self.add("ride1", "2026-09-01", activity_type="Ride")
        create_item(self.conn, {"kind": "bike", "started_on": "2026-01-01"}, TODAY)
        create_item(self.conn, {"kind": "chain", "started_on": "2026-01-01", "threshold_km": 3000}, TODAY)
        create_item(self.conn, {"kind": "shoes", "started_on": "2026-01-01"}, TODAY)
        data = activity_kit(self.conn, "ride1")
        self.assertEqual([slot["slot"] for slot in data["slots"]], ["bike", "chain"])
        self.assertTrue(all(slot["source"] == "auto" for slot in data["slots"]))

    def test_strava_gear_import_starts_at_lifetime_distance(self):
        result = import_strava_gear(self.conn, GEAR, ["g1", "b1", "g0"], TODAY)
        items = {item["name"]: item for item in result["created"]}
        self.assertEqual(items["Pegasus 41"]["used_km"], 512.3)
        self.assertEqual(items["Pegasus 41"]["threshold_km"], 700)
        self.assertTrue(items["Pegasus 41"]["is_default"])
        self.assertEqual(items["Tarmac"]["sport"], "Ride")
        self.assertEqual(items["Old Ghost"]["status"], "retired")
        self.assertTrue(all(gear["kit_id"] for gear in result["gear"]))
        # A later run on that gear adds to Strava's total; importing again creates nothing.
        self.add("r1", TODAY.isoformat(), km=8, gear="g1")
        self.assertEqual(self.item(items["Pegasus 41"]["id"])["used_km"], 520.3)
        self.assertEqual(import_strava_gear(self.conn, GEAR, ["g1"], TODAY)["created"], [])

    def test_strava_gear_import_skips_unselected(self):
        result = import_strava_gear(self.conn, GEAR, ["b1"], TODAY)
        self.assertEqual([item["name"] for item in result["created"]], ["Tarmac"])

    def two_bikes(self):
        road = create_item(self.conn, {"kind": "bike", "name": "Road", "started_on": "2026-01-01"}, TODAY)
        gravel = create_item(self.conn, {"kind": "bike", "name": "Gravel", "started_on": "2026-01-01", "is_default": False}, TODAY)
        return road, gravel

    def test_chain_follows_its_bike(self):
        road, gravel = self.two_bikes()
        chain = create_item(self.conn, {"kind": "chain", "name": "Road chain", "parent_id": road["id"], "started_on": "2026-09-01", "threshold_km": 3000, "is_default": True}, TODAY)
        self.assertFalse(chain["is_default"])  # fitted parts are never sport defaults
        self.add("before", "2026-08-15", activity_type="Ride", km=40)
        self.add("ride1", "2026-09-05", activity_type="Ride", km=50)
        self.add("ride2", "2026-09-06", activity_type="Ride", km=30)
        self.assertEqual(self.item(chain["id"])["used_km"], 80.0)
        # Moving a ride to the gravel bike takes it off the road chain.
        assign_activity_kit(self.conn, "ride2", "bike", gravel["id"])
        self.assertEqual(self.item(chain["id"])["used_km"], 50.0)
        self.assertEqual(self.item(chain["id"])["parent_name"], "Road")

    def test_only_parts_fit_bikes(self):
        road, _ = self.two_bikes()
        shoes = create_item(self.conn, {"kind": "shoes", "started_on": "2026-01-01"}, TODAY)
        with self.assertRaises(ValueError):
            create_item(self.conn, {"kind": "shoes", "parent_id": road["id"]}, TODAY)
        with self.assertRaises(ValueError):
            create_item(self.conn, {"kind": "chain", "parent_id": shoes["id"]}, TODAY)

    def test_wax_interval_counts_from_last_wax(self):
        road, _ = self.two_bikes()
        chain = create_item(self.conn, {"kind": "chain", "parent_id": road["id"], "started_on": "2026-09-01", "service_action": "wax", "service_every_km": 300}, TODAY)
        self.add("ride1", "2026-09-02", activity_type="Ride", km=400)
        # Until a first wax is logged there is nothing to count from, so no cue.
        self.assertEqual(self.item(chain["id"])["service"]["status"], "unlogged")
        self.assertEqual(kit_due(self.conn, TODAY), [])
        log_event(self.conn, chain["id"], {"action": "wax", "done_on": "2026-09-02"}, TODAY)
        log_event(self.conn, chain["id"], {"action": "clean", "done_on": "2026-09-10"}, TODAY)
        self.add("ride2", "2026-09-12", activity_type="Ride", km=275)
        item = self.item(chain["id"])
        self.assertEqual(item["service"]["since_km"], 275.0)  # the clean does not reset the wax
        self.assertEqual(item["service"]["status"], "nearly_due")
        self.assertEqual(item["status"], "no_threshold")
        due = kit_due(self.conn, TODAY)
        self.assertEqual([(entry["id"], entry["due_reason"]) for entry in due], [(chain["id"], "service")])
        self.assertEqual([event["action"] for event in item["events"]], ["clean", "wax"])

    def test_replace_chain_keeps_history(self):
        road, _ = self.two_bikes()
        chain = create_item(self.conn, {"kind": "chain", "name": "KMC", "parent_id": road["id"], "started_on": "2026-06-01", "threshold_km": 3000, "service_action": "wax", "service_every_km": 300}, TODAY)
        self.add("ride1", "2026-09-01", activity_type="Ride", km=60)
        self.add("ride2", "2026-10-10", activity_type="Ride", km=40)
        fresh = replace_item(self.conn, chain["id"], {"on": "2026-10-10", "service_action": "wax"}, TODAY)
        old = self.item(chain["id"])
        self.assertEqual(old["status"], "retired")
        self.assertEqual(old["retired_on"], "2026-10-09")
        self.assertEqual(old["used_km"], 60.0)
        self.assertEqual(fresh["used_km"], 40.0)
        self.assertEqual((fresh["parent_id"], fresh["replaces_id"], fresh["service_every_km"]), (road["id"], chain["id"], 300))
        self.assertEqual(fresh["service"]["last_on"], "2026-10-10")
        with self.assertRaises(ValueError):
            replace_item(self.conn, chain["id"], {}, TODAY)

    def test_tables_from_first_release_gain_new_columns(self):
        self.conn.execute(
            "CREATE TABLE kit_items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, kind TEXT NOT NULL, sport TEXT NOT NULL,"
            " started_on TEXT NOT NULL, threshold_km REAL, threshold_hours REAL, start_km REAL NOT NULL DEFAULT 0,"
            " start_hours REAL NOT NULL DEFAULT 0, is_default INTEGER NOT NULL DEFAULT 0, retired_on TEXT, strava_gear_id TEXT,"
            " notes TEXT, created_at TEXT)"
        )
        self.conn.execute("INSERT INTO kit_items (name, kind, sport, started_on) VALUES ('Old bike', 'bike', 'Ride', '2026-01-01')")
        items = list_kit(self.conn, TODAY)["items"]
        self.assertEqual(items[0]["parent_id"], None)
        self.assertEqual(items[0]["service"], None)

    def test_part_counts_past_rides_on_its_strava_bike(self):
        # The bike came from Strava today; older rides only know its gear id.
        self.add("old1", "2026-08-10", activity_type="Ride", km=70, gear="b1")
        self.add("old2", "2026-08-11", activity_type="Ride", km=40, gear="b2")
        self.add("ride3", "2026-08-12", activity_type="Ride", km=30)
        canyon = create_item(self.conn, {"kind": "bike", "name": "Canyon", "started_on": TODAY.isoformat(), "strava_gear_id": "b1"}, TODAY)
        chain = create_item(self.conn, {"kind": "chain", "parent_id": canyon["id"], "started_on": "2026-08-01"}, TODAY)
        self.assertEqual(self.item(chain["id"])["used_km"], 70.0)
        self.assertEqual(self.item(canyon["id"])["used_km"], 0)  # the bike's own total stays Strava-based
        # A ride moved by hand to another bike leaves the chain.
        other = create_item(self.conn, {"kind": "bike", "name": "Other", "started_on": "2026-01-01", "is_default": False}, TODAY)
        assign_activity_kit(self.conn, "old1", "bike", other["id"])
        self.assertEqual(self.item(chain["id"])["used_km"], 0)

    def test_gear_backfill_range_is_fetched_once(self):
        self.conn.execute("CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT)")
        canyon = create_item(self.conn, {"kind": "bike", "started_on": TODAY.isoformat(), "strava_gear_id": "b1"}, TODAY)
        chain = create_item(self.conn, {"kind": "chain", "parent_id": canyon["id"], "started_on": "2026-08-01"}, TODAY)
        self.assertEqual(gear_backfill_range(self.conn, chain["id"]), ("2026-08-01", TODAY.isoformat()))
        mark_gear_ids_known(self.conn, "2026-08-01")
        self.assertIsNone(gear_backfill_range(self.conn, chain["id"]))
        tyres = create_item(self.conn, {"kind": "tyres", "parent_id": canyon["id"], "started_on": "2026-05-01"}, TODAY)
        self.assertEqual(gear_backfill_range(self.conn, tyres["id"]), ("2026-05-01", "2026-08-01"))
        loose = create_item(self.conn, {"kind": "chain", "started_on": "2026-01-01"}, TODAY)
        self.assertIsNone(gear_backfill_range(self.conn, loose["id"]))


class StravaGearFetchTests(unittest.TestCase):
    def fetch(self, payload):
        response = mock.Mock(status_code=200)
        response.json.return_value = payload
        with mock.patch("backend.app.services.strava.get_strava_access_token", return_value="t"), \
                mock.patch("backend.app.services.strava.httpx.get", return_value=response):
            return fetch_strava_gear(lambda key: None, lambda key, value: None)

    def test_maps_shoes_and_bikes(self):
        gear = self.fetch({
            "shoes": [{"id": "g1", "name": "Pegasus", "distance": 512300, "primary": True, "retired": False}],
            "bikes": [{"id": "b1", "nickname": "Tarmac", "distance": 8000000}],
        })
        self.assertEqual([(item["gear_id"], item["kind"], item["distance_km"]) for item in gear], [("g1", "shoes", 512.3), ("b1", "bike", 8000.0)])
        self.assertEqual(gear[1]["name"], "Tarmac")

    def test_missing_scope_explains_itself(self):
        with self.assertRaises(HTTPException) as caught:
            self.fetch({"id": 1, "firstname": "J"})
        self.assertIn("profile:read_all", caught.exception.detail)

    def test_backfill_writes_gear_ids_onto_source_refs(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute("CREATE TABLE activity_source_refs (source TEXT, external_id TEXT, metadata_json TEXT)")
        conn.executemany("INSERT INTO activity_source_refs VALUES ('strava', ?, ?)", [("1", '{"start_date_local": "x"}'), ("2", None), ("3", "{}")])
        items = [{"id": 1, "gear_id": "b1"}, {"id": 2, "gear_id": "g1"}, {"id": 3, "gear_id": None}]
        with mock.patch("backend.app.services.strava.get_strava_access_token", return_value="t"), \
                mock.patch("backend.app.services.strava.fetch_strava_activities", return_value=items):
            matched = backfill_strava_gear_ids(conn, "2026-08-01", "2026-10-26", lambda key: None, lambda key, value: None)
        self.assertEqual(matched, 2)
        rows = dict(conn.execute("SELECT external_id, json_extract(metadata_json, '$.gear_id') FROM activity_source_refs"))
        self.assertEqual(rows, {"1": "b1", "2": "g1", "3": None})
        self.assertEqual(json.loads(conn.execute("SELECT metadata_json FROM activity_source_refs WHERE external_id = '1'").fetchone()[0])["start_date_local"], "x")


class StravaReconnectTests(unittest.TestCase):
    def test_authorize_url_asks_for_gear_access(self):
        with mock.patch.dict("os.environ", {"STRAVA_CLIENT_ID": "42"}):
            url = build_strava_authorize_url("http://localhost:3000/sync")
        self.assertIn("client_id=42", url)
        self.assertIn("profile%3Aread_all", url)
        self.assertIn("activity%3Aread_all", url)

    def test_exchange_stores_refresh_token_and_scope(self):
        saved = {}
        response = mock.Mock(status_code=200)
        response.json.return_value = {"refresh_token": "new-refresh"}
        with mock.patch.dict("os.environ", {"STRAVA_CLIENT_ID": "42", "STRAVA_CLIENT_SECRET": "s"}), \
                mock.patch("backend.app.services.strava.httpx.post", return_value=response) as post:
            result = exchange_strava_code("abc", "read,profile:read_all,activity:read_all", saved.get, saved.__setitem__)
        self.assertEqual(post.call_args.kwargs["data"]["grant_type"], "authorization_code")
        self.assertEqual(saved["strava_refresh_token"], "new-refresh")
        self.assertTrue(result["gear_access"])
        self.assertEqual(saved["strava_scope"], "activity:read_all,profile:read_all,read")


if __name__ == "__main__":
    unittest.main()
