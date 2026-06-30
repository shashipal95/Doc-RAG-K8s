# Migration Guide - Old Structure to New Production Structure

## 📋 Overview

Your backend has been reorganized into a production-ready structure following FastAPI best practices.

## 🗑️ Files Removed (No Longer Needed)

### Duplicate/Unnecessary Files
- `main-gemini.py` - Merged into main structure
- `raw_code.py` - Merged into main structure
- `test.py` - Replaced with proper tests in `tests/`
- `streamlit_app.py` - Not needed for backend API
- `database.py` - Replaced with `app/core/security.py`
- `supabase_client.py` - Replaced with httpx calls in auth routes
- `settings.py` - Replaced with `app/core/config.py`

### Reason for Removal
- **Duplication**: You had 3 different versions of the main file
- **Not Production-Ready**: Code was scattered without clear organization
- **Mixing Concerns**: Streamlit UI in backend repo

## ✨ New Structure

```
backend/
├── app/                        # ✅ All application code
│   ├── main.py                 # FastAPI entry point
│   ├── core/                   # ✅ Core utilities
│   │   ├── config.py           # Centralized settings
│   │   └── security.py         # JWT verification
│   ├── api/                    # ✅ API routes
│   │   └── v1/
│   │       ├── router.py       # Main router
│   │       ├── auth.py         # Auth endpoints
│   │       ├── documents.py    # Document operations
│   │       └── health.py       # Health checks
│   ├── services/               # ✅ Business logic
│   │   ├── embeddings.py       # Embedding generation
│   │   ├── vector_store.py     # Pinecone operations
│   │   └── llm.py              # LLM streaming
│   └── models/                 # ✅ Data models
│       └── schemas.py          # Pydantic schemas
├── tests/                      # ✅ Test files
│   └── test_api.py
├── .env.example                # ✅ Environment template
├── .gitignore                  # ✅ Git ignore
├── .dockerignore               # ✅ Docker ignore
├── Dockerfile                  # ✅ Docker config
├── requirements.txt            # ✅ Dependencies
├── pyproject.toml              # ✅ UV config
├── run.sh                      # ✅ Dev startup script
└── README.md                   # ✅ Documentation
```

## 🔄 What Changed

### 1. **Separation of Concerns**

**Before:**
```python
# Everything in main.py - 500+ lines
```

**After:**
```python
# Organized by responsibility
app/main.py          # 50 lines - just app setup
app/core/config.py   # Settings
app/services/llm.py  # LLM logic
app/api/v1/auth.py   # Auth routes
```

### 2. **Configuration Management**

**Before:**
```python
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
# ... scattered throughout files
```

**After:**
```python
# app/core/config.py
class Settings(BaseSettings):
    GEMINI_API_KEY: Optional[str] = None
    PINECONE_API_KEY: str  # Required
    
    class Config:
        env_file = ".env"

# Usage
from app.core.config import get_settings
settings = get_settings()  # Cached singleton
```

### 3. **Security**

**Before:**
```python
# database.py - manual JWT verification
def get_current_user(...):
    # Complex JWT logic
```

**After:**
```python
# app/core/security.py
async def verify_token(...):
    # Clean, async Supabase verification
    
# Usage in routes
@router.get("/protected")
async def protected(user: dict = Depends(verify_token)):
    # Automatic JWT verification
```

### 4. **API Versioning**

**Before:**
```python
@app.post("/upload")
@app.post("/query")
```

**After:**
```python
# app/api/v1/documents.py
router = APIRouter()

@router.post("/upload")  # Becomes /api/v1/upload
@router.post("/query")   # Becomes /api/v1/query
```

### 5. **Service Layer**

**Before:**
```python
# LLM logic mixed with routes
@app.post("/query")
async def query_documents(...):
    # 100+ lines of LLM streaming logic
```

**After:**
```python
# app/services/llm.py
async def generate_stream(prompt, provider):
    # Clean, reusable LLM logic
    
# app/api/v1/documents.py
@router.post("/query")
async def query_documents(...):
    async for chunk in generate_stream(prompt, provider):
        yield chunk
```

## 🚀 How to Migrate

### 1. Replace Your Backend Folder

```bash
# Backup your old backend
mv backend backend_old

# Use new structure
mv backend_new backend

# Copy your .env
cp backend_old/.env backend/.env
```

### 2. Update Import Paths in Frontend (if any direct imports)

**Before:**
```python
from main import some_function
```

**After:**
```python
from app.services.embeddings import get_embedding
```

### 3. Update Docker/Deployment Scripts

**Before:**
```bash
uvicorn main:app
```

**After:**
```bash
uvicorn app.main:app
```

## ✅ Benefits of New Structure

1. **Easier Testing**
   - Services are isolated and testable
   - Mock dependencies easily

2. **Better Scalability**
   - Add new providers without touching existing code
   - Easy to add new features

3. **Clearer Responsibilities**
   - Routes handle HTTP
   - Services handle business logic
   - Core handles configuration

4. **Production Ready**
   - Proper error handling
   - Logging configured
   - Security best practices

5. **Team Friendly**
   - Multiple developers can work on different modules
   - Clear file organization

## 📚 Next Steps

1. Copy `.env.example` to `.env` and fill in credentials
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `./run.sh` or `uvicorn app.main:app --reload`
4. Test: `pytest tests/`
5. Deploy: Use Dockerfile or platform-specific commands

## 🆘 Troubleshooting

### Import Errors

Make sure you're running from the `backend/` directory:
```bash
cd backend
uvicorn app.main:app --reload
```

### Module Not Found

Install dependencies:
```bash
pip install -r requirements.txt
```

### Database Connection Issues

Check your `.env` file has all required variables from `.env.example`

## 📝 Summary

- ✅ Removed 7 unnecessary files
- ✅ Organized code into proper structure
- ✅ Separated concerns (routes, services, config)
- ✅ Added proper testing structure
- ✅ Production-ready with Docker
- ✅ Better documentation

Your backend is now production-ready and follows FastAPI best practices! 🎉
