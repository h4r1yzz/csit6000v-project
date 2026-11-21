from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
_ACCOUNT = ContextVar("fitpilot_account", default=None)


@contextmanager
def account_scope(account_id: int | None):
    """Route all database calls in this request to one verified account."""
    if account_id is not None and (type(account_id) is not int or account_id <= 0):
        raise ValueError("Invalid account ID")
    token = _ACCOUNT.set(account_id)
    try:
        yield
    finally:
        _ACCOUNT.reset(token)


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("Set DATABASE_URL to your Neon Postgres connection string.")
    if not url.startswith(("postgres://", "postgresql://")):
        raise ValueError("DATABASE_URL must be a Postgres connection string")
    return url


# Application queries use SQLite-style placeholders. Only SQL tokens outside quoted
# strings are converted; user values always remain bound parameters.
_SQL_TOKEN = re.compile(r"('(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|\?|\bCURRENT_TIMESTAMP\b)")
_UTC_NOW = "to_char(CURRENT_TIMESTAMP AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')"


def postgres_query(query: str) -> str:
    return _SQL_TOKEN.sub(lambda m: "%s" if m[0] == "?" else _UTC_NOW if m[0] == "CURRENT_TIMESTAMP" else m[0], query)


class PostgresConnection:
    def __init__(self, url: str, *, create_schema: bool = False):
        import psycopg
        from psycopg import sql
        from psycopg.rows import dict_row
        # Neon pooled connections use transaction pooling. Avoid session-local
        # prepared statements and close each connection at the end of the operation.
        self.raw = psycopg.connect(url, row_factory=dict_row, connect_timeout=15, prepare_threshold=None, client_encoding="utf8")
        account = _ACCOUNT.get()
        test_schema = os.getenv("FITPILOT_TEST_SCHEMA", "").strip()
        try:
            if account is not None:
                schema = sql.Identifier(f"fitpilot_account_{account}")
                if create_schema:
                    self.raw.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(schema))
                # Transaction-local, including when using Neon's transaction pool.
                self.raw.execute(sql.SQL("SET LOCAL search_path TO {}").format(schema))
            elif test_schema:
                schema = sql.Identifier(test_schema)
                self.raw.execute(sql.SQL("SET LOCAL search_path TO {}").format(schema))
        except Exception:
            self.raw.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self.raw.__exit__(exc_type, exc_value, traceback)

    def execute(self, query: str, args: tuple[Any, ...] = ()):
        return self.raw.execute(postgres_query(query), args or None)


def connect() -> PostgresConnection:
    return PostgresConnection(database_url())


def migration_connection() -> PostgresConnection:
    url = os.getenv("DATABASE_URL_UNPOOLED", "").strip() or database_url()
    return PostgresConnection(url, create_schema=True)


def initialize_postgres(seed: bool = True, profile_name: str = 'Alex Morgan') -> None:
    with migration_connection() as conn:
        # Serialize schema setup across simultaneous serverless cold starts.
        conn.execute("SELECT pg_advisory_xact_lock(?)", (_ACCOUNT.get() or 60006000,))
        conn.raw.execute((ROOT / "database" / "schema.postgres.sql").read_text())
        if seed:
            conn.execute("INSERT INTO profiles(id,name,goal,experience,weekly_days,minutes_per_session,equipment,dietary_preferences,weekly_budget) VALUES(1,?,'Build strength and feel more energetic','beginner',4,35,'bodyweight, dumbbells','high protein',70) ON CONFLICT DO NOTHING", (profile_name,))
            conn.raw.execute((ROOT / "database" / "seed.postgres.sql").read_text())


def initialize_account(account_id: int, name: str) -> None:
    with account_scope(account_id):
        initialize(profile_name=name)


def initialize(profile_name: str = 'Alex Morgan') -> None:
    initialize_postgres(profile_name=profile_name)


def rows(query: str, args: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connect() as db:
        return [dict(row) for row in db.execute(query, args).fetchall()]


def one(query: str, args: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute(query, args).fetchone()
        return dict(row) if row else None


def execute(query: str, args: tuple[Any, ...] = ()) -> int:
    with connect() as db:
        if query.lstrip().upper().startswith("INSERT"):
            return insert_id(db, query, args)
        db.execute(query, args)
        return 0


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def insert_id(conn, query: str, args: tuple[Any, ...] = ()) -> int:
    return conn.execute(query.rstrip().rstrip(";") + " RETURNING id", args).fetchone()["id"]
