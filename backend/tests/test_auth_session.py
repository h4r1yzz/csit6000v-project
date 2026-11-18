import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from app import db
from app.main import app


class SessionBoundaryTest(unittest.TestCase):
    def test_origin_check_expiry_and_credential_storage(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(db, "DB_PATH", Path(folder) / "fitpilot.db"), patch.dict(
            os.environ, {"DATABASE_URL": "", "VERCEL": ""}
        ), TestClient(app) as client:
            signup = {"email": "MEMBER@example.test", "name": "Member", "password": "a-local-passphrase"}
            cross_origin = {"Origin": "https://foreign.example"}
            rejected = client.post("/api/auth/register", json=signup, headers=cross_origin)
            self.assertEqual(rejected.status_code, 403)
            created = client.post("/api/auth/register", json=signup)
            self.assertEqual(created.status_code, 201)
            self.assertIn("HttpOnly", created.headers["set-cookie"])
            self.assertEqual(created.json()["email"], "member@example.test")
            duplicate = client.post("/api/auth/register", json={**signup, "email": "member@example.test"})
            self.assertEqual(duplicate.status_code, 409)
            self.assertEqual(client.post("/api/auth/logout", headers=cross_origin).status_code, 403)
            self.assertEqual(client.get("/api/auth/me").status_code, 200)

            stored = db.one("SELECT password_hash FROM accounts")
            self.assertNotIn(signup["password"], stored["password_hash"])
            self.assertNotEqual(db.one("SELECT token_hash FROM account_sessions")["token_hash"],
                                client.cookies.get("fitpilot_session"))
            db.execute("UPDATE account_sessions SET expires_at=0")
            self.assertEqual(client.get("/api/auth/me").status_code, 401)
