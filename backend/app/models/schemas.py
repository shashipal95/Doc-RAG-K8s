"""
Pydantic Models
Request and response schemas for API validation
"""
from typing import Optional

from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════════════════
# Auth Schemas
# ═══════════════════════════════════════════════════════════════════

class SignupRequest(BaseModel):
    email: str
    password: str
    full_name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: dict


# ═══════════════════════════════════════════════════════════════════
# Document Schemas
# ═══════════════════════════════════════════════════════════════════

class UploadResponse(BaseModel):
    message: str
    filename: str
    chunks_added: int
    url: Optional[str] = None


class QueryRequest(BaseModel):
    question: str
    top_k: int = Field(default=10, ge=1, le=30)
    provider: str = Field(default="groq", pattern="^(groq|gemini|openai|ollama)$")
    embedding_provider: str = Field(default="gemini", pattern="^(gemini|openai)$")
    session_id: Optional[str] = None
    web_search: bool = Field(default=False, description="Enable Tavily web search")
    agent_mode: bool = Field(default=False, description="Enable Weather Agent mode")
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class SessionCreateRequest(BaseModel):
    title: str = Field(max_length=100)


class SessionResponse(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: str

class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_size: int
    file_type: str
    chunks_count: int
    storage_url: Optional[str] = None
    created_at: str
