"""Copy a local SQLite database into an EMPTY Postgres database, atomically.

DATABASE_URL is read from the environment, never accepted as a command argument.
Run before the first deployed API startup (which seeds the database).
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app import db

TABLES = ('profiles', 'exercises', 'recipes', 'workflows', 'plans', 'workout_logs', 'agent_runs', 'pose_sessions', 'chat_messages')


def migrate(source: Path) -> dict[str, int]:
    if not db.database_url():
        raise ValueError('Set DATABASE_URL to the target Postgres database first.')
    if not source.is_file():
        raise ValueError('Source SQLite file does not exist.')
    # Read-only URI prevents any accidental changes to the source database.
    local = sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True)
    local.row_factory = sqlite3.Row
    try:
        local.execute('BEGIN')  # Consistent snapshot including committed WAL data.
        present = {r[0] for r in local.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        with db.migration_connection() as target:
            target.execute('SELECT pg_advisory_xact_lock(60006000)')
            target.raw.execute((db.ROOT / 'database/schema.postgres.sql').read_text())
            target.raw.execute((db.ROOT / 'database/auth.sql').read_text())
            target.execute('LOCK TABLE ' + ','.join(TABLES) + ' IN ACCESS EXCLUSIVE MODE')
            if any(target.execute(f'SELECT COUNT(*) AS n FROM {table}').fetchone()['n'] for table in TABLES):
                raise ValueError('Target is not empty. Use a fresh Neon database; no records were overwritten.')
            counts = {}
            for table in TABLES:
                records = local.execute(f'SELECT * FROM {table}').fetchall() if table in present else []
                for row in records:
                    columns = list(row.keys())
                    # Column names are restricted to the destination schema.
                    allowed = {r['column_name'] for r in target.execute('SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=?', (table,))}
                    if not set(columns) <= allowed:
                        raise ValueError(f'Unsupported source columns in {table}')
                    target.execute(f'INSERT INTO {table} ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})', tuple(row))
                counts[table] = len(records)
                if table != 'profiles':
                    target.execute(f"SELECT setval(pg_get_serial_sequence('{table}','id'), COALESCE(MAX(id),1), MAX(id) IS NOT NULL) FROM {table}")
            return counts
    finally:
        local.close()


if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv(db.ROOT / '.env.local')
    load_dotenv(db.ROOT / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sqlite', type=Path, default=db.ROOT / 'database/fitpilot.db')
    args = parser.parse_args()
    try:
        for table, count in migrate(args.sqlite).items():
            print(f'{table}: {count} records copied')
    except Exception:
        # Connection exceptions can contain host/user information. Keep secrets
        # out of CLI output; the transactional import leaves the target intact.
        raise SystemExit('Migration failed. Check connectivity, source schema, and that the target database is empty. No source data was changed.')
