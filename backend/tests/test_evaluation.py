"""Regression checks for research metrics; all model responses are simulated."""
from copy import deepcopy
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from app import agents, db, tacc
from pg_harness import POSTGRES_URL, isolated_schema

spec = importlib.util.spec_from_file_location('fitpilot_evaluate', Path(__file__).resolve().parents[2] / 'scripts/evaluate.py')
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)


@unittest.skipUnless(POSTGRES_URL, 'Set TEST_DATABASE_URL or DATABASE_URL for Postgres tests')
class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self._schema_cm = isolated_schema(clear_llm=False)
        self._schema_cm.__enter__()
        self.addCleanup(lambda: self._schema_cm.__exit__(None, None, None))
        patch.dict(os.environ, {'LLM_BASE_URL': 'http://model.test/v1', 'LLM_MODEL': 'test-model'}).start()
        self.addCleanup(patch.stopall)
        db.initialize()
        self.ctx = agents.context()
        for agent in agents.AGENTS:
            self.ctx['shared_state'][agent['id']] = agents.fallback(agent['id'], self.ctx)
        self.good = {'content': json.dumps(agents.assemble_plan_content(self.ctx)), 'source': 'llm',
                     'usage': {'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30}}

    def test_revision_counts_all_calls_and_tokens(self):
        bad = {**self.good, 'content': '{}'}
        with patch.object(tacc, '_send_chat', side_effect=[bad, self.good]):
            result = evaluate.run_case(self.ctx, 'single_agent', 'valid_plan')
        self.assertTrue(result['valid_plan'])
        self.assertEqual(result['model_calls'], 2)
        self.assertEqual(result['tokens']['total_tokens'], 60)
        self.assertEqual(len(result['transport_trace']), 2)

    def test_outage_is_not_successful_rejection_or_zero_tokens(self):
        with patch.object(tacc, '_send_chat', side_effect=tacc.ModelUnavailable('offline')):
            result = evaluate.run_case(self.ctx, 'single_call', 'reject')
        self.assertFalse(result['meets_expected_outcome'])
        self.assertIsNone(result['tokens'])
        self.assertEqual(result['model_calls'], 1)

    def test_missing_usage_stays_unknown(self):
        reply = deepcopy(self.good)
        reply.pop('usage')
        with patch.object(tacc, '_send_chat', return_value=reply):
            result = evaluate.run_case(self.ctx, 'single_call', 'valid_plan')
        self.assertTrue(result['valid_plan'])
        self.assertIsNone(result['tokens'])

    def test_transport_preserves_provider_usage(self):
        body = {'choices': [{'message': {'content': 'OK'}}], 'usage': self.good['usage']}
        with patch.object(tacc, 'urlopen', return_value=io.BytesIO(json.dumps(body).encode())):
            result = tacc.chat([{'role': 'user', 'content': 'test'}])
        self.assertEqual(result['usage'], self.good['usage'])

    def test_unrelated_invalid_plan_does_not_get_rejection_credit(self):
        ctx = deepcopy(self.ctx)
        ctx['profile']['weekly_budget'] = 0
        with patch.object(tacc, '_send_chat', return_value=self.good):
            result = evaluate.run_case(ctx, 'single_call', 'reject')
        self.assertEqual(result['outcome'], 'invalid_plan')
        self.assertFalse(result['meets_expected_outcome'])

    def test_menu_abstention_requires_matching_reason_for_baselines(self):
        ctx = deepcopy(self.ctx)
        ctx['profile']['weekly_budget'] = 0
        for signal, expected in [('UNAFFORDABLE_MENU', True), ('NO_COMPATIBLE_MENU', False)]:
            content = json.loads(self.good['content'])
            content.update(summary=f'{signal}: a change is needed', meals=[], estimated_weekly_cost=0)
            with patch.object(tacc, '_send_chat', return_value={**self.good,'content':json.dumps(content)}):
                result = evaluate.run_case(ctx, 'single_call', 'reject')
            self.assertEqual(result['meets_expected_outcome'], expected)

    def test_feasible_case_abstention_gets_generalist_revision(self):
        content = json.loads(self.good['content'])
        content.update(summary='NO_COMPATIBLE_MENU', meals=[], estimated_weekly_cost=0)
        abstention = {**self.good, 'content': json.dumps(content)}
        with patch.object(tacc, '_send_chat', side_effect=[abstention, self.good]) as send:
            result = evaluate.run_case(self.ctx, 'single_agent', 'valid_plan')
        self.assertTrue(result['valid_plan'])
        self.assertTrue(result['meets_expected_outcome'])
        self.assertEqual(result['model_calls'], 2)
        self.assertEqual(send.call_count, 2)

    def test_complete_specialist_flow_requires_all_five_stages_in_order(self):
        names = ['goal_planning', 'exercise_planning', 'nutrition', 'exercise_feedback', 'evaluation_adaptation']
        steps = [{'agent_id': name, 'status': 'completed', 'source': 'tacc_qwen'} for name in names]
        self.assertTrue(evaluate.workflow_stages_complete(steps))
        self.assertFalse(evaluate.workflow_stages_complete(steps[:-1]))
        self.assertFalse(evaluate.workflow_stages_complete(list(reversed(steps))))
        failed = deepcopy(steps)
        failed[2]['status'] = 'failed'
        self.assertFalse(evaluate.workflow_stages_complete(failed))
