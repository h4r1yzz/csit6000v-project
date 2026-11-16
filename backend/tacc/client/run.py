"""Run the FitPilot workflow from the course CPU job with a disposable database."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import traceback
from urllib.parse import urlsplit

MODEL = 'qwen3.8-27b'
RESULT_DIR = 'CSIT6000V-project-results'


def validate_service_url(value: str) -> str:
    url = value.strip().rstrip('/')
    try:
        parts = urlsplit(url)
        valid = (
            parts.scheme in ('http', 'https')
            and parts.hostname
            and parts.hostname.lower() not in ('node', 'current_node', 'current_tacc_node', 'compute-node')
            and parts.path == '/v1'
            and '?' not in url
            and '#' not in url
            and parts.username is None
            and parts.password is None
            and parts.port != 0
            and not any(char.isspace() for char in url)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError('Use the current SERVICE_BASE_URL from the running service log, including /v1.')
    return url


def configure_model(service_url: str, database: Path) -> None:
    # Isolate course model configuration from credentials and paths inherited by the job.
    for key in ('LLM_BASE_URL', 'LLM_MODEL', 'LLM_API_KEY', 'LLM_TIMEOUT_SECONDS'):
        os.environ.pop(key, None)
    os.environ.update(
        QWEN_BASE_URL=service_url,
        QWEN_MODEL=MODEL,
        QWEN_TIMEOUT_SECONDS='120',
        FITPILOT_DB_PATH=str(database),
        # The course runtime has no IANA timezone database. The demo uses UTC.
        FITPILOT_TIMEZONE='UTC',
    )
    hostname = urlsplit(service_url).hostname
    bypass = [os.getenv('no_proxy', ''), os.getenv('NO_PROXY', ''), hostname, '127.0.0.1', 'localhost']
    if ':' in hostname:
        bypass.append(f'[{hostname}]')
    os.environ['no_proxy'] = os.environ['NO_PROXY'] = ','.join(value for value in bypass if value)


def check_runtime() -> None:
    if sys.version_info < (3, 9):
        raise RuntimeError('The course qwen-python runtime must use Python 3.9 or newer.')
    try:
        from pydantic import __version__ as version
    except ImportError as exc:
        raise RuntimeError('The course qwen-python runtime needs Pydantic 2.8 or newer in the 2.x series.') from exc
    version_match = re.match(r'^2\.(\d+)', version)
    if not version_match or int(version_match[1]) < 8:
        raise RuntimeError('The course qwen-python runtime needs Pydantic 2.8 or newer in the 2.x series.')


def save_result(userdir: Path, relative: Path, result: dict) -> None:
    destination = userdir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=destination.parent, encoding='utf-8', delete=False) as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
        temporary_path = Path(handle.name)
    try:
        temporary_path.replace(destination)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def main() -> int:
    job_id = os.environ.get('SLURM_JOB_ID', '')
    userdir_value = os.environ.get('TACC_USERDIR', '')
    if not job_id.isdecimal() or not userdir_value:
        print('Submit the staged directory with tcloud to set SLURM_JOB_ID and TACC_USERDIR.', file=sys.stderr)
        return 1

    userdir = Path(userdir_value)
    relative = Path(RESULT_DIR) / f'fitpilot-job-{job_id}.json'
    result = {'job_id': job_id, 'model': MODEL, 'status': 'failed', 'workflow': None}
    started = time.monotonic()
    try:
        url_file = Path(__file__).resolve().with_name('server-url.txt')
        service_url = validate_service_url(url_file.read_text(encoding='utf-8'))
        check_runtime()
        with tempfile.TemporaryDirectory(prefix='fitpilot-tacc-') as directory:
            configure_model(service_url, Path(directory) / 'fitpilot.db')
            # Import after setting the disposable DB path.
            from backend.app import agents, db

            db.initialize()
            try:
                workflow = agents.workflow_plan()
            except Exception:
                rows = db.rows('SELECT * FROM agent_runs ORDER BY id')
                result['partial_steps'] = [agents.run_row(row) for row in rows]
                raise

        result['workflow'] = workflow
        if any(step['source'] != 'tacc_qwen' for step in workflow['steps']):
            result['status'] = 'fallback'
        elif not workflow['validation']['valid']:
            result['status'] = 'invalid_draft'
        else:
            result['status'] = 'succeeded'
    except (ValueError, OSError, RuntimeError) as exc:
        result['error'] = str(exc)
        print(f'FitPilot client error: {exc}', file=sys.stderr)
    except Exception as exc:
        result['error'] = type(exc).__name__
        traceback.print_exc()

    result['elapsed_seconds'] = round(time.monotonic() - started, 3)
    steps = (result['workflow'] or {}).get('steps', result.get('partial_steps', []))
    for step in steps:
        print(f"STAGE={step['agent_id']} SOURCE={step['source']} STATUS={step['status']}")
        if step.get('error'):
            print(f"STAGE_ERROR={step['error']}")
    try:
        save_result(userdir, relative, result)
    except OSError as exc:
        print(f'Could not save the FitPilot job result: {exc}', file=sys.stderr)
        return 1
    print(f"FITPILOT_STATUS={result['status']}")
    print(f'RESULT_FILE={relative.as_posix()}')
    return 0 if result['status'] == 'succeeded' else 1


if __name__ == '__main__':
    raise SystemExit(main())
