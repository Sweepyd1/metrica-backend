# src/core/services/auth.py
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import HTTPException, status

from database.models import User
from config import cfg
from core.repositories.user import UserRepository
from schemas.user import UserCreate, UserLogin, TokenPayload

# Настройка хеширования паролей
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],
    deprecated="auto",
    bcrypt__rounds=cfg.security.bcrypt_rounds,
)


class AuthService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    # ---------- Хеширование ----------
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
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

    # ---------- JWT ----------
    def create_access_token(self, user_id: int) -> str:
        expires_delta = timedelta(minutes=cfg.security.access_token_expire_minutes)
        expire = datetime.utcnow() + expires_delta
        payload = TokenPayload(
            sub=str(user_id), exp=int(expire.timestamp()), type="access"
        )
        return jwt.encode(
            payload.dict(),
            cfg.security.jwt_secret_key,
            algorithm=cfg.security.jwt_algorithm,
        )

    def create_refresh_token(self, user_id: int) -> str:
        expires_delta = timedelta(days=cfg.security.refresh_token_expire_days)
        expire = datetime.utcnow() + expires_delta
        payload = TokenPayload(
            sub=str(user_id), exp=int(expire.timestamp()), type="refresh"
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

    # ---------- Бизнес-логика ----------
    async def register(self, user_data: UserCreate) -> User:
        # Проверяем, не занят ли email
        if await self.repo.check_exists(user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже существует",
            )

        hashed_password = self.get_password_hash(user_data.password)
        user = await self.repo.create(
            email=user_data.email,
            password=hashed_password,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            role=user_data.role.value,  # если роль передаётся, иначе ставим student
        )
        return user

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        # Поиск пользователя по email или username
        user = await self.repo.get_by_email(email=email)

        if not user or not self.verify_password(
            password, hashed_password=user.password
        ):
            return None
        return user

    async def login(self, login_data: UserLogin) -> dict:
        user = await self.repo.get_by_email(login_data.email)
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

    async def refresh_token(self, refresh_token: str) -> dict:
        user_id = await self.verify_token(refresh_token, token_type="refresh")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный refresh токен",
            )

        user = await self.repo.get(user_id)
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
        user = await self.repo.get(id=int(user_id))
        return user
