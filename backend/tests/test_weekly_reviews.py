import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app import db
from backend.app.routers.weekly_reviews import router


class WeeklyReviewTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = str(Path(self.directory.name) / 'reviews.db')
        self.db_patch = patch.object(db, 'DB_PATH', self.path)
        self.db_patch.start()
        db.init_db()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.db_patch.stop()
        self.directory.cleanup()

    def save(self, week='2026-08-17', **changes):
        return self.client.put('/reviews/weekly', json={
            'week_start': week, 'improved': ' Better consistency ',
            'missed': 'Missed one ride', 'proposed_change': 'Move the ride to Friday',
            'outcome_reason': 'Insufficient evidence to assess a prior suggestion.',
            **changes,
        })

    def test_history_persists_and_updates_do_not_duplicate_weeks(self):
        self.assertEqual(self.client.get('/reviews/weekly').json(), [])
        self.assertEqual(self.save().status_code, 200)
        self.assertEqual(self.save('2026-08-24').status_code, 200)
        self.save(improved='Better sleep')
        db.init_db()  # Startup migration is repeatable and preserves reviews.
        rows = self.client.get('/reviews/weekly').json()
        self.assertEqual([r['week_start'] for r in rows], ['2026-08-24', '2026-08-17'])
        self.assertEqual(rows[1]['improved'], 'Better consistency')
        with sqlite3.connect(self.path) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM weekly_reviews').fetchone()[0], 2)

    def test_outcome_preserves_original_suggestion(self):
        self.save()
        result = self.save('2026-08-24', previous_change_outcome='helped').json()
        self.assertEqual(result['improved'], 'Better consistency')
        self.assertEqual(result['previous_change'], 'Move the ride to Friday')
        self.save(proposed_change='A different suggestion')
        result = self.save('2026-08-24', previous_change_outcome='did_not_help').json()
        self.assertEqual(result['previous_change'], 'Move the ride to Friday')
        self.assertEqual(result['previous_change_outcome'], 'helped')

    def test_missing_previous_week_is_not_assessed_as_a_recent_suggestion(self):
        self.save()
        self.assertEqual(self.save('2026-08-03', previous_change_outcome='helped').status_code, 422)
        self.assertIsNone(self.save('2026-08-03').json()['previous_change'])

    def test_context_excludes_future_data_and_includes_prior_review(self):
        self.save()
        with sqlite3.connect(self.path) as conn:
            conn.execute("INSERT INTO coach_notes (date, category, content) VALUES ('2026-08-25', 'training', 'Relevant')")
            conn.execute("INSERT INTO coach_notes (date, category, content) VALUES ('2026-09-01', 'training', 'Future')")
        result = self.client.get('/reviews/weekly/context?week_start=2026-08-24').json()
        self.assertEqual(result['previous_change'], 'Move the ride to Friday')
        self.assertEqual([n['content'] for n in result['coaching_notes']], ['Relevant'])
        self.assertEqual(result['week_end'], '2026-08-30')

    def test_invalid_reviews_are_rejected(self):
        for changes in ({'improved': '  '}, {'missed': ''}, {'proposed_change': 'x' * 1001},
                        {'previous_change_outcome': 'unknown'}, {'week': '2026-08-18'},
                        {'week': '2099-01-05'}, {'week': 'not-a-date'}):
            with self.subTest(changes=changes):
                self.assertEqual(self.save(**changes).status_code, 422)
        self.assertEqual(self.client.get('/reviews/weekly').json(), [])


if __name__ == '__main__':
    unittest.main()
