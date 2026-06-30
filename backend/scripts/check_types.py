import asyncio

import asyncpg

from app.core.config import get_settings


async def check():
    settings = get_settings()
    conn = await asyncpg.connect(settings.DATABASE_URL)
    rows = await conn.fetch("SELECT filename, file_type FROM user_documents")
    for r in rows:
        print(f"File: {r['filename']} | Type: {r['file_type']}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check())
