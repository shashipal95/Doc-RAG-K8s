import json

from fastapi import APIRouter, Depends, HTTPException, Request
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from app.core.db import get_conn
from app.core.security import get_user_id, verify_token
from app.services.llm import generate_suggestions

router = APIRouter(tags=["Sessions"])

@router.post("/sessions")
async def create_session(
    request: Request,
    payload: dict = Depends(verify_token),
):
    user_id = get_user_id(payload)
    body = await request.json()
    title = body.get("title", "New Chat")

    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO chat_sessions (user_id, title)
            VALUES ($1, $2)
            RETURNING id, user_id, title, created_at
            """,
            user_id, title,
        )
        if not row:
            raise HTTPException(status_code=500, detail="Failed to create session")
        return {
            "id": str(row["id"]),
            "user_id": row["user_id"],
            "title": row["title"],
            "created_at": row["created_at"].isoformat(),
        }


@router.get("/sessions")
async def list_sessions(payload: dict = Depends(verify_token)):
    """List all chat sessions for the current user, newest first."""
    user_id = get_user_id(payload)
    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT s.id, s.user_id, s.title, s.created_at
            FROM chat_sessions s
            LEFT JOIN (
                SELECT session_id, MAX(created_at) as last_msg_at
                FROM chat_messages
                GROUP BY session_id
            ) m ON s.id = m.session_id
            WHERE s.user_id = $1
            ORDER BY COALESCE(m.last_msg_at, s.created_at) DESC
            """,
            user_id,
        )
    return [
        {
            "id": str(r["id"]),
            "user_id": r["user_id"],
            "title": r["title"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, payload: dict = Depends(verify_token)):
    """Delete a chat session and all its messages (CASCADE)."""
    user_id = get_user_id(payload)
    async with get_conn() as conn:
        await conn.execute(
            "DELETE FROM chat_sessions WHERE id = $1 AND user_id = $2",
            session_id, user_id,
        )
    return {"message": "Session deleted"}


@router.patch("/sessions/{session_id}")
async def rename_session(session_id: str, request: Request, payload: dict = Depends(verify_token)):
    """Rename a chat session title."""
    user_id = get_user_id(payload)
    body = await request.json()
    new_title = (body.get("title") or "").strip()
    if not new_title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    if len(new_title) > 120:
        new_title = new_title[:120]
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            UPDATE chat_sessions
            SET title = $1
            WHERE id = $2 AND user_id = $3
            RETURNING id, title
            """,
            new_title, session_id, user_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"id": str(row["id"]), "title": row["title"]}


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str, payload: dict = Depends(verify_token)):
    """Get all messages for a session, ordered by time."""
    user_id = get_user_id(payload)
    async with get_conn() as conn:
        # Verify ownership
        owner = await conn.fetchval(
            "SELECT user_id FROM chat_sessions WHERE id = $1", session_id,
        )
        if owner != user_id:
            raise HTTPException(status_code=403, detail="Not your session")

        rows = await conn.fetch(
            """
            SELECT id, session_id, role, content, metadata, feedback, created_at
            FROM chat_messages
            WHERE session_id = $1
            ORDER BY created_at ASC
            """,
            session_id,
        )
    return [
        {
            "id": str(r["id"]),
            "session_id": str(r["session_id"]),
            "role": r["role"],
            "content": r["content"],
            "metadata": json.loads(r["metadata"]) if isinstance(r["metadata"], str) else r["metadata"],
            "feedback": r["feedback"],
            "created_at": r["created_at"].isoformat(),
        }
        for r in rows
    ]


@router.patch("/sessions/{session_id}/messages/{message_id}/feedback")
async def update_message_feedback(
    session_id: str,
    message_id: str,
    request: Request,
    payload: dict = Depends(verify_token),
):
    """Update feedback for a specific message."""
    user_id = get_user_id(payload)
    body = await request.json()
    feedback = body.get("feedback")

    if feedback not in [None, "up", "down"]:
        raise HTTPException(status_code=400, detail="Invalid feedback value")

    async with get_conn() as conn:
        # Verify ownership of the session
        owner = await conn.fetchval(
            "SELECT user_id FROM chat_sessions WHERE id = $1", session_id,
        )
        if owner != user_id:
            raise HTTPException(status_code=403, detail="Not your session")

        # Update the message feedback
        row = await conn.fetchrow(
            """
            UPDATE chat_messages
            SET feedback = $1
            WHERE id = $2 AND session_id = $3
            RETURNING id, feedback
            """,
            feedback, message_id, session_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Message not found")
            
    return {"id": str(row["id"]), "feedback": row["feedback"]}


@router.post("/sessions/{session_id}/messages")
async def save_session_message(
    session_id: str,
    request: Request,
    payload: dict = Depends(verify_token),
):
    """Save a single message to a session."""
    user_id = get_user_id(payload)
    body = await request.json()
    role = body.get("role", "user")
    content = body.get("content", "")
    metadata = body.get("metadata", {})

    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO chat_messages (session_id, role, content, metadata)
            VALUES ($1, $2, $3, $4::jsonb)
            RETURNING id, created_at
            """,
            session_id, role, content, json.dumps(metadata),
        )
    return {"id": str(row["id"]), "created_at": row["created_at"].isoformat()}

@router.post("/sessions/{session_id}/suggestions")
@traceable(run_type="chain", name="Get Session Suggestions")
async def get_session_suggestions(
    session_id: str,
    request: Request,
    payload: dict = Depends(verify_token),
):
    """Generate follow-up suggestions based on recent session history."""
    user_id = get_user_id(payload)
    
    # Attach session_id to LangSmith trace for thread grouping
    run_tree = get_current_run_tree()
    if run_tree and session_id:
        run_tree.metadata["session_id"] = session_id
    body = await request.json()
    provider = body.get("provider", "groq")

    async with get_conn() as conn:
        # Verify ownership
        owner = await conn.fetchval(
            "SELECT user_id FROM chat_sessions WHERE id = $1", session_id,
        )
        if owner != user_id:
            raise HTTPException(status_code=403, detail="Not your session")

        # Fetch recent history
        rows = await conn.fetch(
            """
            SELECT role, content FROM (
                SELECT role, content, created_at 
                FROM chat_messages 
                WHERE session_id = $1 
                ORDER BY created_at DESC 
                LIMIT 6
            ) AS recent 
            ORDER BY created_at ASC
            """,
            session_id,
        )
        
    history = [{"role": r["role"], "content": r["content"]} for r in rows]
    suggestions = await generate_suggestions(history, provider)
    
    return {"suggestions": suggestions}
