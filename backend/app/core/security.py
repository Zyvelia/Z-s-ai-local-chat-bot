from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.db import get_db
from app.models.entities import User

pwd = PasswordHash.recommended()
bearer = HTTPBearer()

def hash_password(password: str) -> str:
    return pwd.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd.verify(password, hashed)

def create_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=12)}, settings.jwt_secret, algorithm="HS256")

async def authenticated_user(
    auth: HTTPAuthorizationCredentials = Depends(bearer), db: AsyncSession = Depends(get_db)
) -> User:
    try:
        payload = jwt.decode(auth.credentials, settings.jwt_secret, algorithms=["HS256"])
        user_id = payload["sub"]
    except (jwt.InvalidTokenError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user

async def current_user(user: User = Depends(authenticated_user)) -> User:
    if user.is_suspended and (user.suspended_until is None or user.suspended_until > datetime.now(timezone.utc)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account suspended")
    return user
