import json
import unittest
from pydantic import ValidationError
from app.schemas import PoseSession

class BilateralSchemaTests(unittest.TestCase):
    def payload(self):
        return dict(exercise='Bicep curl', duration_seconds=10, reps=3,
                    analyzed_frames=100, average_confidence=.9,
                    range_of_motion={'min': 30, 'max': 175}, source='webcam',
                    counts_by_side={'left': 1, 'right': 2},
                    counting_method='full_cycles_per_arm_sum',
                    thresholds={'bent': 60, 'extended': 145, 'calibrated': True})

    def test_roundtrip(self):
        body = PoseSession(**self.payload()).model_dump()
        self.assertEqual(body['counts_by_side'], {'left': 1, 'right': 2})
        self.assertTrue(body['thresholds']['calibrated'])

    def test_rejects_inconsistent_counts_and_thresholds(self):
        for change in ({'reps': 2}, {'exercise': 'Squat'},
                       {'thresholds': {'bent': 160, 'extended': 100}}):
            with self.assertRaises(ValidationError):
                PoseSession(**(self.payload() | change))

    def test_legacy_summary_still_accepted(self):
        payload = self.payload()
        for key in ('counts_by_side', 'counting_method', 'thresholds'):
            payload.pop(key)
        self.assertIsNone(PoseSession(**payload).counts_by_side)

    def test_api_persists_counts_and_feedback(self):
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from app import agents, db
        from app.main import app
        from pg_harness import POSTGRES_URL, isolated_schema
        if not POSTGRES_URL:
            self.skipTest('Set TEST_DATABASE_URL or DATABASE_URL for Postgres tests')
        with isolated_schema() as (_schema, account_schemas), TestClient(app) as client:
            registered = client.post('/api/auth/register', json={
                'name': 'Demo', 'email': 'person@example.test', 'password': 'example-password-123',
            })
            registered.raise_for_status()
            account_schemas.append(f"fitpilot_account_{registered.json()['id']}")
            saved = client.post('/api/pose-sessions', json=self.payload())
            self.assertEqual(saved.status_code, 200, saved.text)
            restored = client.get('/api/pose-sessions').json()[0]
            self.assertEqual(restored['counts_by_side'], {'left': 1, 'right': 2})
            pose_id = saved.json()['id']
            with db.account_scope(registered.json()['id']):
                answer = agents.fallback('exercise_feedback', agents.context(pose_id))
            with patch.dict('os.environ', {'LLM_BASE_URL': 'http://model.test/v1', 'LLM_MODEL': 'test-model'}), patch(
                'app.tacc._send_chat', return_value={'content': json.dumps(answer), 'source': 'llm'},
            ):
                reply = client.post('/api/agents/exercise_feedback/run', json={'pose_session_id': pose_id})
            self.assertEqual(reply.status_code, 200, reply.text)
            observations = ' '.join(reply.json()['output']['observations'])
            self.assertIn('Left arm: 1; right arm: 2', observations)
            self.assertIn('calibration range', observations)
