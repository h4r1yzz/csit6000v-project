# Database and persistence

FitPilot uses Python's standard-library SQLite adapter. No separate database server is needed. `backend/app/db.py` manages connections, schema initialization, parameterized queries, and JSON serialization. The default file is `database/fitpilot.db`; set `FITPILOT_DB_PATH` to use a different local file.

Connections enable foreign keys, use write-ahead logging (WAL), and wait up to ten seconds for a locked database. WAL may create neighboring `fitpilot.db-wal` and `fitpilot.db-shm` files while the application is running.

## Stored records

| Table | Records and relationships |
| --- | --- |
| `profiles` | One local profile, enforced by `id = 1`. Includes preferences, schedule JSON, food allergies, limitations, currency, and update timestamp. |
| `exercises` | Curated exercise catalog with category, equipment, difficulty, estimated duration, and instructions. Exercise names are unique. |
| `recipes` | Curated recipe catalog with ingredients, dietary tags, calories, protein, and estimated cost. Recipe names are unique. |
| `plans` | Approved plan snapshots in `content_json`, active/inactive flag, generation provenance, and optional originating `workflow_id`. |
| `workout_logs` | Completed exercises with duration, perceived effort, notes, and completion timestamp. |
| `workflows` | Coordinator execution status, shared context JSON, result JSON, and timestamps. |
| `agent_runs` | Specialist ID, input/output JSON, status, source, fallback/error details, timestamps, and optional workflow foreign key. |
| `pose_sessions` | Exercise name and derived pose summary JSON, including at most eight numerical 33-landmark snapshots. Contains no video or image bytes. |
| `chat_messages` | User/assistant text with source, timestamp, and optional agent-run link. |

```mermaid
erDiagram
    WORKFLOWS ||--o{ AGENT_RUNS : contains
    WORKFLOWS ||--o{ PLANS : generates
    AGENT_RUNS ||--o{ CHAT_MESSAGES : supports
    PROFILES ||--o{ WORKFLOWS : supplies_context
    POSE_SESSIONS ||--o{ AGENT_RUNS : supplies_summary
    WORKOUT_LOGS ||--o{ WORKFLOWS : supplies_progress
```

Only the explicit workflow and agent-run links are database foreign keys. Profile, pose, and progress context relationships in the diagram describe application context passed into executions. The single-profile schema has no per-user ownership columns.

## Initialization and migrations

FastAPI initializes storage on startup. `database/schema.sql` uses `CREATE TABLE IF NOT EXISTS`. The adapter checks existing column names and adds missing profile/plan columns with `ALTER TABLE`. Existing profile, plan, and workout records are retained; there is no destructive reset or automatic database deletion.

The seed script uses idempotent catalog inserts. Adding newly curated catalog entries does not require deleting the existing database. Existing historical plan JSON remains an immutable record of what was approved; it is not regenerated from the newest recipe/exercise catalog.

The original `plans.source` check constraint accepts the historical TACC/local values. An additive `execution_source` column retains richer execution provenance without rebuilding or dropping the old table. Application responses expose the appropriate source for newer records while retaining compatibility with old rows.

Schema constraints validate the basic shape of stored values. Pydantic and deterministic application checks enforce schedule, workout, catalog, dietary, equipment, and budget rules at request/workflow boundaries. The approved-plan save operation validates before deactivating the prior plan and inserts the new plan within a transaction.

## Backup

Use SQLite's online backup mechanism for a consistent snapshot while WAL is enabled. From the project root:

```bash
backend/.venv/bin/python - <<'PY'
from pathlib import Path
import sqlite3

source = Path('database/fitpilot.db')
backup = Path('database/fitpilot.backup.db')
if not source.exists():
    raise SystemExit('Start FitPilot once to create the database.')
if backup.exists():
    raise SystemExit('Choose a new backup filename; this example preserves existing backups.')
with sqlite3.connect(source) as live, sqlite3.connect(backup) as snapshot:
    live.backup(snapshot)
print(backup.resolve())
PY
```

If you configured a custom database path, change `source` to that path. Do not copy only the main `.db` file from a running WAL database; recent changes may still be in the WAL file. For restoration, stop both services, retain a copy of the current database and its sidecars, then point `FITPILOT_DB_PATH` at the backup before restarting. Avoid replacing or deleting files while the API is using them.

## Inspecting data

The API provides profile, plan, activity, workflow, agent-run, pose-session, and chat-history read routes. For direct SQL inspection, open the database read-only:

```bash
backend/.venv/bin/python - <<'PY'
from pathlib import Path
import sqlite3

path = Path('database/fitpilot.db').resolve()
with sqlite3.connect(f'{path.as_uri()}?mode=ro', uri=True) as connection:
    for name, in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        print(name)
PY
```

## Limits and hosting

SQLite provides local persistence, not account isolation or cloud synchronization. API requests operate on the same local profile. Workflows store context snapshots, so historical agent inputs can include personal preferences and activity summaries. Backups should be protected accordingly.

The original proposal named Supabase. This implementation uses SQLite so it can run with no external credentials. Introducing Supabase/PostgreSQL requires a storage adapter or migration, authenticated user IDs on all owned records, ownership checks on every route, and a deliberate data migration. Changing a connection string alone does not enable that behavior.
