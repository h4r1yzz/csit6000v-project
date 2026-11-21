"""Render FitPilot's report tables directly from the live evaluation checkpoints."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
MODES = ('multi_agent', 'single_call', 'single_agent')
LABEL = {'multi_agent': 'Five specialists', 'single_call': 'One call', 'single_agent': 'Generalist + revision'}


def passed(rows):
    return sum(bool(row['meets_expected_outcome']) for row in rows)


def fraction(rows):
    return f"{passed(rows)}/{len(rows)}" if rows else '—'


def quantile(values, q):
    values = sorted(values)
    pos = (len(values) - 1) * q
    low = int(pos)
    return values[low] + (values[min(low+1,len(values)-1)] - values[low]) * (pos-low)


def distribution(values, decimals):
    if not values:
        return '—'
    fmt = lambda x: f'{x:,.{decimals}f}'
    return f'{fmt(median(values))} [{fmt(quantile(values,.25))}–{fmt(quantile(values,.75))}]'


def summarize(suites):
    text = []
    add = text.extend
    for suite, title in [('planning','Table 1. New weekly plans'), ('adaptation','Table 2. Replanning after a profile change')]:
        meta = suites[suite]
        adapt = suite == 'adaptation'
        add([f'### {title}', '',
             '| Method | Feasible all-check pass | Passes per repeat, feasible | Explicit menu rejection on infeasible trials |'
             + (' Successful repair when prior fails new rules |' if adapt else ''),
             '|---|---:|---|---:|' + ('---:|' if adapt else '')])
        for mode in MODES:
            rows = [r for r in meta['records'] if r['mode'] == mode]
            feasible = [r for r in rows if r['expected'] == 'valid_plan']
            blocked = [r for r in rows if r['expected'] == 'reject']
            repeats = [fraction([r for r in feasible if r['repeat']==rep]) for rep in range(1,meta['repeats']+1)]
            row = f'| {LABEL[mode]} | {fraction(feasible)} | {", ".join(repeats)} | {fraction(blocked)} |'
            if adapt:
                row += f" {fraction([r for r in feasible if not r['prior_valid_after_change']])} |"
            add([row])
        add([''])
    add(['### Table 3. Cost and elapsed time per attempted scenario', '',
         '| Suite | Method | Trials | Time in seconds, median [IQR] | Mean model calls | Total tokens per trial, median [IQR] | Complete usage |',
         '|---|---|---:|---:|---:|---:|---:|'])
    for suite, meta in suites.items():
        for mode in MODES:
            rows = [r for r in meta['records'] if r['mode'] == mode]
            if not rows:
                continue
            tokens = [r['tokens']['total_tokens'] for r in rows if r['tokens'] is not None]
            add([f"| {suite.title()} | {LABEL[mode]} | {len(rows)} | {distribution([r['elapsed_seconds'] for r in rows], 1)} | "
                 f"{mean(r['model_calls'] for r in rows):.2f} | {distribution(tokens,0)} | {len(tokens)}/{len(rows)} |"])
    add(['', '### Table 4. Outcomes across all scheduled trials', '',
         '| Suite | Method | Valid draft | Invalid draft | Explicit menu conflict | Execution/output error | Transport error |',
         '|---|---|---:|---:|---:|---:|---:|'])
    for suite, meta in suites.items():
        for mode in MODES:
            kinds = Counter(r['outcome'] for r in meta['records'] if r['mode'] == mode)
            add([f'| {suite.title()} | {LABEL[mode]} | ' + ' | '.join(str(kinds[k]) for k in
                ('valid_plan','invalid_plan','menu_infeasible','execution_error','transport_error')) + ' |'])
    add(['', '### Table 5. Specialist workflow flow checks', '',
         '| Suite | Feasible cases completing all five stages | Infeasible cases correctly stopped at nutrition | Other early stage failures |',
         '|---|---:|---:|---:|'])
    for suite, meta in suites.items():
        rows = [r for r in meta['records'] if r['mode'] == 'multi_agent']
        feasible = [r for r in rows if r['expected'] == 'valid_plan']
        infeasible = [r for r in rows if r['expected'] == 'reject']
        complete = [r for r in feasible if r.get('workflow_flow_complete')]
        correctly_stopped = [r for r in infeasible if r['meets_expected_outcome'] and
                             r.get('workflow_stage_order', [])[-1:] == ['nutrition'] and
                             r.get('workflow_steps', [])[-1].get('status') == 'failed']
        early_failures = sum(not r.get('workflow_flow_complete') and r not in correctly_stopped for r in rows)
        add([f'| {suite.title()} | {len(complete)}/{len(feasible)} | {len(correctly_stopped)}/{len(infeasible)} | {early_failures} |'])
    return '\n'.join(text) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--planning', type=Path, default=ROOT/'evaluation/results/planning.json')
    parser.add_argument('--adaptation', type=Path, default=ROOT/'evaluation/results/adaptation.json')
    parser.add_argument('--output', type=Path, help='Write Markdown tables; by default prints to stdout')
    args = parser.parse_args()
    suites = {}
    for suite in ('planning','adaptation'):
        path = getattr(args, suite)
        meta = json.loads(path.read_text())
        source = ROOT/'evaluation'/f'{suite}_cases.json'
        cases = json.loads(source.read_bytes())
        wanted = {(c['id'],m,r) for c in cases for m in MODES for r in range(1,meta['repeats']+1)}
        rows = meta['records']
        actual = {(r['case_id'],r['mode'],r['repeat']) for r in rows}
        if (meta['suite'] != suite or meta['status'] != 'completed'
                or meta['cases_sha256'] != hashlib.sha256(source.read_bytes()).hexdigest()
                or len(actual) != len(rows) or wanted != actual):
            parser.error(f'{path} is incomplete or does not match the case bank and all three comparison modes.')
        suites[suite] = meta
    values = summarize(suites)
    if args.output:
        args.output.write_text(values)
    else:
        print(values, end='')


if __name__ == '__main__':
    main()
