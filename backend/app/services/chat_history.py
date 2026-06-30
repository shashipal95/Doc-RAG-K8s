"""
Chat History — Neon PostgreSQL backed persistence.
Replaces old Supabase httpx REST calls with direct asyncpg queries.
"""
from app.core.db import get_conn


async def save_message(
    session_id: str,
    role: str,
    content: str,
    metadata: dict = None,
):
    """Persist a single chat message to Neon DB."""
    import json
    meta_json = json.dumps(metadata or {})
    async with get_conn() as conn:
        result = await conn.execute(
            """
            INSERT INTO chat_messages (session_id, role, content, metadata)
            VALUES ($1, $2, $3, $4::jsonb)
            """,
            session_id, role, content, meta_json,
        )
        if not result or "INSERT 0" in result:
            print(f"⚠ Failed to save message for session {session_id}")