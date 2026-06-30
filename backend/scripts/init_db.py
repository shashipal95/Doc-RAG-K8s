# backend/scripts/init_db.py
"""
Initialize PostgreSQL database tables.
Run once: python scripts/init_db.py
"""
import asyncio
import os
import sys

import asyncpg
from dotenv import load_dotenv

# Ensure we can load env
load_dotenv()

SQL = """
-- Drop existing tables (clean slate)
DROP TABLE IF EXISTS document_view_tokens CASCADE;
DROP TABLE IF EXISTS password_reset_tokens CASCADE;
DROP TABLE IF EXISTS chat_messages CASCADE;
DROP TABLE IF EXISTS chat_sessions  CASCADE;
DROP TABLE IF EXISTS user_documents CASCADE;
DROP TABLE IF EXISTS users          CASCADE;

-- Users table
CREATE TABLE users (
    id            UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    email         TEXT        NOT NULL UNIQUE,
    password_hash TEXT        NOT NULL,
    full_name     TEXT        NOT NULL DEFAULT '',
    role          TEXT        NOT NULL DEFAULT 'user',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Chat sessions
CREATE TABLE chat_sessions (
    id         UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id    TEXT        NOT NULL,
    title      TEXT        NOT NULL DEFAULT 'New Chat',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chat messages
CREATE TABLE chat_messages (
    id         UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id UUID        NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role       TEXT        NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT        NOT NULL DEFAULT '',
    metadata   JSONB       NOT NULL DEFAULT '{}',
    feedback   TEXT        CHECK (feedback IN ('up', 'down')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- User documents tracking
CREATE TABLE user_documents (
    id            UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id       TEXT        NOT NULL,
    filename      TEXT        NOT NULL,
    file_size     BIGINT      NOT NULL,
    file_type     TEXT        NOT NULL,
    chunks_count  INT         NOT NULL DEFAULT 0,
    file_content  BYTEA,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, filename)
);

-- Password reset tokens
CREATE TABLE password_reset_tokens (
    email      TEXT        PRIMARY KEY,
    token      TEXT        NOT NULL,
    expires_at TIMESTAMP   NOT NULL
);

-- Document view tokens
CREATE TABLE document_view_tokens (
    token      TEXT        PRIMARY KEY,
    doc_id     UUID        NOT NULL REFERENCES user_documents(id) ON DELETE CASCADE,
    user_id    TEXT        NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_users_email             ON users(email);
CREATE INDEX idx_chat_sessions_user_id   ON chat_sessions(user_id);
CREATE INDEX idx_chat_messages_session   ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_created   ON chat_messages(created_at);
CREATE INDEX idx_user_documents_user_id  ON user_documents(user_id);
CREATE INDEX idx_document_view_doc_id    ON document_view_tokens(doc_id);
"""


async def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not set in .env")
        return

    print("Connecting to PostgreSQL DB...")
    try:
        conn = await asyncpg.connect(dsn=url)
        print("Connected!")
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        return

    print("Running schema setup...")
    try:
        await conn.execute(SQL)
        print("Schema created successfully!")
    except Exception as e:
        print(f"Failed to execute schema script: {e}")
        await conn.close()
        return

    # Verify tables exist
    rows = await conn.fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
    )
    print("\nTables in database:")
    for r in rows:
        print(f"  - {r['table_name']}")

    await conn.close()
    print("\nDone! Database is initialized and ready.")


if __name__ == "__main__":
    asyncio.run(main())
