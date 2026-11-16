-- Original checkout schema copied from HEAD before the agent implementation.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS profiles (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  name TEXT NOT NULL,
  goal TEXT NOT NULL,
  experience TEXT NOT NULL CHECK (experience IN ('beginner', 'intermediate', 'advanced')),
  weekly_days INTEGER NOT NULL CHECK (weekly_days BETWEEN 1 AND 7),
  minutes_per_session INTEGER NOT NULL CHECK (minutes_per_session BETWEEN 10 AND 180),
  equipment TEXT NOT NULL DEFAULT '',
  dietary_preferences TEXT NOT NULL DEFAULT '',
  weekly_budget REAL NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS exercises (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  category TEXT NOT NULL,
  equipment TEXT NOT NULL DEFAULT 'bodyweight',
  difficulty TEXT NOT NULL DEFAULT 'beginner',
  duration_minutes INTEGER NOT NULL DEFAULT 10,
  instructions TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS recipes (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  calories INTEGER NOT NULL DEFAULT 0,
  protein_g REAL NOT NULL DEFAULT 0,
  cost REAL NOT NULL DEFAULT 0,
  dietary_tags TEXT NOT NULL DEFAULT '',
  ingredients TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  content_json TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('tacc_qwen', 'local_fallback')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS workout_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  exercise TEXT NOT NULL,
  duration_minutes INTEGER NOT NULL,
  perceived_effort INTEGER NOT NULL CHECK (perceived_effort BETWEEN 1 AND 10),
  notes TEXT NOT NULL DEFAULT '',
  completed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
