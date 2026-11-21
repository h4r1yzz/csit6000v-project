"""Exercise the staged batch payload without submitting jobs or using user data."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

from app import agents, db

STAGER = db.ROOT / 'scripts' / 'prepare_tacc_client.py'


class TaccBatchTests(unittest.TestCase):
    def stage(self, endpoint, destination, use_file=False):
        arguments = ['--service-url', endpoint]
        if use_file:
            url_file = destination.parent / 'current-service-url.txt'
            url_file.write_text(endpoint + '\n', encoding='utf-8')
            arguments = ['--service-url-file', str(url_file)]
        return subprocess.run(
            [sys.executable, str(STAGER), *arguments, '--output', str(destination)],
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_staging_only_copies_allowlisted_files_and_rejects_unsafe_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            staged = root / 'staged'
            success = self.stage('http://qwen-test-node:8000/v1', staged, use_file=True)
            self.assertEqual(success.returncode, 0, success.stderr)
            files = {path.relative_to(staged).as_posix() for path in staged.rglob('*') if path.is_file()}
            self.assertEqual(files, {
                'run.py', 'job.sh', 'tuxiv.conf', 'server-url.txt',
                'backend/app/__init__.py', 'backend/app/agents.py', 'backend/app/db.py',
                'backend/app/schemas.py', 'backend/app/tacc.py', 'database/schema.sql',
                'database/seed.sql',
            })
            self.assertEqual((staged / 'server-url.txt').read_text(), 'http://qwen-test-node:8000/v1\n')
            self.assertNotEqual(self.stage('http://different-node:8000/v1', staged).returncode, 0)
            self.assertEqual((staged / 'server-url.txt').read_text(), 'http://qwen-test-node:8000/v1\n')
            for endpoint in ('http://NODE:8000/v1', 'http://test-node:8000', 'http://a@b:8000/v1'):
                invalid = self.stage(endpoint, root / 'invalid')
                self.assertNotEqual(invalid.returncode, 0)
                self.assertFalse((root / 'invalid').exists())

    def test_batch_calls_tacc_and_preserves_model_provenance_and_fallback(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append((self.path, dict(self.headers), body))
                if reject_requests.is_set():
                    self.send_response(503)
                    self.end_headers()
                    return
                prompt = json.loads(body['messages'][1]['content'])
                index = len(requests) - 1
                agent_id = agents.AGENTS[index]['id']
                if agent_id == 'nutrition':
                    answer = {'menu_id': prompt['approved_menus'][1]['menu_id'], 'summary': 'Selected a compatible menu.'}
                elif agent_id == 'exercise_planning':
                    workouts = [
                        {'focus': 'Strength', 'duration_minutes': 20,
                         'exercises': [{'name': prompt['available_exercises'][0]['name'], 'sets': 2, 'reps': '8', 'rest_seconds': 30}]}
                        for _ in prompt['selected_days']
                    ]
                    answer = {'summary': 'Uses the available exercises.', 'workouts': workouts}
                else:
                    answer = agents.fallback(agent_id, prompt['context'])
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'choices': [{'message': {'content': json.dumps(answer)}}]}).encode())

            def log_message(self, *args):
                pass

        reject_requests = threading.Event()
        server = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                staged = root / 'staged'
                endpoint = f'http://127.0.0.1:{server.server_port}/v1'
                staging = self.stage(endpoint, staged)
                self.assertEqual(staging.returncode, 0, staging.stderr)
                userdir = root / 'userdir'
                env = {
                    **os.environ,
                    'TACC_USERDIR': str(userdir),
                    'LLM_BASE_URL': 'http://unused.local/v1',
                    'LLM_API_KEY': 'inherited-test-value',
                    'FITPILOT_DB_PATH': str(root / 'must-not-create.db'),
                    'HTTP_PROXY': 'http://127.0.0.1:1',
                    'http_proxy': 'http://127.0.0.1:1',
                    'NO_PROXY': '',
                    'no_proxy': '',
                }
                outcome = self.execute_batch(staged, env, '123')
                self.assertEqual(outcome.returncode, 0, outcome.stderr)
                report = self.read_report(userdir, '123')
                self.assertEqual(report['status'], 'succeeded')
                self.assertEqual(report['workflow']['source'], 'tacc_qwen')
                self.assertTrue(report['workflow']['requires_approval'])
                self.assertEqual(len(requests), 5)
                self.assertEqual(outcome.stdout.count('SOURCE=tacc_qwen'), 5)
                self.assertFalse((root / 'must-not-create.db').exists())
                for path, headers, body in requests:
                    self.assertEqual(path, '/v1/chat/completions')
                    self.assertNotIn('Authorization', headers)
                    self.assertEqual(body['model'], 'qwen3.8-27b')
                    self.assertEqual(body['chat_template_kwargs'], {'enable_thinking': False})

                self.assertIn('structured_outputs', requests[0][2])
                self.assertIn('structured_outputs', requests[2][2])
                exercise_request = requests[1][2]
                days = json.loads(exercise_request['messages'][1]['content'])['selected_days']
                workout_schema = exercise_request['structured_outputs']['json']['properties']['workouts']
                self.assertEqual(workout_schema['minItems'], len(days))
                self.assertEqual(workout_schema['maxItems'], len(days))
                self.assertEqual([workout['day'] for workout in report['workflow']['content']['workouts']], days)

                reject_requests.set()
                failed = self.execute_batch(staged, env, '124')
                self.assertEqual(failed.returncode, 1, failed.stderr)
                report = self.read_report(userdir, '124')
                self.assertEqual(report['status'], 'failed')
                self.assertIsNone(report['workflow'])
                self.assertTrue(report.get('error'))
                self.assertIn('RESULT_FILE=CSIT6000V-project-results/fitpilot-job-124.json', failed.stdout)
                self.assertEqual(len(requests), 6)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def execute_batch(self, staged, env, job_id):
        return subprocess.run(
            [sys.executable, 'run.py'],
            cwd=staged,
            env={**env, 'SLURM_JOB_ID': job_id},
            capture_output=True,
            text=True,
            timeout=20,
        )

    def read_report(self, userdir, job_id):
        path = userdir / 'CSIT6000V-project-results' / f'fitpilot-job-{job_id}.json'
        return json.loads(path.read_text(encoding='utf-8'))
