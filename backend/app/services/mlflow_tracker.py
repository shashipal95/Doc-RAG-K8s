"""
MLflow Tracker — Non-blocking chat monitoring.

Logs every chat query as an MLflow run with parameters, metrics, and tags.
All logging runs in a background thread so it never blocks the streaming response.
If MLflow is unreachable, the chat continues normally.
"""
import threading
import time
from typing import Optional
from contextlib import contextmanager

import mlflow

from app.core.config import get_settings

settings = get_settings()

_initialized = False


def init_mlflow():
    """Initialize MLflow tracking URI and experiment. Call once at startup."""
    global _initialized
    try:
        mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
        _initialized = True
        print(f"  MLflow tracking    : {settings.MLFLOW_TRACKING_URI}")
        print(f"  MLflow experiment  : {settings.MLFLOW_EXPERIMENT_NAME}")
        
        # Run set_experiment in a daemon thread so it doesn't block FastAPI startup
        def _set_exp():
            for i in range(15):
                try:
                    mlflow.set_experiment(settings.MLFLOW_EXPERIMENT_NAME)
                    print(f"[mlflow] Connected to tracking server and set experiment '{settings.MLFLOW_EXPERIMENT_NAME}'")
                    break
                except Exception as ex:
                    if i == 14:
                        print(f"[mlflow] Failed to connect/set experiment after 15 retries: {ex}")
                    time.sleep(2)
                    
        threading.Thread(target=_set_exp, daemon=True).start()
    except Exception as e:
        print(f"  MLflow tracking    : [ERROR] {e}")
        _initialized = False


@contextmanager
def mlflow_span(name: str, span_type: str = "chain", inputs: dict = None):
    """Context manager for MLflow tracing spans. Safe to use when MLflow is not initialized."""
    global _initialized
    if not _initialized:
        yield None
        return

    try:
        with mlflow.start_span(name=name, span_type=span_type) as span:
            if inputs:
                span.set_inputs(inputs)
            yield span
    except Exception as e:
        print(f"[mlflow] trace span '{name}' error: {e}")
        yield None


def log_chat_query(
    *,
    question: str,
    provider: str,
    query_mode: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    model_name: Optional[str] = None,
    latency_seconds: float = 0.0,
    input_tokens_est: int = 0,
    output_tokens_est: int = 0,
    doc_chunks_used: int = 0,
    response_preview: str = "",
    error: Optional[str] = None,
    embedding_provider: Optional[str] = None,
):
    """
    Log a chat query as an MLflow run in a background thread.

    This is fire-and-forget — it will not block the response or raise
    exceptions to the caller.

    Args:
        question:           The user's question text
        provider:           LLM provider (gemini, groq, openai, ollama)
        query_mode:         One of: rag, web_search, followup, weather_agent, vision
        session_id:         Chat session UUID
        user_id:            User UUID
        model_name:         Specific model used (e.g. gemini-2.5-flash)
        latency_seconds:    Total pipeline latency in seconds
        input_tokens_est:   Estimated input token count (prompt + context)
        output_tokens_est:  Estimated output token count
        doc_chunks_used:    Number of document chunks retrieved
        response_preview:   First ~200 chars of the response
        error:              Error message if the query failed
        embedding_provider: Embedding provider used (e.g. gemini)
    """
    if not _initialized:
        return

    def _log():
        try:
            # Create a user-friendly run name from the question prefix
            clean_q = question.replace("\n", " ").strip()
            trunc_q = clean_q[:25]
            run_name = f"{trunc_q}..." if len(clean_q) > 25 else clean_q
            if not run_name:
                run_name = f"Session {session_id[:8]}" if session_id else "Chat Query"

            with mlflow.start_run(run_name=run_name):
                # ── Parameters (what was requested) ─────────────────────
                mlflow.log_param("provider", provider)
                mlflow.log_param("query_mode", query_mode)
                if model_name:
                    mlflow.log_param("model", model_name)
                if session_id:
                    mlflow.log_param("session_id", session_id[:36])
                if embedding_provider:
                    mlflow.log_param("embedding_provider", embedding_provider)

                # ── Metrics (measurable outcomes) ───────────────────────
                mlflow.log_metric("latency_seconds", round(latency_seconds, 3))
                mlflow.log_metric("input_tokens_est", input_tokens_est)
                mlflow.log_metric("output_tokens_est", output_tokens_est)
                mlflow.log_metric("doc_chunks_used", doc_chunks_used)

                # ── Tags (searchable metadata) ─────────────────────────
                if user_id:
                    mlflow.set_tag("user_id", user_id[:36])
                mlflow.set_tag("question", question[:250])
                if response_preview:
                    mlflow.set_tag("response_preview", response_preview[:250])
                mlflow.set_tag("error", error or "none")

        except Exception as e:
            # Never let MLflow logging crash the application
            print(f"[mlflow] logging failed: {e}")

    thread = threading.Thread(target=_log, daemon=True)
    thread.start()


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    if not text:
        return 0
    return max(1, len(text) // 4)
