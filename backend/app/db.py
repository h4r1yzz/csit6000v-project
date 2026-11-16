from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv("FITPILOT_DB_PATH", ROOT / "database" / "fitpilot.db")).expanduser()
SCHEMA = ROOT / "database" / "schema.sql"


class ClosingConnection(sqlite3.Connection):
    """Commit/rollback then close; sqlite3's default context manager leaves it open."""
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10, factory=ClosingConnection)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    return db


def initialize() -> None:
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
            "VALUES(1, 'Alex Morgan', 'Build strength and feel more energetic', 'beginner', 4, 35, 'bodyweight, dumbbells', 'high protein', 70)"
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
        cur = db.execute(query, args)
        return cur.lastrowid


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)
