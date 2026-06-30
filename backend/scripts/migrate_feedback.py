import asyncio
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not set in .env")
        return

    print("Connecting to Neon DB...")
    conn = await asyncpg.connect(dsn=url)
    print("Connected!")

    print("Adding feedback column to chat_messages...")
    try:
        await conn.execute("""
            ALTER TABLE chat_messages 
            ADD COLUMN IF NOT EXISTS feedback TEXT CHECK (feedback IN ('up', 'down'));
        """)
        print("Column added successfully!")
    except Exception as e:
        print(f"Error: {e}")

    await conn.close()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
