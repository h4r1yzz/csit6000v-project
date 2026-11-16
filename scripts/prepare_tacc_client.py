#!/usr/bin/env python3
"""Stage a minimal FitPilot CPU client in a new directory outside the checkout."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.tacc.client.run import validate_service_url

TEMPLATES = ROOT / 'backend' / 'tacc' / 'client'
SOURCE_FILES = (
    'backend/app/__init__.py',
    'backend/app/agents.py',
    'backend/app/db.py',
    'backend/app/schemas.py',
    'backend/app/tacc.py',
    'database/schema.sql',
    'database/seed.sql',
)


def stage(service_url: str, output: Path) -> Path:
    url = validate_service_url(service_url)
    output = output.expanduser()
    destination = output.parent.resolve(strict=True) / output.name
    if destination.resolve().is_relative_to(ROOT):
        raise ValueError('Choose an output directory outside the checkout.')
    destination.mkdir(mode=0o700)
    for relative in SOURCE_FILES:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)

    for name in ('run.py', 'job.sh'):
        shutil.copyfile(TEMPLATES / name, destination / name)
    endpoint_file = destination / 'server-url.txt'
    endpoint_file.touch(mode=0o600, exist_ok=False)
    endpoint_file.write_text(url + '\n', encoding='utf-8')
    shutil.copyfile(TEMPLATES / 'tuxiv.conf', destination / 'tuxiv.conf')
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--service-url', help='Current SERVICE_BASE_URL from the course service log')
    source.add_argument('--service-url-file', type=Path, help='Read the current service base from a text file')
    parser.add_argument('--output', type=Path, required=True, help='New directory outside the checkout with an existing parent')
    args = parser.parse_args()
    try:
        value = args.service_url
        if args.service_url_file:
            value = args.service_url_file.expanduser().read_text(encoding='utf-8')
        destination = stage(value, args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f'FitPilot TACC client staged in {destination}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
