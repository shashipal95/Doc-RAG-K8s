import asyncio

import bcrypt

from app.core.config import get_settings
from app.core.db import get_conn


async def create_demo_user():
    settings = get_settings()
    email = "demo@shashipal.in"
    password = "demouser123"
    full_name = "Demo User"
    
    print(f"Creating demo user: {email}")
    
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    
    async with get_conn() as conn:
        # Check if exists
        existing = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
        if existing:
            print("Demo user already exists.")
            return
        
        await conn.execute(
            "INSERT INTO users (email, password_hash, full_name) VALUES ($1, $2, $3)",
            email, hashed, full_name
        )
        print("Demo user created successfully!")

if __name__ == "__main__":
    asyncio.run(create_demo_user())
