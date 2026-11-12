"""Run from repository root: python scripts/promote-admin.py EMAIL
Requires backend dependencies installed and DATABASE_URL accessible.
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sqlalchemy import select
from app.core.db import Session
from app.models.entities import User

async def run(email):
    async with Session() as db:
        user = await db.scalar(select(User).where(User.email == email.lower()))
        if user is None: raise SystemExit("Account not found; register it before promotion")
        user.role = "admin"
        await db.commit()
        print("Admin role granted to", user.id)

if __name__ == "__main__":
    if len(sys.argv) != 2: raise SystemExit("Usage: python scripts/promote-admin.py EMAIL")
    asyncio.run(run(sys.argv[1]))
