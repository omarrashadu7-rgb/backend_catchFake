"""
create_admin.py
───────────────
One-shot script to insert an admin account into MongoDB.
Run from the project root:
    python create_admin.py
"""

import asyncio
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI    = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB     = os.getenv("MONGO_DB_NAME", "deepfake_db")

# ── Admin credentials — change before running ──────────────────────────────────
ADMIN_NAME     = "Admin"
ADMIN_EMAIL    = "admin@catchfake.com"
ADMIN_PASSWORD = "Admin@1234"
# ──────────────────────────────────────────────────────────────────────────────

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_admin():
    client = AsyncIOMotorClient(MONGO_URI)
    db     = client[MONGO_DB]
    users  = db["users"]

    email = ADMIN_EMAIL.strip().lower()

    existing = await users.find_one({"email": email})
    if existing:
        # If account exists but isn't admin, promote it
        if existing.get("role") != "admin":
            await users.update_one({"email": email}, {"$set": {"role": "admin"}})
            print(f"[OK]  Existing user '{email}' promoted to admin.")
        else:
            print(f"[INFO] Admin account '{email}' already exists. Nothing to do.")
        client.close()
        return

    doc = {
        "name":               ADMIN_NAME,
        "email":              email,
        "hashed_password":    _pwd_ctx.hash(ADMIN_PASSWORD),
        "role":               "admin",
        "refresh_token_hash": None,
        "created_at":         datetime.now(timezone.utc),
    }

    result = await users.insert_one(doc)
    print(f"[OK]  Admin account created successfully!")
    print(f"    ID       : {result.inserted_id}")
    print(f"    Email    : {email}")
    print(f"    Password : {ADMIN_PASSWORD}")
    print(f"    Role     : admin")

    client.close()


if __name__ == "__main__":
    asyncio.run(create_admin())
