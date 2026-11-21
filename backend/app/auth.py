"""Browser sessions for FitPilot. Credentials and sessions live in the registry."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from . import db


router = APIRouter(prefix="/api/auth")
COOKIE = "fitpilot_session"
SESSION_LIFETIME = 7 * 24 * 60 * 60
PUBLIC_ROUTES = {"/api/health", "/api/auth/register", "/api/auth/login"}


def initialize_registry() -> None:
    schema = (db.ROOT / "database/auth.sql").read_text(encoding="utf-8")
    with db.account_scope(None), db.connect() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(60006000)")
        conn.raw.execute(schema)


class Login(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128, repr=False)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        email = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("Enter a valid email address")
        return email


class Registration(Login):
    name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128, repr=False)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter your name")
        return value.strip()


def _derive(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=32768, r=8, p=1,
                          dklen=32, maxmem=64 * 1024 * 1024)


def _password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    return f"scrypt-v1${salt.hex()}${_derive(password, salt).hex()}"


def _matches(password: str, record: str | None) -> bool:
    # Missing emails incur the same password-derivation cost as existing ones.
    encoded = record or ("scrypt-v1$" + "00" * 16 + "$" + "00" * 32)
    version, salt, expected = encoded.split("$")
    return (version == "scrypt-v1" and
            hmac.compare_digest(_derive(password, bytes.fromhex(salt)).hex(), expected)
            and record is not None)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _start_session(conn, account_id: int, request: Request, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    conn.execute("DELETE FROM account_sessions WHERE expires_at<=?", (now,))
    old_token = request.cookies.get(COOKIE)
    if old_token:
        conn.execute("DELETE FROM account_sessions WHERE token_hash=?", (_token_hash(old_token),))
    conn.execute("INSERT INTO account_sessions(token_hash,account_id,expires_at) VALUES(?,?,?)",
                 (_token_hash(token), account_id, now + SESSION_LIFETIME))
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", path="/api",
                        secure=request.url.scheme == "https" or bool(os.getenv("VERCEL")),
                        max_age=SESSION_LIFETIME)


def _identity(token: str) -> dict | None:
    return db.one("SELECT a.id,a.email,a.name FROM accounts a JOIN account_sessions s "
                  "ON s.account_id=a.id WHERE s.token_hash=? AND s.expires_at>?",
                  (_token_hash(token), int(time.time())))


async def session_middleware(request: Request, call_next):
    path = request.url.path.rstrip("/")
    if not path.startswith("/api/") or request.method == "OPTIONS":
        return await call_next(request)
    # Resolve the cookie in the registry before selecting a workspace. This
    # also isolates auth routes from any account context inherited by a caller.
    with db.account_scope(None):
        return await _dispatch(request, call_next, path)


async def _dispatch(request: Request, call_next, path: str):
    if request.method not in {"GET", "HEAD"}:
        # Reject cross-origin browser writes, including login and logout. CLI
        # clients generally omit Origin. Vite forwards browser Origin unchanged.
        origin = request.headers.get("origin")
        same_origin = str(request.base_url).rstrip("/")
        trusted = request.app.state.trusted_origins
        if ((origin and origin != same_origin and origin not in trusted)
                or (not origin and request.headers.get("sec-fetch-site") == "cross-site")):
            return JSONResponse({"detail": "Request origin is not allowed"}, status_code=403)
    if path in PUBLIC_ROUTES:
        response = await call_next(request)
    else:
        token = request.cookies.get(COOKIE)
        account = await run_in_threadpool(_identity, token) if token else None
        if account is None:
            return JSONResponse({"detail": "Sign in to continue"}, status_code=401,
                                headers={"Cache-Control": "no-store"})
        request.state.account = account
        if path in {"/api/auth/me", "/api/auth/logout"}:
            response = await call_next(request)
        else:
            with db.account_scope(account["id"]):
                response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/register", status_code=201)
def register(body: Registration, request: Request, response: Response) -> dict:
    account = {"id": secrets.randbelow(2**52 - 1) + 1, "name": body.name, "email": body.email}
    password_hash = _password_hash(body.password)
    with db.connect() as conn:
        cursor = conn.execute(
            "INSERT INTO accounts(id,name,email,password_hash) VALUES(?,?,?,?) "
            "ON CONFLICT(email) DO NOTHING",
            (account["id"], account["name"], account["email"], password_hash),
        )
        if cursor.rowcount != 1:
            raise HTTPException(409, "An account with this email already exists")
        db.initialize_account(account["id"], account["name"])
        _start_session(conn, account["id"], request, response)
    return account


@router.post("/login")
def login(body: Login, request: Request, response: Response) -> dict:
    account = db.one("SELECT id,name,email,password_hash FROM accounts WHERE email=?", (body.email,))
    if not _matches(body.password, account and account.pop("password_hash")):
        raise HTTPException(401, "Email or password is incorrect")
    with db.connect() as conn:
        _start_session(conn, account["id"], request, response)
    return account


@router.get("/me")
def current_account(request: Request) -> dict:
    return request.state.account


@router.post("/logout", status_code=204)
def logout(request: Request) -> Response:
    db.execute("DELETE FROM account_sessions WHERE token_hash=?",
               (_token_hash(request.cookies[COOKIE]),))
    response = Response(status_code=204)
    response.delete_cookie(COOKIE, path="/api", httponly=True, samesite="lax")
    return response
