import os
import io
import docx
import json
import asyncio
import requests
import re
from dotenv import load_dotenv
from groq import Groq
from openai import OpenAI

import httpx
import jwt
from jwt import PyJWTError

from fastapi import FastAPI, File, UploadFile, HTTPException, Request, Depends, Form
from fastapi.responses import StreamingResponse, JSONResponse   
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware


from pydantic import BaseModel
from PyPDF2 import PdfReader

from pinecone import Pinecone, ServerlessSpec
import google.genai as genai
from google.genai import types

from langsmith import traceable, wrappers
from langsmith.middleware import TracingMiddleware


# ─────────────────────────────────────────
# ENV
# ─────────────────────────────────────────
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Supabase → Dashboard → Settings → API
SUPABASE_URL = os.getenv("SUPABASE_URL")  # https://xxxx.supabase.co
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")  # anon/public key
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")  # JWT Secret — keep PRIVATE

if not PINECONE_API_KEY:
    raise ValueError("PINECONE_API_KEY is required")
if not SUPABASE_URL or not SUPABASE_JWT_SECRET or not SUPABASE_ANON_KEY:
    raise ValueError(
        "SUPABASE_URL, SUPABASE_ANON_KEY and SUPABASE_JWT_SECRET are all required"
    )


# ─────────────────────────────────────────
# Supabase REST helper
# ─────────────────────────────────────────
def supa_headers(token: str | None = None) -> dict:
    """Build headers for Supabase Auth REST API calls."""
    return {
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token or SUPABASE_ANON_KEY}",
    }


async def supabase_post(path: str, body: dict, token: str | None = None) -> dict:
    """POST to Supabase REST/Auth API."""
    url = f"{SUPABASE_URL}{path}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=supa_headers(token), json=body)
    if resp.status_code >= 400:
        try:
            detail = (
                resp.json().get("error_description")
                or resp.json().get("msg")
                or resp.text
            )
        except Exception:
            detail = resp.text
        raise HTTPException(status_code=resp.status_code, detail=detail)
    return resp.json()


# ─────────────────────────────────────────
# JWT verification (for protected routes)
# ─────────────────────────────────────────
security = HTTPBearer()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {token}",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return resp.json()


def get_user_id(user: dict) -> str:
    uid = user.get("id")
    if not uid:
        raise HTTPException(status_code=401, detail="Invalid user payload")
    return uid


# ─────────────────────────────────────────
# AI Clients
# ─────────────────────────────────────────
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
gemini_client = (
    wrappers.wrap_gemini(genai.Client(api_key=GEMINI_API_KEY))
    if GEMINI_API_KEY
    else None
)


# ─────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────
app = FastAPI(title="DocChat RAG API", version="4.0.0")
app.add_middleware(TracingMiddleware)

ALLOWED_ORIGINS = ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # use your list here
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# @app.middleware("http")
# async def cors_middleware(request: Request, call_next):
#     origin = request.headers.get("origin", "")
#     is_allowed = origin in ALLOWED_ORIGINS

#     if request.method == "OPTIONS":
#         res = JSONResponse(content={}, status_code=200)
#         if is_allowed:
#             res.headers["Access-Control-Allow-Origin"] = origin
#             res.headers["Access-Control-Allow-Credentials"] = "true"
#             res.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
#             res.headers["Access-Control-Allow-Headers"] = "*"
#         return res

#     response = await call_next(request)
#     if is_allowed:
#         response.headers["Access-Control-Allow-Origin"] = origin
#         response.headers["Access-Control-Allow-Credentials"] = "true"
#         response.headers["Access-Control-Allow-Headers"] = "*"
#     return response


# ─────────────────────────────────────────
# Pinecone
# ─────────────────────────────────────────
INDEX_NAME = "gemini-rag2"
pc = Pinecone(api_key=PINECONE_API_KEY)


def setup_index():
    existing = [idx["name"] for idx in pc.list_indexes()]
    if INDEX_NAME not in existing:
        pc.create_index(
            name=INDEX_NAME,
            dimension=3072,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    return pc.Index(INDEX_NAME)


index = setup_index()


# ─────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────
class SignupRequest(BaseModel):
    email: str
    password: str
    full_name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class QueryRequest(BaseModel):
    question: str
    top_k: int = 3
    provider: str = "groq"  # groq | gemini | openai | ollama
    embedding_provider: str = "gemini"
    session_id: str | None = None


class UploadResponse(BaseModel):
    message: str
    filename: str
    chunks_added: int


# ─────────────────────────────────────────
# Embeddings
# ─────────────────────────────────────────
@traceable(run_type="embedding")
def get_embedding(text: str, provider: str):
    clean = text.encode("ascii", "ignore").decode("utf-8")

    if provider == "gemini":
        if not gemini_client:
            raise ValueError("Gemini not configured")
        result = gemini_client.models.embed_content(
            model="gemini-embedding-001",
            contents=clean,
            config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
        )
        return result.embeddings[0].values

    elif provider == "openai":
        if not openai_client:
            raise ValueError("OpenAI not configured")
        response = openai_client.embeddings.create(
            model="text-embedding-3-large",
            input=clean,
        )
        return response.data[0].embedding

    raise ValueError(f"Invalid embedding provider: {provider}")


# ─────────────────────────────────────────
# Output sanitizer
# ─────────────────────────────────────────
def sanitize_output(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return text.replace("<think>", "").replace("</think>", "")


# ─────────────────────────────────────────
# Chunk extractor
# ─────────────────────────────────────────
def extract_text(chunk, provider: str):
    if provider == "gemini":
        return getattr(chunk, "text", None)
    elif provider in ("openai", "groq"):
        return chunk.choices[0].delta.content
    return None


# ─────────────────────────────────────────
# Streaming LLM generator
# ─────────────────────────────────────────
async def generate_stream(prompt: str, provider: str):
    if provider == "gemini":
        if not gemini_client:
            yield "Gemini not configured."
            return
        stream = gemini_client.models.generate_content_stream(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        for chunk in stream:
            text = extract_text(chunk, provider)
            if text:
                yield sanitize_output(text)
            await asyncio.sleep(0)

    elif provider == "groq":
        if not groq_client:
            yield "Groq not configured."
            return
        stream = groq_client.chat.completions.create(
            model="qwen/qwen3-32b",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Never include <think> tags. Return only the final answer.",
                },
                {"role": "user", "content": prompt},
            ],
            stream=True,
        )
        for chunk in stream:
            text = extract_text(chunk, provider)
            if text:
                yield sanitize_output(text)
            await asyncio.sleep(0)

    elif provider == "openai":
        if not openai_client:
            yield "OpenAI not configured."
            return
        stream = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        for chunk in stream:
            text = extract_text(chunk, provider)
            if text:
                yield sanitize_output(text)
            await asyncio.sleep(0)

    elif provider == "ollama":
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={"model": "tinyllama:latest", "prompt": prompt, "stream": True},
            stream=True,
        )
        for line in response.iter_lines():
            if line:
                data = json.loads(line.decode("utf-8"))
                if "response" in data:
                    yield sanitize_output(data["response"])
            await asyncio.sleep(0)

    else:
        yield "Invalid provider selected."


# ═════════════════════════════════════════════════════════════════
# AUTH ROUTES  — calls Supabase Auth API on behalf of the frontend
# ═════════════════════════════════════════════════════════════════


@app.post("/auth/signup")
async def signup(body: SignupRequest):
    """
    Creates a new user in Supabase Auth.
    Frontend calls POST /auth/signup instead of supabase.auth.signUp().
    """
    data = await supabase_post(
        "/auth/v1/signup",
        {
            "email": body.email,
            "password": body.password,
            "data": {"full_name": body.full_name},
        },
    )
    return {
        "message": "Account created. Please verify your email.",
        "user_id": data.get("id") or data.get("user", {}).get("id"),
        "email": body.email,
        "access_token": data.get("access_token"),
        "refresh_token": data.get("refresh_token"),
    }


@app.post("/sessions")
async def create_session(
    request: Request,
    payload: dict = Depends(verify_token),
):
    """Create a new chat session for the authenticated user."""
    user_id = get_user_id(payload)
    body = await request.json()
    title = body.get("title", "New Chat")

    # Insert into Supabase using REST API
    async with httpx.AsyncClient() as client:
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/chat_sessions",
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json={
                "user_id": user_id,
                "title": title,
            },
        )

        if resp.status_code >= 400:
            raise HTTPException(
                status_code=resp.status_code,
                detail=resp.json() if resp.text else "Failed to create session",
            )

        session_data = resp.json()
        return session_data[0] if isinstance(session_data, list) else session_data


@app.post("/auth/login")
async def login(body: LoginRequest):
    """
    Authenticates a user and returns JWT tokens.
    Frontend calls POST /auth/login instead of supabase.auth.signInWithPassword().
    """
    data = await supabase_post(
        "/auth/v1/token?grant_type=password",
        {"email": body.email, "password": body.password},
    )
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_in": data.get("expires_in", 3600),
        "user": {
            "id": data["user"]["id"],
            "email": data["user"]["email"],
            "name": (data["user"].get("user_metadata") or {}).get("full_name", ""),
        },
    }


@app.post("/auth/logout")
async def logout(
    payload: dict = Depends(verify_token),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Revokes the user's session in Supabase.
    Frontend calls POST /auth/logout instead of supabase.auth.signOut().
    """
    await supabase_post("/auth/v1/logout", {}, token=credentials.credentials)
    return {"message": "Logged out successfully"}


@app.post("/auth/refresh")
async def refresh_token(request: Request):
    """
    Exchanges a refresh_token for a new access_token.
    Call this when the access token expires (after expires_in seconds).
    """
    body = await request.json()
    refresh = body.get("refresh_token")
    if not refresh:
        raise HTTPException(status_code=400, detail="refresh_token is required")
    data = await supabase_post(
        "/auth/v1/token?grant_type=refresh_token",
        {"refresh_token": refresh},
    )
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_in": data.get("expires_in", 3600),
    }


@app.get("/auth/me")
async def get_me(payload: dict = Depends(verify_token)):
    """Returns current user info decoded from the JWT."""
    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "name": (payload.get("user_metadata") or {}).get("full_name", ""),
        "role": payload.get("role"),
    }


# ═════════════════════════════════════════════════════════════════
# PUBLIC ROUTES
# ═════════════════════════════════════════════════════════════════


@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "4.0.0"}


# ═════════════════════════════════════════════════════════════════
# PROTECTED ROUTES  — Bearer JWT required
# ═════════════════════════════════════════════════════════════════


@app.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    embedding_provider: str = Form("gemini"),
    payload: dict = Depends(verify_token),
):
    """Upload a document. Vectors are namespaced per user — full data isolation."""
    user_id = get_user_id(payload)
    content = await file.read()

    if file.filename.endswith(".txt"):
        text = content.decode("utf-8", errors="ignore")
    elif file.filename.endswith(".pdf"):
        pdf_reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in pdf_reader.pages)
    elif file.filename.endswith(".docx"):
        doc = docx.Document(io.BytesIO(content))
        text = "\n".join(para.text for para in doc.paragraphs)
    else:
        raise HTTPException(
            status_code=400, detail="Unsupported file type (.txt, .pdf, .docx only)"
        )

    chunks = [text[i : i + 1000] for i in range(0, len(text), 800)]
    vectors = [
        {
            "id": f"{user_id}_{file.filename}_{i}",
            "values": get_embedding(chunk, embedding_provider),
            "metadata": {"text": chunk, "filename": file.filename, "user_id": user_id},
        }
        for i, chunk in enumerate(chunks)
    ]
    index.upsert(vectors=vectors, namespace=user_id)

    return UploadResponse(
        message="Success", filename=file.filename, chunks_added=len(chunks)
    )


@app.post("/query")
async def query_documents(
    request: QueryRequest,
    payload: dict = Depends(verify_token),
):
    """Query only this user's documents. Streams response as SSE."""
    user_id = get_user_id(payload)

    @traceable(run_type="chain", name="RAG Query Pipeline")
    def build_prompt():
        query_embedding = get_embedding(request.question, request.embedding_provider)
        results = index.query(
            vector=query_embedding,
            top_k=request.top_k,
            include_metadata=True,
            namespace=user_id,
        )
        if not results["matches"]:
            return None, None
        context_text = "\n\n".join(m["metadata"]["text"] for m in results["matches"])
        prompt = f"""Use ONLY the context below to answer.

Context:
{context_text}

Question: {request.question}
"""
        return prompt, results["matches"]

    async def stream_generator():
        try:
            prompt, matches = build_prompt()
            if not matches:
                yield "data: No relevant context found in your documents.\n\n"
                yield "event: done\ndata: [DONE]\n\n"
                return
            async for chunk in generate_stream(prompt, request.provider):
                safe = chunk.replace("\n", "\\n")
                yield f"data: {safe}\n\n"
            yield "event: done\ndata: [DONE]\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.delete("/clear")
async def clear_user_documents(payload: dict = Depends(verify_token)):
    """Delete ALL documents for the calling user only."""
    user_id = get_user_id(payload)
    try:
        index.delete(delete_all=True, namespace=user_id)
        return {"message": "All your documents deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
