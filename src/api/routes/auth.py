# src/api/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from typing import Any

from src.config import cfg
from src.schemas.user import (
    PhoneCodeRequest,
    PhoneCodeRequestOut,
    PhoneCodeVerify,
    TelegramMessageAuthComplete,
    TelegramMessageAuthStart,
    TelegramMessageAuthStartOut,
    TelegramMessageAuthStatusOut,
    TelegramLoginRequest,
    Token,
    UserCreate,
    UserLogin,
    UserRole,
    UserOut,
)
from src.core.service.auth import AuthService
from src.api.dependencies import get_auth_service, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


def get_oauth_flow_cookie_name(provider: str) -> str:
    return f"{cfg.auth.oauth_flow_cookie_prefix}_{provider}"


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Установка httpOnly кук с токенами"""
    response.set_cookie(
        key=cfg.auth.access_cookie_name,
        value=access_token,
        httponly=True,
        secure=cfg.auth.cookie_secure,
        samesite=cfg.auth.cookie_samesite,
        max_age=cfg.security.access_token_expire_minutes * 60,
        domain=cfg.auth.cookie_domain,
    )
    response.set_cookie(
        key=cfg.auth.refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=cfg.auth.cookie_secure,
        samesite=cfg.auth.cookie_samesite,
        max_age=cfg.security.refresh_token_expire_days * 86400,
        domain=cfg.auth.cookie_domain,
    )


def clear_auth_cookies(response: Response) -> None:
    """Удаление кук (выход)"""
    response.delete_cookie(cfg.auth.access_cookie_name, domain=cfg.auth.cookie_domain)
    response.delete_cookie(cfg.auth.refresh_cookie_name, domain=cfg.auth.cookie_domain)


def set_oauth_flow_cookie(response: Response, provider: str, flow_token: str) -> None:
    response.set_cookie(
        key=get_oauth_flow_cookie_name(provider),
        value=flow_token,
        httponly=True,
        secure=cfg.auth.cookie_secure,
        samesite=cfg.auth.cookie_samesite,
        max_age=cfg.auth.oauth_flow_ttl_seconds,
        domain=cfg.auth.cookie_domain,
    )


def clear_oauth_flow_cookie(response: Response, provider: str) -> None:
    response.delete_cookie(
        get_oauth_flow_cookie_name(provider),
        domain=cfg.auth.cookie_domain,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    """Регистрация нового пользователя и автоматический вход"""
    user = await auth_service.register_with_password(user_data)
    # Генерируем токены и устанавливаем куки
    tokens = await auth_service.create_tokens(user.id)
    set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return user


@router.post("/register/password", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register_password(
    user_data: UserCreate,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    user = await auth_service.register_with_password(user_data)
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
    user = await auth_service.authenticate_with_password(
        login_data.email, login_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )
    tokens = await auth_service.create_tokens(user.id)
    set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return user


@router.post("/login/password", response_model=UserOut)
async def login_password(
    login_data: UserLogin,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    user = await auth_service.authenticate_with_password(
        login_data.email, login_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
        )
    tokens = await auth_service.create_tokens(user.id)
    set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return user


@router.post("/phone/request-code", response_model=PhoneCodeRequestOut)
async def request_phone_code(
    request_data: PhoneCodeRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> PhoneCodeRequestOut:
    return await auth_service.request_phone_code(request_data)


@router.post("/phone/verify-code", response_model=UserOut)
async def verify_phone_code(
    verify_data: PhoneCodeVerify,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    user = await auth_service.verify_phone_code(verify_data)
    tokens = await auth_service.create_tokens(user.id)
    set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return user


@router.post("/telegram/message/start", response_model=TelegramMessageAuthStartOut)
async def telegram_message_start(
    request_data: TelegramMessageAuthStart,
    auth_service: AuthService = Depends(get_auth_service),
) -> TelegramMessageAuthStartOut:
    return await auth_service.start_telegram_message_auth(request_data)


@router.get(
    "/telegram/message/status/{session_token}",
    response_model=TelegramMessageAuthStatusOut,
)
async def telegram_message_status(
    session_token: str,
    auth_service: AuthService = Depends(get_auth_service),
) -> TelegramMessageAuthStatusOut:
    return await auth_service.get_telegram_message_auth_status(session_token)


@router.post("/telegram/message/complete", response_model=UserOut)
async def telegram_message_complete(
    request_data: TelegramMessageAuthComplete,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    user = await auth_service.complete_telegram_message_auth(request_data)
    tokens = await auth_service.create_tokens(user.id)
    set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return user


@router.post("/telegram/register", response_model=UserOut)
@router.post("/telegram/login", response_model=UserOut)
async def telegram_login(
    login_data: TelegramLoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    user = await auth_service.authenticate_telegram(login_data)
    tokens = await auth_service.create_tokens(user.id)
    set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    return user


@router.get("/oauth/yandex/start")
async def oauth_yandex_start(
    role: UserRole | None = None,
    auth_service: AuthService = Depends(get_auth_service),
) -> RedirectResponse:
    authorize_url, flow_token = auth_service.prepare_yandex_oauth(
        role.value if role else None
    )
    response = RedirectResponse(authorize_url, status_code=status.HTTP_302_FOUND)
    set_oauth_flow_cookie(response, "yandex", flow_token)
    return response


@router.get("/oauth/yandex/callback", response_model=UserOut)
async def oauth_yandex_callback(
    request: Request,
    response: Response,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_description or error,
        )
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yandex OAuth не вернул code",
        )

    flow_token = request.cookies.get(get_oauth_flow_cookie_name("yandex"))
    user = await auth_service.authenticate_yandex_callback(
        code=code,
        state=state,
        flow_token=flow_token,
    )
    tokens = await auth_service.create_tokens(user.id)
    set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    clear_oauth_flow_cookie(response, "yandex")
    return user


@router.get("/oauth/vk/start")
async def oauth_vk_start(
    role: UserRole | None = None,
    auth_service: AuthService = Depends(get_auth_service),
) -> RedirectResponse:
    authorize_url, flow_token = auth_service.prepare_vk_oauth(role.value if role else None)
    response = RedirectResponse(authorize_url, status_code=status.HTTP_302_FOUND)
    set_oauth_flow_cookie(response, "vk", flow_token)
    return response


@router.get("/oauth/vk/callback", response_model=UserOut)
async def oauth_vk_callback(
    request: Request,
    response: Response,
    payload: str | None = None,
    code: str | None = None,
    state: str | None = None,
    device_id: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    auth_service: AuthService = Depends(get_auth_service),
) -> Any:
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_description or error,
        )

    flow_token = request.cookies.get(get_oauth_flow_cookie_name("vk"))
    user = await auth_service.authenticate_vk_callback(
        payload=payload,
        code=code,
        state=state,
        device_id=device_id,
        flow_token=flow_token,
    )
    tokens = await auth_service.create_tokens(user.id)
    set_auth_cookies(response, tokens["access_token"], tokens["refresh_token"])
    clear_oauth_flow_cookie(response, "vk")
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
    refresh_token = request.cookies.get(cfg.auth.refresh_cookie_name)
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
    current_user: Any = Depends(get_current_user),
) -> Any:
    """Информация о текущем пользователе по access_token из куки или Bearer токену"""
    return current_user


@router.post("/logout")
async def logout(response: Response) -> dict:
    """Выход – очищаем куки"""
    clear_auth_cookies(response)
    return {"message": "Вы вышли из системы"}
