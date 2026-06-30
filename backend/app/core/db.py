"""
Database — Neon PostgreSQL connection pool
Provides a reusable async connection pool via asyncpg.
"""
from contextlib import asynccontextmanager

import asyncpg

from app.core.config import get_settings

settings = get_settings()

# Module-level pool (initialized on first use / app startup)
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return (and lazily create) the shared connection pool."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=1,
            max_size=10,
        )
    return _pool


@asynccontextmanager
async def get_conn():
    """Async context manager that yields a single connection from the pool."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


async def close_pool():
    """Gracefully close the pool (call from app shutdown event)."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
