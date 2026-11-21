"""Extract a complete method's records from a completed multi-method run."""
import argparse
import json
from pathlib import Path

MODES = ('multi_agent', 'single_call', 'single_agent')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--mode', required=True, choices=MODES)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    data = json.loads(args.source.read_text())
    suite, case_ids, repeats = data.get('suite'), data.get('case_ids'), data.get('repeats')
    records = [row for row in data.get('records', []) if row['mode'] == args.mode]
    wanted = {(case_id, repeat) for case_id in case_ids for repeat in range(1, repeats + 1)}
    actual = {(row['case_id'], row['repeat']) for row in records}
    if (data.get('status') != 'completed' or args.mode not in data.get('modes', [])
            or len(actual) != len(records) or actual != wanted):
        parser.error('The selected method is incomplete or duplicated in the source result.')
    output = dict(data)
    output.update(modes=[args.mode], records=records,
                  summary={args.mode: data.get('summary', {}).get(args.mode, {})})
    if data.get('mode_runner_sha256'):
        output['runner_sha256'] = data['mode_runner_sha256'].get(args.mode)
    if data.get('mode_base_commits'):
        output['base_commit'] = data['mode_base_commits'].get(args.mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    print(f"Extracted {len(records)} {args.mode} trials to {args.output}")


if __name__ == '__main__':
    main()
