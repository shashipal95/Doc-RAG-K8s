import asyncio

import asyncpg

from app.core.config import get_settings


async def create_table():
    settings = get_settings()
    conn = await asyncpg.connect(settings.DATABASE_URL)
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                email TEXT PRIMARY KEY,
                token TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL
            )
        """)
        print("Table 'password_reset_tokens' created or already exists.")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(create_table())
