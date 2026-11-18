CREATE TABLE IF NOT EXISTS accounts (
    id BIGINT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS account_sessions (
    token_hash TEXT PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    expires_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_account_sessions_expiry ON account_sessions(expires_at);
