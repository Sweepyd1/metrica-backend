# src/core/services/auth.py
import asyncio
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import logging
import re
import secrets
from typing import Any, Optional
from urllib.parse import parse_qsl, urlencode, unquote

import httpx
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    AuthIdentity,
    AuthProvider,
    PhoneAuthCode,
    TelegramAuthSession,
    User,
    UserRole,
)
from src.config import cfg
from src.core.repositories.auth_identity import AuthIdentityRepository
from src.core.repositories.phone_auth_code import PhoneAuthCodeRepository
from src.core.repositories.telegram_auth_session import TelegramAuthSessionRepository
from src.core.repositories.user import UserRepository
from src.schemas.user import (
    PhoneCodeRequest,
    PhoneCodeRequestOut,
    PhoneCodeVerify,
    TelegramAuthData,
    TelegramMessageAuthComplete,
    TelegramMessageAuthStart,
    TelegramMessageAuthStartOut,
    TelegramMessageAuthStatus,
    TelegramMessageAuthStatusOut,
    TelegramLoginRequest,
    UserCreate,
    UserLogin,
    TokenPayload,
)

# Настройка хеширования паролей
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    bcrypt__rounds=cfg.security.bcrypt_rounds,
)

logger = logging.getLogger(__name__)


class AuthService:
    _telegram_updates_offset: int | None = None
    _telegram_updates_lock: asyncio.Lock | None = None
    _telegram_polling_ready: bool = False

    def __init__(
        self,
        session: AsyncSession,
        user_repo: UserRepository,
        identity_repo: AuthIdentityRepository,
        phone_code_repo: PhoneAuthCodeRepository,
        telegram_auth_session_repo: TelegramAuthSessionRepository,
    ):
        self.session = session
        self.user_repo = user_repo
        self.identity_repo = identity_repo
        self.phone_code_repo = phone_code_repo
        self.telegram_auth_session_repo = telegram_auth_session_repo

    async def commit_and_refresh(self, *instances: object) -> None:
        await self.session.commit()
        for instance in instances:
            if instance is not None:
                await self.session.refresh(instance)

    # ---------- Хеширование ----------
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        if not hashed_password:
            return False
        # bcrypt ограничен 72 байтами
        if isinstance(plain_password, str):
            plain_password = plain_password.encode("utf-8")[:72].decode(
                "utf-8", errors="ignore"
            )
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        if isinstance(password, str):
            password = password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
        return pwd_context.hash(password)

    def normalize_email(self, email: str) -> str:
        return email.strip().lower()

    def normalize_phone(self, phone: str) -> str:
        digits = re.sub(r"\D", "", phone)
        if not 10 <= len(digits) <= 15:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Некорректный номер телефона",
            )
        return f"+{digits}"

    def generate_phone_code(self) -> str:
        code_length = cfg.auth.phone_code_length
        return f"{secrets.randbelow(10**code_length):0{code_length}d}"

    def hash_phone_code(self, phone: str, code: str) -> str:
        return hashlib.sha256(
            f"{cfg.security.jwt_secret_key}:{phone}:{code}".encode("utf-8")
        ).hexdigest()

    def create_oauth_flow_state(self) -> str:
        return secrets.token_urlsafe(32)

    def create_pkce_code_verifier(self) -> str:
        return secrets.token_urlsafe(48)

    def build_pkce_code_challenge(self, code_verifier: str) -> str:
        digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")

    def current_utc_timestamp(self) -> int:
        return int(datetime.now(timezone.utc).timestamp())

    def create_oauth_flow_token(
        self,
        *,
        provider: AuthProvider,
        state: str,
        role: str | None,
        code_verifier: str,
    ) -> str:
        expire_ts = self.current_utc_timestamp() + cfg.auth.oauth_flow_ttl_seconds
        payload = {
            "type": "oauth_flow",
            "provider": provider.value,
            "state": state,
            "role": role,
            "code_verifier": code_verifier,
            "exp": expire_ts,
        }
        return jwt.encode(
            payload,
            cfg.security.jwt_secret_key,
            algorithm=cfg.security.jwt_algorithm,
        )

    def decode_oauth_flow_token(
        self,
        flow_token: str | None,
        provider: AuthProvider,
    ) -> dict[str, Any]:
        if not flow_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth-сессия не найдена. Начните авторизацию заново.",
            )
        try:
            payload = jwt.decode(
                flow_token,
                cfg.security.jwt_secret_key,
                algorithms=[cfg.security.jwt_algorithm],
            )
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth-сессия истекла или повреждена. Начните авторизацию заново.",
            ) from exc

        if payload.get("type") != "oauth_flow":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Некорректный тип OAuth-сессии",
            )
        if payload.get("provider") != provider.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OAuth-сессия относится к другому провайдеру",
            )
        return payload

    def clean_text(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = value.strip()
        return cleaned or None

    def safe_normalize_email(self, email: Any) -> str | None:
        cleaned = self.clean_text(email)
        if not cleaned:
            return None
        return self.normalize_email(cleaned)

    def safe_normalize_phone(self, phone: Any) -> str | None:
        cleaned = self.clean_text(phone)
        if not cleaned:
            return None
        try:
            return self.normalize_phone(cleaned)
        except HTTPException:
            return None

    def split_full_name(self, value: str | None) -> tuple[str | None, str | None]:
        cleaned = self.clean_text(value)
        if not cleaned:
            return None, None
        parts = [part for part in cleaned.split() if part]
        if not parts:
            return None, None
        if len(parts) == 1:
            return parts[0], None
        return parts[0], " ".join(parts[1:])

    def pick_first_non_empty_str(self, *values: Any) -> str | None:
        for value in values:
            cleaned = self.clean_text(value)
            if cleaned:
                return cleaned
        return None

    def extract_email_from_value(self, value: Any) -> str | None:
        if isinstance(value, str):
            return self.safe_normalize_email(value)
        if isinstance(value, dict):
            for key in ("email", "value", "address"):
                email = self.extract_email_from_value(value.get(key))
                if email:
                    return email
            return None
        if isinstance(value, list):
            for item in value:
                email = self.extract_email_from_value(item)
                if email:
                    return email
        return None

    def extract_phone_from_value(self, value: Any) -> str | None:
        if isinstance(value, str):
            return self.safe_normalize_phone(value)
        if isinstance(value, dict):
            for key in ("number", "phone", "value"):
                phone = self.extract_phone_from_value(value.get(key))
                if phone:
                    return phone
            return None
        if isinstance(value, list):
            for item in value:
                phone = self.extract_phone_from_value(item)
                if phone:
                    return phone
        return None

    async def request_provider_json(
        self,
        method: str,
        url: str,
        *,
        provider_name: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=cfg.auth.oauth_http_timeout_seconds
            ) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            logger.exception("OAuth request to %s failed", provider_name)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Не удалось связаться с {provider_name}",
            ) from exc

        try:
            payload = response.json()
        except ValueError:
            payload = None

        if response.is_error:
            detail: str | None = None
            if isinstance(payload, dict):
                detail = self.pick_first_non_empty_str(
                    payload.get("error_description"),
                    payload.get("error_msg"),
                    payload.get("error"),
                )
            if not detail:
                detail = self.clean_text(response.text) or "ошибка провайдера"
            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                    if 400 <= response.status_code < 500
                    else status.HTTP_502_BAD_GATEWAY
                ),
                detail=f"{provider_name}: {detail}",
            )

        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"{provider_name}: неожиданный формат ответа",
            )
        return payload

    def ensure_yandex_configured(self) -> None:
        if not cfg.auth.yandex_client_id or not cfg.auth.yandex_redirect_uri:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Yandex OAuth не настроен. Проверьте AUTH_YANDEX_CLIENT_ID и AUTH_YANDEX_REDIRECT_URI.",
            )

    def ensure_vk_configured(self) -> None:
        if not cfg.auth.vk_client_id or not cfg.auth.vk_redirect_uri:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="VK ID не настроен. Проверьте AUTH_VK_CLIENT_ID и AUTH_VK_REDIRECT_URI.",
            )

    def prepare_yandex_oauth(self, role: str | None) -> tuple[str, str]:
        self.ensure_yandex_configured()
        state = self.create_oauth_flow_state()
        code_verifier = self.create_pkce_code_verifier()
        code_challenge = self.build_pkce_code_challenge(code_verifier)
        params = {
            "response_type": "code",
            "client_id": cfg.auth.yandex_client_id,
            "redirect_uri": cfg.auth.yandex_redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if cfg.auth.yandex_scope.strip():
            params["scope"] = cfg.auth.yandex_scope.strip()

        flow_token = self.create_oauth_flow_token(
            provider=AuthProvider.YANDEX,
            state=state,
            role=role,
            code_verifier=code_verifier,
        )
        return f"{cfg.auth.yandex_authorize_url}?{urlencode(params)}", flow_token

    def prepare_vk_oauth(self, role: str | None) -> tuple[str, str]:
        self.ensure_vk_configured()
        state = self.create_oauth_flow_state()
        code_verifier = self.create_pkce_code_verifier()
        code_challenge = self.build_pkce_code_challenge(code_verifier)
        params = {
            "response_type": "code",
            "client_id": cfg.auth.vk_client_id,
            "redirect_uri": cfg.auth.vk_redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        if cfg.auth.vk_scope.strip():
            params["scope"] = cfg.auth.vk_scope.strip()

        flow_token = self.create_oauth_flow_token(
            provider=AuthProvider.VK,
            state=state,
            role=role,
            code_verifier=code_verifier,
        )
        return f"{cfg.auth.vk_authorize_url}?{urlencode(params)}", flow_token

    def build_user_name(
        self,
        *,
        first_name: Any = None,
        last_name: Any = None,
        display_name: Any = None,
        full_name: Any = None,
        login: Any = None,
        email: str | None = None,
    ) -> tuple[str, str | None]:
        normalized_first = self.clean_text(first_name)
        normalized_last = self.clean_text(last_name)

        if not normalized_first:
            split_first, split_last = self.split_full_name(self.clean_text(full_name))
            normalized_first = split_first
            if not normalized_last:
                normalized_last = split_last

        if not normalized_first:
            split_first, split_last = self.split_full_name(self.clean_text(display_name))
            normalized_first = split_first
            if not normalized_last:
                normalized_last = split_last

        if not normalized_first:
            normalized_first = self.pick_first_non_empty_str(login)

        if not normalized_first and email:
            normalized_first = email.split("@", 1)[0]

        return normalized_first or "Пользователь", normalized_last

    async def exchange_yandex_code(
        self,
        *,
        code: str,
        code_verifier: str,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": cfg.auth.yandex_client_id,
            "redirect_uri": cfg.auth.yandex_redirect_uri,
            "code_verifier": code_verifier,
        }
        if cfg.auth.yandex_client_secret:
            data["client_secret"] = cfg.auth.yandex_client_secret
        return await self.request_provider_json(
            "POST",
            cfg.auth.yandex_token_url,
            provider_name="Yandex OAuth",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    async def fetch_yandex_user_info(self, access_token: str) -> dict[str, Any]:
        return await self.request_provider_json(
            "GET",
            cfg.auth.yandex_user_info_url,
            provider_name="Yandex ID",
            params={"format": "json"},
            headers={"Authorization": f"OAuth {access_token}"},
        )

    async def exchange_vk_code(
        self,
        *,
        code: str,
        state: str,
        device_id: str,
        code_verifier: str,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "grant_type": "authorization_code",
            "redirect_uri": cfg.auth.vk_redirect_uri,
            "client_id": cfg.auth.vk_client_id,
            "code_verifier": code_verifier,
            "state": state,
            "device_id": device_id,
        }
        if cfg.auth.vk_client_secret:
            params["client_secret"] = cfg.auth.vk_client_secret
        return await self.request_provider_json(
            "POST",
            cfg.auth.vk_token_url,
            provider_name="VK ID",
            params=params,
            data={"code": code},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    async def fetch_vk_user_info(self, access_token: str) -> dict[str, Any]:
        return await self.request_provider_json(
            "POST",
            cfg.auth.vk_user_info_url,
            provider_name="VK ID",
            params={"client_id": cfg.auth.vk_client_id},
            data={"access_token": access_token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    def parse_vk_callback_payload(
        self,
        *,
        payload: str | None,
        code: str | None,
        state: str | None,
        device_id: str | None,
    ) -> dict[str, str]:
        parsed_payload: dict[str, Any] = {}

        if payload:
            for candidate in (payload, unquote(payload)):
                try:
                    parsed_candidate = json.loads(candidate)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed_candidate, dict):
                    parsed_payload = parsed_candidate
                    break
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="VK ID вернул payload в неожиданном формате",
                )

        if code:
            parsed_payload.setdefault("code", code)
        if state:
            parsed_payload.setdefault("state", state)
        if device_id:
            parsed_payload.setdefault("device_id", device_id)

        provider_error = self.pick_first_non_empty_str(
            parsed_payload.get("error_description"),
            parsed_payload.get("error"),
        )
        if provider_error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"VK ID: {provider_error}",
            )

        result = {
            "code": str(parsed_payload.get("code") or ""),
            "state": str(parsed_payload.get("state") or ""),
            "device_id": str(parsed_payload.get("device_id") or ""),
        }
        if not all(result.values()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="VK ID не вернул code, state или device_id",
            )
        return result

    @classmethod
    def get_telegram_updates_lock(cls) -> asyncio.Lock:
        if cls._telegram_updates_lock is None:
            cls._telegram_updates_lock = asyncio.Lock()
        return cls._telegram_updates_lock

    def ensure_telegram_message_auth_configured(self) -> tuple[str, str]:
        bot_token = self.clean_text(cfg.auth.telegram_bot_token)
        bot_username = self.clean_text(cfg.auth.telegram_bot_username)
        if not bot_token or not bot_username:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Telegram-бот не настроен. Проверьте AUTH_TELEGRAM_BOT_TOKEN "
                    "и AUTH_TELEGRAM_BOT_USERNAME."
                ),
            )
        return bot_token, bot_username

    def generate_telegram_message_auth_code(self) -> str:
        code_length = cfg.auth.telegram_message_code_length
        return f"{secrets.randbelow(10**code_length):0{code_length}d}"

    def build_telegram_message_auth_url(self, bot_username: str, session_token: str) -> str:
        return f"https://t.me/{bot_username}?start=auth_{session_token}"

    def get_telegram_message_session_status(
        self,
        session: TelegramAuthSession,
    ) -> TelegramMessageAuthStatus:
        now = datetime.utcnow()
        if session.completed_at is not None:
            return TelegramMessageAuthStatus.COMPLETED
        if session.confirmed_at is not None:
            return TelegramMessageAuthStatus.CONFIRMED
        if session.expires_at <= now:
            return TelegramMessageAuthStatus.EXPIRED
        return TelegramMessageAuthStatus.PENDING

    def build_telegram_message_auth_status_out(
        self,
        session: TelegramAuthSession,
    ) -> TelegramMessageAuthStatusOut:
        return TelegramMessageAuthStatusOut(
            status=self.get_telegram_message_session_status(session),
            expires_at=session.expires_at,
            confirmed_at=session.confirmed_at,
            completed_at=session.completed_at,
            telegram_username=session.telegram_username,
            telegram_first_name=session.telegram_first_name,
        )

    async def request_telegram_api(
        self,
        method: str,
        *,
        data: dict[str, Any] | None = None,
    ) -> Any:
        bot_token, _ = self.ensure_telegram_message_auth_configured()
        url = (
            f"{cfg.auth.telegram_api_base_url.rstrip('/')}/bot{bot_token}/{method}"
        )
        try:
            async with httpx.AsyncClient(
                timeout=cfg.auth.oauth_http_timeout_seconds
            ) as client:
                response = await client.post(url, json=data)
        except httpx.HTTPError as exc:
            logger.exception("Telegram Bot API request %s failed", method)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Не удалось связаться с Telegram Bot API",
            ) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Telegram Bot API вернул неожиданный ответ",
            ) from exc

        if response.is_error or not payload.get("ok"):
            detail = self.pick_first_non_empty_str(
                payload.get("description"),
                payload.get("error"),
            )
            raise HTTPException(
                status_code=(
                    status.HTTP_400_BAD_REQUEST
                    if 400 <= response.status_code < 500
                    else status.HTTP_502_BAD_GATEWAY
                ),
                detail=detail or "Ошибка Telegram Bot API",
            )
        return payload.get("result")

    async def ensure_telegram_polling_mode(self) -> None:
        if self.__class__._telegram_polling_ready:
            return
        await self.request_telegram_api(
            "deleteWebhook",
            data={"drop_pending_updates": False},
        )
        self.__class__._telegram_polling_ready = True

    async def send_telegram_bot_message(self, chat_id: str, text: str) -> None:
        try:
            await self.request_telegram_api(
                "sendMessage",
                data={
                    "chat_id": chat_id,
                    "text": text,
                },
            )
        except HTTPException:
            logger.exception("Failed to send Telegram bot message to %s", chat_id)

    async def handle_telegram_auth_confirmation(
        self,
        session: TelegramAuthSession,
        *,
        chat_id: str,
        user_data: dict[str, Any],
    ) -> None:
        now = datetime.utcnow()
        session.telegram_user_id = str(user_data.get("id"))
        session.telegram_chat_id = chat_id
        session.telegram_username = self.clean_text(user_data.get("username"))
        session.telegram_first_name = self.clean_text(user_data.get("first_name"))
        session.telegram_last_name = self.clean_text(user_data.get("last_name"))
        if session.confirmed_at is None:
            session.confirmed_at = now

    async def process_telegram_message_update(self, update: dict[str, Any]) -> bool:
        message = update.get("message")
        if not isinstance(message, dict):
            return False

        chat = message.get("chat")
        from_user = message.get("from")
        text = self.clean_text(message.get("text"))
        if (
            not isinstance(chat, dict)
            or not isinstance(from_user, dict)
            or not text
            or chat.get("type") != "private"
        ):
            return False

        chat_id = str(chat.get("id"))
        normalized_text = text.strip()
        session: TelegramAuthSession | None = None

        if normalized_text.startswith("/start"):
            parts = normalized_text.split(maxsplit=1)
            payload = parts[1].strip() if len(parts) > 1 else ""
            if payload.startswith("auth_"):
                session = await self.telegram_auth_session_repo.get_active_by_session_token(
                    payload[5:]
                )
        else:
            match = re.search(
                rf"\b\d{{{cfg.auth.telegram_message_code_length}}}\b", normalized_text
            )
            if match:
                session = (
                    await self.telegram_auth_session_repo.get_active_by_confirmation_code(
                        match.group(0)
                    )
                )

        if not session:
            await self.send_telegram_bot_message(
                chat_id,
                (
                    "Не нашёл активного входа. Вернитесь на сайт, нажмите "
                    "'Продолжить через Telegram' и отправьте новый код."
                ),
            )
            return False

        await self.handle_telegram_auth_confirmation(
            session,
            chat_id=chat_id,
            user_data=from_user,
        )
        await self.send_telegram_bot_message(
            chat_id,
            "Подтверждение получено. Возвращайтесь на сайт, вход уже почти готов.",
        )
        return True

    async def sync_telegram_updates(self) -> None:
        self.ensure_telegram_message_auth_configured()
        lock = self.get_telegram_updates_lock()
        async with lock:
            await self.ensure_telegram_polling_mode()
            updates = await self.request_telegram_api(
                "getUpdates",
                data={
                    "offset": self.__class__._telegram_updates_offset,
                    "limit": 100,
                    "timeout": 0,
                    "allowed_updates": ["message"],
                },
            )

            if not isinstance(updates, list):
                return

            has_changes = False
            last_update_id: int | None = None
            for update in updates:
                if not isinstance(update, dict):
                    continue
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    last_update_id = update_id
                if await self.process_telegram_message_update(update):
                    has_changes = True

            if last_update_id is not None:
                self.__class__._telegram_updates_offset = last_update_id + 1

            if has_changes:
                await self.session.commit()

    async def start_telegram_message_auth(
        self,
        request_data: TelegramMessageAuthStart,
    ) -> TelegramMessageAuthStartOut:
        _, bot_username = self.ensure_telegram_message_auth_configured()
        now = datetime.utcnow()

        for _ in range(10):
            confirmation_code = self.generate_telegram_message_auth_code()
            existing_session = (
                await self.telegram_auth_session_repo.get_active_by_confirmation_code(
                    confirmation_code
                )
            )
            if existing_session is None:
                break
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось сгенерировать код Telegram. Попробуйте ещё раз.",
            )

        session_token = secrets.token_urlsafe(24)
        session = TelegramAuthSession(
            session_token=session_token,
            confirmation_code=confirmation_code,
            role=UserRole(request_data.role.value),
            expires_at=now
            + timedelta(seconds=cfg.auth.telegram_message_auth_ttl_seconds),
        )
        self.session.add(session)
        await self.commit_and_refresh(session)
        return TelegramMessageAuthStartOut(
            session_token=session.session_token,
            confirmation_code=session.confirmation_code,
            bot_username=bot_username,
            bot_url=self.build_telegram_message_auth_url(
                bot_username, session.session_token
            ),
            expires_in_seconds=cfg.auth.telegram_message_auth_ttl_seconds,
        )

    async def get_telegram_message_auth_status(
        self,
        session_token: str,
    ) -> TelegramMessageAuthStatusOut:
        await self.sync_telegram_updates()
        session = await self.telegram_auth_session_repo.get_by_session_token(session_token)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Telegram-сессия не найдена",
            )
        return self.build_telegram_message_auth_status_out(session)

    async def complete_telegram_message_auth(
        self,
        request_data: TelegramMessageAuthComplete,
    ) -> User:
        await self.sync_telegram_updates()
        session = await self.telegram_auth_session_repo.get_by_session_token(
            request_data.session_token
        )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Telegram-сессия не найдена",
            )

        session_status = self.get_telegram_message_session_status(session)
        if session_status == TelegramMessageAuthStatus.EXPIRED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Срок действия Telegram-подтверждения истёк. Начните заново.",
            )
        if session_status == TelegramMessageAuthStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Подтверждение в Telegram ещё не получено",
            )

        user = await self.user_repo.get(session.user_id) if session.user_id else None
        if user is None:
            if not session.telegram_user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Telegram-пользователь не определён. Начните заново.",
                )
            first_name = self.pick_first_non_empty_str(
                session.telegram_first_name,
                session.telegram_username,
            ) or "Пользователь"
            user = await self.get_or_create_user_by_identity(
                provider=AuthProvider.TELEGRAM,
                provider_user_id=session.telegram_user_id,
                first_name=first_name,
                last_name=session.telegram_last_name,
                role=(
                    session.role.value
                    if hasattr(session.role, "value")
                    else str(session.role)
                ),
                provider_email=None,
                provider_phone=None,
            )
            session.user_id = user.id

        session.completed_at = session.completed_at or datetime.utcnow()
        await self.commit_and_refresh(session)
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Пользователь деактивирован",
            )
        return user

    # ---------- JWT ----------
    def create_access_token(self, user_id: int) -> str:
        payload = TokenPayload(
            sub=str(user_id),
            exp=(
                self.current_utc_timestamp()
                + cfg.security.access_token_expire_minutes * 60
            ),
            type="access",
        )
        return jwt.encode(
            payload.dict(),
            cfg.security.jwt_secret_key,
            algorithm=cfg.security.jwt_algorithm,
        )

    def create_refresh_token(self, user_id: int) -> str:
        payload = TokenPayload(
            sub=str(user_id),
            exp=(
                self.current_utc_timestamp()
                + cfg.security.refresh_token_expire_days * 86400
            ),
            type="refresh",
        )
        return jwt.encode(
            payload.dict(),
            cfg.security.jwt_secret_key,
            algorithm=cfg.security.jwt_algorithm,
        )

    async def create_tokens(self, user_id: int) -> dict:
        """Создание пары токенов"""
        access_token = self.create_access_token(user_id)
        refresh_token = self.create_refresh_token(user_id)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def verify_token(
        self, token: str, token_type: str = "access"
    ) -> Optional[int]:
        try:
            payload = jwt.decode(
                token,
                cfg.security.jwt_secret_key,
                algorithms=[cfg.security.jwt_algorithm],
            )
            if payload.get("type") != token_type:
                return None
            user_id = int(payload.get("sub"))
            return user_id
        except (JWTError, ValueError, TypeError):
            return None

    async def ensure_identity(
        self,
        user: User,
        provider: AuthProvider,
        provider_user_id: str,
        *,
        provider_email: str | None = None,
        provider_phone: str | None = None,
        is_verified: bool = True,
    ) -> AuthIdentity:
        identity = await self.identity_repo.get_by_provider_identity(
            provider, provider_user_id
        )
        now = datetime.utcnow()
        if identity:
            updates_needed = False
            if identity.user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Этот способ входа уже привязан к другому пользователю",
                )
            if provider_email is not None and identity.provider_email != provider_email:
                identity.provider_email = provider_email
                updates_needed = True
            if provider_phone is not None and identity.provider_phone != provider_phone:
                identity.provider_phone = provider_phone
                updates_needed = True
            if identity.is_verified != is_verified:
                identity.is_verified = is_verified
                updates_needed = True
            identity.last_login_at = now
            updates_needed = True
            if updates_needed:
                await self.session.flush()
            return identity

        identity = AuthIdentity(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
            provider_email=provider_email,
            provider_phone=provider_phone,
            is_verified=is_verified,
            last_login_at=now,
        )
        self.session.add(identity)
        await self.session.flush()
        return identity

    async def create_user(
        self,
        *,
        first_name: str,
        last_name: str | None,
        role: UserRole | str,
        email: str | None = None,
        phone: str | None = None,
        password_hash: str | None = None,
        is_email_verified: bool = False,
        is_phone_verified: bool = False,
    ) -> User:
        if isinstance(role, str):
            role = UserRole(role)
        user = User(
            email=email,
            phone=phone,
            password=password_hash,
            first_name=first_name,
            last_name=last_name,
            role=role,
            is_email_verified=is_email_verified,
            is_phone_verified=is_phone_verified,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_or_create_user_by_identity(
        self,
        *,
        provider: AuthProvider,
        provider_user_id: str,
        first_name: str,
        last_name: str | None,
        role: str | None,
        provider_email: str | None = None,
        provider_phone: str | None = None,
        email_verified: bool = False,
        phone_verified: bool = False,
    ) -> User:
        identity = await self.identity_repo.get_by_provider_identity(
            provider, provider_user_id
        )
        if identity:
            user = await self.user_repo.get(identity.user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Пользователь для identity не найден",
                )
            identity.last_login_at = datetime.utcnow()
            if provider_email and not user.email:
                user.email = provider_email
                user.is_email_verified = email_verified
            if provider_phone and not user.phone:
                user.phone = provider_phone
                user.is_phone_verified = phone_verified
            if not user.last_name and last_name:
                user.last_name = last_name
            await self.session.flush()
            await self.commit_and_refresh(user)
            return user

        if role is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для нового пользователя нужно передать role",
            )

        if provider_email:
            existing_user = await self.user_repo.get_by_email(provider_email)
            if existing_user:
                await self.ensure_identity(
                    existing_user,
                    provider,
                    provider_user_id,
                    provider_email=provider_email,
                    provider_phone=provider_phone,
                    is_verified=True,
                )
                await self.commit_and_refresh(existing_user)
                return existing_user

        if provider_phone:
            existing_user = await self.user_repo.get_by_phone(provider_phone)
            if existing_user:
                await self.ensure_identity(
                    existing_user,
                    provider,
                    provider_user_id,
                    provider_email=provider_email,
                    provider_phone=provider_phone,
                    is_verified=True,
                )
                await self.commit_and_refresh(existing_user)
                return existing_user

        user = await self.create_user(
            email=provider_email,
            phone=provider_phone,
            password_hash=None,
            first_name=first_name,
            last_name=last_name,
            role=role,
            is_email_verified=email_verified,
            is_phone_verified=phone_verified,
        )
        await self.ensure_identity(
            user,
            provider,
            provider_user_id,
            provider_email=provider_email,
            provider_phone=provider_phone,
            is_verified=True,
        )
        await self.commit_and_refresh(user)
        return user

    # ---------- Бизнес-логика ----------
    async def register(self, user_data: UserCreate) -> User:
        return await self.register_with_password(user_data)

    async def register_with_password(self, user_data: UserCreate) -> User:
        email = self.normalize_email(user_data.email)
        # Проверяем, не занят ли email
        if await self.user_repo.check_exists_by_email(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже существует",
            )

        hashed_password = self.get_password_hash(user_data.password)
        user = await self.create_user(
            email=email,
            password_hash=hashed_password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            role=user_data.role.value,
            is_email_verified=False,
        )
        await self.ensure_identity(
            user,
            AuthProvider.PASSWORD,
            email,
            provider_email=email,
            is_verified=True,
        )
        await self.commit_and_refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        return await self.authenticate_with_password(email, password)

    async def authenticate_with_password(self, email: str, password: str) -> Optional[User]:
        email = self.normalize_email(email)
        user = await self.user_repo.get_by_email(email=email)
        if not user or not self.verify_password(
            password, hashed_password=user.password
        ):
            return None
        if not user.is_active:
            return None
        await self.ensure_identity(
            user,
            AuthProvider.PASSWORD,
            email,
            provider_email=email,
            is_verified=True,
        )
        await self.commit_and_refresh(user)
        return user

    async def login(self, login_data: UserLogin) -> dict:
        email = self.normalize_email(login_data.email)
        user = await self.user_repo.get_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
            )

        if not self.verify_password(login_data.password, user.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный email или пароль",
            )

        access_token = self.create_access_token(user.id)
        refresh_token = self.create_refresh_token(user.id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": user,  # можно сериализовать через UserOut
        }

    async def request_phone_code(
        self, request_data: PhoneCodeRequest
    ) -> PhoneCodeRequestOut:
        phone = self.normalize_phone(request_data.phone)
        if not cfg.auth.debug_return_phone_code:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SMS-провайдер пока не настроен. Для локальной проверки включите AUTH_DEBUG_RETURN_PHONE_CODE=true.",
            )

        now = datetime.utcnow()
        latest_code = await self.phone_code_repo.get_latest_by_phone(phone)
        if (
            latest_code
            and latest_code.used_at is None
            and latest_code.resend_available_at > now
        ):
            retry_after = int((latest_code.resend_available_at - now).total_seconds())
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Повторная отправка будет доступна через {retry_after} сек.",
            )

        active_codes = await self.session.execute(
            select(PhoneAuthCode).where(
                PhoneAuthCode.phone == phone,
                PhoneAuthCode.used_at.is_(None),
            )
        )
        for active_code in active_codes.scalars().all():
            active_code.used_at = now

        code = self.generate_phone_code()
        phone_code = PhoneAuthCode(
            phone=phone,
            code_hash=self.hash_phone_code(phone, code),
            expires_at=now + timedelta(seconds=cfg.auth.phone_code_ttl_seconds),
            resend_available_at=now
            + timedelta(seconds=cfg.auth.phone_code_resend_seconds),
        )
        self.session.add(phone_code)
        await self.session.flush()
        await self.session.commit()

        logger.info("Phone auth code generated for %s: %s", phone, code)
        return PhoneCodeRequestOut(
            message="Код сгенерирован в debug-режиме",
            retry_after_seconds=cfg.auth.phone_code_resend_seconds,
            expires_in_seconds=cfg.auth.phone_code_ttl_seconds,
            debug_code=code,
        )

    async def verify_phone_code(self, verify_data: PhoneCodeVerify) -> User:
        phone = self.normalize_phone(verify_data.phone)
        auth_code = await self.phone_code_repo.get_latest_active_by_phone(phone)
        if not auth_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Код не найден или уже использован",
            )

        now = datetime.utcnow()
        if auth_code.expires_at < now:
            auth_code.used_at = now
            await self.commit_and_refresh(auth_code)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Срок действия кода истёк",
            )

        if auth_code.attempts >= cfg.auth.phone_code_attempt_limit:
            auth_code.used_at = now
            await self.commit_and_refresh(auth_code)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Превышено число попыток ввода кода",
            )

        expected_hash = self.hash_phone_code(phone, verify_data.code)
        auth_code.attempts += 1
        if not hmac.compare_digest(auth_code.code_hash, expected_hash):
            if auth_code.attempts >= cfg.auth.phone_code_attempt_limit:
                auth_code.used_at = now
            await self.commit_and_refresh(auth_code)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный код подтверждения",
            )

        auth_code.used_at = now
        user = await self.user_repo.get_by_phone(phone)
        if user:
            user.is_phone_verified = True
            await self.ensure_identity(
                user,
                AuthProvider.PHONE,
                phone,
                provider_phone=phone,
                is_verified=True,
            )
            await self.commit_and_refresh(user, auth_code)
            return user

        if not verify_data.first_name or not verify_data.role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для нового пользователя передайте first_name и role",
            )

        user = await self.create_user(
            phone=phone,
            password_hash=None,
            first_name=verify_data.first_name,
            last_name=verify_data.last_name,
            role=verify_data.role.value,
            is_phone_verified=True,
        )
        await self.ensure_identity(
            user,
            AuthProvider.PHONE,
            phone,
            provider_phone=phone,
            is_verified=True,
        )
        await self.commit_and_refresh(user, auth_code)
        return user

    def ensure_telegram_auth_configured(self) -> str:
        bot_token = cfg.auth.telegram_bot_token
        if not bot_token:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AUTH_TELEGRAM_BOT_TOKEN не настроен",
            )
        return bot_token

    def validate_telegram_auth_age(self, auth_date: int) -> None:
        now_ts = self.current_utc_timestamp()
        if now_ts - auth_date > cfg.auth.telegram_auth_max_age_seconds:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Данные Telegram устарели",
            )

    def validate_telegram_login_widget_auth(
        self,
        auth_data: TelegramAuthData,
        bot_token: str,
    ) -> TelegramAuthData:
        payload = auth_data.model_dump(exclude_none=True)
        received_hash = payload.pop("hash")
        data_check_string = "\n".join(
            f"{key}={payload[key]}" for key in sorted(payload.keys())
        )
        secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Некорректная подпись Telegram",
            )
        self.validate_telegram_auth_age(auth_data.auth_date)
        return auth_data

    def validate_telegram_webapp_init_data(
        self,
        init_data: str,
        bot_token: str,
    ) -> TelegramAuthData:
        parsed_init_data = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = self.clean_text(parsed_init_data.pop("hash", None))
        parsed_init_data.pop("signature", None)
        if not received_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Telegram initData не содержит hash",
            )

        data_check_string = "\n".join(
            f"{key}={parsed_init_data[key]}" for key in sorted(parsed_init_data.keys())
        )
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(calculated_hash, received_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Некорректная подпись Telegram initData",
            )

        auth_date_raw = parsed_init_data.get("auth_date")
        try:
            auth_date = int(str(auth_date_raw))
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram initData не содержит корректный auth_date",
            ) from exc
        self.validate_telegram_auth_age(auth_date)

        user_raw = parsed_init_data.get("user")
        if not user_raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram initData не содержит данных пользователя",
            )
        try:
            user_payload = json.loads(user_raw)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram initData содержит некорректный user",
            ) from exc
        if not isinstance(user_payload, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram initData содержит неожиданный формат user",
            )

        first_name = self.clean_text(user_payload.get("first_name"))
        if user_payload.get("id") is None or not first_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram initData не содержит обязательные поля пользователя",
            )

        try:
            return TelegramAuthData(
                id=int(user_payload["id"]),
                first_name=first_name,
                last_name=self.clean_text(user_payload.get("last_name")),
                username=self.clean_text(user_payload.get("username")),
                photo_url=self.clean_text(user_payload.get("photo_url")),
                auth_date=auth_date,
                hash=received_hash,
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram initData содержит некорректные данные пользователя",
            ) from exc

    def validate_telegram_auth(
        self,
        login_data: TelegramLoginRequest,
    ) -> TelegramAuthData:
        bot_token = self.ensure_telegram_auth_configured()
        if login_data.init_data:
            return self.validate_telegram_webapp_init_data(
                login_data.init_data,
                bot_token,
            )
        if login_data.auth_data is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Передайте auth_data или init_data Telegram",
            )
        return self.validate_telegram_login_widget_auth(
            login_data.auth_data,
            bot_token,
        )

    async def authenticate_telegram(self, login_data: TelegramLoginRequest) -> User:
        auth_data = self.validate_telegram_auth(login_data)
        user = await self.get_or_create_user_by_identity(
            provider=AuthProvider.TELEGRAM,
            provider_user_id=str(auth_data.id),
            first_name=auth_data.first_name,
            last_name=auth_data.last_name,
            role=login_data.role.value,
            provider_email=None,
            provider_phone=None,
        )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Пользователь деактивирован",
            )
        return user

    async def authenticate_yandex_callback(
        self,
        *,
        code: str,
        state: str | None,
        flow_token: str | None,
    ) -> User:
        self.ensure_yandex_configured()
        flow_payload = self.decode_oauth_flow_token(flow_token, AuthProvider.YANDEX)
        expected_state = flow_payload.get("state")
        if state != expected_state:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Некорректный state для Yandex OAuth",
            )

        token_payload = await self.exchange_yandex_code(
            code=code,
            code_verifier=str(flow_payload.get("code_verifier") or ""),
        )
        access_token = self.clean_text(token_payload.get("access_token"))
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Yandex OAuth не вернул access_token",
            )

        user_info = await self.fetch_yandex_user_info(access_token)
        provider_user_id = self.pick_first_non_empty_str(
            user_info.get("id"),
            user_info.get("uid"),
        )
        if not provider_user_id:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Yandex ID не вернул идентификатор пользователя",
            )

        email = self.extract_email_from_value(
            user_info.get("default_email")
            or user_info.get("email")
            or user_info.get("emails")
        )
        phone = self.extract_phone_from_value(
            user_info.get("default_phone") or user_info.get("number")
        )
        first_name, last_name = self.build_user_name(
            first_name=user_info.get("first_name"),
            last_name=user_info.get("last_name"),
            display_name=user_info.get("display_name"),
            full_name=user_info.get("real_name") or user_info.get("name"),
            login=user_info.get("login"),
            email=email,
        )
        user = await self.get_or_create_user_by_identity(
            provider=AuthProvider.YANDEX,
            provider_user_id=str(provider_user_id),
            first_name=first_name,
            last_name=last_name,
            role=flow_payload.get("role"),
            provider_email=email,
            provider_phone=phone,
            email_verified=bool(email),
            phone_verified=bool(phone),
        )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Пользователь деактивирован",
            )
        return user

    async def authenticate_vk_callback(
        self,
        *,
        payload: str | None,
        code: str | None,
        state: str | None,
        device_id: str | None,
        flow_token: str | None,
    ) -> User:
        self.ensure_vk_configured()
        callback_payload = self.parse_vk_callback_payload(
            payload=payload,
            code=code,
            state=state,
            device_id=device_id,
        )
        flow_payload = self.decode_oauth_flow_token(flow_token, AuthProvider.VK)
        expected_state = flow_payload.get("state")
        if callback_payload["state"] != expected_state:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Некорректный state для VK ID",
            )

        token_payload = await self.exchange_vk_code(
            code=callback_payload["code"],
            state=callback_payload["state"],
            device_id=callback_payload["device_id"],
            code_verifier=str(flow_payload.get("code_verifier") or ""),
        )
        returned_state = self.clean_text(token_payload.get("state"))
        if returned_state and returned_state != callback_payload["state"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="VK ID вернул неожиданный state",
            )

        access_token = self.clean_text(token_payload.get("access_token"))
        if not access_token:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="VK ID не вернул access_token",
            )

        user_info_payload = await self.fetch_vk_user_info(access_token)
        raw_user = user_info_payload.get("user")
        if not isinstance(raw_user, dict):
            raw_user = user_info_payload.get("response")
        if not isinstance(raw_user, dict):
            raw_user = user_info_payload

        provider_user_id = self.pick_first_non_empty_str(
            raw_user.get("user_id"),
            raw_user.get("id"),
            token_payload.get("user_id"),
        )
        if not provider_user_id:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="VK ID не вернул идентификатор пользователя",
            )

        email = self.extract_email_from_value(raw_user.get("email"))
        phone = self.extract_phone_from_value(raw_user.get("phone"))
        first_name, last_name = self.build_user_name(
            first_name=raw_user.get("first_name"),
            last_name=raw_user.get("last_name"),
            display_name=raw_user.get("display_name") or raw_user.get("name"),
            full_name=raw_user.get("name") or raw_user.get("real_name"),
            login=raw_user.get("screen_name") or raw_user.get("login"),
            email=email,
        )

        user = await self.get_or_create_user_by_identity(
            provider=AuthProvider.VK,
            provider_user_id=str(provider_user_id),
            first_name=first_name,
            last_name=last_name,
            role=flow_payload.get("role"),
            provider_email=email,
            provider_phone=phone,
            email_verified=bool(email),
            phone_verified=bool(phone),
        )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Пользователь деактивирован",
            )
        return user

    async def refresh_token(self, refresh_token: str) -> dict:
        user_id = await self.verify_token(refresh_token, token_type="refresh")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный refresh токен",
            )

        user = await self.user_repo.get(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден",
            )

        access_token = self.create_access_token(user.id)
        new_refresh_token = self.create_refresh_token(user.id)

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
        }

    async def get_user_from_token(
        self, token: str, token_type: str = "access"
    ) -> Optional[User]:
        try:
            payload = jwt.decode(
                token,
                cfg.security.jwt_secret_key,
                algorithms=[cfg.security.jwt_algorithm],
            )
            if payload.get("type") != token_type:
                return None
            user_id = payload.get("sub")
            if user_id is None:
                return None
        except JWTError:
            return None
        user = await self.user_repo.get(id=int(user_id))
        if user and not user.is_active:
            return None
        return user
