import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

async def main():
    dsn = os.getenv("DATABASE_URL")
    print(f"Connecting to database: {dsn}")
    conn = await asyncpg.connect(dsn)
    try:
        rows = await conn.fetch("SELECT id, email, password_hash, full_name, role, created_at FROM users")
        print(f"Found {len(rows)} users:")
        for r in rows:
            print(f"- ID: {r['id']}, Email: {r['email']}, Hashed: {r['password_hash']}, Name: {r['full_name']}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
