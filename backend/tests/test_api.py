import json
import os
import re
from pathlib import Path
import sqlite3
import tempfile
import unittest
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

from fastapi.testclient import TestClient
from app import agents, db, tacc
from app.main import app


class FitPilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous_path = db.DB_PATH
        db.DB_PATH = Path(self.tmp.name) / 'fitness.db'
        self.env = patch.dict(os.environ, {'QWEN_BASE_URL': '', 'LLM_BASE_URL': ''})
        self.env.start()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        self.env.stop()
        db.DB_PATH = self.previous_path
        self.tmp.cleanup()

    def generate(self):
        response = self.client.post('/api/workflows/plan', json={})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def update_profile(self, **values):
        profile = self.client.get('/api/profile').json()
        profile.update(values)
        response = self.client.put('/api/profile', json=profile)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_coordinator_persists_five_stages_and_requires_approval(self):
        draft = self.generate()
        self.assertEqual([x['agent_id'] for x in draft['steps']], [a['id'] for a in agents.AGENTS])
        self.assertEqual(len(draft['steps']), 5)
        self.assertTrue(draft['validation']['valid'])
        self.assertTrue(draft['requires_approval'])
        self.assertIsNone(self.client.get('/api/overview').json()['active_plan'])
        self.assertTrue(all(x['source'] == 'local_fallback' for x in draft['steps']))
        self.assertEqual(len(self.client.get('/api/agent-runs').json()), 5)
        restored = self.client.get(f"/api/workflows/{draft['workflow_id']}").json()
        self.assertEqual(restored['result']['content'], draft['content'])
        response = self.client.post('/api/plans', json=draft)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get('/api/overview').json()['active_plan']['workflow_id'], draft['workflow_id'])

    def test_schedule_diet_allergies_equipment_and_time_enforced(self):
        self.update_profile(weekly_days=2, scheduled_days=['Tuesday', 'Saturday'], minutes_per_session=10,
                            equipment='bodyweight', dietary_preferences='vegan, gluten free', food_allergies='peanuts, soy', weekly_budget=100)
        draft = self.generate()
        self.assertTrue(draft['validation']['valid'])
        self.assertEqual([w['day'] for w in draft['content']['workouts']], ['Tuesday', 'Saturday'])
        self.assertTrue(all(w['duration_minutes'] <= 10 for w in draft['content']['workouts']))
        self.assertFalse(any(e['name'] == 'Bicep curl' for w in draft['content']['workouts'] for e in w['exercises']))
        self.assertFalse(any('peanut' in m['ingredients'].lower() or 'tofu' in m['ingredients'].lower() for m in draft['content']['meals']))
        self.assertEqual(sum(m['servings_per_week'] for m in draft['content']['meals']), 21)

    def test_impossible_budget_cannot_replace_active_plan(self):
        first = self.generate()
        approved = self.client.post('/api/plans', json=first).json()
        self.update_profile(weekly_budget=0)
        draft = self.generate()
        self.assertFalse(draft['validation']['valid'])
        response = self.client.post('/api/plans', json=draft)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get('/api/overview').json()['active_plan']['id'], approved['id'])

    def test_changed_constraints_and_tampered_draft_rejected(self):
        draft = self.generate()
        self.update_profile(minutes_per_session=10)
        self.assertEqual(self.client.post('/api/plans', json=draft).status_code, 422)
        draft = self.generate()
        draft['content']['summary'] = 'Tampered summary'
        self.assertEqual(self.client.post('/api/plans', json=draft).status_code, 422)

    def test_bad_model_output_falls_back_and_transport_failure_circuits_workflow(self):
        with patch('app.tacc.ask', return_value='{"workouts": "wrong"}'):
            draft = self.generate()
        self.assertTrue(draft['validation']['valid'])
        self.assertTrue(all(step['source'] == 'local_fallback' for step in draft['steps']))
        with patch('app.tacc.ask', side_effect=tacc.ModelUnavailable('offline')) as ask:
            draft = self.generate()
        self.assertEqual(ask.call_count, 1)
        self.assertTrue(draft['validation']['valid'])

    def test_valid_model_stages_are_used_and_source_is_truthful(self):
        ctx = agents.context()
        answers = [json.dumps(agents.fallback(a['id'], ctx)) for a in agents.AGENTS]
        answers[2] = json.dumps({'menu_id': 'menu_2', 'summary': 'A model-selected catalog menu.'})
        first = json.loads(answers[0])
        first['summary'] = 'A model-authored goal summary.'
        answers[0] = json.dumps(first)
        with patch.dict(os.environ, {'LLM_BASE_URL': 'http://localhost:12345/v1'}):
            with patch('app.tacc.ask', side_effect=answers) as ask:
                draft = self.generate()
        self.assertEqual(ask.call_count, 5)
        self.assertEqual(draft['source'], 'llm')
        self.assertEqual(draft['content']['summary'], 'A model-authored goal summary.')
        self.assertEqual(draft['steps'][2]['output']['summary'], 'A model-selected catalog menu.')
        self.assertEqual(draft['content']['meals'], agents.nutrition_options(ctx)['menu_2'])
        self.assertTrue(draft['validation']['valid'])

    def test_model_client_openai_compatible_request_contract(self):
        captured = {}
        class Handler(BaseHTTPRequestHandler):
            def do_POST(handler):
                captured['path'] = handler.path
                captured['authorization'] = handler.headers.get('Authorization')
                captured['body'] = json.loads(handler.rfile.read(int(handler.headers['Content-Length'])))
                handler.send_response(200)
                handler.send_header('Content-Type', 'application/json')
                handler.end_headers()
                handler.wfile.write(json.dumps({'choices':[{'message':{'content':'OK'}}]}).encode())
            def log_message(self, *args):
                pass
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(os.environ, {'LLM_BASE_URL':f'http://127.0.0.1:{server.server_port}/v1', 'LLM_MODEL':'test-model', 'LLM_API_KEY':'test-only-key'}):
                self.assertEqual(tacc.ask([{'role':'user','content':'hello'}]), 'OK')
            self.assertEqual(captured['path'], '/v1/chat/completions')
            self.assertEqual(captured['body']['model'], 'test-model')
            self.assertEqual(captured['authorization'], 'Bearer test-only-key')
            self.assertNotIn('chat_template_kwargs', captured['body'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_evaluator_detects_changed_active_constraints(self):
        self.client.post('/api/plans', json=self.generate())
        self.update_profile(weekly_budget=1)
        result = self.client.post('/api/agents/evaluation_adaptation/run', json={}).json()['output']
        self.assertTrue(result['replan_recommended'])
        self.assertTrue(any('no longer matches' in s for s in result['observations']))

    def test_pose_summary_feedback_and_progress(self):
        summary = {'exercise': 'Squat', 'duration_seconds': 34.5, 'reps': 8, 'analyzed_frames': 170,
                   'average_confidence': 0.5, 'range_of_motion': {'min': 78, 'max': 172}, 'form_cues': ['Keep your full body visible'], 'source': 'webcam'}
        response = self.client.post('/api/pose-sessions', json=summary)
        self.assertEqual(response.status_code, 200, response.text)
        pose = response.json()
        run = self.client.post('/api/agents/exercise_feedback/run', json={'pose_session_id': pose['id']}).json()
        self.assertEqual(run['output']['metrics']['reps'], 8)
        self.assertIn('Low visibility', run['output']['confidence_note'])
        self.assertEqual(len(self.client.get('/api/pose-sessions').json()), 1)
        self.assertEqual(self.client.get('/api/overview').json()['stats']['total_workouts'], 0)
        self.client.post('/api/workouts', json={'exercise':'Squat','duration_minutes':2,'perceived_effort':9,'notes':'8 reps'})
        evaluation = self.client.post('/api/agents/evaluation_adaptation/run', json={}).json()['output']
        self.assertTrue(evaluation['replan_recommended'])
        self.assertEqual(evaluation['average_effort'], 9)
        self.assertEqual(self.client.get('/api/overview').json()['stats']['total_minutes'], 2)

    def test_validation_errors_and_chat_routing(self):
        self.assertEqual(self.client.post('/api/pose-sessions', json={}).status_code, 422)
        self.assertEqual(self.client.post('/api/agents/missing/run', json={}).status_code, 404)
        self.assertEqual(self.client.post('/api/agents/exercise_feedback/run', json={'pose_session_id': 999}).status_code, 404)
        profile = self.client.get('/api/profile').json()
        profile['scheduled_days'] = ['Monday']
        self.assertEqual(self.client.put('/api/profile', json=profile).status_code, 422)
        response = self.client.post('/api/assistant/chat', json={'message':'Suggest nutrition for my week'}).json()
        self.assertEqual(response['agent_id'], 'nutrition')
        self.assertEqual(len(self.client.get('/api/assistant/messages').json()), 2)
        self.assertFalse(self.client.get('/api/health').json()['llm_configured'])

    def test_migration_is_additive_and_repeatable(self):
        self.client.post('/api/workouts', json={'exercise':'Walking','duration_minutes':20,'perceived_effort':3})
        db.initialize()
        db.initialize()
        self.assertEqual(len(self.client.get('/api/workouts').json()), 1)
        self.assertTrue(self.client.get('/api/profile').json()['scheduled_days'] == [])

    def test_landmark_samples_validate_and_reach_feedback_context(self):
        summary = {'exercise':'Squat','duration_seconds':10,'reps':2,'analyzed_frames':100,
                   'average_confidence':0.8,'range_of_motion':{'min':75,'max':170},'form_cues':[], 'source':'upload',
                   'landmark_samples':[{'time_seconds':1, 'landmarks':[{'x':0.5,'y':0.4,'z':-0.1,'visibility':0.9} for _ in range(33)]}]}
        response = self.client.post('/api/pose-sessions', json=summary)
        self.assertEqual(response.status_code, 200, response.text)
        pose = response.json()
        self.assertEqual(len(agents.context(pose['id'])['pose_session']['landmark_samples'][0]['landmarks']), 33)
        summary['landmark_samples'] *= 9
        self.assertEqual(self.client.post('/api/pose-sessions', json=summary).status_code, 422)
        summary['landmark_samples'] = [{'time_seconds':11, 'landmarks':summary['landmark_samples'][0]['landmarks']}]
        self.assertEqual(self.client.post('/api/pose-sessions', json=summary).status_code, 422)

    def test_oversized_workout_and_unsupported_diet_cannot_be_approved(self):
        draft = self.generate()
        draft['content']['workouts'][0]['duration_minutes'] = 10
        for ex in draft['content']['workouts'][0]['exercises']:
            ex.update(sets=6, reps='30', rest_seconds=180)
        self.assertEqual(self.client.post('/api/plans', json=draft).status_code, 422)
        self.update_profile(dietary_preferences='halal')
        draft = self.generate()
        self.assertFalse(draft['validation']['valid'])
        self.assertEqual(draft['content']['meals'], [])
        self.assertEqual(self.client.post('/api/plans', json=draft).status_code, 422)

    def test_allergen_phrases_and_equipment_negation(self):
        self.update_profile(dietary_preferences='no peanuts', food_allergies='soy allergy, nuts', equipment='bodyweight, no dumbbells')
        ctx = agents.context()
        meals = agents.compatible_recipes(ctx)
        self.assertFalse(any('peanut' in m['ingredients'].lower() or 'tofu' in m['ingredients'].lower() for m in meals))
        self.assertFalse(any(e['name'] == 'Bicep curl' for e in agents.available_exercises(ctx)))
        self.update_profile(equipment='dumbbells unavailable')
        self.assertFalse(any(e['name'] == 'Bicep curl' for e in agents.available_exercises(agents.context())))
        self.update_profile(food_allergies='', dietary_preferences='no peanuts')
        self.assertFalse(any('peanut' in m['ingredients'].lower() for m in agents.compatible_recipes(agents.context())))

    def test_next_draft_reduces_volume_after_high_effort(self):
        before = self.generate()
        self.client.post('/api/workouts', json={'exercise':'Strength training','duration_minutes':35,'perceived_effort':9})
        after = self.generate()
        self.assertTrue(after['validation']['valid'])
        self.assertTrue(all(w['duration_minutes'] < before['content']['workouts'][i]['duration_minutes'] for i,w in enumerate(after['content']['workouts'])))
        self.assertTrue(all(ex['sets'] == 1 for w in after['content']['workouts'] for ex in w['exercises']))
        self.assertTrue(after['steps'][-1]['output']['replan_recommended'])
        self.assertIn('reduces', after['steps'][1]['output']['summary'])

    def test_model_evaluation_cannot_suppress_required_adaptation(self):
        self.client.post('/api/workouts', json={'exercise':'Walking','duration_minutes':20,'perceived_effort':9})
        ctx = agents.context()
        response = agents.fallback('evaluation_adaptation', ctx)
        response.update(replan_recommended=False, average_effort=0, adherence_percent=0, observations=[])
        with patch('app.tacc.ask', return_value=json.dumps(response)):
            run = self.client.post('/api/agents/evaluation_adaptation/run', json={}).json()
        self.assertTrue(run['output']['replan_recommended'])
        self.assertEqual(run['output']['average_effort'], 9)
        self.assertTrue(run['output']['observations'])

    def test_pescatarian_catalog_excludes_chicken(self):
        self.update_profile(dietary_preferences='pescatarian')
        self.assertFalse(any('chicken' in m['ingredients'].lower() for m in agents.compatible_recipes(agents.context())))
        draft = self.generate()
        self.assertTrue(draft['validation']['valid'])
        self.assertFalse(any('chicken' in m['ingredients'].lower() for m in draft['content']['meals']))

    def test_invalid_model_configuration_and_timeout_are_bounded(self):
        with patch.dict(os.environ, {'LLM_BASE_URL':'http://bad host/v1'}):
            self.assertFalse(tacc.configuration()['configured'])
        with patch.dict(os.environ, {'LLM_BASE_URL':'http://localhost:1234/v1', 'LLM_TIMEOUT_SECONDS':'invalid'}):
            with patch('app.tacc.urlopen', side_effect=tacc.URLError('offline')) as request:
                with self.assertRaises(tacc.ModelUnavailable):
                    tacc.ask([{'role':'user','content':'hello'}])
                self.assertEqual(request.call_args.kwargs['timeout'], 45)
        with patch.dict(os.environ, {'LLM_BASE_URL':'http://localhost:1234/v1', 'LLM_TIMEOUT_SECONDS':'9999999'}):
            with patch('app.tacc.urlopen', side_effect=tacc.URLError('offline')) as request:
                with self.assertRaises(tacc.ModelUnavailable):
                    tacc.ask([{'role':'user','content':'hello'}])
                self.assertEqual(request.call_args.kwargs['timeout'], 120)

    def test_legacy_checkout_migration_preserves_user_data(self):
        path = Path(self.tmp.name) / 'legacy.db'
        fixture = Path(__file__).parent / 'fixtures' / 'legacy_schema.sql'
        old_content = json.dumps({'summary':'My existing plan', 'workouts':[{'day':'Monday','focus':'Legacy strength','duration_minutes':25,'exercises':[{'name':'Squat','sets':2,'reps':'8'}]}], 'meals':[{'name':'Lentil tomato soup','why':'Existing meal choice'}], 'adaptation_note':'My note', 'safety_note':'Keep comfortable'})
        with sqlite3.connect(path) as conn:
            conn.executescript(fixture.read_text())
            conn.execute("INSERT INTO profiles(id,name,goal,experience,weekly_days,minutes_per_session,equipment,dietary_preferences,weekly_budget) VALUES(1,'Legacy owner','Keep my saved goal','intermediate',3,25,'dumbbells','vegetarian',81)")
            conn.execute("INSERT INTO workout_logs(exercise,duration_minutes,perceived_effort,notes) VALUES('My saved workout',23,7,'Keep this journal entry')")
            conn.execute("INSERT INTO plans(title,content_json,source,is_active) VALUES('Legacy Qwen plan',?,'tacc_qwen',1)", (old_content,))
            conn.execute("INSERT INTO plans(title,content_json,source,is_active) VALUES('Legacy local plan',?,'local_fallback',0)", (old_content,))
            conn.execute("INSERT INTO recipes(name,calories,protein_g,cost,dietary_tags,ingredients) VALUES('My custom recipe',400,25,3,'vegetarian','Custom ingredients')")
        current_path = db.DB_PATH
        db.DB_PATH = path
        try:
            db.initialize()
            db.initialize()
            profile = self.client.get('/api/profile').json()
            self.assertEqual(profile['name'], 'Legacy owner')
            self.assertEqual(profile['goal'], 'Keep my saved goal')
            self.assertEqual(profile['weekly_budget'], 81)
            self.assertEqual(profile['scheduled_days'], [])
            self.assertEqual(profile['food_allergies'], '')
            self.assertEqual(profile['limitations'], '')
            self.assertEqual(profile['budget_currency'], 'USD')
            logs = self.client.get('/api/workouts').json()
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0]['notes'], 'Keep this journal entry')
            plans = db.rows('SELECT * FROM plans ORDER BY id')
            self.assertEqual(len(plans), 2)
            self.assertEqual([p['content_json'] for p in plans], [old_content, old_content])
            self.assertEqual([p['source'] for p in plans], ['tacc_qwen', 'local_fallback'])
            self.assertEqual([p['is_active'] for p in plans], [1, 0])
            self.assertTrue(all(p['workflow_id'] is None and p['execution_source'] is None for p in plans))
            active = self.client.get('/api/overview').json()['active_plan']
            self.assertEqual(active['title'], 'Legacy Qwen plan')
            self.assertEqual(active['content'], json.loads(old_content))
            self.assertIsNotNone(db.one("SELECT id FROM recipes WHERE name='My custom recipe'"))
            draft = self.generate()
            self.assertEqual(len(draft['steps']), 5)
            summary = {'exercise':'Squat','duration_seconds':10,'reps':2,'analyzed_frames':50,'average_confidence':0.8,'range_of_motion':{'min':80,'max':170},'form_cues':[], 'source':'upload'}
            self.assertEqual(self.client.post('/api/pose-sessions', json=summary).status_code, 200)
            self.assertEqual(self.client.get('/api/overview').json()['active_plan']['title'], 'Legacy Qwen plan')
        finally:
            db.DB_PATH = current_path

    @unittest.skipUnless((db.ROOT / 'frontend' / 'dist' / 'index.html').is_file(), 'Build frontend first to check SPA hosting')
    def test_built_frontend_and_api_routes_are_served_together(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])
        assets = re.findall(r'(?:src|href)="(/assets/[^"]+)"', response.text)
        self.assertTrue(assets, 'Built index must reference a bundled asset')
        for asset in assets:
            served = self.client.get(asset)
            self.assertEqual(served.status_code, 200, asset)
            self.assertGreater(len(served.content), 0)
        self.assertEqual(self.client.get('/api/nonexistent').status_code, 404)
        self.assertEqual(self.client.get('/docs').status_code, 200)
        self.assertEqual(self.client.get('/openapi.json').status_code, 200)

    def test_catalog_prices_not_client_supplied_values(self):
        draft = self.generate()
        draft['content']['meals'][0]['cost'] = 0.01
        draft['content']['estimated_weekly_cost'] = sum(m['cost'] * m['servings_per_week'] for m in draft['content']['meals'])
        self.assertEqual(self.client.post('/api/plans', json=draft).status_code, 422)


if __name__ == '__main__':
    unittest.main()
