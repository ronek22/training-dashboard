import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from backend.app import db
from backend.app.services.activity_photos import (
    photo_path,
    photos_for,
    sync_activity_photos,
    sync_listed_photos,
    sync_track_photos,
)
from backend.app.services.mountain_trips import build_trip_recap

CDN = "https://cdn.example/"


def photo(uid, size, lat=49.2, lon=20.0, taken="2030-08-01T09:00:00Z", **extra):
    return {
        "unique_id": uid, "urls": {str(size): f"{CDN}{uid}-{size}.jpg"}, "sizes": {str(size): [size * 3 // 4, size]},
        "location": [lat, lon] if lat is not None else None, "created_at": taken, "created_at_local": taken.replace("09:", "11:"),
        "caption": "", "placeholder_image": None, **extra,
    }


def strava(photos_by_activity, limited=()):
    """Photos endpoint and CDN; records every request and the auth header it carried."""
    def handler(request):
        handler.requests.append((str(request.url), request.headers.get("Authorization")))
        if request.url.host == "cdn.example":
            return httpx.Response(200, content=request.url.path.encode(), headers={"content-type": "image/jpeg"})
        activity_id = request.url.path.split("/")[-2]
        if activity_id in limited:
            return httpx.Response(429, json={})
        size = int(request.url.params["size"])
        return httpx.Response(200, json=[photo(uid, size, **extra) for uid, extra in photos_by_activity.get(activity_id, [])])
    handler.requests = []
    return handler


class PhotoSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(db, "DB_PATH", str(Path(self.temp.name) / "test.db"))
        self.patch.start()
        db.init_db()
        self.conn = db.get_db()

    def tearDown(self):
        self.conn.close()
        self.patch.stop()
        self.temp.cleanup()

    def sync(self, handler, activity_id="1"):
        with httpx.Client(transport=httpx.MockTransport(handler), headers={"Authorization": "Bearer secret"}) as client:
            return sync_activity_photos(self.conn, client, activity_id)

    def test_stores_both_sizes_without_sending_the_token_to_the_cdn(self):
        handler = strava({"1": [("a", {}), ("b", {"lat": None}), ("c", {"placeholder_image": "x"})]})
        self.assertEqual(self.sync(handler), (2, True))
        stored = photos_for(self.conn, ["1"])["1"]
        self.assertEqual([p["id"] for p in stored], ["a", "b"])  # The placeholder is skipped until processed.
        self.assertEqual((stored[0]["lat"], stored[0]["lon"], stored[0]["width"], stored[0]["height"]), (49.2, 20.0, 1200, 1600))
        self.assertEqual(stored[0]["taken_at_local"], "2030-08-01T11:00:00Z")
        self.assertIsNone(stored[1]["lat"])  # No GPS: filmstrip only.
        self.assertEqual((photo_path("a", thumb=True).read_bytes(), photo_path("a").read_bytes()), (b"/a-256.jpg", b"/a-1600.jpg"))
        self.assertEqual(photo_path("a").parent, Path(self.temp.name) / "photos")  # Beside the database, not in it.
        cdn = [auth for url, auth in handler.requests if url.startswith(CDN)]
        self.assertEqual(len(cdn), 4)
        self.assertTrue(all(auth is None for auth in cdn))
        self.assertTrue(all(auth == "Bearer secret" for url, auth in handler.requests if not url.startswith(CDN)))

    def test_resync_keeps_downloaded_photos_and_drops_deleted_ones(self):
        self.sync(strava({"1": [("a", {}), ("b", {})]}))
        handler = strava({"1": [("b", {"caption": "Ridge"})]})
        self.assertEqual(self.sync(handler), (0, True))
        self.assertEqual([url for url, _ in handler.requests], ["https://www.strava.com/api/v3/activities/1/photos?size=1600&photo_sources=true"])
        stored = photos_for(self.conn, ["1"])["1"]
        self.assertEqual([(p["id"], p["caption"]) for p in stored], [("b", "Ridge")])
        self.assertEqual(self.conn.execute("SELECT photo_count FROM activity_photo_syncs WHERE activity_id = '1'").fetchone()[0], 1)
        self.assertFalse(photo_path("a").exists())
        self.assertIsNone(photo_path("../etc/passwd"))

    def test_listing_fetches_only_activities_whose_photo_count_changed(self):
        self.sync(strava({"1": [("a", {})]}))
        handler = strava({"1": [("a", {})], "2": [("x", {})]})
        listed = [{"id": 1, "total_photo_count": 1}, {"id": 2, "total_photo_count": 1}, {"id": 3, "total_photo_count": 0}]
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            self.assertEqual(sync_listed_photos(self.conn, client, listed), (1, 0))
        self.assertEqual({url.split("/")[-2] for url, _ in handler.requests if "strava.com" in url}, {"2"})

    def test_track_pass_checks_new_and_recent_tracks_and_stops_at_the_rate_limit(self):
        for activity_id, day in (("old", "2030-01-01"), ("seen", "2030-01-02"), ("recent", "2030-07-30"), ("new", "2030-03-01")):
            self.conn.execute("INSERT INTO mountain_tracks (activity_id, region, date, latlng_json) VALUES (?, 'tatras', ?, '[]')", (activity_id, day))
        self.conn.execute("INSERT INTO activity_photo_syncs VALUES ('seen', 0, 'x'), ('recent', 0, 'x')")
        self.conn.commit()
        handler = strava({"recent": [("r", {})]}, limited=("new",))
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            added, pending = sync_track_photos(self.conn, client, today=date(2030, 8, 2))
        self.assertEqual((added, pending), (1, 2))  # recent done; new hit the limit, old waits behind it.
        checked = [url.split("/")[-2] for url, _ in handler.requests if "strava.com" in url and "size=1600" in url]
        self.assertEqual(checked, ["recent", "new"])

    def test_recap_lists_photos_and_the_api_serves_them(self):
        self.conn.execute("INSERT INTO life_load_days (date, tags_json) VALUES ('2030-08-01', ?)", (json.dumps(["mountains"]),))
        self.conn.execute("INSERT INTO activities (id, date, type, name, distance_km, duration_min, elevation_m) VALUES ('1', '2030-08-01', 'Hike', 'Ridge', 12, 300, 900)")
        self.conn.commit()
        self.sync(strava({"1": [("a", {}), ("b", {})]}))
        recap = build_trip_recap(self.conn, "2030-08-01", today=date(2030, 9, 1))
        self.assertEqual(recap["trip"]["photos"], 2)
        self.assertEqual([p["id"] for p in recap["days"][0]["activities"][0]["photos"]], ["a", "b"])

        from backend.app.main import app
        client = TestClient(app)
        thumb = client.get("/trails/photos/a?size=thumb")
        self.assertEqual((thumb.status_code, thumb.content, thumb.headers["content-type"]), (200, b"/a-256.jpg", "image/jpeg"))
        self.assertEqual(client.get("/trails/photos/a").content, b"/a-1600.jpg")
        self.assertEqual(client.get("/trails/photos/missing").status_code, 404)


if __name__ == "__main__":
    unittest.main()
