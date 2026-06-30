import asyncio
from typing import List

import google.genai as genai
from google.genai import types
from langsmith import traceable
from app.services.mlflow_tracker import mlflow_span
from openai import OpenAI

from app.core.config import get_settings

settings = get_settings()

# models/gemini-embedding-001 is the recommended model for stable embeddings
GEMINI_EMBED_MODEL = "models/gemini-embedding-001"

_gemini_client = None
_openai_client = None
_current_gemini_key = None
_current_openai_key = None

def get_gemini_client():
    global _gemini_client, _current_gemini_key
    key = settings.GEMINI_API_KEY
    if (_gemini_client is None or key != _current_gemini_key) and key:
        print(f"[embeddings] Initializing Gemini client with key starting with '{key[:6]}...'")
        _gemini_client = genai.Client(api_key=key)
        _current_gemini_key = key
    return _gemini_client


def get_openai_client():
    global _openai_client, _current_openai_key
    key = settings.OPENAI_API_KEY
    if (_openai_client is None or key != _current_openai_key) and key:
        print(f"[embeddings] Initializing OpenAI client with key starting with '{key[:6]}...'")
        _openai_client = OpenAI(api_key=key)
        _current_openai_key = key
    return _openai_client


@traceable(run_type="embedding")
async def get_embedding(text: str, provider: str) -> List[float]:
    """Single text embedding wrapper."""
    embeddings = await get_embeddings([text], provider)
    return embeddings[0]


@traceable(run_type="embedding")
async def get_embeddings(texts: List[str], provider: str) -> List[List[float]]:
    with mlflow_span("Get Embeddings", span_type="embedding", inputs={"texts_count": len(texts), "provider": provider}):
        return await _get_embeddings_impl(texts, provider)

async def _get_embeddings_impl(texts: List[str], provider: str) -> List[List[float]]:
    """
    Generate embeddings for a list of texts using batching and retries.
    """
    if not texts:
        return []

    # Clean texts
    clean_texts = [t.encode("ascii", "ignore").decode("utf-8") for t in texts]

    # Max batch size for Gemini is 100. We use 90 to be safe.
    # Higher batch size = fewer "requests" counted against your daily 1,000 limit.
    batch_size = 90 if provider == "gemini" else 100
    results = []

    for i in range(0, len(clean_texts), batch_size):
        batch = clean_texts[i : i + batch_size]
        success = False
        retries = 5
        delay = 5

        while not success and retries > 0:
            try:
                batch_embeddings = []
                if provider == "gemini":
                    client = get_gemini_client()
                    if not client:
                        raise ValueError("Gemini API key not configured")
                    
                    res = client.models.embed_content(
                        model=GEMINI_EMBED_MODEL,
                        contents=batch,
                        config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
                    )
                    batch_embeddings = [e.values for e in res.embeddings]
                    
                    # 🧩 FALLBACK: If Gemini returned 1 vector for multiple texts, process them individually
                    if len(batch_embeddings) == 1 and len(batch) > 1:
                        print(f"[embeddings] Gemini returned 1 vector for {len(batch)} chunks. Falling back to individual processing...")
                        batch_embeddings = []
                        for txt in batch:
                            r = client.models.embed_content(
                                model=GEMINI_EMBED_MODEL,
                                contents=txt,
                                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
                            )
                            # Single content return might not be a list in 'embeddings' attribute
                            if hasattr(r, 'embeddings') and r.embeddings:
                                batch_embeddings.append(r.embeddings[0].values)
                            else:
                                batch_embeddings.append(r.embedding.values)

                elif provider == "openai":
                    client = get_openai_client()
                    if not client:
                        raise ValueError("OpenAI API key not configured")
                    
                    res = client.embeddings.create(
                        model="text-embedding-3-large",
                        input=batch,
                    )
                    batch_embeddings = [d.embedding for d in res.data]

                # 🛑 CRITICAL CHECK: Ensure we got back what we sent
                if len(batch_embeddings) != len(batch):
                    raise ValueError(f"Provider {provider} returned {len(batch_embeddings)} embeddings for {len(batch)} chunks.")
                
                results.extend(batch_embeddings)
                success = True

            except Exception as e:
                err = str(e).lower()
                if ("quota" in err or "429" in err or "limit" in err or "exhausted" in err):
                    if retries > 1:
                        sleep_time = delay if "exhausted" not in err else 15
                        print(f"[embeddings] {provider} quota hit. Waiting {sleep_time}s... ({retries-1} left)")
                        await asyncio.sleep(sleep_time)
                        delay *= 2
                        retries -= 1
                    else:
                        raise ValueError(f"{provider.upper()} quota exhausted. Please switch providers or check billing.") from e
                else:
                    raise

    if len(results) != len(texts):
        raise ValueError(f"Embedding mismatch: Expected {len(texts)} but got {len(results)}")

    return results