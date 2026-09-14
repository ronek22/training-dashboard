import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app import db
from backend.app.routers.coaching import router


def result(key):
    return {'context_key': key, 'specialists': [
        {'sport': sport, 'verdict': 'Insufficient evidence', 'assessment': 'No sessions in this snapshot.',
         'next_week_focus': 'Record training before assessing goal support.', 'evidence_ids': [], 'uncertainty': 'No training recorded.'}
        for sport in ('running', 'cycling', 'strength')],
        'head_coach': {'headline': 'Build a useful baseline', 'verdict': 'The week cannot yet be assessed.',
                      'tradeoff': 'Sport priorities are unknown.', 'next_week_change': 'Record the next week.',
                      'success_check': 'Check whether sessions and goals are recorded.', 'uncertainty': 'No evidence.'}}


class TeamAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(db, 'DB_PATH', str(Path(self.temp.name) / 'analysis.db'))
        self.patch.start(); db.init_db()
        app = FastAPI(); app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close(); self.patch.stop(); self.temp.cleanup()

    def test_cache_is_stable_and_no_plan_is_written(self):
        initial = self.client.get('/coaching/team-analysis').json()
        self.assertIsNone(initial['review'])
        context = self.client.get('/coaching/team-analysis/context').json()
        self.assertEqual(initial['context_key'], context['context_key'])
        saved = self.client.put('/coaching/team-analysis', json=result(initial['context_key']))
        self.assertEqual(saved.status_code, 200, saved.text)
        cached = self.client.get('/coaching/team-analysis').json()
        self.assertFalse(cached['stale'])
        self.assertEqual(cached['review']['head_coach']['headline'], 'Build a useful baseline')
        weekly = self.client.get('/coaching/weekly').json()
        self.assertEqual(weekly['team_analysis']['review']['head_coach']['headline'], 'Build a useful baseline')
        self.assertFalse(weekly['team_analysis']['stale'])
        self.assertNotIn('head_coach', context['snapshot']['team_facts'])
        conn = db.get_db()
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM weekly_plans').fetchone()[0], 0)
        self.assertEqual(conn.execute('SELECT COUNT(*) FROM plan_revisions').fetchone()[0], 0)
        conn.close()

    def test_changed_data_rejects_obsolete_write_and_preserves_previous(self):
        initial = self.client.get('/coaching/team-analysis').json()
        self.client.put('/coaching/team-analysis', json=result(initial['context_key']))
        conn = db.get_db()
        conn.execute('INSERT INTO activities(id,date,type,duration_min) VALUES (?,?,?,?)', ('new-run', initial['through_date'], 'Run', 30))
        conn.commit(); conn.close()
        self.assertEqual(self.client.put('/coaching/team-analysis', json=result(initial['context_key'])).status_code, 409)
        latest = self.client.get('/coaching/team-analysis').json()
        self.assertTrue(latest['stale'])
        self.assertIsNotNone(latest['review'])

    def test_invalid_citations_duplicate_sports_and_overlong_text_rejected(self):
        key = self.client.get('/coaching/team-analysis').json()['context_key']
        invalid = result(key); invalid['specialists'][0]['evidence_ids'] = ['invented']
        self.assertEqual(self.client.put('/coaching/team-analysis', json=invalid).status_code, 422)
        invalid = result(key); invalid['specialists'][0]['sport'] = 'cycling'
        self.assertEqual(self.client.put('/coaching/team-analysis', json=invalid).status_code, 422)
        invalid = result(key); invalid['head_coach']['headline'] = 'x' * 101
        self.assertEqual(self.client.put('/coaching/team-analysis', json=invalid).status_code, 422)
