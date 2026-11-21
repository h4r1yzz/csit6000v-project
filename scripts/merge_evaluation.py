"""Combine complete, independently checkpointed method runs into a report suite."""
import argparse
import json
from pathlib import Path

MODES = ('multi_agent', 'single_call', 'single_agent')


def load_complete(path: Path, suite: str, mode: str, repeats: int, case_ids: list[str]) -> dict:
    data = json.loads(path.read_text())
    wanted = {(case_id, mode, repeat) for case_id in case_ids for repeat in range(1, repeats + 1)}
    actual = {(row['case_id'], row['mode'], row['repeat']) for row in data.get('records', [])}
    if (data.get('suite') != suite or data.get('status') != 'completed' or data.get('modes') != [mode]
            or data.get('case_ids') != case_ids or data.get('repeats') != repeats
            or len(actual) != len(data.get('records', [])) or actual != wanted):
        raise ValueError(f'{path} does not contain exactly one complete run for {suite}/{mode}.')
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--multi-agent', required=True, type=Path)
    parser.add_argument('--single-call', required=True, type=Path)
    parser.add_argument('--single-agent', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    paths = {'multi_agent': args.multi_agent, 'single_call': args.single_call, 'single_agent': args.single_agent}
    runs = {mode: json.loads(path.read_text()) for mode, path in paths.items()}
    first = runs[MODES[0]]
    case_ids, repeats = first.get('case_ids'), first.get('repeats')
    if not isinstance(case_ids, list) or not isinstance(repeats, int):
        parser.error('Input run metadata is missing the case list or repeat count.')
    try:
        runs = {mode: load_complete(paths[mode], 'planning', mode, repeats, case_ids) for mode in MODES}
    except (OSError, KeyError, ValueError) as exc:
        parser.error(str(exc))
    for mode in MODES:
        current = runs[mode]
        for key in ('model', 'provider', 'cases_sha256'):
            if current.get(key) != first.get(key):
                parser.error(f'Method runs disagree about {key}.')
    merged = dict(first)
    merged.update(
        modes=list(MODES),
        status='completed',
        records=[row for mode in MODES for row in runs[mode]['records']],
        mode_runner_sha256={mode: runs[mode].get('runner_sha256') for mode in MODES},
        mode_base_commits={mode: runs[mode].get('base_commit') for mode in MODES},
        working_tree_modified=any(runs[mode].get('working_tree_modified', False) for mode in MODES),
        merged_method_runs={mode: str(paths[mode]) for mode in MODES},
    )
    merged['summary'] = {mode: runs[mode].get('summary', {}).get(mode, {}) for mode in MODES}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(merged, indent=2) + '\n', encoding='utf-8')
    print(f"Merged {len(merged['records'])} trials into {args.output}")


if __name__ == '__main__':
    main()
