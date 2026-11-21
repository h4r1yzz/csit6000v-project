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
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
import random
import time
from unittest.mock import patch
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'backend/tests'))
from app import agents, db, tacc
from app.schemas import PlanContent, ProfileUpdate


def invoke(ctx, mode, expected='valid_plan', transport_trace=None, workflow_steps=None):
    if mode == 'multi_agent':
        trace = transport_trace if transport_trace is not None else []
        stages = workflow_steps if workflow_steps is not None else []
        run_agent = agents.run_agent
        def record_stage(agent_id, *args, **kwargs):
            first_call = len(trace)
            try:
                row = run_agent(agent_id, *args, **kwargs)
                stages.append({key: deepcopy(row.get(key)) for key in ('agent_id', 'status', 'source', 'output', 'error')})
                stages[-1]['model_calls'] = len(trace) - first_call
                return row
            except Exception as exc:
                stages.append({'agent_id': agent_id, 'status': 'failed', 'source': tacc.configuration()['source'],
                               'error_type': type(exc).__name__, 'error': str(exc)[:500],
                               'model_calls': len(trace) - first_call})
                raise
        with patch.object(agents, 'context', return_value=deepcopy(ctx)), patch.object(agents, 'run_agent', side_effect=record_stage):
            result = agents.workflow_plan()
        return result['content'], result['validation']
    # Both baselines receive the same user context/catalogs and final plan schema.
    # single_agent is one generalist with one validator-guided revision (at most two calls).
    schema = PlanContent.model_json_schema()
    # Give the baselines the same rule book and resolved catalog facts.
    cfg = ctx['profile']
    inputs = {**ctx, 'selected_days': agents.selected_days(cfg),
              'eligible_exercises': [item['name'] for item in agents.available_exercises(ctx)],
              'compatible_meal_facts': [agents.catalog_meal(r, 1, cfg) for r in agents.compatible_recipes(ctx)]}
    rules = ('Use the exact selected weekdays and eligible exercise names. Budget five minutes of warm-up, '
             'four seconds per counted repetition, and rest between sets. Copy meal costs and facts from '
             'compatible_meal_facts. Select 21 servings per week and sum cost times servings in the profile currency. '
             'If no compatible menu exists, return meals=[] and start summary with NO_COMPATIBLE_MENU. '
             'If 21 servings exceed budget, return meals=[] and start summary with UNAFFORDABLE_MENU.')
    messages = [
        {'role':'system', 'content':'Generate a weekly fitness and meal plan using only the supplied catalogs. Respect all profile constraints. ' + rules + ' Return JSON matching this schema: ' + json.dumps(schema)},
        {'role':'user', 'content':json.dumps(inputs)},
    ]
    for attempt in range(2 if mode == 'single_agent' else 1):
        raw = tacc.ask(messages, max_tokens=4000, structured_schema=schema)
        try:
            content = PlanContent.model_validate(agents.parse_json(raw)).model_dump()
            validation = agents.validate_plan(content, ctx)
            # Preserve a clear abstention for a genuinely infeasible case. If
            # the case is feasible, its empty/abstaining draft fails validation
            # and the generalist receives its one validator-guided revision.
            if ((expected == 'reject' and rejection_signal(content)) or validation['valid']
                    or mode == 'single_call' or attempt == 1):
                return content, validation
            feedback = json.dumps(validation)
        except (ValueError, TypeError, KeyError) as exc:
            feedback = str(exc)
            if mode == 'single_call' or attempt == 1:
                raise
        messages += [{'role':'assistant', 'content':raw}, {'role':'user', 'content':'Revise the plan to fix validation errors: ' + feedback}]
    raise RuntimeError('No baseline output')


def rejection_signal(content):
    if not content or content['meals']:
        return None
    for signal in ('NO_COMPATIBLE_MENU', 'UNAFFORDABLE_MENU'):
        if content['summary'].strip().upper().startswith(signal):
            return signal
    return None


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
    workflow_steps = []
    record = {'expected':expected, 'model_calls':0, 'tokens':None, 'content':None, 'validation':None,
              'error_type':None, 'transport_trace':trace, 'workflow_steps':workflow_steps}
    try:
        with patch.object(tacc, '_send_chat', side_effect=measured):
            content, validation = invoke(ctx, mode, expected, trace, workflow_steps)
        record.update(content=content, validation=validation)
        record['valid_plan'] = bool(validation['valid'])
    except Exception as exc:
        record.update(valid_plan=False, error_type=type(exc).__name__, error_message=str(exc)[:500])
    usage = [entry['response'].get('usage') if entry['response'] else None for entry in trace]
    token_fields = ('prompt_tokens', 'completion_tokens', 'total_tokens')
    if usage and all(isinstance(u, dict) and all(type(u.get(k)) is int and u[k] >= 0 for k in token_fields) for u in usage):
        record['tokens'] = {key: sum(u[key] for u in usage) for key in token_fields}
    record.update(model_calls=calls, elapsed_seconds=round(time.monotonic()-started, 4))
    signal = rejection_signal(record['content'])
    if any(entry['error_type'] for entry in trace):
        kind = 'transport_error'
    elif (record.get('error_message') or '').endswith('No menu meets the recorded dietary and budget constraints'):
        kind = 'menu_infeasible'
    elif signal:
        kind = 'menu_infeasible'
    elif record['error_type']:
        kind = 'execution_error'
    elif record['valid_plan']:
        kind = 'valid_plan'
    else:
        kind = 'invalid_plan'
    record['outcome'] = kind
    record['rejection_signal'] = signal
    record['workflow_stage_order'] = [step['agent_id'] for step in workflow_steps]
    record['workflow_stages_completed'] = sum(step.get('status') == 'completed' for step in workflow_steps)
    record['workflow_flow_complete'] = (workflow_stages_complete(workflow_steps) if mode == 'multi_agent' else None)
    expected_signal = 'NO_COMPATIBLE_MENU' if not agents.compatible_recipes(ctx) else 'UNAFFORDABLE_MENU'
    record['meets_expected_outcome'] = (kind == 'valid_plan' if expected == 'valid_plan'
                                        else kind == 'menu_infeasible' and signal in (None, expected_signal))
    return record


def workflow_stages_complete(steps):
    required = ['goal_planning', 'exercise_planning', 'nutrition', 'exercise_feedback', 'evaluation_adaptation']
    return ([step.get('agent_id') for step in steps] == required
            and all(step.get('status') == 'completed' and step.get('source') == 'tacc_qwen' for step in steps))


def task_run(base, suite, case, mode, repeat):
    ctx = deepcopy(base)
    ctx['profile'].update(case.get('profile', case.get('before', {})))
    prior_valid_after = None
    if suite == 'adaptation':
        # An identical, validated fixture allows independent scoring of all methods.
        fixture = deepcopy(ctx)
        for agent_id in ('goal_planning', 'exercise_planning', 'nutrition'):
            fixture['shared_state'][agent_id] = agents.fallback(agent_id, fixture)
        prior = agents.assemble_plan_content(fixture)
        if not agents.validate_plan(prior, ctx)['valid']:
            raise ValueError(f"Invalid prior fixture for {case['id']}")
        ctx['active_plan'] = prior
        ctx['profile'].update(case['after'])
        prior_valid_after = agents.validate_plan(prior, ctx)['valid']
    outcome = run_case(ctx, mode, case['expected'])
    return {'case_id': case['id'], 'repeat': repeat, 'mode': mode,
            'prior_valid_after_change': prior_valid_after, **outcome}


def write_json(path, value):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, separators=(',', ':')) + '\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=['planning','adaptation'], default='planning')
    parser.add_argument('--modes', nargs='+', choices=['multi_agent','single_call','single_agent'], default=['multi_agent','single_call','single_agent'])
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--validate-only', action='store_true')
    parser.add_argument('--workers', type=int, default=1, help='Maximum concurrently evaluated scenarios')
    parser.add_argument('--case-ids', nargs='+', help='Evaluate only the specified IDs')
    parser.add_argument('--resume', action='store_true', help='Resume a matching checkpoint')
    args = parser.parse_args()
    if args.workers < 1:
        parser.error('workers must be positive')
    if args.repeats < 1 or (args.limit is not None and args.limit < 1):
        parser.error('repeats and limit must be positive')
    if args.env_file:
        from dotenv import load_dotenv
        load_dotenv(args.env_file, override=True)
    cases_path = ROOT / 'evaluation' / f'{args.suite}_cases.json'
    cases = json.loads(cases_path.read_text())
    if args.limit:
        cases = cases[:args.limit]
    if args.case_ids:
        selected = set(args.case_ids)
        if not selected <= {case['id'] for case in cases}:
            parser.error('Unknown case ID')
        cases = [case for case in cases if case['id'] in selected]
    cfg = tacc.configuration()
    if not args.validate_only and not cfg['configured']:
        parser.error('A live model is required. Configure an endpoint or pass --env-file; no simulated results are generated.')
    output = args.output or ROOT / 'evaluation/results' / f'{args.suite}-{time.time_ns()}.json'
    if output.exists() and not args.resume and not args.validate_only:
        parser.error('Output already exists; use a new filename to preserve prior results')
    records = []
    result = {'created_utc':datetime.now(timezone.utc).isoformat(), 'suite':args.suite, 'model':cfg['model'],
              'provider':cfg['provider'], 'repeats':args.repeats, 'cases_file':cases_path.name,
              'cases_sha256':hashlib.sha256(cases_path.read_bytes()).hexdigest(),
              'base_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'modes':args.modes, 'case_ids':[case['id'] for case in cases], 'workers':args.workers,
              'working_tree_modified':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
              'status':'running',
              'limitations':['Synthetic profiles; not human recommendation-quality ratings.',
                  'Adaptation scores replan constraint satisfaction, not correct agent selection or unchanged-plan preservation.',
                  'Rejection requires an explicit menu-infeasibility signal. Multi-agent reports a generic menu conflict; baselines must label the cause.',
                  'Token totals are null unless the provider reports usage for every attempted call.',
                  'No fixed generation seed; temperature 0.2; latency includes model calls and local validation.'], 'records':records}
    from pg_harness import isolated_schema
    with isolated_schema(clear_llm=False), patch.dict(os.environ, {'FITPILOT_TIMEZONE':'UTC'}):
        db.initialize()
        base = agents.context()
        # Avoid volatile timestamps in the synthetic inputs.
        base['profile'].pop('updated_at', None)
        for case in cases:
            for field in (['profile'] if args.suite == 'planning' else ['before','after']):
                ProfileUpdate.model_validate({**base['profile'], **case[field]})
        if args.validate_only:
            print(f'PASS: {len(cases)} {args.suite} cases satisfy the profile schema; no model requests made.')
            return 0
        output.parent.mkdir(parents=True, exist_ok=True)
        if args.resume and output.exists():
            old = json.loads(output.read_text())
            for key in ('suite','model','provider','cases_sha256','runner_sha256','repeats','modes','case_ids','workers'):
                if result[key] != old.get(key):
                    parser.error(f'Checkpoint differs in {key}')
            records.extend(old['records'])
            result['created_utc'] = old['created_utc']
        completed = {(r['case_id'],r['mode'],r['repeat']) for r in records}
        tasks = [(case,mode,repeat) for repeat in range(1,args.repeats+1)
                 for case in cases for mode in args.modes
                 if (case['id'],mode,repeat) not in completed]
        random.Random(6000).shuffle(tasks)
        with ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context('spawn')) as pool:
            futures = [pool.submit(task_run, base, args.suite, *task) for task in tasks]
            for future in as_completed(futures):
                row = future.result()
                records.append(row)
                write_json(output, result)
                print(f"{row['case_id']} repeat={row['repeat']} mode={row['mode']} outcome={row['outcome']}", flush=True)
    result['status'] = 'completed'
    result['summary'] = {}
    for mode in args.modes:
        rows = [r for r in records if r['mode']==mode]
        result['summary'][mode] = {'runs':len(rows), 'expected_outcome_rate':sum(r['meets_expected_outcome'] for r in rows)/len(rows),
            'median_seconds':statistics.median(r['elapsed_seconds'] for r in rows),
            'mean_model_calls':statistics.mean(r['model_calls'] for r in rows)}
    write_json(output, result)
    print(f'Results: {output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
