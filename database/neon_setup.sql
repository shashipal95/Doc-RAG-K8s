-- ============================================================
-- DocChat — Neon PostgreSQL Setup Script
-- Run this in: Neon Console → SQL Editor
-- ============================================================


-- ────────────────────────────────────────────────────────────
-- STEP 1: DROP EXISTING (clean slate)
-- ────────────────────────────────────────────────────────────
DROP TABLE IF EXISTS chat_messages CASCADE;
DROP TABLE IF EXISTS chat_sessions  CASCADE;
DROP TABLE IF EXISTS users          CASCADE;


-- ────────────────────────────────────────────────────────────
-- STEP 2: CREATE TABLES
-- ────────────────────────────────────────────────────────────

-- Users table (replaces Supabase GoTrue auth)
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
    created_at TIMESTAMPTZ DEFAULT NOW()
);


-- ────────────────────────────────────────────────────────────
-- STEP 3: INDEXES
-- ────────────────────────────────────────────────────────────
CREATE INDEX idx_users_email             ON users(email);
CREATE INDEX idx_chat_sessions_user_id   ON chat_sessions(user_id);
CREATE INDEX idx_chat_messages_session   ON chat_messages(session_id);
CREATE INDEX idx_chat_messages_created   ON chat_messages(created_at);


-- ────────────────────────────────────────────────────────────
-- STEP 4: VERIFY
-- ────────────────────────────────────────────────────────────
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
