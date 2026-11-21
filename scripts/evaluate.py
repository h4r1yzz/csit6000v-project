"""Live synthetic planning/baseline evaluation. Never substitutes simulated model answers."""
import argparse
import hashlib
import subprocess
from copy import deepcopy
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time
from unittest.mock import patch
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app import agents, db, tacc
from app.schemas import PlanContent, ProfileUpdate


def invoke(ctx, mode):
    if mode == 'multi_agent':
        with patch.object(agents, 'context', return_value=deepcopy(ctx)):
            result = agents.workflow_plan()
        return result['content'], result['validation']
    # Both baselines receive the same user context/catalogs and final plan schema.
    # single_agent is one generalist with one validator-guided revision (at most two calls).
    schema = PlanContent.model_json_schema()
    messages = [
        {'role':'system', 'content':'Generate a weekly fitness and meal plan using only the supplied catalogs. Respect all profile constraints. Return JSON matching this schema: ' + json.dumps(schema)},
        {'role':'user', 'content':json.dumps(ctx)},
    ]
    for attempt in range(2 if mode == 'single_agent' else 1):
        raw = tacc.ask(messages, max_tokens=4000, structured_schema=schema)
        try:
            content = PlanContent.model_validate(agents.parse_json(raw)).model_dump()
            validation = agents.validate_plan(content, ctx)
            if validation['valid'] or mode == 'single_call' or attempt == 1:
                return content, validation
            feedback = json.dumps(validation)
        except (ValueError, TypeError, KeyError) as exc:
            feedback = str(exc)
            if mode == 'single_call' or attempt == 1:
                raise
        messages += [{'role':'assistant', 'content':raw}, {'role':'user', 'content':'Revise the plan to fix validation errors: ' + feedback}]
    raise RuntimeError('No baseline output')


def run_case(ctx, mode, expected):
    calls = 0
    started = time.monotonic()
    transport = tacc._send_chat
    trace = []
    def measured(*args, **kwargs):
        nonlocal calls
        calls += 1
        entry = {'request': deepcopy(args[1]), 'response': None, 'error_type': None}
        trace.append(entry)
        try:
            reply = transport(*args, **kwargs)
            entry['response'] = deepcopy(reply)
            return reply
        except Exception as exc:
            entry['error_type'] = type(exc).__name__
            raise
    record = {'expected':expected, 'model_calls':0, 'tokens':None, 'content':None, 'validation':None, 'error_type':None, 'transport_trace':trace}
    try:
        with patch.object(tacc, '_send_chat', side_effect=measured):
            content, validation = invoke(ctx, mode)
        record.update(content=content, validation=validation)
        record['valid_plan'] = bool(validation['valid'])
    except Exception as exc:
        record.update(valid_plan=False, error_type=type(exc).__name__, error_message=str(exc)[:500])
    usage = [entry['response'].get('usage') if entry['response'] else None for entry in trace]
    token_fields = ('prompt_tokens', 'completion_tokens', 'total_tokens')
    if usage and all(isinstance(u, dict) and all(type(u.get(k)) is int and u[k] >= 0 for k in token_fields) for u in usage):
        record['tokens'] = {key: sum(u[key] for u in usage) for key in token_fields}
    record.update(model_calls=calls, elapsed_seconds=round(time.monotonic()-started, 4))
    # A network failure is never counted as successful rejection/clarification.
    record['meets_expected_outcome'] = bool(record['valid_plan']) if expected == 'valid_plan' else (
        record['validation'] is not None and not record['valid_plan'])
    record['requires_manual_review'] = expected == 'reject'
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=['planning','adaptation'], default='planning')
    parser.add_argument('--modes', nargs='+', choices=['multi_agent','single_call','single_agent'], default=['multi_agent','single_call','single_agent'])
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    if args.repeats < 1 or (args.limit is not None and args.limit < 1):
        parser.error('repeats and limit must be positive')
    if args.env_file:
        from dotenv import load_dotenv
        load_dotenv(args.env_file, override=True)
    cases_path = ROOT / 'evaluation' / f'{args.suite}_cases.json'
    cases = json.loads(cases_path.read_text())
    if args.limit:
        cases = cases[:args.limit]
    cfg = tacc.configuration()
    if not args.validate_only and not cfg['configured']:
        parser.error('A live model is required. Configure an endpoint or pass --env-file; no simulated results are generated.')
    output = args.output or ROOT / 'evaluation/results' / f'{args.suite}-{time.time_ns()}.json'
    if output.exists() and not args.validate_only:
        parser.error('Output already exists; use a new filename to preserve prior results')
    records = []
    result = {'created_utc':datetime.now(timezone.utc).isoformat(), 'suite':args.suite, 'model':cfg['model'],
              'provider':cfg['provider'], 'repeats':args.repeats, 'cases_file':cases_path.name,
              'cases_sha256':hashlib.sha256(cases_path.read_bytes()).hexdigest(),
              'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'working_tree_modified':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
              'status':'running',
              'limitations':['Synthetic profiles; not human recommendation-quality ratings.',
                  'Adaptation scores replan constraint satisfaction, not correct agent selection or unchanged-plan preservation.',
                  'Rejection/clarification responses need manual review; transport failures never count as success.',
                  'Token totals are null unless the provider reports usage for every attempted call.',
                  'No fixed generation seed; temperature 0.2; latency includes model calls and local validation.'], 'records':records}
    with tempfile.TemporaryDirectory() as folder, patch.object(db, 'DB_PATH', Path(folder)/'evaluation.db'), patch.dict(os.environ, {
        'DATABASE_URL':'', 'DATABASE_URL_UNPOOLED':'', 'VERCEL':'', 'FITPILOT_TIMEZONE':'UTC',
    }):
        db.initialize()
        base = agents.context()
        for case in cases:
            for field in (['profile'] if args.suite == 'planning' else ['before','after']):
                ProfileUpdate.model_validate({**base['profile'], **case[field]})
        if args.validate_only:
            print(f'PASS: {len(cases)} {args.suite} cases satisfy the profile schema; no model requests made.')
            return 0
        output.parent.mkdir(parents=True, exist_ok=True)
        for repeat in range(args.repeats):
            for case in cases:
                for mode in args.modes:
                    ctx = deepcopy(base)
                    ctx['profile'].update(case.get('profile', case.get('before', {})))
                    initial = None
                    if args.suite == 'adaptation':
                        initial = run_case(ctx, mode, 'valid_plan')
                        if initial['valid_plan']:
                            ctx['active_plan'] = initial['content']
                        ctx['profile'].update(case['after'])
                    if initial is not None and not initial['valid_plan']:
                        outcome = {'meets_expected_outcome':False, 'elapsed_seconds':0, 'model_calls':0,
                                   'error_type':'InitialPlanFailed', 'valid_plan':False, 'tokens':None}
                    else:
                        outcome = run_case(ctx, mode, case['expected'])
                    records.append({'case_id':case['id'], 'repeat':repeat+1, 'mode':mode, 'initial':initial, **outcome})
                    output.write_text(json.dumps(result, indent=2)+'\n')
                    print(f'{case["id"]} repeat={repeat+1} mode={mode} valid={outcome["valid_plan"]}', flush=True)
    result['status'] = 'completed'
    result['summary'] = {}
    for mode in args.modes:
        rows = [r for r in records if r['mode']==mode]
        result['summary'][mode] = {'runs':len(rows), 'expected_outcome_rate':sum(r['meets_expected_outcome'] for r in rows)/len(rows),
            'median_seconds':statistics.median(r['elapsed_seconds'] for r in rows),
            'mean_model_calls':statistics.mean(r['model_calls'] for r in rows)}
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(f'Results: {output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
