import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from backend.app import db
from backend.app.routers.metrics import router
from backend.app.services import power_trends
from scripts import cycling_power_helper


class CyclingAdviceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(db, 'DB_PATH', str(Path(self.temp.name) / 'test.db'))
        self.patch.start(); db.init_db()
        app = FastAPI(); app.include_router(router)
        self.client = TestClient(app)
        self.add_ride('one')

    def tearDown(self):
        self.client.close(); self.patch.stop(); self.temp.cleanup()

    def add_ride(self, identifier):
        conn = db.get_db()
        conn.execute('INSERT INTO activities(id,date,type,name) VALUES (?,?,?,?)', (identifier,'2026-09-20','VirtualRide',identifier))
        conn.execute('INSERT INTO activity_details(activity_id,fetched_at,source_status,streams_json) VALUES (?,?,?,?)',
                     (identifier,'2026-09-20','streams_backfill',json.dumps({'time':{'data':list(range(61))},'watts':{'data':[250]*61}})))
        conn.commit(); conn.close()

    def test_cache_persists_and_invalidates_for_new_and_changed_streams(self):
        with patch.object(power_trends, '_build_cycling_power_trends_data', wraps=power_trends._build_cycling_power_trends_data) as build:
            first = self.client.get('/metrics/cycling-power').json()
            self.assertEqual(first, self.client.get('/metrics/cycling-power').json())
            self.assertEqual(build.call_count, 1)
            self.add_ride('two')
            self.client.get('/metrics/cycling-power')
            self.assertEqual(build.call_count, 2)
            conn = db.get_db(); conn.execute("UPDATE activity_details SET streams_json = '{}' WHERE activity_id='two'"); conn.commit(); conn.close()
            self.client.get('/metrics/cycling-power')
            self.assertEqual(build.call_count, 3)
            conn = db.get_db(); conn.execute("INSERT INTO activities(id,date,type) VALUES ('run','2026-09-22','Run')"); conn.commit(); conn.close()
            self.client.get('/metrics/cycling-power')
            self.assertEqual(build.call_count, 3)

    def test_cache_preserves_caller_transaction_and_backfill_invalidates(self):
        self.client.get('/metrics/cycling-power')
        conn = db.get_db()
        conn.execute("INSERT INTO activities(id,date,type) VALUES ('late','2026-09-22','VirtualRide')")
        power_trends.get_cycling_power_trends_data(conn)
        self.assertTrue(conn.in_transaction)
        conn.rollback()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM activities WHERE id='late'").fetchone()[0], 0)
        conn.execute("UPDATE activity_details SET streams_json=NULL WHERE activity_id='one'")
        conn.commit()
        self.assertEqual(power_trends.get_cycling_power_trends_data(conn)['coverage']['analyzed_activities'],0)
        conn.execute("UPDATE activity_details SET streams_json=? WHERE activity_id='one'", (json.dumps({'time':{'data':list(range(61))},'watts':{'data':[275]*61}}),))
        conn.commit()
        self.assertEqual(power_trends.get_cycling_power_trends_data(conn)['records'][0]['watts'],275)
        conn.close()

    def test_saved_advice_stale_protection_and_citations(self):
        state = self.client.get('/metrics/cycling-power/advice').json()
        result = dict(context_key=state['context_key'], headline='Build evidence', assessment='Record a repeatable effort.',
                      focus=[dict(title='Repeat',reason='One ride',action='Compare another similar effort',success_check='Recorded power')],uncertainty='Not a maximal test', evidence_ids=['one'])
        saved = self.client.put('/metrics/cycling-power/advice',json=result)
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertFalse(self.client.get('/metrics/cycling-power/advice').json()['stale'])
        bad = {**result,'evidence_ids':['invented']}
        self.assertEqual(self.client.put('/metrics/cycling-power/advice',json=bad).status_code,422)
        self.add_ride('two')
        self.assertEqual(self.client.put('/metrics/cycling-power/advice',json=result).status_code,409)
        latest = self.client.get('/metrics/cycling-power/advice').json()
        self.assertTrue(latest['stale']); self.assertEqual(latest['review'],saved.json())

    def test_helper_reuses_saved_advice_without_the_coach(self):
        run = Mock()
        with patch.object(cycling_power_helper,'request',return_value={'review':{'headline':'Saved'},'stale':False}):
            self.assertEqual(cycling_power_helper.run_review(run,Mock()),{'headline':'Saved'})
        run.assert_not_called()

    def test_helper_calls_the_coach_once_and_saves_same_snapshot(self):
        result = {'context_key':'abc','headline':'Advice'}
        run = Mock(return_value=json.dumps(result))
        with patch.object(cycling_power_helper,'request',side_effect=[{'review':None},{'context_key':'abc','snapshot':{'status':'available','recording_gaps':[]}},result]) as request:
            self.assertEqual(cycling_power_helper.run_review(run,Mock()),result)
            self.assertEqual(request.call_args.args,('/metrics/cycling-power/advice',result))
        self.assertEqual(run.call_count,1)
