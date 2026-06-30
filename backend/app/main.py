"""
FastAPI Application - Main Entry Point
"""
import os
import sys

# Reconfigure stdout and stderr to use UTF-8 to prevent UnicodeEncodeError on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import nltk

from app.core import db as _db

# Configure NLTK data path to use local directory
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_nltk_data_dir = os.path.join(_backend_dir, "nltk_data")
os.environ["NLTK_DATA"] = _nltk_data_dir
nltk.data.path.insert(0, _nltk_data_dir)
print(f"[NLTK] Set NLTK_DATA to {_nltk_data_dir}")
from app.core.config import get_settings

try:
    from langsmith.middleware import TracingMiddleware
    _langsmith_ok = True
except ImportError:
    _langsmith_ok = False

settings = get_settings()

# These must match the constants in app/services/llm.py
GEMINI_TEXT_MODEL   = "gemini-1.5-flash"
GEMINI_VISION_MODEL = "gemini-1.5-flash"
GROQ_TEXT_MODEL     = "llama-3.3-70b-versatile"
GROQ_VISION_MODEL   = "meta-llama/llama-4-scout-17b-16e-instruct"

app = FastAPI(
    title="DocChat RAG API",
    description="Production RAG API with multi-provider LLM support",
    version="1.0.0",
    docs_url=None,    # Disabled to use custom route below
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "https://rag.shashipal.in",
        "https://doc-rag-ui.vercel.app",
        "https://shashipal.in",
        "https://www.shashipal.in",
        "https://doc-rag.shashipal.in",
        "http://192.168.1.36:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.LANGCHAIN_TRACING_V2 and _langsmith_ok:
    app.add_middleware(TracingMiddleware)

from prometheus_client import make_asgi_app, Counter, Histogram
import time

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests counter",
    ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency histogram",
    ["method", "endpoint"]
)

@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    if request.url.path in ("/metrics", "/health", "/api/v1/health"):
        return await call_next(request)
    
    start_time = time.time()
    method = request.method
    endpoint = request.url.path
    
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as e:
        status_code = 500
        raise e
    finally:
        duration = time.time() - start_time
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status_code).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)
        
    return response

app.mount("/metrics", make_asgi_app())

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

from app.services.mlflow_tracker import init_mlflow

from app.api.v1.auth import router as auth_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.sessions import router as sessions_router

app.include_router(auth_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1/documents")
app.include_router(health_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")

# Serve uploaded chat images (replaces Supabase Storage)
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_uploads_dir = os.path.join(_backend_dir, "uploads")
os.makedirs(_uploads_dir, exist_ok=True)
from fastapi.responses import FileResponse


@app.get("/uploads/{filename}")
async def serve_upload(filename: str):
    # Sanitize filename to prevent directory traversal
    safe_filename = os.path.basename(filename)
    fpath = os.path.join(_uploads_dir, safe_filename)
    if not os.path.exists(fpath):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="File not found")
    
    # Force inline disposition so browsers try to view it instead of downloading
    import mimetypes
    content_type, _ = mimetypes.guess_type(fpath)
    
    return FileResponse(
        fpath, 
        headers={"Content-Disposition": "inline"},
        media_type=content_type or "application/octet-stream"
    )

# Fallback static file serving (keeps compatibility with existing URLs)
app.mount("/uploads", StaticFiles(directory=_uploads_dir), name="uploads")

@app.get("/debug/files")
def debug_files():
    return {
        "uploads_dir": _uploads_dir,
        "exists": os.path.exists(_uploads_dir),
        "files": os.listdir(_uploads_dir) if os.path.exists(_uploads_dir) else []
    }

@app.get("/docs", include_in_schema=False)
async def overridden_swagger_ui():
    res = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - API Docs",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
    )
    # Inject JS into the response body
    custom_js = """
    <script>
    const interval = setInterval(() => {
        const topbar = document.querySelector('.topbar-wrapper');
        
        // 1. Add Login/Signup buttons to topbar
        if (topbar && !document.getElementById('custom-auth-btns')) {
            const container = document.createElement('div');
            container.id = 'custom-auth-btns';
            container.style.cssText = 'display: flex; gap: 10px; margin-left: 20px;';
            const btnStyle = 'padding: 5px 15px; border-radius: 4px; color: white; font-weight: bold; text-decoration: none; cursor: pointer; font-size: 14px; border: none;';
            
            const loginBtn = document.createElement('button');
            loginBtn.innerHTML = 'Login';
            loginBtn.style.cssText = btnStyle + 'background: #4990e2;';
            loginBtn.onclick = () => document.getElementById('operations-Authentication-login').scrollIntoView({behavior: "smooth"});
            
            const signupBtn = document.createElement('button');
            signupBtn.innerHTML = 'Signup';
            signupBtn.style.cssText = btnStyle + 'background: #2ecc71;';
            signupBtn.onclick = () => document.getElementById('operations-Authentication-signup').scrollIntoView({behavior: "smooth"});
            
            container.appendChild(loginBtn);
            container.appendChild(signupBtn);
            topbar.appendChild(container);
        }

        // 2. Add Show/Hide toggle to all password fields
        const passwordInputs = document.querySelectorAll('input[type="password"], input.password-toggle-active');
        passwordInputs.forEach(input => {
            if (input.dataset.hasToggle) return;
            input.dataset.hasToggle = "true";
            
            const toggle = document.createElement('span');
            toggle.innerHTML = '👁️';
            toggle.style.cssText = 'cursor: pointer; margin-left: -30px; z-index: 10; position: relative; user-select: none; filter: grayscale(1);';
            toggle.onclick = () => {
                if (input.type === 'password') {
                    input.type = 'text';
                    input.classList.add('password-toggle-active');
                    toggle.style.filter = 'none';
                } else {
                    input.type = 'password';
                    toggle.style.filter = 'grayscale(1)';
                }
            };
            input.parentNode.insertBefore(toggle, input.nextSibling);
        });
    }, 500);
    </script>
    """
    new_content = res.body.decode().replace("</body>", custom_js + "</body>")
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=new_content)

@app.get("/")
def root():
    return {
        "name": "DocChat RAG API",
        "version": "1.0.0",
        "active_models": {
            "gemini_text": GEMINI_TEXT_MODEL,
            "gemini_vision": GEMINI_VISION_MODEL,
            "groq_text": GROQ_TEXT_MODEL,
            "groq_vision": GROQ_VISION_MODEL,
        },
        "docs": "/docs",
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.on_event("startup")
async def startup_event():
    print("\n" + "=" * 55)
    print("  DocChat RAG API starting...")
    print(f"  Gemini text model  : {GEMINI_TEXT_MODEL}")
    print(f"  Gemini vision model: {GEMINI_VISION_MODEL}")
    print(f"  Groq text model    : {GROQ_TEXT_MODEL}")
    print(f"  Groq vision model  : {GROQ_VISION_MODEL}")
    print(f"  LangSmith tracing  : {settings.LANGCHAIN_TRACING_V2}")
    # Initialise PostgreSQL connection pool
    try:
        db_url = settings.DATABASE_URL
        masked_url = db_url.split("@")[-1] if "@" in db_url else "hidden"
        print(f"  PostgreSQL DB Host : {masked_url}")
        await _db.get_pool()
        print("  PostgreSQL DB Status: [CONNECTED]")
    except Exception as e:
        print(f"  PostgreSQL DB      : [ERROR] {e}")
    # Initialise MLflow tracking
    try:
        init_mlflow()
    except Exception as e:
        print(f"  MLflow tracking    : [ERROR] {e}")
    print("=" * 55 + "\n")

@app.on_event("shutdown")
async def shutdown_event():
    await _db.close_pool()
    print("DocChat shutting down...")