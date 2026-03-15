"""Database schema definitions.

SECURITY NOTE: All SQL queries MUST use parameterized statements.
Never use f-strings or string concatenation with user input in SQL queries.
Example:
    ✅ CORRECT: await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    ❌ WRONG:   await db.execute(f"SELECT * FROM users WHERE id = {user_id}")
"""

CREATE_USERS_TABLE: str = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    default_mode TEXT NOT NULL DEFAULT 'no_memory',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_SESSIONS_TABLE: str = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    memory_mode TEXT NOT NULL DEFAULT 'no_memory',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
"""

CREATE_MESSAGES_TABLE: str = """
CREATE TABLE IF NOT EXISTS messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_used TEXT,
    memory_mode_at_time TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
"""

CREATE_INDEXES: str = """
-- Index for user lookup by Telegram ID
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);

-- Index for session lookup by user ID
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);

-- Index for filtering active sessions
CREATE INDEX IF NOT EXISTS idx_sessions_last_activity ON sessions(last_activity);

-- Index for message lookup by session
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id);

-- Index for message ordering by timestamp
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);

-- Composite index for efficient session messages query (session_id + timestamp)
-- Optimizes: SELECT ... WHERE session_id = ? ORDER BY timestamp
CREATE INDEX IF NOT EXISTS idx_messages_session_timestamp ON messages(session_id, timestamp);
"""
