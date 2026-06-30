import asyncio
import os
import sys

# Add the current directory to path so we can import app
sys.path.append(os.getcwd())

from app.core.db import get_pool


async def migrate_db():
    try:
        pool = await get_pool()
        print("Adding file_content column to user_documents if missing...")
        await pool.execute("ALTER TABLE user_documents ADD COLUMN IF NOT EXISTS file_content BYTEA")
        
        print("Backfilling file_content from disk files...")
        rows = await pool.fetch("SELECT id, file_path FROM user_documents WHERE file_content IS NULL OR LENGTH(file_content) = 0")
        
        uploads_dir = os.path.join(os.getcwd(), "uploads")
        updated_count = 0
        
        for r in rows:
            fpath = r['file_path']
            if fpath.startswith("/uploads/"):
                fname = fpath.replace("/uploads/", "")
                full_path = os.path.join(uploads_dir, fname)
                
                if os.path.exists(full_path):
                    print(f"Reading {fname}...")
                    with open(full_path, "rb") as f:
                        content = f.read()
                        await pool.execute(
                            "UPDATE user_documents SET file_content = $1 WHERE id = $2",
                            content, r['id']
                        )
                        updated_count += 1
                else:
                    print(f"File not found on disk: {full_path}")
        
        print(f"Success! Updated {updated_count} records.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await pool.close()

if __name__ == "__main__":
    asyncio.run(migrate_db())
