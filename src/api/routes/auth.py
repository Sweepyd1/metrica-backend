# src/api/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from typing import Any

from src.schemas.user import UserCreate, UserOut, UserLogin, Token
from src.core.service.auth import AuthService
from src.api.dependencies import get_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

# Конфигурация кук (вынесите в .env при необходимости)
ACCESS_TOKEN_EXPIRE = 3600  # 1 час
REFRESH_TOKEN_EXPIRE = 86400 * 7  # 7 дней
COOKIE_SECURE = False  # В production True (HTTPS)
COOKIE_SAMESITE = "lax"


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Установка httpOnly кук с токенами"""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_TOKEN_EXPIRE,
    )


def clear_auth_cookies(response: Response) -> None:
    """Удаление кук (выход)"""
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    """Регистрация нового пользователя и автоматический вход"""
    user = await auth_service.register(user_data)
    # Генерируем токены и устанавливаем куки
    tokens = await auth_service.create_tokens(user.id)
    set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return user


@router.post("/login", response_model=UserOut)
async def login(
    login_data: UserLogin,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    """Вход по email и паролю, установка кук"""
    user = await auth_service.authenticate(login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )
    tokens = await auth_service.create_tokens(user.id)
    set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return user


# Альтернативный вход через OAuth2 форму (для совместимости со Swagger UI)
@router.post("/token", response_model=Token)
async def token_login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    """OAuth2 совместимый endpoint для получения токенов (не использует куки)"""
    user = await auth_service.authenticate(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    tokens = await auth_service.create_tokens(user.id)
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
    }


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    """Обновление access токена по refresh токену из куки"""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found",
        )
    new_tokens = await auth_service.refresh_token(refresh_token)
    set_auth_cookies(response, new_tokens["access_token"], new_tokens["refresh_token"])
    return {"message": "Токен обновлён"}


@router.get("/me", response_model=UserOut)
async def get_me(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    """Информация о текущем пользователе по access_token из куки"""
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user = await auth_service.get_user_from_token(access_token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    return user


@router.post("/logout")
async def logout(response: Response) -> dict:
    """Выход – очищаем куки"""
    clear_auth_cookies(response)
    return {"message": "Вы вышли из системы"}
