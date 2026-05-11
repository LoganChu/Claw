-- Event log: raw signals from all monitor agents
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,       -- ISO-8601 UTC
    agent       TEXT NOT NULL,       -- 'git' | 'focus' | 'calendar' | 'slack' | 'goal'
    event_type  TEXT NOT NULL,       -- agent-specific: 'commit', 'window_change', 'meeting_start', etc.
    payload     TEXT NOT NULL,       -- JSON blob (privacy-filtered before insert)
    session_id  TEXT NOT NULL        -- groups events within one work session (date string YYYY-MM-DD)
);

CREATE INDEX IF NOT EXISTS idx_events_session  ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_agent    ON events(agent);
CREATE INDEX IF NOT EXISTS idx_events_ts       ON events(timestamp);

-- Daily summaries produced by the analysis pipeline
CREATE TABLE IF NOT EXISTS daily_summaries (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id          TEXT UNIQUE NOT NULL,
    generated_at        TEXT NOT NULL,
    focus_minutes       INTEGER,
    distracted_minutes  INTEGER,
    meeting_minutes     INTEGER,
    commit_count        INTEGER,
    goal_completion_pct REAL,
    predicted_score     REAL,        -- pipeline's 1-10 productivity score
    self_rating         INTEGER,     -- user's 1-5 rating (nullable until provided)
    report_md           TEXT,        -- full rendered markdown report
    raw_insights        TEXT         -- JSON array of insight strings
);

-- Goal definitions (user sets these; agent tracks progress)
CREATE TABLE IF NOT EXISTS goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    title       TEXT NOT NULL,
    description TEXT,
    metric      TEXT NOT NULL,   -- 'commit_count' | 'focus_minutes' | 'custom'
    target      REAL NOT NULL,
    period      TEXT NOT NULL,   -- 'daily' | 'weekly'
    active      INTEGER NOT NULL DEFAULT 1
);

-- Goal progress log
CREATE TABLE IF NOT EXISTS goal_progress (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    goal_id     INTEGER NOT NULL REFERENCES goals(id),
    value       REAL NOT NULL,
    achieved    INTEGER NOT NULL DEFAULT 0
);
