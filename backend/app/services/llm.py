"""
LLM Service
Streaming generation with multiple LLM providers + vision (multimodal) support.

Free-tier model map
───────────────────
Provider │ Text model                              │ Vision model
─────────┼─────────────────────────────────────────┼──────────────────────────────────────
Groq     │ llama-3.3-70b-versatile                 │ meta-llama/llama-4-scout-17b-16e-instruct
Gemini   │ gemini-1.5-flash  (15 RPM free)         │ gemini-1.5-flash  (same)
OpenAI   │ gpt-4o-mini       (paid)                │ gpt-4o            (paid)
Ollama   │ tinyllama:latest  (local/free)           │ llava:latest      (local/free)
"""
import asyncio
import base64
import json
import re
from typing import AsyncGenerator

import google.genai as genai
import httpx
from google.api_core.exceptions import ResourceExhausted
from google.genai import types as genai_types
from groq import Groq
from groq import RateLimitError as GroqRateLimitError
from openai import OpenAI
from langsmith import traceable
from app.services.mlflow_tracker import mlflow_span

from app.core.config import get_settings

from prometheus_client import Counter, Histogram
import time

LLM_REQUESTS = Counter(
    "llm_requests_total",
    "Total LLM requests completed",
    ["provider", "model"]
)
LLM_PROMPT_TOKENS = Counter(
    "llm_prompt_tokens_total",
    "Total LLM prompt tokens",
    ["provider", "model"]
)
LLM_GENERATION_TOKENS = Counter(
    "llm_generation_tokens_total",
    "Total LLM generation tokens",
    ["provider", "model"]
)
LLM_TTFT = Histogram(
    "llm_time_to_first_token_seconds",
    "Time to first token (TTFT) latency",
    ["provider", "model"],
    buckets=(0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
)
LLM_DURATION = Histogram(
    "llm_request_duration_seconds",
    "End-to-end request duration",
    ["provider", "model"],
    buckets=(0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, 15.0, 20.0, 30.0)
)

async def instrumented_generator(gen, provider, model, prompt_text):
    start_time = time.time()
    ttft_measured = False
    generated_text = ""
    
    # Estimate prompt tokens (characters / 4)
    prompt_tokens = len(prompt_text) // 4
    
    try:
        async for chunk in gen:
            if not ttft_measured:
                ttft = time.time() - start_time
                LLM_TTFT.labels(provider=provider, model=model).observe(ttft)
                ttft_measured = True
            
            generated_text += chunk
            yield chunk
            
        # Success, record metrics
        duration = time.time() - start_time
        generation_tokens = len(generated_text) // 4
        
        LLM_REQUESTS.labels(provider=provider, model=model).inc()
        LLM_PROMPT_TOKENS.labels(provider=provider, model=model).inc(prompt_tokens)
        LLM_GENERATION_TOKENS.labels(provider=provider, model=model).inc(generation_tokens)
        LLM_DURATION.labels(provider=provider, model=model).observe(duration)
        
    except Exception as e:
        raise e

settings = get_settings()

# ── Free-tier model names ──────────────────────────────────────────────────────
GEMINI_TEXT_MODEL   = "gemini-2.5-flash"          # 15 RPM · 1 500 RPD free
GEMINI_VISION_MODEL = "gemini-2.5-flash"           # same model, supports multimodal
GROQ_TEXT_MODEL     = "llama-3.3-70b-versatile"   # free, 6 000 tokens/min
GROQ_AGENT_MODEL    = "llama-3.1-8b-instant"      # high RPM, great for tools
GROQ_VISION_MODEL   = "meta-llama/llama-4-scout-17b-16e-instruct"  # free vision on Groq

# ── Lazy-loaded clients ────────────────────────────────────────────────────────
_gemini_client = None
_groq_client   = None
_openai_client = None


def get_gemini_client():
    global _gemini_client
    if _gemini_client is None and settings.GEMINI_API_KEY:
        _gemini_client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
        )
    return _gemini_client


def get_groq_client():
    global _groq_client
    if _groq_client is None and settings.GROQ_API_KEY:
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client


def get_openai_client():
    global _openai_client
    if _openai_client is None and settings.OPENAI_API_KEY:
        _openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


# ── Helpers ────────────────────────────────────────────────────────────────────




def sanitize_output(text: str) -> str:
    """Strip chain-of-thought tags and tool-calling artifacts that some models leak."""
    if not text:
        return ""
    
    # If the chunk is just whitespace or newlines, preserve it strictly for streaming
    if text.isspace():
        return text

    # Remove <think> blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = text.replace("<think>", "").replace("</think>", "")
    
    # Remove common tool-calling confirmations and internal dialogue
    text = re.sub(r"(?i)(I need to|To provide you with).*? (API calls?|tools?).*?(\n|\.)", "", text)
    text = re.sub(r"(?i)(I will|Calling|I'll|Let me) (call|use|run|check) (the )?['\"]?get_current_location['\"]?.*?\.", "", text)
    text = re.sub(r"(?i)(I will|Calling|I'll|Let me) (call|use|run|check) (the )?['\"]?get_weather['\"]?.*?\.", "", text)
    
    # Remove Groq/Llama tool-calling artifacts
    text = re.sub(r"get_weather\s*>[^<]+", "", text)
    text = re.sub(r"<function>.*?</function>", "", text, flags=re.DOTALL)
    text = re.sub(r"\{[^{}]*\"lat\"[^{}]*\"lon\"[^{}]*\}", "", text)
    text = text.replace("</function>", "").replace("<function>", "")
    
    # Collapse excessive newlines (3+) but keep standard double newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    return text






def _rate_limit_message(retry_after=None, current_provider: str = "gemini") -> str:
    wait = f"{int(retry_after)}s" if retry_after else "~30s"
    # Recommend a different provider than the current one
    alt_provider = "Groq" if current_provider == "gemini" else "Gemini"
    
    return (
        f"⚠️ Free-tier rate limit reached. "
        f"The model will be available again in {wait}. "
        f"Please try again shortly, or switch to **{alt_provider}** (fastest free option)."
    )


# ══════════════════════════════════════════════════════════════════════════════
# Vision (Multimodal) Streaming
# ══════════════════════════════════════════════════════════════════════════════

@traceable(run_type="llm", name="LLM Vision Stream")
async def generate_vision_stream(
    image_bytes: bytes,
    mime_type: str,
    question: str,
    provider: str,
    history: list = None,
) -> AsyncGenerator[str, None]:
    model = "unknown"
    if provider == "gemini":
        model = GEMINI_VISION_MODEL
    elif provider == "groq":
        model = GROQ_VISION_MODEL
    elif provider == "openai":
        model = "gpt-4o"
    elif provider == "ollama":
        model = "llava"
    
    prompt_text = question
    if history:
        prompt_text += " ".join([m["content"] for m in history])
        
    gen = _generate_vision_stream_impl(image_bytes, mime_type, question, provider, history)
    async for chunk in instrumented_generator(gen, provider, model, prompt_text):
        yield chunk

async def _generate_vision_stream_impl(
    image_bytes: bytes,
    mime_type: str,
    question: str,
    provider: str,
    history: list = None,
) -> AsyncGenerator[str, None]:
    """
    Stream a vision response for an uploaded image.

    Groq   -> llama-3.2-11b-vision-preview (free)
    Gemini -> gemini-1.5-flash (free tier)
    OpenAI -> gpt-4o  (paid)
    Ollama -> llava   (local/free)
    """
    hist = history or []
    # Keep last few turns for context in vision
    hist = hist[-10:]

    # ── Groq Vision (llama-3.2-11b-vision-preview / llama-3.2-90b-vision-preview)
    if provider == "groq":
        client = get_groq_client()
        if not client:
            yield "Groq API key is not configured."
            return

        b64 = base64.b64encode(image_bytes).decode()
        messages = [{"role": "system", "content": "You are a helpful assistant with vision capabilities."}]
        for msg in hist:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Add current image + question
        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
            ],
        })

        try:
            stream = client.chat.completions.create(
                model=GROQ_VISION_MODEL,
                messages=messages,
                stream=True,
                max_tokens=1024,
            )
            for chunk in stream:
                text = chunk.choices[0].delta.content
                if text:
                    yield sanitize_output(text)
                await asyncio.sleep(0)
        except Exception as e:
            yield f"Groq vision error: {e}"

    # ── Gemini vision (FREE tier -- gemini-1.5-flash) ─────────────────────────
    elif provider == "gemini":
        client = get_gemini_client()
        if not client:
            yield "Gemini API key is not configured."
            return

        contents = []
        for msg in hist:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        
        # Current message with image
        image_part = genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        text_part  = genai_types.Part.from_text(text=question)
        contents.append({"role": "user", "parts": [image_part, text_part]})

        try:
            stream = client.models.generate_content_stream(
                model=GEMINI_VISION_MODEL,
                contents=contents,
            )
            for chunk in stream:
                text = getattr(chunk, "text", None)
                if text:
                    yield sanitize_output(text)
                await asyncio.sleep(0)
        except Exception as e:
            yield f"Gemini vision error: {e}"

    # ── OpenAI vision (paid -- gpt-4o) ────────────────────────────────────────
    elif provider == "openai":
        client = get_openai_client()
        if not client:
            yield "OpenAI API key is not configured."
            return

        b64 = base64.b64encode(image_bytes).decode()
        messages = []
        for msg in hist:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        messages.append({
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}},
                {"type": "text", "text": question},
            ],
        })

        try:
            stream = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                text = chunk.choices[0].delta.content
                if text:
                    yield sanitize_output(text)
                await asyncio.sleep(0)
        except Exception as e:
            yield f"OpenAI vision error: {e}"

    # ── Ollama vision (local / free -- llava) ─────────────────────────────────
    elif provider == "ollama":
        b64 = base64.b64encode(image_bytes).decode()
        messages = []
        for msg in hist:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Ollama /api/chat supports vision
        messages.append({
            "role": "user",
            "content": question,
            "images": [b64],
        })

        # Detect if we should use OpenAI-compatible endpoint (/v1)
        use_v1 = "/v1" in settings.OLLAMA_BASE_URL
        endpoint = f"{settings.OLLAMA_BASE_URL}/chat/completions" if use_v1 else f"{settings.OLLAMA_BASE_URL}/api/chat"
        model_name = settings.OLLAMA_MODEL if settings.OLLAMA_MODEL else "llava:latest"

        headers = {}
        auth = None
        if settings.OLLAMA_API_KEY:
            if ":" in settings.OLLAMA_API_KEY:
                # Basic Auth
                user, pwd = settings.OLLAMA_API_KEY.split(":", 1)
                auth = (user, pwd)
            else:
                # Bearer token
                headers["Authorization"] = f"Bearer {settings.OLLAMA_API_KEY}"

        try:
            payload = {
                "model": model_name,
                "messages": messages,
                "stream": True
            }
            # Standard Ollama /api/chat uses a slightly different response format than OpenAI v1
            async with httpx.AsyncClient() as client:
                # We use stream=True-like behavior with httpx.stream
                async with client.stream("POST", endpoint, json=payload, headers=headers, auth=auth, timeout=180.0) as response:
                    if response.status_code != 200:
                        try:
                            err_msg = (await response.json()).get("error", {}).get("message", await response.aread())
                        except Exception:
                            err_msg = await response.aread()
                        yield f"Ollama HTTP error {response.status_code}: {err_msg}"
                        return

                    async for line in response.aiter_lines():
                        if line:
                            data = json.loads(line)
                            if use_v1:
                                # OpenAI v1 format
                                text = data.get("choices", [{}])[0].get("delta", {}).get("content")
                                if text: yield sanitize_output(text)
                            else:
                                # Standard Ollama format
                                msg_chunk = data.get("message", {})
                                if msg_chunk.get("content"):
                                    yield sanitize_output(msg_chunk["content"])
                await asyncio.sleep(0)
        except Exception as e:
            yield f"Ollama vision error: {e}"

    else:
        yield "Image analysis is not supported for the selected provider."


# ══════════════════════════════════════════════════════════════════════════════
# Text Streaming
# ══════════════════════════════════════════════════════════════════════════════

@traceable(run_type="llm", name="LLM Stream")
async def generate_stream(
    prompt: str,
    provider: str,
    history: list = None,
) -> AsyncGenerator[str, None]:
    with mlflow_span("LLM Stream", span_type="llm", inputs={"prompt": prompt, "provider": provider}):
        model = "unknown"
        if provider == "gemini":
            model = GEMINI_TEXT_MODEL
        elif provider == "groq":
            model = GROQ_TEXT_MODEL
        elif provider == "openai":
            model = "gpt-4o-mini"
        elif provider == "ollama":
            model = settings.OLLAMA_MODEL or "tinyllama"
        
        prompt_text = prompt
        if history:
            prompt_text += " ".join([m["content"] for m in history])
            
        gen = _generate_stream_impl(prompt, provider, history)
        async for chunk in instrumented_generator(gen, provider, model, prompt_text):
            yield chunk

async def _generate_stream_impl(
    prompt: str,
    provider: str,
    history: list = None,
) -> AsyncGenerator[str, None]:
    """
    Stream a text response from the selected LLM provider.
    
    Args:
        prompt: The current user prompt (may include system instructions + context)
        provider: LLM provider name
        history: Optional list of previous messages [{"role": "user"|"assistant", "content": "..."}]
    """
    # Build a messages list: system + history + current prompt
    hist = history or []
    # Keep last 10 exchanges max to avoid token overflow
    hist = hist[-(20):]  # 20 messages = ~10 exchanges

    # ── Gemini (FREE -- gemini-2.5-flash) ─────────────────────────────────────
    if provider == "gemini":
        client = get_gemini_client()
        if not client:
            yield "Gemini API key is not configured."
            return

        # Gemini uses a contents list; build multi-turn conversation
        contents = []
        for msg in hist:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        # Add current prompt as user message
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        try:
            stream = client.models.generate_content_stream(
                model=GEMINI_TEXT_MODEL,
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    system_instruction="You are a helpful assistant. Use Markdown to structure your responses (headings, bold, lists). Always use double asterisks for headers."
                )
            )
            for chunk in stream:
                text = getattr(chunk, "text", None)
                if text:
                    yield sanitize_output(text)
                await asyncio.sleep(0)

        except ResourceExhausted as e:
            retry_after = None
            try:
                details = e.details() if callable(e.details) else []
                for d in details:
                    if hasattr(d, "retry_delay"):
                        retry_after = d.retry_delay.seconds
                        break
            except Exception:
                pass
            yield _rate_limit_message(retry_after, "gemini")

        except Exception as e:
            yield f"Gemini error: {e}"

    # ── Groq (FREE -- llama-3.3-70b-versatile) ────────────────────────────────
    elif provider == "groq":
        client = get_groq_client()
        if not client:
            yield "Groq API key is not configured."
            return

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. "
                    "Use Markdown to structure your responses (headings, bold, lists). "
                    "Always use double asterisks for headers. "
                    "Never include <think> tags. "
                    "Return only the final answer."
                ),
            },
        ]
        # Add conversation history
        for msg in hist:
            messages.append({"role": msg["role"], "content": msg["content"]})
        # Add current prompt
        messages.append({"role": "user", "content": prompt})

        try:
            stream = client.chat.completions.create(
                model=GROQ_TEXT_MODEL,
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                text = chunk.choices[0].delta.content
                if text:
                    yield sanitize_output(text)
                await asyncio.sleep(0)

        except GroqRateLimitError as e:
            retry_after = getattr(e, "retry_after", None)
            yield _rate_limit_message(retry_after, "groq")

        except Exception as e:
            yield f"Groq error: {e}"

    # ── OpenAI (paid -- gpt-4o-mini) ──────────────────────────────────────────
    elif provider == "openai":
        client = get_openai_client()
        if not client:
            yield "OpenAI API key is not configured."
            return

        messages = []
        for msg in hist:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})

        try:
            stream = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                text = chunk.choices[0].delta.content
                if text:
                    yield sanitize_output(text)
                await asyncio.sleep(0)
        except Exception as e:
            yield f"OpenAI error: {e}"

    # ── Ollama (local / free -- tinyllama) ────────────────────────────────────
    elif provider == "ollama":
        # Ollama uses /api/chat for multi-turn
        messages = []
        for msg in hist:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})

        # Detect if we should use OpenAI-compatible endpoint (/v1)
        use_v1 = "/v1" in settings.OLLAMA_BASE_URL
        endpoint = f"{settings.OLLAMA_BASE_URL}/chat/completions" if use_v1 else f"{settings.OLLAMA_BASE_URL}/api/chat"
        model_name = settings.OLLAMA_MODEL if settings.OLLAMA_MODEL else "tinyllama:latest"

        headers = {}
        auth = None
        if settings.OLLAMA_API_KEY:
            if ":" in settings.OLLAMA_API_KEY:
                # Basic Auth
                user, pwd = settings.OLLAMA_API_KEY.split(":", 1)
                auth = (user, pwd)
            else:
                # Bearer token
                headers["Authorization"] = f"Bearer {settings.OLLAMA_API_KEY}"

        try:
            payload = {
                "model": model_name,
                "messages": messages,
                "stream": True
            }
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", endpoint, json=payload, headers=headers, auth=auth, timeout=180.0) as response:
                    if response.status_code != 200:
                        try:
                            err_msg = (await response.json()).get("error", {}).get("message", await response.aread())
                        except Exception:
                            err_msg = await response.aread()
                        yield f"Ollama HTTP error {response.status_code}: {err_msg}"
                        return

                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                if use_v1:
                                    text = data.get("choices", [{}])[0].get("delta", {}).get("content")
                                    if text: yield sanitize_output(text)
                                else:
                                    msg_chunk = data.get("message", {})
                                    if msg_chunk.get("content"):
                                        yield sanitize_output(msg_chunk["content"])
                            except Exception:
                                continue
                await asyncio.sleep(0)
        except Exception as e:
            yield f"Ollama error: {e}"

    else:
        yield "Invalid provider selected."

# ══════════════════════════════════════════════════════════════════════════════
# Follow-up Suggestions
# ══════════════════════════════════════════════════════════════════════════════

@traceable(run_type="llm", name="Generate Suggestions")
async def generate_suggestions(history: list, provider: str) -> list[str]:
    """
    Generate 3 short follow-up questions based on the chat history.
    """
    hist = history[-6:] if history else []
    
    system_instruction = (
        "You are a helpful assistant that suggests follow-up questions. "
        "Based on the provided conversation, suggest exactly 3 short, highly relevant follow-up "
        "questions that the user is likely to ask next. "
        "Rules:\n"
        "1. Be specific to the topics discussed in the chat.\n"
        "2. Do NOT suggest generic questions like 'Tell me more'.\n"
        "3. Output ONLY a valid JSON object with a single key 'suggestions' containing an array of 3 strings.\n"
        "4. No markdown formatting, no preamble, just the JSON."
    )
    
    messages = [{"role": "system", "content": system_instruction}]
    for msg in hist:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Add a final reminder to ensure the model stays on track
    messages.append({
        "role": "user", 
        "content": "Suggest 3 specific follow-up questions based on our chat so far. Return JSON: {\"suggestions\": [...]}"
    })
        
    text = ""
    try:
        if provider == "groq":
            client = get_groq_client()
            if client:
                resp = await asyncio.to_thread(
                    client.chat.completions.create,
                    model=GROQ_TEXT_MODEL,
                    messages=messages,
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )
                text = resp.choices[0].message.content
        elif provider == "gemini":
            client = get_gemini_client()
            if client:
                # For Google GenAI SDK, we pass system_instruction as a separate config
                # but we can also just append it. Let's stick to the current pattern.
                contents = []
                for msg in messages:
                    # Map roles
                    role = "user"
                    if msg["role"] == "assistant" or msg["role"] == "model":
                        role = "model"
                    elif msg["role"] == "system":
                         # Gemini 1.5 Pro/Flash handles system_instruction better
                         # but for simplicity in this loop we can treat it as user
                         role = "user"
                    
                    contents.append({"role": role, "parts": [{"text": msg["content"]}]})
                
                resp = await asyncio.to_thread(
                    client.models.generate_content,
                    model=GEMINI_TEXT_MODEL,
                    contents=contents,
                    config={"temperature": 0.7}
                )
                text = resp.text
        elif provider == "openai":
            client = get_openai_client()
            if client:
                resp = await asyncio.to_thread(
                    client.chat.completions.create,
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )
                text = resp.choices[0].message.content
        elif provider == "ollama":
            # For Ollama we'll just try to get a response and parse it
            use_v1 = "/v1" in settings.OLLAMA_BASE_URL
            endpoint = f"{settings.OLLAMA_BASE_URL}/chat/completions" if use_v1 else f"{settings.OLLAMA_BASE_URL}/api/chat"
            model_name = settings.OLLAMA_MODEL if settings.OLLAMA_MODEL else "tinyllama:latest"

            headers = {}
            auth = None
            if settings.OLLAMA_API_KEY:
                if ":" in settings.OLLAMA_API_KEY:
                    user, pwd = settings.OLLAMA_API_KEY.split(":", 1)
                    auth = (user, pwd)
                else:
                    headers["Authorization"] = f"Bearer {settings.OLLAMA_API_KEY}"

            payload = {
                "model": model_name,
                "messages": messages,
                "stream": False,
                "format": "json"
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(endpoint, json=payload, headers=headers, auth=auth, timeout=60.0)
            
            if response.status_code == 200:
                data = response.json()
                if use_v1:
                    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                else:
                    text = data.get("message", {}).get("content", "")
                    
        # Parse the output
        if not text:
            return []
            
        # Clean markdown code blocks if any
        text = text.strip()
        # Find first { and last } to extract JSON
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end+1]
        
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "suggestions" in parsed:
            parsed = parsed["suggestions"]
        if isinstance(parsed, list):
            return [str(q) for q in parsed[:3]]
    except Exception as e:
        print(f"[generate_suggestions] Error: {e}")
        
    return []