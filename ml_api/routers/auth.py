from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr
from datetime import datetime

from ml_api.database import get_db
from ml_api.services import auth_service
from ml_api.services.email_service import send_verification_email
from ml_api.dependencies import get_current_user
from ml_api.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    full_name: str
    password: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ResendCodeRequest(BaseModel):
    email: EmailStr


def _user_response(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
    }


@router.post("/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await auth_service.get_user_by_email(db, req.email)

    if existing and existing.is_verified:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")

    if existing and not existing.is_verified:
        code = auth_service.generate_verification_code()
        await auth_service.save_verification_code(db, req.email, code)
        try:
            await send_verification_email(req.email, code)
        except Exception:
            raise HTTPException(status_code=500, detail="Ошибка отправки письма")
        return {"status": "success", "message": "Код подтверждения отправлен повторно"}

    await auth_service.create_user(db, req.email, req.username, req.full_name, req.password)
    code = auth_service.generate_verification_code()
    await auth_service.save_verification_code(db, req.email, code)

    try:
        await send_verification_email(req.email, code)
    except Exception:
        raise HTTPException(
            status_code=500, detail="Ошибка отправки письма. Проверьте настройки SMTP."
        )

    return {"status": "success", "message": "Код подтверждения отправлен на почту"}


@router.post("/verify-email")
async def verify_email(req: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    valid = await auth_service.verify_code(db, req.email, req.code)
    if not valid:
        raise HTTPException(status_code=400, detail="Неверный или истёкший код")

    user = await auth_service.get_user_by_email(db, req.email)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user.is_verified = True

    access_token = auth_service.create_access_token(user.id, user.email)
    refresh_token = auth_service.create_refresh_token(user.id)

    return {
        "status": "success",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": _user_response(user),
    }


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.get_user_by_email(db, req.email)
    if not user or not auth_service.verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    if not user.is_verified:
        code = auth_service.generate_verification_code()
        await auth_service.save_verification_code(db, req.email, code)
        try:
            await send_verification_email(req.email, code)
        except Exception:
            pass
        raise HTTPException(
            status_code=403, detail="Email не подтверждён. Код отправлен повторно."
        )

    user.last_login = datetime.utcnow()

    access_token = auth_service.create_access_token(user.id, user.email)
    refresh_token = auth_service.create_refresh_token(user.id)

    return {
        "status": "success",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": _user_response(user),
    }


@router.post("/refresh")
async def refresh_token(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = auth_service.decode_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Невалидный refresh токен")

    user = await auth_service.get_user_by_id(db, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    new_access = auth_service.create_access_token(user.id, user.email)
    return {"status": "success", "access_token": new_access}


@router.post("/resend-code")
async def resend_code(req: ResendCodeRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.get_user_by_email(db, req.email)
    if not user:
        return {"status": "success", "message": "Если email зарегистрирован, код будет отправлен"}

    code = auth_service.generate_verification_code()
    await auth_service.save_verification_code(db, req.email, code)

    try:
        await send_verification_email(req.email, code)
    except Exception:
        raise HTTPException(status_code=500, detail="Ошибка отправки письма")

    return {"status": "success", "message": "Код подтверждения отправлен"}


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
    return {"status": "success", "user": _user_response(user)}
