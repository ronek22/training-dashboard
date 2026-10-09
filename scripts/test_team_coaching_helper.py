import json
import unittest
from unittest.mock import patch
from scripts import team_coaching_helper as helper


class TeamHelperTests(unittest.TestCase):
    def test_job_exposes_completed_review_and_reports_failure(self):
        from scripts import coach_helper as bridge
        with patch.dict(bridge.JOBS, {'test-team': {'status': 'queued'}}, clear=True):
            with patch.object(helper, 'run_review', return_value={'head_coach': {'headline': 'Done'}}):
                bridge.execute_team_review_job('test-team')
            self.assertEqual(bridge.JOBS['test-team']['status'], 'succeeded')
            self.assertEqual(bridge.JOBS['test-team']['review']['head_coach']['headline'], 'Done')
            with patch.object(helper, 'run_review', side_effect=ValueError('Snapshot changed')):
                bridge.execute_team_review_job('test-team')
            self.assertEqual(bridge.JOBS['test-team']['status'], 'failed')
            self.assertEqual(bridge.JOBS['test-team']['message'], 'Snapshot changed')

    def test_one_consolidated_call_and_one_save(self):
        snapshot = {'activities': [{'id': 'run', 'type': 'Run'}, {'id': 'ride', 'type': 'Ride'}], 'strength_detail': []}
        calls = []; saved = []
        def request(path, payload=None):
            if payload is None: return {'context_key': 'a' * 64, 'snapshot': snapshot}
            saved.append(payload); return payload
        def run(prompt, **kwargs):
            calls.append(prompt)
            return json.dumps({
                'specialists': [
                    {'sport': 'running'}, {'sport': 'cycling'}, {'sport': 'strength'},
                ],
                'head_coach': {'headline': 'Specific tradeoff'},
            })
        with patch.object(helper, 'request', side_effect=request):
            result = helper.run_review(run)
        self.assertEqual(len(calls), 1)
        self.assertIn('three concise specialist reports', calls[0])
        self.assertIn('head_coach', calls[0])
        self.assertEqual(len(saved), 1)
        self.assertEqual(len(result['specialists']), 3)

    def test_failed_specialist_never_persists_partial_review(self):
        with patch.object(helper, 'request', return_value={'context_key': 'a'*64, 'snapshot': {'activities': [], 'strength_detail': []}}) as request:
            with self.assertRaises(ValueError):
                helper.run_review(lambda *args, **kwargs: 'not json')
            self.assertEqual(request.call_count, 1)

    def test_prompts_scope_evidence_and_require_goal_tradeoffs(self):
        snapshot = {'activities': [{'id':'run-only','type':'Run'}, {'id':'bike-only','type':'Ride'}], 'strength_detail': ['private-lift']}
        prompt = helper.team_prompt(snapshot)
        self.assertIn('run-only', prompt); self.assertIn('bike-only', prompt)
        self.assertIn('private-lift', prompt)
        self.assertIn('Do not use tools', prompt)
        self.assertIn('Daily readiness is context, not the weekly verdict', prompt)
