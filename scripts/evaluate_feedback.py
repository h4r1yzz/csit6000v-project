"""Exercise the signed-in feedback API with synthetic measurements and a live model."""
import argparse
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'backend/tests')]
from fastapi.testclient import TestClient
from app import tacc
from app.main import app
from pg_harness import isolated_schema

FIELDS = ('reps', 'average_confidence', 'analyzed_frames', 'range_of_motion', 'duration_seconds')


def run():
    rows = []
    for name, visibility in [('missing-session', None), ('low-visibility', .43), ('clear-view', .91)]:
        with isolated_schema(clear_llm=False) as (_, accounts), TestClient(app) as client:
            signup = client.post('/api/auth/register', json={
                'name': 'Synthetic reviewer', 'password': 'synthetic-data-only', 'email': 'example@example.test'})
            signup.raise_for_status()
            accounts.append(f"fitpilot_account_{signup.json()['id']}")
            payload = {}
            summary = None
            if visibility is not None:
                summary = dict(exercise='Squat', reps=4, average_confidence=visibility, analyzed_frames=145,
                               range_of_motion={'min': 79, 'max': 171}, duration_seconds=15, source='upload', form_cues=[])
                session = client.post('/api/pose-sessions', json=summary)
                session.raise_for_status()
                payload['pose_session_id'] = session.json()['id']
            calls = []
            send = tacc._send_chat
            def measure(config, body, timeout):
                calls.append(None)
                response = send(config, body, timeout)
                calls[-1] = response.get('usage')
                return response
            with patch.object(tacc, '_send_chat', side_effect=measure):
                started = time.monotonic()
                response = client.post('/api/agents/exercise_feedback/run', json=payload)
                elapsed = time.monotonic() - started
            result = response.json()
            output = result.get('output', {})
            expected = {k: summary[k] for k in FIELDS} if summary else {}
            expected_note = {'missing-session':'No measurements', 'low-visibility':'Low visibility'}.get(name)
            passed = (response.is_success and output.get('metrics') == expected and
                      (expected_note is None or expected_note in output.get('confidence_note', '')))
            rows.append(dict(case=name, input=summary, passed=passed, http=response.status_code,
                             result=output or result.get('detail'), model_calls=len(calls),
                             usage_by_call=calls, elapsed_seconds=round(elapsed, 3)))
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    options = parser.parse_args()
    if not tacc.configuration()['configured']:
        parser.error('Export QWEN_BASE_URL or LLM_BASE_URL for the live service')
    if options.output.exists():
        parser.error('Choose an unused output path')
    rows = run()
    options.output.write_text(json.dumps({'model': tacc.configuration()['model'], 'cases': rows}, indent=2) + '\n')
    print(f"{sum(r['passed'] for r in rows)}/{len(rows)} feedback cases passed")
