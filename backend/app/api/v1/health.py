"""
Health Routes
Health checks and system status
"""
from fastapi import APIRouter

from app.core.config import get_settings
from app.services.vector_store import get_index_stats

router = APIRouter(tags=["Health"])
settings = get_settings()


@router.get("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "tracing": settings.LANGCHAIN_TRACING_V2,
    }


@router.get("/stats")
async def get_stats():
    """Get Pinecone index statistics"""
    try:
        stats = get_index_stats()
        return {
            "total_vectors": stats.total_vector_count,
            "dimension": stats.dimension,
            "index_fullness": stats.index_fullness,
        }
    except Exception as e:
        return {"error": str(e)}
