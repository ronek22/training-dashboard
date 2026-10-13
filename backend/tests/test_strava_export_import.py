import gzip
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.app import db
from backend.app.services import strava_history_backfill
from backend.app.services.strava_export_import import import_export_streams, points_to_streams, read_points

GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">
 <trk><trkseg>
  <trkpt lat="54.0000" lon="18.0000"><ele>10</ele><time>2015-05-01T07:00:00Z</time></trkpt>
  <trkpt lat="54.0009" lon="18.0000"><ele>11</ele><time>2015-05-01T07:00:30Z</time></trkpt>
  <trkpt lat="54.0018" lon="18.0000"><ele>12</ele><time>2015-05-01T07:01:00Z</time></trkpt>
 </trkseg></trk>
</gpx>"""

TCX = """<?xml version="1.0" encoding="UTF-8"?>
<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2" xmlns:ns3="http://www.garmin.com/xmlschemas/ActivityExtension/v2">
 <Activities><Activity Sport="Biking"><Lap><Track>
  <Trackpoint><Time>2016-06-01T08:00:00Z</Time><Position><LatitudeDegrees>54.0</LatitudeDegrees><LongitudeDegrees>18.0</LongitudeDegrees></Position><DistanceMeters>0</DistanceMeters><HeartRateBpm><Value>130</Value></HeartRateBpm><Extensions><ns3:TPX><ns3:Watts>180</ns3:Watts></ns3:TPX></Extensions></Trackpoint>
  <Trackpoint><Time>2016-06-01T08:00:10Z</Time><DistanceMeters>80</DistanceMeters><HeartRateBpm><Value>140</Value></HeartRateBpm></Trackpoint>
  <Trackpoint><Time>2016-06-01T08:00:20Z</Time><Position><LatitudeDegrees>54.0015</LatitudeDegrees><LongitudeDegrees>18.0</LongitudeDegrees></Position><DistanceMeters>160</DistanceMeters><HeartRateBpm><Value>150</Value></HeartRateBpm></Trackpoint>
 </Track></Lap></Activity></Activities>
</TrainingCenterDatabase>"""


class StravaExportImportTests(unittest.TestCase):
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
        self.export = Path(temp.name) / "export"
        (self.export / "activities").mkdir(parents=True)
        self.rows = []

    def add(self, activity_id, day, kind, filename=None, content=None, gz=False):
        self.conn.execute("INSERT INTO activities (id, date, type, name, duration_min, distance_km) VALUES (?, ?, ?, ?, 1, 0.2)",
                          (activity_id, day, kind, kind))
        self.conn.commit()
        if filename:
            path = self.export / filename
            data = content.encode()
            path.write_bytes(gzip.compress(data) if gz else data)
        self.rows.append((activity_id, filename or ""))

    def write_csv(self):
        lines = ["Activity ID,Activity Date,Activity Name,Activity Type,Filename"]
        lines += [f"{activity_id},x,x,x,{filename}" for activity_id, filename in self.rows]
        (self.export / "activities.csv").write_text("\n".join(lines))

    def streams(self, activity_id):
        row = self.conn.execute("SELECT streams_json, source_status FROM activity_details WHERE activity_id = ?", (activity_id,)).fetchone()
        return (json.loads(row["streams_json"]), row["source_status"]) if row else (None, None)

    def test_gpx_gets_measured_distance_and_aligned_streams(self):
        self.add("gpx-run", "2015-05-01", "Run", "activities/1.gpx", GPX)
        self.write_csv()

        result = import_export_streams(self.conn, self.export)

        self.assertEqual(result["imported"], 1)
        streams, source = self.streams("gpx-run")
        self.assertEqual(source, "strava_export")
        self.assertEqual(streams["time"]["data"], [0, 30, 60])
        self.assertAlmostEqual(streams["distance"]["data"][-1], 200.1, delta=1.0)  # 0.0018° of latitude is about 200 m.
        self.assertEqual({len(stream["data"]) for stream in streams.values()}, {3})
        self.assertNotIn("heartrate", streams)
        # No heart rate or power: no invented training-load summary, and the API backfill skips it.
        self.assertIsNone(self.conn.execute("SELECT 1 FROM activity_stream_summaries WHERE activity_id = 'gpx-run'").fetchone())
        self.assertEqual(strava_history_backfill.status(self.conn)["remaining"], 0)

    def test_gzipped_tcx_keeps_device_distance_heart_rate_and_power(self):
        self.add("tcx-ride", "2016-06-01", "Ride", "activities/2.tcx.gz", TCX, gz=True)
        self.write_csv()

        import_export_streams(self.conn, self.export)

        streams, _ = self.streams("tcx-ride")
        self.assertEqual(streams["distance"]["data"], [0.0, 80.0, 160.0])
        self.assertEqual(streams["heartrate"]["data"], [130.0, 140.0, 150.0])
        self.assertEqual(streams["watts"]["data"], [180.0, None, None])
        self.assertEqual(streams["latlng"]["data"][1], streams["latlng"]["data"][0])  # A dropout keeps the last fix.
        self.assertIsNotNone(self.conn.execute("SELECT 1 FROM activity_stream_summaries WHERE activity_id = 'tcx-ride'").fetchone())

    def test_existing_streams_missing_files_dry_runs_and_unsafe_files(self):
        self.add("has-streams", "2020-01-01", "Run", "activities/3.gpx", GPX)
        self.conn.execute("INSERT INTO activity_details (activity_id, fetched_at, source_status, streams_json) VALUES ('has-streams', 'x', 'api', '{}')")
        self.add("no-file", "2013-02-01", "Run")
        self.add("entity", "2014-03-01", "Run", "activities/4.gpx", '<?xml version="1.0"?><!DOCTYPE gpx [<!ENTITY a "aaaa">]><gpx>&a;</gpx>')
        self.add("escape", "2014-04-01", "Run", "../outside.gpx", GPX)
        self.add("dry", "2014-05-01", "Run", "activities/5.gpx", GPX)
        self.write_csv()

        result = import_export_streams(self.conn, self.export, dry_run=True)

        self.assertEqual((result["candidates"], result["imported"], result["no_file"], result["unreadable"]), (4, 1, 2, 1))
        self.assertIn("DOCTYPE", result["errors"][0])
        self.assertIsNone(self.streams("dry")[0])  # A dry run writes nothing.
        self.assertEqual(self.streams("has-streams")[1], "api")

    def test_points_need_a_time_series(self):
        self.assertIsNone(points_to_streams([]))
        path = self.export / "activities" / "single.gpx"
        path.write_text('<gpx xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>'
                        '<trkpt lat="54" lon="18"><time>2015-05-01T07:00:00Z</time></trkpt></trkseg></trk></gpx>')
        self.assertIsNone(points_to_streams(read_points(path)))  # One point is not a recording.

if __name__ == "__main__":
    unittest.main()
