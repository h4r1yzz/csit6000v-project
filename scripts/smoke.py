"""End-to-end API smoke check with simulated responses or a reachable live model."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'backend' / 'tests'))
from fastapi.testclient import TestClient
from app import agents, db, tacc
from app.main import app
from pg_harness import isolated_schema, require_postgres_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Use the configured live model for all five stages')
    args = parser.parse_args()
    require_postgres_url()
    if args.live and not tacc.configuration()['configured']:
        parser.error('Configure QWEN_BASE_URL or LLM_BASE_URL before running --live.')

    with isolated_schema(clear_llm=False) as (_schema, account_schemas), TestClient(app) as client:
        registered = client.post('/api/auth/register', json={
            'name': 'Smoke Reviewer', 'email': 'reviewer@example.test', 'password': 'smoke-password-123',
        })
        registered.raise_for_status()
        account_id = registered.json()['id']
        account_schemas.append(f'fitpilot_account_{account_id}')
        if args.live:
            profile = client.get('/api/profile').raise_for_status().json()
            profile.update(weekly_days=2, scheduled_days=['Tuesday', 'Saturday'])
            client.put('/api/profile', json=profile).raise_for_status()

        with ExitStack() as model:
            if not args.live:
                model.enter_context(patch.dict(os.environ, {
                    'LLM_BASE_URL': 'http://simulated-model.invalid/v1', 'LLM_MODEL': 'simulated-smoke',
                }))
                with db.account_scope(account_id):
                    ctx = agents.context()
                    goal = agents.fallback('goal_planning', ctx)
                    answers = [
                        {'summary': goal['summary'], 'priorities': goal['priorities']},
                        agents.fallback('exercise_planning', ctx),
                        {'menu_id': next(iter(agents.nutrition_options(ctx))), 'summary': 'Simulated catalog selection'},
                        agents.fallback('exercise_feedback', ctx),
                        agents.fallback('evaluation_adaptation', ctx),
                    ]
                model.enter_context(patch('app.tacc._send_chat', side_effect=[
                    {'content': json.dumps(answer), 'source': 'llm'} for answer in answers
                ]))
            response = client.post('/api/workflows/plan', json={})
            config = tacc.configuration()
        response.raise_for_status()
        draft = response.json()
        assert [step['agent_id'] for step in draft['steps']] == [agent['id'] for agent in agents.AGENTS]
        assert all(step['source'] == config['source'] and step['status'] == 'completed' for step in draft['steps'])
        assert draft['validation']['valid']
        assert client.get('/api/overview').json()['active_plan'] is None
        client.post('/api/plans', json=draft).raise_for_status()
        assert client.get('/api/overview').json()['active_plan']['workflow_id'] == draft['workflow_id']
        if args.live:
            print('PASS: account -> five live model stages -> valid draft -> approval -> persisted active plan')
            print(f"Live model: {config['model']} ({config['provider']}); all seven constraints passed.")
        else:
            print('PASS: account -> five simulated model stages -> valid draft -> approval -> persisted active plan')
            print('SIMULATED MODEL: this checks application integration, not live inference or recommendation quality.')


if __name__ == '__main__':
    main()
