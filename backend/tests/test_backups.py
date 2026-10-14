import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from backend.app.services import backups


def row_counts(path):
    conn = sqlite3.connect(path)
    try:
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")]
        return {table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in tables}
    finally:
        conn.close()


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {"TRAINING_BACKUP_DIR": ""})
        env.start()
        self.addCleanup(env.stop)
        self.root = Path(self.tmp.name)
        self.db = self.root / "training.db"
        self.dir = self.root / "backups"
        # A live connection in WAL mode with uncheckpointed writes: a file copy would miss them.
        self.live = sqlite3.connect(self.db)
        self.addCleanup(self.live.close)
        self.live.execute("PRAGMA journal_mode=WAL")
        self.live.execute("CREATE TABLE activities (id INTEGER PRIMARY KEY, name TEXT)")
        self.live.execute("CREATE TABLE coach_notes (id INTEGER PRIMARY KEY, content TEXT)")
        self.live.executemany("INSERT INTO activities (name) VALUES (?)", [(f"run {i}",) for i in range(250)])
        self.live.executemany("INSERT INTO coach_notes (content) VALUES (?)", [("note",)] * 12)
        self.live.commit()

    def test_backup_and_restore_keep_row_counts(self):
        expected = row_counts(self.db)
        status = backups.create_backup(str(self.db), "manual", datetime(2026, 10, 14, 9, 0))
        self.assertTrue(status["ok"], status["message"])
        snapshot = self.dir / status["file"]
        self.assertEqual(row_counts(snapshot), expected)

        # Damage the live data, then restore the snapshot the way `just restore` does.
        self.live.execute("DELETE FROM activities")
        self.live.commit()
        self.live.close()
        aside = self.db.with_name("training.db.replaced")
        for ext in ("", "-wal", "-shm"):
            if Path(f"{self.db}{ext}").exists():
                Path(f"{self.db}{ext}").rename(f"{aside}{ext}")
        shutil.copy(snapshot, self.db)
        self.assertEqual(row_counts(self.db), expected)
        self.assertEqual(row_counts(aside)["activities"], 0)

    def test_status_reports_integrity_failure(self):
        with patch.object(backups, "integrity_check", return_value="row 3 missing from index"):
            status = backups.create_backup(str(self.db), "daily", datetime(2026, 10, 14, 9, 0))
        self.assertFalse(status["ok"])
        self.assertIn("Integrity check failed", status["message"])
        self.assertEqual(backups.list_backups(self.dir), [])
        shown = backups.get_status(str(self.db), datetime(2026, 10, 14, 10, 0))
        self.assertFalse(shown["ok"])
        self.assertIsNone(shown["last_success_at"])

    def test_retention_keeps_seven_daily_and_four_weekly_and_ignores_other_files(self):
        self.dir.mkdir()
        start = datetime(2026, 10, 14, 3, 0)
        for days in range(60):
            for hour in (0, 5):  # two copies a day: only the newest of each day survives
                when = start - timedelta(days=days) + timedelta(hours=hour)
                (self.dir / f"training-{when:%Y%m%d-%H%M%S}-daily.db").write_bytes(b"x")
        for minutes in range(4):
            (self.dir / f"training-20261014-10{minutes:02d}00-startup.db").write_bytes(b"x")
        (self.dir / "training-before-export-import-2026-10-13.db").write_bytes(b"keep")

        backups.prune(self.dir)

        left = backups.list_backups(self.dir)
        daily = [item for item in left if item["kind"] == "daily"]
        self.assertEqual(len(daily), 11)
        self.assertEqual([item["created_at"][:10] for item in daily[:7]],
                         [(start - timedelta(days=d)).date().isoformat() for d in range(7)])
        self.assertTrue(all(item["created_at"].endswith("08:00:00") for item in daily))
        weeks = {datetime.fromisoformat(item["created_at"]).isocalendar()[:2] for item in daily[7:]}
        self.assertEqual(len(weeks), 4)
        self.assertEqual(len([item for item in left if item["kind"] == "startup"]), 2)
        self.assertTrue((self.dir / "training-before-export-import-2026-10-13.db").exists())

    def test_startup_snapshot_skips_new_databases_and_recent_copies(self):
        empty = self.root / "empty.db"
        sqlite3.connect(empty).close()
        self.assertIsNone(backups.snapshot_before_migrations(str(empty)))
        self.assertIsNone(backups.snapshot_before_migrations(str(self.root / "missing.db")))

        now = datetime(2026, 10, 14, 7, 0)
        first = backups.snapshot_before_migrations(str(self.db), now)
        self.assertEqual(first["kind"], "daily")  # first copy of the day doubles as the daily one
        self.assertIsNone(backups.snapshot_before_migrations(str(self.db), now + timedelta(minutes=20)))
        later = backups.snapshot_before_migrations(str(self.db), now + timedelta(hours=2))
        self.assertEqual(later["kind"], "startup")
        self.assertFalse(backups.daily_backup_due(str(self.db), now + timedelta(hours=3)))
        self.assertTrue(backups.daily_backup_due(str(self.db), now + timedelta(days=1)))

    def test_init_db_snapshots_before_migrating(self):
        from backend.app import db
        with patch.object(db, "DB_PATH", str(self.db)):
            db.init_db()
        self.assertEqual(len(backups.list_backups(self.dir)), 1)

    def test_backup_command_line(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "-m", "app.services.backups"], cwd=root, capture_output=True, text=True,
                                env={**os.environ, "TRAINING_DB_PATH": str(self.db)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK: training-", result.stdout)



class RestoreDrillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        env = patch.dict(os.environ, {"TRAINING_BACKUP_DIR": ""})
        env.start()
        self.addCleanup(env.stop)
        self.root = Path(self.tmp.name)
        self.db = self.root / "training.db"
        self.dir = self.root / "backups"
        self.dir.mkdir()
        # Fixture backup: a database built by the real migrations, with a little history in it.
        from backend.app import db
        fixture = self.root / "fixture.db"
        with patch.object(db, "DB_PATH", str(fixture)):
            db.init_db(snapshot=False)
        conn = sqlite3.connect(fixture)
        conn.executemany("INSERT INTO activities (id, date, type) VALUES (?, ?, 'Run')",
                         [("a1", "2026-10-01"), ("a2", "2026-10-12")])
        conn.execute("INSERT INTO weekly_plans (week_start, days_json) VALUES ('2026-10-12', '[]')")
        conn.commit()
        conn.close()
        self.backup = self.dir / "training-20261014-090000-daily.db"
        shutil.move(fixture, self.backup)
        self.db.write_bytes(b"live database, must stay untouched")

    def test_drill_restores_migrates_and_queries_newest_backup(self):
        # Leftover from a drill that was killed mid-copy.
        (self.dir / "restore-drill-killed").mkdir()
        (self.dir / "restore-drill-killed" / "training.db").write_bytes(b"partial")
        backup_bytes = self.backup.read_bytes()
        status = backups.restore_drill(str(self.db), datetime(2026, 10, 15, 9, 0))
        self.assertTrue(status["ok"], status["message"])
        self.assertEqual((status["file"], status["activities"], status["latest_activity"], status["plan_weeks"]),
                         (self.backup.name, 2, "2026-10-12", 1))
        # Neither the live database nor the backup changed, no extra copy was taken, scratch copies are gone.
        self.assertEqual(self.db.read_bytes(), b"live database, must stay untouched")
        self.assertEqual(self.backup.read_bytes(), backup_bytes)
        self.assertEqual([item["file"] for item in backups.list_backups(self.dir)], [self.backup.name])
        self.assertEqual(sorted(path.name for path in self.dir.iterdir()), sorted([self.backup.name, backups.DRILL_FILE]))
        reported = backups.get_status(str(self.db))["restore_drill"]
        self.assertEqual((reported["ok"], reported["ran_at"]), (True, "2026-10-15T09:00:00"))
        self.assertFalse(backups.restore_drill_due(str(self.db), datetime(2026, 10, 21, 9, 0)))
        self.assertTrue(backups.restore_drill_due(str(self.db), datetime(2026, 10, 22, 9, 0)))

    def test_drill_records_migration_failure_with_reason(self):
        conn = sqlite3.connect(self.backup)
        # A view where a table should be: the migrations cannot add columns or indexes to it.
        conn.execute("DROP TABLE activities")
        conn.execute("CREATE VIEW activities AS SELECT 1 AS id")
        conn.commit()
        conn.close()
        status = backups.restore_drill(str(self.db))
        self.assertFalse(status["ok"])
        self.assertTrue(status["message"].startswith("Migrations failed:"), status["message"])
        self.assertFalse(backups.get_status(str(self.db))["restore_drill"]["ok"])

    def test_drill_records_smoke_query_failure(self):
        conn = sqlite3.connect(self.backup)
        conn.execute("DELETE FROM activities")
        conn.commit()
        conn.close()
        status = backups.restore_drill(str(self.db))
        self.assertFalse(status["ok"])
        self.assertIn("no activities", status["message"])

    def test_drill_without_backups_fails(self):
        self.backup.unlink()
        status = backups.restore_drill(str(self.db))
        self.assertEqual((status["ok"], status["message"]), (False, "No backup to restore"))

    def test_drill_command_line(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, "-m", "app.services.backups", "drill"], cwd=root, capture_output=True,
                                text=True, env={**os.environ, "TRAINING_DB_PATH": str(self.db)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK: training-20261014-090000-daily.db: 2 activities", result.stdout)


if __name__ == "__main__":
    unittest.main()
