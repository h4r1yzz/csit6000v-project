"""Reproduce a two-turn coach conversation and verify its Postgres readback."""
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'backend/tests')]
from fastapi.testclient import TestClient
from app import db
from app.main import app
from pg_harness import isolated_schema


def main():
    credentials = {'email': 'demo-chat@example.test', 'password': 'synthetic-chat-demo'}
    questions = ('What goal did I save?', 'How many minutes did I set for each session?')
    tool_request = {'role': 'assistant', 'content': None, 'source': 'llm', 'tool_calls': [{
        'id': 'demo-profile', 'type': 'function',
        'function': {'name': 'get_profile', 'arguments': '{}'},
    }]}

    def simulated_model(_config, body, _timeout):
        messages = body['messages']
        context = json.loads(messages[1]['content'])
        if context['question'] == questions[0] and messages[-1]['role'] == 'user':
            return tool_request
        if context['question'] == questions[0]:
            assert messages[-1]['role'] == 'tool'
            profile = json.loads(messages[-1]['content'])
            reply = f"Your saved goal is: {profile['goal']}."
        else:
            assert context['question'] == questions[1]
            assert questions[0] in context['recent_questions']
            reply = f"You set {context['profile']['minutes_per_session']} minutes per session."
        return {'role': 'assistant', 'content': reply, 'source': 'llm'}

    with isolated_schema() as (_, account_schemas), TestClient(app) as client:
        account = client.post('/api/auth/register', json={'name': 'Demo reviewer', **credentials})
        account.raise_for_status()
        account_id = account.json()['id']
        account_schemas.append(f'fitpilot_account_{account_id}')
        profile = client.get('/api/profile').raise_for_status().json()
        profile.update(goal='Train for a walking holiday', minutes_per_session=20)
        client.put('/api/profile', json=profile).raise_for_status()
        env = {'LLM_BASE_URL': 'http://simulated-model.invalid/v1', 'LLM_MODEL': 'simulated-chat'}
        with patch.dict(os.environ, env), patch('app.tacc._send_chat', side_effect=simulated_model):
            replies = [client.post('/api/assistant/chat', json={'message': question}).raise_for_status().json()
                       for question in questions]
        assert [(step['tool'], step['ok']) for step in replies[0]['tool_trace']] == [('get_profile', True)]
        assert replies[1]['tool_trace'] == []

        client.post('/api/auth/logout').raise_for_status()
        assert client.get('/api/assistant/messages').status_code == 401
        client.post('/api/auth/login', json=credentials).raise_for_status()
        messages = client.get('/api/assistant/messages').raise_for_status().json()
        expected = [(role, text) for question, reply in zip(questions, replies)
                    for role, text in [('user', question), ('assistant', reply['answer'])]]
        assert [(message['role'], message['text']) for message in messages] == expected
        with db.account_scope(account_id):
            rows = db.rows('SELECT agent_id, status, request_json FROM model_prompts ORDER BY id')
        assert [(row['agent_id'], row['status']) for row in rows] == [('orchestrator', 'answered')] * 3
        assert any(msg['role'] == 'tool' for msg in json.loads(rows[1]['request_json'])['messages'])

    print('SIMULATED MODEL: FitPilot API, tools, and Postgres are exercised.')
    for role, line in expected:
        print(f"{'User' if role == 'user' else 'FitPilot'}: {line}")
    print('PASS: get_profile succeeded; 4 chat messages restored after login; 3 model requests recorded.')


if __name__ == '__main__':
    main()
