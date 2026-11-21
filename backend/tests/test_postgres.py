"""Extra Postgres-specific checks on a disposable schema."""
import unittest

from fastapi.testclient import TestClient
from app import db
from app.main import app
from pg_harness import POSTGRES_URL, isolated_schema


@unittest.skipUnless(POSTGRES_URL, 'Set TEST_DATABASE_URL or DATABASE_URL for Postgres tests')
class PostgresTests(unittest.TestCase):
    def setUp(self):
        self._schema_cm = isolated_schema()
        self.schema, self.account_schemas = self._schema_cm.__enter__()
        self.client_context = TestClient(app)
        self.client = self.client_context.__enter__()
        created = self.client.post('/api/auth/register', json={
            'name': 'Alex Morgan', 'email': 'alex@example.test', 'password': 'example-password-123',
        })
        created.raise_for_status()
        self.account_id = int(created.json()['id'])
        self.account_schemas.append(f'fitpilot_account_{self.account_id}')
        self.account_context = db.account_scope(self.account_id)
        self.account_context.__enter__()

    def tearDown(self):
        self.account_context.__exit__(None, None, None)
        self.client_context.__exit__(None, None, None)
        self._schema_cm.__exit__(None, None, None)

    def test_transaction_rolls_back(self):
        before = db.one('SELECT COUNT(*) AS n FROM workout_logs')['n']
        with self.assertRaises(RuntimeError):
            with db.connect() as conn:
                db.insert_id(conn, 'INSERT INTO workout_logs(exercise,duration_minutes,perceived_effort) VALUES(?,?,?)', ('Curl? 50%', 2, 3))
                raise RuntimeError('Abort')
        self.assertEqual(db.one('SELECT COUNT(*) AS n FROM workout_logs')['n'], before)

    def test_bound_values_and_utc_timestamp(self):
        name = "Curl? It's 100%"
        row_id = db.execute('INSERT INTO workout_logs(exercise,duration_minutes,perceived_effort) VALUES(?,?,?)', (name, 2, 3))
        row = db.one('SELECT * FROM workout_logs WHERE id=?', (row_id,))
        self.assertEqual(row['exercise'], name)
        self.assertRegex(row['completed_at'], r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$')
