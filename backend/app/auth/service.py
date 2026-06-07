from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.security.jwt import (
    create_access_token,
    create_refresh_token,
    hash_token,
)
from app.security.password import hash_password, verify_password
from app.users import repository as user_repo
from app.users.models import User


async def register(
    db: AsyncSession,
    email: str,
    password: str,
    full_name: str,
    phone: str | None,
) -> User:
    existing = await user_repo.get_user_by_email(db, email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "EMAIL_ALREADY_EXISTS",
                "message": "อีเมลนี้ถูกใช้งานแล้ว",
            },
        )
    return await user_repo.create_user(db, email, hash_password(password), full_name, phone)


async def login(
    db: AsyncSession,
    email: str,
    password: str,
    request: Request,
) -> tuple[str, str]:
    user = await user_repo.get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "อีเมลหรือรหัสผ่านไม่ถูกต้อง"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCOUNT_DISABLED", "message": "บัญชีนี้ถูกระงับการใช้งาน"},
        )

    access_token = create_access_token(str(user.id), user.email, user.role)
    raw_refresh = create_refresh_token()
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)

    await user_repo.save_refresh_token(
        db,
        user_id=str(user.id),
        token_hash=hash_token(raw_refresh),
        expires_at=expires_at,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    return access_token, raw_refresh


async def refresh(db: AsyncSession, raw_refresh: str, request: Request) -> tuple[str, str]:
    token_hash = hash_token(raw_refresh)
    rt = await user_repo.get_refresh_token(db, token_hash)

    if not rt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_REFRESH_TOKEN", "message": "Refresh token ไม่ถูกต้องหรือหมดอายุ"},
        )

    user = await user_repo.get_user_by_id(db, str(rt.user_id))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "ไม่ได้รับอนุญาต"},
        )

    await user_repo.revoke_refresh_token(db, token_hash)

    new_access = create_access_token(str(user.id), user.email, user.role)
    new_refresh = create_refresh_token()
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)

    await user_repo.save_refresh_token(
        db,
        user_id=str(user.id),
        token_hash=hash_token(new_refresh),
        expires_at=expires_at,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    return new_access, new_refresh


async def logout(db: AsyncSession, raw_refresh: str | None) -> None:
    if raw_refresh:
        await user_repo.revoke_refresh_token(db, hash_token(raw_refresh))
