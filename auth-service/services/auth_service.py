from datetime import datetime, timedelta
from typing import Optional
import secrets
import hashlib
import base64

import bcrypt
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from auth_service.config import settings
from auth_service.models.user import User, VerificationCode


def _prepare(password: str) -> bytes:
    """SHA-256 pre-hash to handle bcrypt's 72-byte limit."""
    return base64.b64encode(hashlib.sha256(password.encode()).digest())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(_prepare(plain_password), hashed_password.encode())


def create_access_token(user_id: int, email: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "email": email, "type": "access", "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "type": "refresh", "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def generate_verification_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession, email: str, username: str, full_name: str, password: str
) -> User:
    user = User(
        email=email,
        username=username,
        full_name=full_name,
        password_hash=hash_password(password),
    )
    db.add(user)
    await db.flush()
    return user


async def save_verification_code(db: AsyncSession, email: str, code: str) -> VerificationCode:
    vc = VerificationCode(
        email=email,
        code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(vc)
    await db.flush()
    return vc


async def verify_code(db: AsyncSession, email: str, code: str) -> bool:
    result = await db.execute(
        select(VerificationCode)
        .where(
            VerificationCode.email == email,
            VerificationCode.code == code,
            VerificationCode.is_used == False,  # noqa: E712
            VerificationCode.expires_at > datetime.utcnow(),
        )
        .order_by(VerificationCode.created_at.desc())
    )
    vc = result.scalar_one_or_none()
    if vc:
        vc.is_used = True
        return True
    return False
