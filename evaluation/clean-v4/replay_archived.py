"""Replay the original trace responses against a clean FitPilot clone using Postgres."""
import argparse
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

FIELDS = ('expected', 'valid_plan', 'outcome', 'meets_expected_outcome', 'validation', 'content',
          'prior_valid_after_change', 'model_calls', 'tokens', 'workflow_stage_order', 'workflow_steps',
          'workflow_flow_complete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path, help='Root of the clean grading clone')
    args = parser.parse_args()
    root = args.source.resolve()
    sys.path.insert(0, str(root / 'scripts'))
    from evaluate import agents, db, task_run, tacc
    from pg_harness import isolated_schema

    def git(*command):
        return subprocess.check_output(['git', *command], cwd=root, text=True).strip()

    if git('status', '--porcelain'):
        parser.error('The source checkout must be clean.')
    report = {'source_commit': git('rev-parse', 'HEAD'), 'working_tree_modified': False,
              'mode': 'recorded model transport; no live inference or latency measurement', 'suites': {}}
    env = {'QWEN_BASE_URL': 'http://replay.invalid/v1', 'QWEN_MODEL': 'qwen3.8-27b',
           'LLM_BASE_URL': '', 'FITPILOT_TIMEZONE': 'UTC'}
    with isolated_schema(clear_llm=False), patch.dict(os.environ, env):
        db.initialize()
        base = agents.context()
        base['profile'].pop('updated_at', None)
        for suite in ('planning', 'adaptation'):
            entries = json.loads((root / 'evaluation/results' / f'{suite}.json').read_text())['records']
            cases = {c['id']: c for c in json.loads((root / 'evaluation' / f'{suite}_cases.json').read_text())}
            checked = Counter()
            differences = []
            for row in entries:
                responses = [entry['response'] for entry in row['transport_trace']]
                if any(reply is None for reply in responses):
                    raise ValueError('Recorded transport failures require additional replay handling.')
                with patch.object(tacc, '_send_chat', side_effect=deepcopy(responses)):
                    replay = task_run(base, suite, cases[row['case_id']], row['mode'], row['repeat'])
                mismatches = [key for key in FIELDS if key in row and row[key] != replay[key]]
                original_requests = [entry['request'] for entry in row['transport_trace']]
                new_requests = [entry['request'] for entry in replay['transport_trace']]
                if original_requests != new_requests:
                    mismatches.append('model_request')
                if mismatches:
                    differences.append({'case': row['case_id'], 'mode': row['mode'], 'repeat': row['repeat'],
                                        'fields': mismatches})
                checked[row['mode']] += 1
            report['suites'][suite] = {'records': len(entries), 'method_counts': dict(checked),
                                      'differences': differences}
    if git('status', '--porcelain'):
        raise RuntimeError('The source checkout changed during replay.')
    print(json.dumps(report, indent=2))
    return int(any(suite['differences'] for suite in report['suites'].values()))


if __name__ == '__main__':
    raise SystemExit(main())
