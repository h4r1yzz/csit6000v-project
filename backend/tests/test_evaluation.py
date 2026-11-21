"""Regression checks for research metrics; all model responses are simulated."""
from copy import deepcopy
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import agents, db, tacc

spec = importlib.util.spec_from_file_location('fitpilot_evaluate', Path(__file__).resolve().parents[2] / 'scripts/evaluate.py')
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for context in [patch.object(db, 'DB_PATH', Path(self.temp.name)/'test.db'),
                        patch.dict(os.environ, {'DATABASE_URL':'', 'VERCEL':'', 'LLM_BASE_URL':'http://model.test/v1'})]:
            context.start()
            self.addCleanup(context.stop)
        db.initialize()
        self.ctx = agents.context()
        for agent in agents.AGENTS:
            self.ctx['shared_state'][agent['id']] = agents.fallback(agent['id'], self.ctx)
        self.good = {'content': json.dumps(agents.assemble_plan_content(self.ctx)), 'source':'llm',
                     'usage':{'prompt_tokens':10,'completion_tokens':20,'total_tokens':30}}

    def test_revision_counts_all_calls_and_tokens(self):
        bad = {**self.good, 'content':'{}'}
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
        body = {'choices':[{'message':{'content':'OK'}}], 'usage':self.good['usage']}
        with patch.object(tacc, 'urlopen', return_value=io.BytesIO(json.dumps(body).encode())):
            result = tacc.chat([{'role':'user','content':'test'}])
        self.assertEqual(result['usage'], self.good['usage'])
