"""Disposable Postgres schemas for unit tests and smoke checks."""
from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from unittest.mock import patch

POSTGRES_URL = (os.getenv('TEST_DATABASE_URL') or os.getenv('DATABASE_URL') or '').strip()
POSTGRES_ADMIN_URL = (os.getenv('DATABASE_URL_UNPOOLED') or POSTGRES_URL).strip()


def require_postgres_url() -> str:
    if not POSTGRES_URL:
        raise RuntimeError('Set TEST_DATABASE_URL or DATABASE_URL to a disposable Neon/Postgres database.')
    return POSTGRES_URL


@contextmanager
def isolated_schema(*, clear_llm: bool = True):
    """Create a fresh schema and point the app at it via FITPILOT_TEST_SCHEMA (SET LOCAL)."""
    import psycopg
    from psycopg import sql

    app_url = require_postgres_url()
    admin_url = POSTGRES_ADMIN_URL or app_url
    schema = 'test_' + uuid.uuid4().hex
    admin = psycopg.connect(admin_url, autocommit=True)
    admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    env = {
        'DATABASE_URL': app_url,
        'DATABASE_URL_UNPOOLED': admin_url,
        'FITPILOT_TEST_SCHEMA': schema,
        'VERCEL': '',
    }
    # Avoid leftover PGOPTIONS from the shell breaking Neon pooler connections.
    env['PGOPTIONS'] = ''
    if clear_llm:
        # Clear endpoint URLs only. Do not blank LLM_MODEL/QWEN_MODEL — an empty
        # value disables configuration() even when a test later sets a base URL.
        env.update({'LLM_BASE_URL': '', 'QWEN_BASE_URL': ''})
    account_schemas: list[str] = []
    try:
        with patch.dict(os.environ, env, clear=False):
            # Remove blank model overrides inherited from the shell/.env if present.
            for key in ('LLM_MODEL', 'QWEN_MODEL'):
                if key in os.environ and not os.environ.get(key, '').strip():
                    os.environ.pop(key, None)
            yield schema, account_schemas
    finally:
        try:
            for name in account_schemas:
                admin.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(name)))
            admin.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)))
        finally:
            admin.close()
