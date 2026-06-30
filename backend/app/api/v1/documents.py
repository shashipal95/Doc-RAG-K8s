"""
Document Routes
Upload, query, delete, and image-vision operations
"""
import asyncio
import io
import json
import os
import secrets
import tempfile
import urllib.request as _urllib_req
from datetime import datetime
from typing import List, Optional

import docx
import google.genai as genai
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from google.genai import types as genai_types
from groq import Groq
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree
from app.services.sparse_encoder import BM25Encoder
from pypdf import PdfReader

from app.core.config import get_settings
from app.core.db import get_conn
from app.core.security import get_user_id, verify_token
from app.models.schemas import DocumentResponse, QueryRequest, UploadResponse
from app.services.agent import run_weather_agent_stream
from app.services.embeddings import get_embedding
from app.services.llm import generate_stream, generate_vision_stream
from app.services.mlflow_tracker import log_chat_query, _estimate_tokens, mlflow_span
from app.services.vector_store import delete_all_user_vectors, query_vectors, upsert_vectors

# Initialize BM25 Encoder globally
# Note: In a production system, you might want to load a custom fitted model, 
# but the default one uses MS MARCO and works well for general English.
bm25_encoder = BM25Encoder.default()

# Persistent view tokens are now stored in the 'document_view_tokens' table in Neon DB.

router = APIRouter(tags=["Documents"])
settings = get_settings()

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
AUDIO_VIDEO_EXTENSIONS = (".mp3", ".wav", ".m4a", ".webm", ".mp4", ".ogg", ".flac", ".mpeg", ".mpga")
AUDIO_MIME_MAP = {
    ".mp3":  "audio/mpeg",
    ".wav":  "audio/wav",
    ".m4a":  "audio/mp4",
    ".webm": "audio/webm",
    ".mp4":  "video/mp4",
    ".ogg":  "audio/ogg",
    ".flac": "audio/flac",
    ".mpeg": "audio/mpeg",
    ".mpga": "audio/mpeg",
}

def _get_upload_dir() -> str:
    """Helper to return the absolute path to the root 'uploads' directory."""
    _v1_dir = os.path.dirname(os.path.abspath(__file__))
    _api_dir = os.path.dirname(_v1_dir)
    _app_dir = os.path.dirname(_api_dir)
    _root_dir = os.path.dirname(_app_dir)
    return os.path.join(_root_dir, "uploads")


def _is_image_request(question: str) -> bool:
    """Return True when the question is asking for images in any way."""
    # Single words that strongly imply image search
    IMAGE_SINGLE_WORDS = {
        "images", "photos", "pictures", "visuals",
        "wallpaper", "wallpapers", "photography",
    }
    # Multi-word phrases
    IMAGE_PHRASES = {
        "show me", "find me", "recommend", "suggest", "get me",
        "search for", "look for", "display", "show some",
        "give me some", "i want to see", "can i see",
    }
    q = question.lower()

    # If question contains an image word AND an action phrase → image request
    has_image_word = any(w in q.split() for w in IMAGE_SINGLE_WORDS)
    has_action = any(p in q for p in IMAGE_PHRASES)

    # Also match classic explicit combos
    EXPLICIT = {
        "show me images", "show me photos", "show me pictures",
        "find images", "find photos", "search images", "search photos",
        "images of", "photos of", "pictures of",
        "show images", "show photos", "find pictures",
        "recommend images", "recommend photos", "suggest images",
        "nature images", "nature photos", "nature pictures",
    }
    explicit_match = any(kw in q for kw in EXPLICIT)

    return explicit_match or (has_image_word and has_action)


def _is_transcript_request(question: str) -> bool:
    """Detect when user is asking for transcript of their uploaded file."""
    q = question.lower()
    TRANSCRIPT_KEYWORDS = [
        "transcript", "transcription", "transcribe",
        "what does it say", "what was said", "what did it say",
        "text of", "content of", "lyrics", "words in",
        "what is in the audio", "what is in the video",
        "read the audio", "read the file",
    ]
    return any(kw in q for kw in TRANSCRIPT_KEYWORDS)


def _is_weather_request(question: str) -> bool:
    """Detect when user is asking about weather, temperature, or gear like umbrellas."""
    q = question.lower()
    WEATHER_KEYWORDS = [
        "weather", "temperature", "temp", "humidity", "rain", 
        "umbrella", "snow", "wind", "forecast", "sunny", 
        "cloudy", "storm", "hot", "cold", "outside", "degree"
    ]
    return any(kw in q for kw in WEATHER_KEYWORDS)


def _extract_image_search_query(question: str) -> str:
    stop_phrases = [
        "show me", "find", "get", "search for", "search", "display", "give me",
        "images of", "photos of", "pictures of", "image of", "photo of", "picture of",
        "some", "a few", "related", "similar", "show",
    ]
    q = question.lower()
    for phrase in sorted(stop_phrases, key=len, reverse=True):
        q = q.replace(phrase, "")
    return q.strip(" ?.,!")


def _search_images_pexels(query: str, count: int = 4) -> List[dict]:
    """
    Search for images using the Pexels API.
    Requires PEXELS_API_KEY in .env — free tier: 200 req/hour, 20000 req/month.
    Get your free key at: https://www.pexels.com/api/
    """
    api_key = settings.PEXELS_API_KEY
    if not api_key:
        print("[pexels] ⚠️  PEXELS_API_KEY not set in .env — skipping image search")
        return []
    print(f"[pexels] searching for: {query}")
    try:
        import urllib.parse
        import urllib.request
        params = urllib.parse.urlencode({"query": query, "per_page": count, "orientation": "landscape"})
        req = urllib.request.Request(
            f"https://api.pexels.com/v1/search?{params}",
            headers={"Authorization": api_key},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        return [
            {
                "url":    photo.get("src", {}).get("large", ""),
                "thumb":  photo.get("src", {}).get("medium", ""),
                "title":  photo.get("alt", f"Photo by {photo.get('photographer', 'Unknown')}"),
                "source": photo.get("url", ""),
            }
            for photo in data.get("photos", [])
            if photo.get("src", {}).get("large")
        ]
    except Exception as e:
        print(f"[pexels] search failed for '{query}': {e}")
        return []


def _clean_extracted_text(text: str) -> str:
    """
    Clean up messy text artifacts often produced by PDF-to-Markdown tools.
    """
    import re
    # 1. Normalize headers: 1-6 hashtags at the start of a line are kept (max 3 for aesthetics)
    # We replace any sequence of 3+ hashtags at start of line with '###'
    text = re.sub(r'^[ \t]*#{3,}', '###', text, flags=re.MULTILINE)
    
    # 2. Remove ANY hashtags that are NOT at the start of a line
    # (Matches # preceded by any non-newline character)
    text = re.sub(r'(?<!\n)[ \t]*#+', ' ', text)
    
    # 3. Clean up broken table pipes '|' if they are surrounded by text
    text = re.sub(r'(?<=\w)[ \t]*\|[ \t]*(?=\w)', ' ', text)
    # Also remove leading/trailing pipes in lines
    text = re.sub(r'^[ \t]*\|', '', text, flags=re.MULTILINE)
    text = re.sub(r'\|[ \t]*$', '', text, flags=re.MULTILINE)
    
    # 4. Collapse multiple spaces
    text = re.sub(r'[ \t]+', ' ', text)
    
    # 5. Collapse multiple newlines (max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


# ══════════════════════════════════════════════════════════════════
# Transcription — routes to Gemini or Groq based on selected provider
# ══════════════════════════════════════════════════════════════════

def _transcribe_with_groq(content: bytes, filename: str) -> str:
    """Transcribe audio/video using Groq Whisper (free tier ~40 min/day)."""
    if not settings.GROQ_API_KEY:
        raise HTTPException(
            status_code=400,
            detail="Groq API key not configured. Add GROQ_API_KEY to your .env.",
        )
    ext = os.path.splitext(filename)[1].lower()
    mime_type = AUDIO_MIME_MAP.get(ext, "audio/mpeg")
    client = Groq(api_key=settings.GROQ_API_KEY)

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=(filename, audio_file, mime_type),
                response_format="text",
            )
        return transcription if isinstance(transcription, str) else transcription.text
    except Exception as e:
        err = str(e)
        if "413" in err or "too large" in err.lower():
            raise HTTPException(status_code=413, detail="File exceeds Groq 25 MB limit.")
        if "429" in err or "quota" in err.lower():
            raise HTTPException(status_code=429, detail="Groq audio quota exceeded. Try again later.")
        raise HTTPException(status_code=500, detail=f"Groq transcription failed: {err}")
    finally:
        os.unlink(tmp_path)


def _transcribe_with_gemini(content: bytes, filename: str) -> str:
    """Transcribe audio/video using Gemini 1.5 Flash native audio understanding."""
    if not settings.GEMINI_API_KEY:
        raise HTTPException(
            status_code=400,
            detail="Gemini API key not configured. Add GEMINI_API_KEY to your .env.",
        )
    ext = os.path.splitext(filename)[1].lower()
    mime_type = AUDIO_MIME_MAP.get(ext, "audio/mpeg")

    try:
        client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options={"api_version": "v1beta"},  # generateContent needs v1beta
        )
        audio_part = genai_types.Part.from_bytes(data=content, mime_type=mime_type)
        prompt_part = genai_types.Part.from_text(
            text="Transcribe all speech and lyrics in this audio/video accurately. Return only the transcript text, no commentary."
        )
        response = client.models.generate_content(
            model="gemini-1.5-flash",  # use 1.5-flash for broader free compatibility
            contents=[audio_part, prompt_part],
        )
        return response.text or ""
    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower():
            raise HTTPException(status_code=429, detail="Gemini quota exceeded. Try again later.")
        raise HTTPException(status_code=500, detail=f"Gemini transcription failed: {err}")


def _transcribe_audio(content: bytes, filename: str, provider: str) -> str:
    """
    Route transcription to the correct provider based on user selection.
      gemini → Gemini 2.0 Flash native audio, auto-falls back to Groq on quota error
      groq   → Groq Whisper large-v3
      openai → Groq Whisper (OpenAI has no free transcription)
      ollama → Groq Whisper (Ollama has no Whisper endpoint by default)
    """
    print(f"[transcribe] provider={provider} file={filename}")
    if provider == "gemini":
        try:
            return _transcribe_with_gemini(content, filename)
        except HTTPException as e:
            if e.status_code == 429:
                # Gemini quota exceeded — silently fall back to Groq Whisper
                print("[transcribe] Gemini quota exceeded, falling back to Groq Whisper")
                return _transcribe_with_groq(content, filename)
            raise
    else:
        # groq, openai, ollama — all use Groq Whisper
        return _transcribe_with_groq(content, filename)


# ══════════════════════════════════════════════════════════════════
# Upload — text document OR audio/video
# ══════════════════════════════════════════════════════════════════

@router.post("/upload", response_model=UploadResponse)
@traceable(run_type="chain", name="Document Ingestion")
async def upload_file(
    file: UploadFile = File(...),
    provider: str = Form("gemini"),
    embedding_provider: str = Form("gemini"),
    payload: dict = Depends(verify_token),
):
    """
    Upload and index a document or media file (user-isolated).

    Supported formats:
      Text  → .txt, .pdf, .docx
      Audio → .mp3, .wav, .m4a, .ogg, .flac, .mpeg, .mpga, .webm
      Video → .mp4, .webm

    Transcription provider:
      Gemini selected → Gemini 1.5 Flash native audio understanding
      Groq selected   → Groq Whisper large-v3 (free ~40 min/day)
      Others          → Groq Whisper as fallback
    """
    user_id = get_user_id(payload)
    fname = file.filename or ""
    fname_lower = fname.lower()
    
    # ── Automatic Deduplication ───────────────────────────────────
    # If a file with the same name exists, delete it first to avoid 
    # mixing old and new versions in Pinecone/DB.
    async with get_conn() as conn:
        existing_doc = await conn.fetchrow(
            "SELECT id FROM user_documents WHERE user_id = $1 AND filename = $2",
            user_id, fname
        )
        if existing_doc:
            print(f"[upload] Found existing version of '{fname}'. Auto-deleting before re-upload.")
            # Trigger deletion flow (we'll call our existing logic)
            from app.services.vector_store import delete_vectors_by_filter
            await conn.execute("DELETE FROM user_documents WHERE id = $1", existing_doc["id"])
            try:
                delete_vectors_by_filter(namespace=user_id, filter={"filename": fname})
            except Exception as e:
                print(f"[upload] Warning: Failed to clear old vectors: {e}")

    content = await file.read()

    # ── Text formats ──────────────────────────────────────────────
    if fname_lower.endswith(".txt"):
        text = content.decode("utf-8", errors="ignore")
        text = _clean_extracted_text(text)

    elif fname_lower.endswith(".pdf"):
        pdf_reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text(extraction_mode="layout") or "" for page in pdf_reader.pages)
        print(f"[upload] Extracted {len(text)} chars from PDF using PyPDF")
        
        # Clean up artifacts like excessive hashtags
        text = _clean_extracted_text(text)

    elif fname_lower.endswith(".docx"):
        doc = docx.Document(io.BytesIO(content))
        text = "\n".join(para.text for para in doc.paragraphs)
        text = _clean_extracted_text(text)

    # ── Audio / Video ─────────────────────────────────────────────
    elif fname_lower.endswith(AUDIO_VIDEO_EXTENSIONS):
        if len(content) > 25 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="File exceeds the 25 MB limit for audio/video transcription.",
            )
        text = await asyncio.to_thread(_transcribe_audio, content, fname, provider)

        if not text or not text.strip():
            raise HTTPException(
                status_code=422,
                detail="Transcription failed or returned empty. Try changing the LLM provider to Groq.",
            )

        # Save audio file for direct playback if possible
        import uuid
        ext = fname_lower.split(".")[-1]
        save_fname = f"{user_id}_media_{uuid.uuid4().hex[:8]}.{ext}"
        u_dir = _get_upload_dir()
        os.makedirs(u_dir, exist_ok=True)
        with open(os.path.join(u_dir, save_fname), "wb") as f:
            f.write(content)
        media_url = f"/uploads/{save_fname}"
        print(f"[transcribe] '{fname}' -> {len(text)} chars via {provider} (Saved: {media_url})")

    # ── Unsupported ───────────────────────────────────────────────
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Accepted: .txt, .pdf, .docx, .mp3, .wav, .m4a, .ogg, .flac, .webm, .mp4",
        )

    # ── Chunk → Embed → Upsert ────────────────────────────────────
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    from app.services.embeddings import get_embeddings
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    chunks = text_splitter.split_text(text)

    if not chunks:
        raise HTTPException(status_code=422, detail="No text content could be extracted from the file.")

    # 🔥 BATCH EMBEDDING: Get all vectors in one (or few) calls
    print(f"[upload] Generating embeddings for {len(chunks)} chunks via {embedding_provider}...")
    all_embeddings = await get_embeddings(chunks, embedding_provider)
    
    print("[upload] Generating BM25 sparse vectors...")
    sparse_embeddings = bm25_encoder.encode_documents(chunks)

    vectors = [
        {
            "id": f"{user_id}_{fname}_{i}",
            "values": all_embeddings[i],
            "sparse_values": sparse_embeddings[i],
            "metadata": {
                "text": chunk,
                "filename": fname,
                "user_id": user_id,
                "uploaded_at": datetime.utcnow().isoformat()
            },
        }
        for i, chunk in enumerate(chunks)
    ]

    upsert_vectors(vectors, namespace=user_id)

    # ── Track in PostgreSQL ───────────────────────────────────────
    async with get_conn() as conn:
        await conn.execute(
            """
            INSERT INTO user_documents (user_id, filename, file_size, file_type, chunks_count, file_content)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            user_id, fname, len(content), file.content_type or "application/octet-stream", 
            len(chunks), content
        )

    return UploadResponse(
        message="Success",
        filename=fname,
        chunks_added=len(chunks),
        url=media_url if fname_lower.endswith(AUDIO_VIDEO_EXTENSIONS) else None,
    )


# ══════════════════════════════════════════════════════════════════
# Query with optional image attachment (vision)
# ══════════════════════════════════════════════════════════════════

@router.post("/query-image")
@traceable(run_type="chain", name="Image Query (Vision)")
async def query_with_image(
    question: str = Form(""),
    provider: str = Form("gemini"),
    embedding_provider: str = Form("gemini"),
    session_id: Optional[str] = Form(None),
    image: UploadFile = File(...),
    payload: dict = Depends(verify_token),
):
    user_id = get_user_id(payload)

    # Attach session_id to LangSmith trace for thread grouping
    run_tree = get_current_run_tree()
    if run_tree and session_id:
        run_tree.metadata["session_id"] = session_id

    content_type = image.content_type or ""
    if content_type not in SUPPORTED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type '{content_type}'. Use JPEG, PNG, WebP, or GIF.",
        )

    image_bytes = await image.read()
    question = question.strip() or "Describe this image in detail."

    try:
        query_embedding = await get_embedding(question, embedding_provider)
        sparse_query = bm25_encoder.encode_queries(question)
        matches = query_vectors(query_vector=query_embedding, namespace=user_id, top_k=3, sparse_vector=sparse_query)
        doc_context = "\n\n".join(m["metadata"]["text"] for m in matches) if matches else ""
    except Exception:
        doc_context = ""

    full_prompt = question
    if doc_context:
        full_prompt = (
            f"Use the document context below if helpful, then analyse the image to answer.\n\n"
            f"Document Context:\n{doc_context}\n\n"
            f"Question: {question}"
        )

    wants_images = _is_image_request(question)
    image_results: List[dict] = []
    if wants_images:
        search_query = _extract_image_search_query(question)
        image_results = await asyncio.to_thread(_search_images_pexels, search_query, count=4)

    # ── Fetch conversation history from DB ──────────────────────
    chat_history = []
    if session_id:
        try:
            async with get_conn() as conn:
                rows = await conn.fetch(
                    """
                    SELECT role, content FROM (
                        SELECT role, content, created_at 
                        FROM chat_messages 
                        WHERE session_id = $1 
                        ORDER BY created_at DESC 
                        LIMIT 20
                    ) AS recent 
                    ORDER BY created_at ASC
                    """,
                    session_id,
                )
                chat_history = [{"role": r["role"], "content": r["content"]} for r in rows]
                if chat_history:
                    print(f"[query-image] loaded {len(chat_history)} history messages from session {session_id[:8]}…")
        except Exception as e:
            print(f"[query-image] failed to load history: {e}")

    async def stream_generator():
        try:
            async for chunk in generate_vision_stream(image_bytes, content_type, full_prompt, provider, history=chat_history):
                # Wrap in JSON for robust whitespace preservation
                yield f"data: {json.dumps({'tok': chunk})}\n\n"
            if image_results:
                yield f"event: images\ndata: {json.dumps(image_results)}\n\n"
            yield f"data: {json.dumps({'tok': '[DONE]'})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ══════════════════════════════════════════════════════════════════
# Standard text query (RAG)
# ══════════════════════════════════════════════════════════════════

def _web_search_tavily(query: str, max_results: int = 5) -> str:
    """
    Search the web using Tavily API and return results as formatted text context.
    Free tier: 1000 searches/month. Get key at: https://tavily.com
    Falls back to empty string if key not set.
    """
    api_key = settings.TAVILY_API_KEY
    if not api_key:
        print("[tavily] TAVILY_API_KEY not set — skipping web search")
        return ""
    try:
        payload = json.dumps({
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": True,
        }).encode()
        req = _urllib_req.Request(
            "https://api.tavily.com/search",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _urllib_req.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        parts = []
        # Include Tavily's own answer summary if available
        if data.get("answer"):
            parts.append(f"Summary: {data['answer']}")

        # Include top result snippets
        for r in data.get("results", []):
            title = r.get("title", "")
            snippet = r.get("content", "")
            url = r.get("url", "")
            if snippet:
                parts.append(f"Source: {title}\n{snippet}\nURL: {url}")

        context = "\n\n".join(parts)
        print(f"[tavily] found {len(data.get('results', []))} results for: {query}")
        return context

    except Exception as e:
        print(f"[tavily] search failed: {e}")
        return ""


@router.post("/query")
@traceable(run_type="chain", name="Document Query (RAG)")
async def query_documents(
    request: QueryRequest,
    raw_request: Request,
    payload: dict = Depends(verify_token),
):
    user_id = get_user_id(payload)

    # Attach session_id to LangSmith trace for thread grouping
    run_tree = get_current_run_tree()
    if run_tree and request.session_id:
        run_tree.metadata["session_id"] = request.session_id

    @traceable(run_type="chain", name="RAG Query Pipeline")
    async def get_all_docs():
        """Fetch ALL matching doc chunks — no score threshold."""
        with mlflow_span("RAG Query Pipeline", span_type="chain", inputs={"question": request.question}):
            query_embedding = await get_embedding(request.question, request.embedding_provider)
            sparse_query = bm25_encoder.encode_queries(request.question)
            
            # TRANSCRIPT SPECIAL CASE: Fetch more chunks for media files if user is asking for a transcript
            if _is_transcript_request(request.question):
                 # fetch top 50 chunks (enough for a long video/song)
                 all_matches = query_vectors(query_vector=query_embedding, namespace=user_id, top_k=50, sparse_vector=sparse_query)
                 # return only matches that come from audio/video files
                 media_matches = [
                     m for m in all_matches 
                     if any(m.get("metadata", {}).get("filename", "").lower().endswith(ext) for ext in AUDIO_VIDEO_EXTENSIONS)
                 ]
                 if media_matches:
                     print(f"[query] transcript request -> returned {len(media_matches)} media chunks")
                     return media_matches

            # Fetch more candidates for reranking
            broad_k = request.top_k * 3
            matches = query_vectors(query_vector=query_embedding, namespace=user_id, top_k=broad_k, sparse_vector=sparse_query)
            
            cohere_key = settings.COHERE_API_KEY
            if cohere_key and matches:
                try:
                    import httpx
                    docs_for_rerank = [m.get("metadata", {}).get("text", "") for m in matches]
                    
                    # Direct HTTP request avoids SDK versioning and sync/async event loop conflicts
                    with httpx.Client() as client:
                        resp = client.post(
                            "https://api.cohere.com/v1/rerank",
                            headers={
                                "Authorization": f"Bearer {cohere_key}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "model": "rerank-english-v3.0",
                                "query": request.question,
                                "documents": docs_for_rerank,
                                "top_n": request.top_k
                            },
                            timeout=10.0
                        )
                        resp.raise_for_status()
                        data = resp.json()
                        
                    reranked_matches = []
                    for result in data.get("results", []):
                        idx = result.get("index")
                        m = matches[idx]
                        
                        # Pinecone ScoredVector causes TypeError with dict()
                        # We manually construct the dictionary with what we need
                        match_dict = {
                            "id": m.get("id", ""),
                            "metadata": m.get("metadata", {}),
                            "score": result.get("relevance_score", 0.0)
                        }
                        reranked_matches.append(match_dict)
                        
                    print(f"[query] Cohere reranked {len(matches)} -> top {len(reranked_matches)}")
                    return reranked_matches
                except Exception as e:
                    import traceback
                    err_str = traceback.format_exc()
                    print(f"[query] Cohere HTTP rerank failed: {e}\n{err_str}")
                    return matches[:request.top_k]

            scores = [round(m.get("score", 0), 3) for m in matches[:request.top_k]]
            print(f"[query] embedding scores={scores} -> returning top {request.top_k} matches")
            return matches[:request.top_k]

    wants_images = _is_image_request(request.question)

    async def stream_generator():
        import time
        start_time = time.time()
        doc_matches = None
        response_text = []
        query_mode = "rag"
        doc_chunks_count = 0
        error_msg = None
        prompt_used = request.question
        chat_history = []

        try:
            # ── Fetch conversation history from DB ─────────────────────
            if request.session_id:
                try:
                    async with get_conn() as conn:
                        rows = await conn.fetch(
                            """
                            SELECT role, content, metadata FROM (
                                SELECT role, content, metadata, created_at 
                                FROM chat_messages 
                                WHERE session_id = $1 
                                ORDER BY created_at DESC 
                                LIMIT 20
                            ) AS recent 
                            ORDER BY created_at ASC
                            """,
                            request.session_id,
                        )
                        chat_history = []
                        for r in rows:
                            msg = {"role": r["role"], "content": r["content"]}
                            # If there was an attachment/image, add a text hint so history includes it
                            meta = json.loads(r["metadata"]) if isinstance(r["metadata"], str) else r["metadata"]
                            if meta and meta.get("attachment"):
                                att = meta["attachment"]
                                hint = f"\n[User uploaded {att.get('type', 'file')}: {att.get('name', 'file')}]"
                                if msg["role"] == "user":
                                    msg["content"] += hint
                            elif meta and meta.get("images"):
                                # This was from an image search or vision turn
                                msg["content"] += "\n[Message includes image search results]"
                            chat_history.append(msg)

                        if chat_history:
                            print(f"[query] loaded {len(chat_history)} history messages (including metadata hints) from session {request.session_id[:8]}…")
                except Exception as e:
                    print(f"[query] failed to load history: {e}")

            # ── Detect conversational follow-ups ──────────────────────
            # Messages that reference previous context should NOT trigger
            # a new web/embedding search — just let the LLM continue
            # the conversation using chat history.
            q = request.question.strip().lower().rstrip("!?.,:;")
            words = q.split()
            word_count = len(words)

            # ── Extract Client IP ──────────────────────
            # On FastAPICloud/Proxies, we check X-Forwarded-For
            forwarded = raw_request.headers.get("x-forwarded-for")
            if forwarded:
                client_ip = forwarded.split(",")[0].strip()
            else:
                client_ip = raw_request.client.host if raw_request.client else None

            # Strategy 1: Exact match on common follow-up phrases
            FOLLOWUP_EXACT = {
                "yes", "no", "yeah", "yep", "nope", "sure", "ok", "okay",
                "please", "thanks", "thank you", "go on", "continue",
                "tell me more", "more", "explain", "elaborate", "why",
                "how", "what", "yes please", "no thanks", "got it",
                "i see", "interesting", "really", "wow", "great",
                "can you explain", "tell me", "go ahead", "sure thing",
                "and", "also", "then", "so", "right", "transcript",
            }

            # Strategy 2: Short messages with context-referencing words
            # ("this", "that", "it") indicate the user is referring to
            # something from the previous conversation, not a new topic
            CONTEXT_WORDS = {
                "this", "that", "it", "its", "these", "those",
                "above", "previous", "same", "earlier",
                "uploaded", "upload", "attached", "image", "photo",
                "picture", "file", "document", "which",
            }

            has_context_ref = any(w in CONTEXT_WORDS for w in words)

            is_followup = (
                len(chat_history) > 0
                and (
                    q in FOLLOWUP_EXACT           # exact match: "yes", "tell me more"
                    or len(q) <= 3                 # ultra-short: "ok", "no", "ya"
                    or (word_count <= 8 and has_context_ref)  # "name of this flower", "what is it"
                )
            )

            if request.agent_mode:
                query_mode = "weather_agent"
                # ── MODE 1: Weather Agent (Universal) ────────
                print(f"[query] -> WEATHER AGENT mode using {request.provider} (IP: {client_ip}, GPS: {request.latitude},{request.longitude})")
                async for chunk in run_weather_agent_stream(
                    request.question, 
                    history=chat_history, 
                    provider=request.provider, 
                    user_ip=client_ip,
                    lat=request.latitude,
                    lon=request.longitude
                ):
                    response_text.append(chunk)
                    yield f"data: {json.dumps({'tok': chunk})}\n\n"
                yield f"data: {json.dumps({'tok': '[DONE]'})}\n\n"
                
                # MLflow Logging
                latency_seconds = time.time() - start_time
                full_resp = "".join(response_text)
                model_name = "gemini-2.5-flash" if request.provider == "gemini" else "llama-3.1-8b-instant"
                input_tokens = _estimate_tokens(request.question) + _estimate_tokens(str(chat_history))
                log_chat_query(
                    question=request.question,
                    provider=request.provider,
                    query_mode=query_mode,
                    session_id=request.session_id,
                    user_id=user_id,
                    model_name=model_name,
                    latency_seconds=latency_seconds,
                    input_tokens_est=input_tokens,
                    output_tokens_est=_estimate_tokens(full_resp),
                    doc_chunks_used=0,
                    response_preview=full_resp,
                    embedding_provider=request.embedding_provider,
                )
                return

            elif is_followup:
                query_mode = "followup"
                # ── MODE 0: Conversational follow-up → history only ────
                prompt = request.question
                prompt_used = prompt
                print(f"[query] -> FOLLOW-UP mode (skipping search, using {len(chat_history)} history msgs)")

            elif request.web_search:
                query_mode = "web_search"
                # ── MODE 1: Web Search ON → only internet results ──────
                has_tavily = bool(settings.TAVILY_API_KEY)
                if has_tavily:
                    web_context = await asyncio.to_thread(_web_search_tavily, request.question)
                    if web_context:
                        prompt = (
                            f"Use the web search results below to give an accurate, up-to-date answer.\n\n"
                            f"Web Search Results:\n{web_context}\n\n"
                            f"Question: {request.question}\n"
                        )
                        prompt_used = prompt
                        print("[query] -> WEB SEARCH mode (web results)")
                    else:
                        prompt = (
                            f"Answer as accurately as possible.\n\n"
                            f"Question: {request.question}\n"
                        )
                        prompt_used = prompt
                        print("[query] -> WEB SEARCH mode (Tavily returned nothing, general knowledge)")
                else:
                    prompt = (
                        f"Answer as accurately as possible.\n\n"
                        f"Question: {request.question}\n"
                    )
                    prompt_used = prompt
                    print("[query] -> WEB SEARCH mode (no TAVILY_API_KEY, general knowledge)")

            # ── MODE 2: Web Search OFF → only document embeddings ──────
            else:
                query_mode = "rag"
                doc_matches = await get_all_docs()

                if doc_matches:
                    doc_chunks_count = len(doc_matches)
                    context_parts = []
                    for m in doc_matches:
                        meta = m.get("metadata", {})
                        f_name = meta.get("filename", "Unknown")
                        u_date = meta.get("uploaded_at", "Unknown Date")
                        # Format: [Source: file.pdf (Uploaded: 2024-04-30)] content...
                        context_parts.append(f"[Source: {f_name} | Uploaded: {u_date}]\n{meta.get('text', '')}")
                    
                    context_text = "\n\n".join(context_parts)
                    prompt = (
                        f"You are a document assistant. Answer the question ONLY using the "
                        f"document context provided below. Do NOT use external knowledge. "
                        f"The context includes upload dates [Uploaded: YYYY-MM-DD] to help you "
                        f"identify the most recent information if there are conflicts.\n\n"
                        f"Document Context:\n{context_text}\n\n"
                        f"Question: {request.question}\n"
                    )
                    prompt_used = prompt
                    print(f"[query] -> DOC EMBEDDING mode ({len(doc_matches)} chunks with upload dates)")
                else:
                    prompt = (
                        f"The user has not uploaded any documents yet, or no documents "
                        f"match this query. Tell them to upload a document first using the "
                        f"attachment button, or enable web search for internet-based answers.\n\n"
                        f"Question: {request.question}\n"
                    )
                    prompt_used = prompt
                    print("[query] -> DOC EMBEDDING mode (no documents found)")

            # Stream LLM response (with conversation history for context)
            async for chunk in generate_stream(prompt, request.provider, history=chat_history):
                response_text.append(chunk)
                yield f"data: {json.dumps({'tok': chunk})}\n\n"

            # Append document snippets at the end if we used them
            if doc_matches and not request.web_search and not is_followup and not request.agent_mode:
                sources_dict = {}
                # Take only the top 3 matches with the highest score overall
                top_matches = sorted(doc_matches, key=lambda x: x.get("score", 0.0), reverse=True)[:3]
                for m in top_matches:
                    fn = m.get("metadata", {}).get("filename", "Unknown Document")
                    text_snippet = m.get("metadata", {}).get("text", "").strip()
                    score = m.get("score", 0.0)
                    if fn not in sources_dict:
                        sources_dict[fn] = []
                    
                    # Store up to 3 context chunks per document
                    if len(sources_dict[fn]) < 3 and text_snippet:
                        snippet_preview = text_snippet.replace('\n', ' ').strip()
                        sources_dict[fn].append({"text": snippet_preview, "score": score})

                if sources_dict:
                    # Look up doc_ids and tokens for these files
                    filenames = list(sources_dict.keys())
                    doc_tokens = {}
                    try:
                        async with get_conn() as conn:
                            # Fetch documents for this user OR matching the filenames across all users
                            rows = await conn.fetch(
                                "SELECT id, filename, user_id FROM user_documents WHERE user_id = $1 OR filename = ANY($2)",
                                user_id, filenames
                            )
                            
                            # Prioritize the current user's documents
                            doc_map = {}
                            for r in rows:
                                if str(r["user_id"]) == str(user_id):
                                    doc_map[r["filename"].strip()] = r["id"]
                                elif r["filename"].strip() not in doc_map:
                                    doc_map[r["filename"].strip()] = r["id"]
                            
                            for fn in filenames:
                                # Try exact match first on stripped filename
                                doc_id = doc_map.get(fn.strip())
                                if not doc_id:
                                    # Try case-insensitive match
                                    for db_fn, d_id in doc_map.items():
                                        if db_fn.lower() == fn.strip().lower():
                                            doc_id = d_id
                                            break
                                if not doc_id:
                                    continue
                                
                                token = await conn.fetchval(
                                    "SELECT token FROM document_view_tokens WHERE doc_id = $1 AND user_id = $2 LIMIT 1",
                                    doc_id, user_id
                                )
                                if not token:
                                    import secrets
                                    token = secrets.token_urlsafe(32)
                                    await conn.execute(
                                        "INSERT INTO document_view_tokens (token, doc_id, user_id) VALUES ($1, $2, $3)",
                                        token, doc_id, user_id
                                    )
                                doc_tokens[fn] = token
                    except Exception as e:
                        print(f"[query] failed to look up doc tokens: {e}")

                    lines = ["\n\n---\n<details style='border: 1px solid rgba(232,168,48,0.2); border-radius: 12px; padding: 10px; background: rgba(232,168,48,0.03);'>\n<summary style='font-weight: 700; color: #E8A830; cursor: pointer; outline: none;'>📚 View Context Sources & Snippets</summary>\n<div style='margin-top: 15px;'>"]
                    
                    for fn, snippets in sources_dict.items():
                        lines.append("<div style='margin-bottom: 20px; border-bottom: 1px dashed rgba(232,168,48,0.15); padding-bottom: 10px;'>")
                        
                        token = doc_tokens.get(fn)
                        if token:
                            # Handle reverse proxy base URL
                            forwarded_host = raw_request.headers.get("x-forwarded-host")
                            forwarded_proto = raw_request.headers.get("x-forwarded-proto", "https")
                            
                            if forwarded_host:
                                view_url = f"{forwarded_proto}://{forwarded_host}/api/v1/documents/view/{token}"
                            else:
                                view_url = f"{str(raw_request.base_url).rstrip('/')}/api/v1/documents/view/{token}"
                            lines.append(f"<p style='font-size: 13px; font-weight: 700; margin: 0 0 10px 0; display: flex; justify-content: space-between; align-items: center;'><span>📄 File: <code style='background: rgba(232,168,48,0.1); padding: 2px 6px; border-radius: 4px;'>{fn}</code></span> <a href='{view_url}' target='_blank' style='color: #E8A830; text-decoration: none; border: 1px solid #E8A830; padding: 2px 6px; border-radius: 4px; font-size: 11px;'>View Document</a></p>")
                        else:
                            lines.append(f"<p style='font-size: 13px; font-weight: 700; margin: 0 0 10px 0;'>📄 File: <code style='background: rgba(232,168,48,0.1); padding: 2px 6px; border-radius: 4px;'>{fn}</code></p>")
                        
                        for i, snip_data in enumerate(snippets):
                            snip = snip_data["text"]
                            score = snip_data["score"]
                            lines.append("<div style='background: rgba(128, 128, 128, 0.08); color: inherit; padding: 12px; border-left: 4px solid #E8A830; border-radius: 6px; font-size: 13.5px; line-height: 1.6; margin-bottom: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);'>")
                            lines.append("<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;'>")
                            lines.append(f"<strong style='color: #C07C10; font-size: 11px; text-transform: uppercase;'>[Snippet #{i+1}]</strong>")
                            lines.append(f"<span style='font-size: 11px; font-weight: 600; color: #E8A830; background: rgba(232, 168, 48, 0.1); padding: 2px 6px; border-radius: 12px;'>Match: {round(score * 100, 1)}%</span>")
                            lines.append("</div>")
                            lines.append(f"<i>{snip}</i>")
                            lines.append("</div>")
                        
                        lines.append("</div>")
                    
                    lines.append("</div>\n</details>")
                    source_str = "\n".join(lines)
                    yield f"data: {json.dumps({'tok': source_str})}\n\n"
                
            # Fetch Pexels images if requested
            if wants_images:
                search_query = _extract_image_search_query(request.question)
                image_results = await asyncio.to_thread(_search_images_pexels, search_query, count=4)
                if image_results:
                    yield f"event: images\ndata: {json.dumps(image_results)}\n\n"

            yield f"data: {json.dumps({'tok': '[DONE]'})}\n\n"

            # MLflow Logging on success
            latency_seconds = time.time() - start_time
            full_resp = "".join(response_text)
            model_name = None
            if request.provider == "gemini":
                model_name = "gemini-2.5-flash"
            elif request.provider == "groq":
                model_name = "llama-3.3-70b-versatile"
            elif request.provider == "openai":
                model_name = "gpt-4o-mini"
            elif request.provider == "ollama":
                model_name = "tinyllama:latest"

            input_tokens = _estimate_tokens(prompt_used) + _estimate_tokens(str(chat_history))
            log_chat_query(
                question=request.question,
                provider=request.provider,
                query_mode=query_mode,
                session_id=request.session_id,
                user_id=user_id,
                model_name=model_name,
                latency_seconds=latency_seconds,
                input_tokens_est=input_tokens,
                output_tokens_est=_estimate_tokens(full_resp),
                doc_chunks_used=doc_chunks_count,
                response_preview=full_resp,
                embedding_provider=request.embedding_provider,
            )

        except Exception as e:
            error_msg = str(e)
            yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"

            # MLflow Logging on error
            latency_seconds = time.time() - start_time
            model_name = None
            if request.provider == "gemini":
                model_name = "gemini-2.5-flash"
            elif request.provider == "groq":
                model_name = "llama-3.3-70b-versatile"
            elif request.provider == "openai":
                model_name = "gpt-4o-mini"
            elif request.provider == "ollama":
                model_name = "tinyllama:latest"

            input_tokens = _estimate_tokens(request.question) + _estimate_tokens(str(chat_history))
            log_chat_query(
                question=request.question,
                provider=request.provider,
                query_mode=query_mode,
                session_id=request.session_id,
                user_id=user_id,
                model_name=model_name,
                latency_seconds=latency_seconds,
                input_tokens_est=input_tokens,
                output_tokens_est=0,
                doc_chunks_used=doc_chunks_count,
                response_preview="",
                error=error_msg,
                embedding_provider=request.embedding_provider,
            )

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ══════════════════════════════════════════════════════════════════
# Clear documents
# ══════════════════════════════════════════════════════════════════

@router.delete("/clear")
async def delete_embedded_documents(payload: dict = Depends(verify_token)):
    """
    Delete all embedded documents for the current user.
    Removes Pinecone vector embeddings and any locally-stored uploaded files.
    Does NOT affect chat sessions or message history stored in PostgreSQL.
    """
    user_id = get_user_id(payload)
    print(f"[delete-embedded] Request to delete embedded documents for user: {user_id}")
    try:
        # 1. Delete vectors from Pinecone (user namespace)
        delete_all_user_vectors(namespace=user_id)
        print(f"[delete-embedded] Pinecone vectors deleted for namespace: {user_id}")

        # 2. Delete locally-saved upload files (audio, video, images)
        upload_dir = _get_upload_dir()
        if os.path.exists(upload_dir):
            deleted_count = 0
            for f in os.listdir(upload_dir):
                if f.startswith(f"{user_id}_"):
                    try:
                        os.remove(os.path.join(upload_dir, f))
                        deleted_count += 1
                    except Exception as e:
                        print(f"[delete-embedded] Error deleting file {f}: {e}")
            print(f"[delete-embedded] Deleted {deleted_count} local files for user: {user_id}")

        print(f"[delete-embedded] Successfully deleted all embedded documents for: {user_id}")
        return {"message": "All your embedded documents and associated files have been deleted successfully"}
    except Exception as e:
        print(f"[delete-embedded] FAILED: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[DocumentResponse])
async def list_documents(payload: dict = Depends(verify_token)):
    """List all documents uploaded by the current user."""
    user_id = get_user_id(payload)
    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT id, filename, file_size, file_type, chunks_count, created_at
            FROM user_documents
            WHERE user_id = $1
            ORDER BY created_at DESC
            """,
            user_id
        )
    
    return [
        {
            "id": str(r["id"]),
            "filename": r["filename"],
            "file_size": r["file_size"],
            "file_type": r["file_type"],
            "chunks_count": r["chunks_count"],
            "created_at": r["created_at"].isoformat()
        }
        for r in rows
    ]


@router.delete("/{doc_id}")
async def delete_document(doc_id: str, payload: dict = Depends(verify_token)):
    """Delete a specific document from DB and Pinecone."""
    user_id = get_user_id(payload)
    async with get_conn() as conn:
        # 1. Get filename first to delete from Pinecone
        row = await conn.fetchrow(
            "SELECT filename FROM user_documents WHERE id = $1 AND user_id = $2",
            doc_id, user_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        
        fname = row["filename"]
        
        # 2. Delete from PostgreSQL
        await conn.execute("DELETE FROM user_documents WHERE id = $1", doc_id)
        
        # 3. Delete from Pinecone
        from app.services.vector_store import delete_vectors_by_filter
        try:
            delete_vectors_by_filter(namespace=user_id, filter={"filename": fname})
            print(f"[delete-document] Vectors for '{fname}' deleted from Pinecone namespace: {user_id}")
        except Exception as e:
            print(f"[delete-document] Failed to delete vectors from Pinecone: {e}")
            
    return {"message": f"Document '{fname}' deleted successfully"}


@router.post("/{doc_id}/view-token")
async def create_view_token(doc_id: str, payload: dict = Depends(verify_token)):
    """Generate a persistent token for viewing a document (stored in DB)."""
    user_id = get_user_id(payload)
    token = secrets.token_urlsafe(32)
    
    async with get_conn() as conn:
        await conn.execute(
            """
            INSERT INTO document_view_tokens (token, doc_id, user_id)
            VALUES ($1, $2, $3)
            """,
            token, doc_id, user_id
        )
    
    return {"token": token}


@router.get("/view/{token}")
async def view_document_public(token: str):
    """Public route to view document using a persistent token from DB."""
    # 1. Validate token from DB
    async with get_conn() as conn:
        token_data = await conn.fetchrow(
            "SELECT doc_id, user_id FROM document_view_tokens WHERE token = $1",
            token
        )
        
        if not token_data:
            raise HTTPException(status_code=403, detail="Invalid or expired view token")
        
        doc_id = token_data["doc_id"]
        user_id = token_data["user_id"]
        
        # 2. Fetch file content from DB
        row = await conn.fetchrow(
            "SELECT filename, file_type, file_content FROM user_documents WHERE id = $1",
            doc_id
        )
        
    if not row or not row["file_content"]:
        raise HTTPException(status_code=404, detail="File content not found")
        
    return Response(
        content=row["file_content"],
        media_type=row["file_type"],
        headers={"Content-Disposition": f'inline; filename="{row["filename"]}"'}
    )


@router.get("/{doc_id}/download")
async def download_document(
    doc_id: str, 
    inline: bool = False,
    payload: dict = Depends(verify_token)
):
    """Download or view the original file content."""
    user_id = get_user_id(payload)
    async with get_conn() as conn:
        row = await conn.fetchrow(
            "SELECT filename, file_type, file_content FROM user_documents WHERE id = $1 AND user_id = $2",
            doc_id, user_id
        )
        if not row or not row["file_content"]:
            raise HTTPException(status_code=404, detail="File content not found")
            
        # For inline, we still provide a filename for the tab title, but use 'inline'
        disposition = f'inline; filename="{row["filename"]}"' if inline else f'attachment; filename="{row["filename"]}"'
            
        return Response(
            content=row["file_content"],
            media_type=row["file_type"],
            headers={"Content-Disposition": disposition}
        )


@router.post("/upload-image")
async def upload_chat_image(
    file: UploadFile = File(...),
    payload: dict = Depends(verify_token),
):
    """
    Upload an image for chat. Saves to local uploads/ dir and returns public URL.
    Replaces Supabase Storage.
    """
    user_id = get_user_id(payload)
    content = await file.read()
    ext = (file.filename or "img").split(".")[-1]
    import uuid
    fname = f"{user_id}_{uuid.uuid4().hex[:8]}.{ext}"

    upload_dir = _get_upload_dir()
    os.makedirs(upload_dir, exist_ok=True)
    fpath = os.path.join(upload_dir, fname)
    with open(fpath, "wb") as f:
        f.write(content)

    # Return a URL the frontend can use
    return {"url": f"/uploads/{fname}", "filename": fname}