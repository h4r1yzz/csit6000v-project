"""Deterministic end-to-end API smoke check; model transport is explicitly simulated."""
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app import agents, db
from app.main import app


def main():
    with tempfile.TemporaryDirectory() as directory, patch.object(db, 'DB_PATH', Path(directory) / 'smoke.db'), patch.dict(os.environ, {
        'DATABASE_URL': '', 'DATABASE_URL_UNPOOLED': '', 'VERCEL': '',
        'LLM_BASE_URL': 'http://simulated-model.invalid/v1', 'LLM_MODEL': 'simulated-smoke', 'QWEN_BASE_URL': '',
    }), TestClient(app) as client:
        registered = client.post('/api/auth/register', json={
            'name': 'Smoke Reviewer', 'email': 'reviewer@example.test', 'password': 'smoke-password-123',
        })
        registered.raise_for_status()
        with db.account_scope(registered.json()['id']):
            ctx = agents.context()
            goal = agents.fallback('goal_planning', ctx)
            answers = [
                {'summary': goal['summary'], 'priorities': goal['priorities']},
                agents.fallback('exercise_planning', ctx),
                {'menu_id': next(iter(agents.nutrition_options(ctx))), 'summary': 'Simulated catalog selection'},
                agents.fallback('exercise_feedback', ctx),
                agents.fallback('evaluation_adaptation', ctx),
            ]
        with patch('app.tacc._send_chat', side_effect=[{'content': json.dumps(a), 'source': 'llm'} for a in answers]):
            response = client.post('/api/workflows/plan', json={})
        response.raise_for_status()
        draft = response.json()
        assert len(draft['steps']) == 5 and draft['validation']['valid']
        assert client.get('/api/overview').json()['active_plan'] is None
        client.post('/api/plans', json=draft).raise_for_status()
        assert client.get('/api/overview').json()['active_plan']['workflow_id'] == draft['workflow_id']
        print('PASS: account -> five simulated model stages -> valid draft -> approval -> persisted active plan')
        print('SIMULATED MODEL: this checks application integration, not live inference or recommendation quality.')


if __name__ == '__main__':
    main()
