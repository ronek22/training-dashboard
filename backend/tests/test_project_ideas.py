import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers import project_ideas as router
from backend.app.services import project_ideas as service
from scripts.publish_project_ideas import publish, validate


class ProjectIdeasTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'project-ideas.json'
        self.review = {'reviewed_at': '2026-09-10T09:00:00+02:00', 'summary': 'A focused fixture review for project ideas.', 'ideas': [{
            'id': 'test-proposal', 'title': 'A useful improvement', 'category': 'Engineering', 'effort': 'Small', 'priority': 'High',
            'problem': 'A concrete problem that needs solving.', 'proposal': 'A concrete implementation proposal.', 'benefit': 'An observable user benefit.',
            'evidence': ['frontend/package.json'], 'acceptance_criteria': ['The workflow succeeds.', 'Failures are explained.'], 'created_on': '2026-09-10',
        }]}
        self.path.write_text(json.dumps(self.review))
        self.db = Path(self.tmp.name) / 'test.db'
        self.conn = sqlite3.connect(self.db)
        service.init_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_decisions_survive_new_review_and_restart(self):
        idea_id = self.review['ideas'][0]['id']
        service.set_status(self.conn, idea_id, 'shortlisted', self.path)
        self.conn.commit()
        publish({**self.review, 'summary': 'No new proposals after reviewing current changes.', 'ideas': []}, self.path)
        with sqlite3.connect(self.db) as second:
            board = service.get_board(second, self.path)
        idea = next(item for item in board['ideas'] if item['id'] == idea_id)
        self.assertEqual(idea['status'], 'shortlisted')
        self.assertIn(idea['acceptance_criteria'][0], idea['build_brief'])
        self.assertNotIn('status', json.loads(self.path.read_text())['ideas'][0])

    def test_all_workflow_states_can_be_saved_and_restored(self):
        idea_id = self.review['ideas'][0]['id']
        for status in ['shortlisted', 'building', 'done', 'dismissed', 'new']:
            service.set_status(self.conn, idea_id, status, self.path)
            idea = next(i for i in service.get_board(self.conn, self.path)['ideas'] if i['id'] == idea_id)
            self.assertEqual(idea['status'], status)
        with self.assertRaises(ValueError):
            service.set_status(self.conn, idea_id, 'invented', self.path)
        with self.assertRaises(LookupError):
            service.set_status(self.conn, 'unknown-idea', 'done', self.path)

    def test_publish_deduplicates_without_overwriting_existing_proposal(self):
        review = copy.deepcopy(self.review)
        review['ideas'][0]['proposal'] = 'Changed text must not overwrite the saved proposal.'
        self.assertEqual(publish(review, self.path), 0)
        self.assertEqual(json.loads(self.path.read_text())['ideas'], self.review['ideas'])
        idea = copy.deepcopy(review['ideas'][0])
        idea['id'] = 'new-unique-id'
        self.assertEqual(publish({**review, 'ideas': [idea]}, self.path), 0)
        idea['title'] = 'A genuinely different proposal'
        self.assertEqual(publish({**review, 'ideas': [idea]}, self.path), 1)
        self.assertEqual(len(service.load_catalog(self.path)['ideas']), 2)

    def test_invalid_or_old_review_leaves_current_file_untouched(self):
        before = self.path.read_text()
        invalid = copy.deepcopy(self.review)
        invalid['ideas'][0]['acceptance_criteria'] = []
        with self.assertRaises(ValueError):
            publish(invalid, self.path)
        older = {**self.review, 'reviewed_at': '2020-01-01T00:00:00Z'}
        with self.assertRaises(ValueError):
            publish(older, self.path)
        self.assertEqual(before, self.path.read_text())

    def test_generator_cannot_set_user_status_or_repeat_ids(self):
        invalid = copy.deepcopy(self.review)
        invalid['ideas'][0]['status'] = 'done'
        with self.assertRaises(ValueError):
            validate(invalid)
        invalid = copy.deepcopy(self.review)
        invalid['ideas'].append(invalid['ideas'][0])
        with self.assertRaises(ValueError):
            validate(invalid)
        with self.assertRaises(ValueError):
            validate({**self.review, 'reviewed_at': '2026-09-10T12:00:00'})

    def test_api_persistence_validation_missing_and_unavailable(self):
        app = FastAPI()
        app.include_router(router.router)
        def db():
            return sqlite3.connect(self.db, check_same_thread=False)
        with patch.object(router, 'get_db', db), patch.object(service, '_find_docs_dir', lambda: Path(self.tmp.name)), TestClient(app) as client:
            response = client.get('/project-ideas')
            self.assertEqual(response.status_code, 200)
            idea = response.json()['ideas'][0]
            self.assertIn('Acceptance criteria', idea['build_brief'])
            self.assertEqual(client.patch('/project-ideas/' + idea['id'], json={'status': 'building'}).status_code, 200)
            self.assertEqual(next(i for i in client.get('/project-ideas').json()['ideas'] if i['id'] == idea['id'])['status'], 'building')
            self.assertEqual(client.patch('/project-ideas/' + idea['id'], json={'status': 'invalid'}).status_code, 422)
            self.assertEqual(client.patch('/project-ideas/not-found', json={'status': 'done'}).status_code, 404)
            self.path.write_text('{broken')
            self.assertEqual(client.get('/project-ideas').status_code, 503)


if __name__ == '__main__':
    unittest.main()
