"""Integration tests: TEST_DATABASE_URL must point to a disposable Postgres DB.
Each test gets a fresh schema; existing schemas and data are never dropped.
"""
import os
import unittest
import uuid
from unittest.mock import patch

import test_api
from app import db


@unittest.skipUnless(os.getenv('TEST_DATABASE_URL'), 'Set TEST_DATABASE_URL to run Postgres integration tests')
class PostgresTests(test_api.FitPilotTests):
    def setUp(self):
        import psycopg
        from psycopg import sql
        self.schema = 'test_' + uuid.uuid4().hex
        self.admin = psycopg.connect(os.environ['TEST_DATABASE_URL'], autocommit=True)
        self.admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.config = patch.dict(os.environ, {'DATABASE_URL': os.environ['TEST_DATABASE_URL'], 'DATABASE_URL_UNPOOLED': os.environ['TEST_DATABASE_URL'], 'PGOPTIONS': f'-c search_path={self.schema}'})
        self.config.start()
        super().setUp()

    def tearDown(self):
        from psycopg import sql
        try:
            super().tearDown()
        finally:
            self.config.stop()
            self.admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(f'fitpilot_account_{self.account_id}')))
            self.admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
            self.admin.close()

    @unittest.skip('SQLite legacy-file migration is covered by FitPilotTests')
    def test_legacy_checkout_migration_preserves_user_data(self):
        pass

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
