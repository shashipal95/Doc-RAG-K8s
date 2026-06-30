import asyncio
import os

import asyncpg
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

async def create_table():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment.")
        return

    print("Connecting to database...")
    conn = await asyncpg.connect(database_url)
    try:
        print("Creating table 'document_view_tokens'...")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS document_view_tokens (
                token TEXT PRIMARY KEY,
                doc_id UUID NOT NULL,
                user_id TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        print("Table 'document_view_tokens' created or already exists.")
    except Exception as e:
        print(f"Error creating table: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(create_table())
