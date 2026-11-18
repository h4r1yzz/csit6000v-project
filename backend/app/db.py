from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv("FITPILOT_DB_PATH", ROOT / "database" / "fitpilot.db")).expanduser()
SCHEMA = ROOT / "database" / "schema.sql"
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


class ClosingConnection(sqlite3.Connection):
    """Commit/rollback then close; sqlite3's default context manager leaves it open."""
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if os.getenv("VERCEL") and not url:
        raise RuntimeError("Set DATABASE_URL to your Neon Postgres connection string in Vercel.")
    if url and not url.startswith(("postgres://", "postgresql://")):
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
        if account is not None:
            schema = sql.Identifier(f"fitpilot_account_{account}")
            try:
                if create_schema:
                    self.raw.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(schema))
                # Transaction-local, including when using Neon's transaction pool.
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


def connect() -> sqlite3.Connection | PostgresConnection:
    url = database_url()
    if url:
        return PostgresConnection(url)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    account = _ACCOUNT.get()
    path = DB_PATH if account is None else DB_PATH.with_name(f"{DB_PATH.name}.account-{account}.db")
    db = sqlite3.connect(path, timeout=10, factory=ClosingConnection)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    return db


def migration_connection() -> PostgresConnection:
    url = os.getenv("DATABASE_URL_UNPOOLED", "").strip() or database_url()
    if not url:
        raise ValueError("A Postgres connection is required for migration")
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
    if database_url():
        initialize_postgres(profile_name=profile_name)
        return
    with connect() as db:
        db.executescript(SCHEMA.read_text(encoding="utf-8"))
        # SQLite ALTER TABLE preserves existing user records. Each migration is idempotent.
        migrations = {
            "profiles": {"scheduled_days": "TEXT NOT NULL DEFAULT '[]'", "food_allergies": "TEXT NOT NULL DEFAULT ''", "limitations": "TEXT NOT NULL DEFAULT ''", "budget_currency": "TEXT NOT NULL DEFAULT 'USD'"},
            "plans": {"workflow_id": "INTEGER REFERENCES workflows(id)", "execution_source": "TEXT"},
        }
        for table, columns in migrations.items():
            existing = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
            for column, definition in columns.items():
                if column not in existing:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        db.execute(
            "INSERT OR IGNORE INTO profiles(id, name, goal, experience, weekly_days, minutes_per_session, equipment, dietary_preferences, weekly_budget) "
            "VALUES(1, ?, 'Build strength and feel more energetic', 'beginner', 4, 35, 'bodyweight, dumbbells', 'high protein', 70)", (profile_name,)
        )
        seed = ROOT / "database" / "seed.sql"
        db.executescript(seed.read_text(encoding="utf-8"))


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
    if isinstance(conn, PostgresConnection):
        return conn.execute(query.rstrip().rstrip(";") + " RETURNING id", args).fetchone()["id"]
    return conn.execute(query, args).lastrowid
