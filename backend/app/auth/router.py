from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import service as auth_service
from app.auth.schemas import LoginRequest, LoginResponse, RegisterRequest, TokenResponse
from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.users.models import User
from app.users.schemas import UserOut, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
COOKIE_MAX_AGE = settings.refresh_token_expire_days * 24 * 3600


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.environment != "development",
        samesite="strict",
        max_age=COOKIE_MAX_AGE,
        path="/api/v1/auth/refresh",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path="/api/v1/auth/refresh")


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> dict:
    user = await auth_service.register(db, body.email, body.password, body.full_name, body.phone)
    return {"success": True, "data": UserPublic.model_validate(user).model_dump(), "error": None}


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    access_token, raw_refresh = await auth_service.login(db, body.email, body.password, request)
    _set_refresh_cookie(response, raw_refresh)
    return {
        "success": True,
        "data": {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
        },
        "error": None,
    }


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
) -> dict:
    if not refresh_token:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "NO_REFRESH_TOKEN", "message": "ไม่พบ refresh token"},
        )
    new_access, new_refresh = await auth_service.refresh(db, refresh_token, request)
    _set_refresh_cookie(response, new_refresh)
    return {
        "success": True,
        "data": {
            "access_token": new_access,
            "expires_in": settings.access_token_expire_minutes * 60,
        },
        "error": None,
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(default=None),
    _: User = Depends(get_current_user),
) -> None:
    await auth_service.logout(db, refresh_token)
    _clear_refresh_cookie(response)


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)) -> dict:
    return {"success": True, "data": UserOut.model_validate(current_user).model_dump(), "error": None}
