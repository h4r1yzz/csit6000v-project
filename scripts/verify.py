"""Run local artifact checks and save auditable logs without loading private model .env secrets."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'evaluation/results/verification.json')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    db_url = (os.environ.get('TEST_DATABASE_URL') or os.environ.get('DATABASE_URL') or '').strip()
    if not db_url:
        print('Set TEST_DATABASE_URL or DATABASE_URL (disposable Neon/Postgres) before verify.', file=sys.stderr)
        return 1
    env = dict(os.environ)
    for key in ('VERCEL', 'LLM_BASE_URL', 'QWEN_BASE_URL', 'LLM_API_KEY', 'QWEN_API_KEY'):
        env[key] = ''
    env['DATABASE_URL'] = db_url
    env['DATABASE_URL_UNPOOLED'] = os.environ.get('DATABASE_URL_UNPOOLED', '').strip() or db_url
    env['TEST_DATABASE_URL'] = db_url
    env['FITPILOT_TIMEZONE'] = 'UTC'
    npm = 'npm.cmd' if os.name == 'nt' else 'npm'
    commands = [
        ('frontend_build', [npm, 'run', 'build', '--prefix', 'frontend'], ROOT),
        ('backend_tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], ROOT / 'backend'),
        ('pose_tests', ['node', '--test', 'frontend/src/pose/analysis.test.mjs'], ROOT),
        ('api_smoke', [sys.executable, 'scripts/smoke.py'], ROOT),
    ]
    result = {
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'python': platform.python_version(),
        'platform': platform.platform(),
        'scope': 'Postgres + simulated-model / synthetic-landmark integration; no live model or real-video claims',
        'base_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'working_tree_modified': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
        'checks': [],
    }
    for name, command, cwd in commands:
        print(f'Running {name}', flush=True)
        try:
            completed = subprocess.run(command, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
            code, output = completed.returncode, completed.stdout
        except (OSError, subprocess.TimeoutExpired) as exc:
            code, output = 1, str(exc)
        log = args.output.parent / f'{name}.log'
        log.write_text(output, encoding='utf-8')
        result['checks'].append({'name': name, 'command': command, 'exit_code': code, 'log': log.name})
        print(f'{name}: {"PASS" if code == 0 else "FAIL"}')
    result['passed'] = all(c['exit_code'] == 0 for c in result['checks'])
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
