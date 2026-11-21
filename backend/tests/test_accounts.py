import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import agents, db
from app.main import app


class AccountIsolationTest(unittest.TestCase):
    def test_private_recommendations_history_and_logout(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(db, 'DB_PATH', Path(folder) / 'demo.db'), patch.dict(os.environ, {
            'DATABASE_URL': '', 'VERCEL': '', 'QWEN_BASE_URL': '', 'LLM_BASE_URL': '',
        }), TestClient(app) as ada, TestClient(app) as sam:
            self.assertEqual(ada.get('/api/overview').status_code, 401)
            password = 'example-passphrase'
            def register(client, name):
                response = client.post('/api/auth/register', json={
                    'name': name, 'email': f'{name.lower()}@example.test', 'password': password,
                })
                self.assertEqual(response.status_code, 201, response.text)
                return response.json()['id']

            ada_id = register(ada, 'Ada')
            sam_id = register(sam, 'Sam')
            self.assertNotEqual(ada_id, sam_id)
            profile = ada.get('/api/profile').json()
            profile.update(goal='Train for a walking holiday', minutes_per_session=20)
            ada.put('/api/profile', json=profile).raise_for_status()
            question = 'Plan my walking holiday training'
            # Exercise the real prompt logging path with a simulated model transport.
            with db.account_scope(ada_id):
                goal = agents.fallback('goal_planning', agents.context())
            answer = json.dumps({'summary': goal['summary'], 'priorities': goal['priorities']})
            with patch.dict(os.environ, {'LLM_BASE_URL': 'http://model.test/v1', 'LLM_MODEL': 'test-model'}), patch(
                'app.tacc._send_chat', return_value={'content': answer, 'source': 'llm'},
            ):
                run = ada.post('/api/agents/goal_planning/run', json={'message': question})
            run.raise_for_status()
            self.assertEqual(run.json()['output']['target_minutes'], 20)
            self.assertEqual(sam.get('/api/profile').json()['name'], 'Sam')
            self.assertEqual(sam.get('/api/agent-runs').json(), [])
            with db.account_scope(ada_id):
                row = db.one('SELECT * FROM model_prompts WHERE agent_run_id=?', (run.json()['id'],))
                self.assertEqual(row['status'], 'answered')
                self.assertIn(question, json.loads(row['request_json'])['messages'][-1]['content'])
            with db.account_scope(sam_id):
                self.assertEqual(db.rows('SELECT id FROM model_prompts'), [])
            cookie = ada.cookies.get('fitpilot_session')
            ada.post('/api/auth/logout').raise_for_status()
            self.assertEqual(ada.get('/api/profile', headers={'Cookie': f'fitpilot_session={cookie}'}).status_code, 401)
            credentials = {'email': 'ada@example.test', 'password': 'incorrect-password'}
            self.assertEqual(ada.post('/api/auth/login', json=credentials).status_code, 401)
            credentials['password'] = password
            ada.post('/api/auth/login', json=credentials).raise_for_status()
            self.assertEqual(ada.get('/api/profile').json()['goal'], profile['goal'])
            self.assertEqual(len(ada.get('/api/agent-runs').json()), 1)
