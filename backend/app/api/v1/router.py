"""
API Router
Combines all v1 endpoint routers
"""
from fastapi import APIRouter

from app.api.v1 import auth, documents, health

api_router = APIRouter()

# Auth routes at root level (no /api/v1 prefix) to match frontend
# Frontend expects: /auth/login, /auth/signup, etc.
api_router.include_router(auth.router, tags=["Authentication"])

# Other routes under /api/v1
api_router.include_router(documents.router, tags=["Documents"])
api_router.include_router(health.router, tags=["Health"])
