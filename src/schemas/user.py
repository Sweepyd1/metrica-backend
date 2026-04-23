# src/schemas/user.py
from datetime import datetime
from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, model_validator
from enum import Enum
from typing import Optional


# Enums (должны совпадать с модельными)
class UserRole(str, Enum):
    TUTOR = "tutor"
    STUDENT = "student"
    PARENT = "parent"


# ---------- Запросы ----------
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    first_name: str
    last_name: Optional[str] = None
    role: UserRole = UserRole.STUDENT  # по умолчанию студент


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class PhoneCodeRequest(BaseModel):
    phone: str


class PhoneCodeVerify(BaseModel):
    phone: str
    code: str = Field(..., min_length=4, max_length=8)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[UserRole] = None


class PhoneCodeRequestOut(BaseModel):
    message: str
    retry_after_seconds: int
    expires_in_seconds: int
    debug_code: Optional[str] = None


class TelegramAuthData(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


class TelegramLoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    auth_data: Optional[TelegramAuthData] = Field(
        default=None,
        validation_alias=AliasChoices("auth_data", "authData"),
    )
    init_data: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("init_data", "initData"),
    )
    role: UserRole = UserRole.STUDENT

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        normalized = dict(value)
        auth_data = normalized.get("auth_data") or normalized.get("authData")
        init_data = normalized.get("init_data") or normalized.get("initData")

        telegram_auth_keys = {
            "id",
            "first_name",
            "last_name",
            "username",
            "photo_url",
            "auth_date",
            "hash",
        }
        if auth_data is None and any(key in normalized for key in telegram_auth_keys):
            auth_data = {
                key: normalized[key]
                for key in telegram_auth_keys
                if key in normalized
            }

        if auth_data is not None:
            normalized["auth_data"] = auth_data
        if init_data is not None:
            normalized["init_data"] = init_data
        return normalized

    @model_validator(mode="after")
    def validate_payload(self) -> "TelegramLoginRequest":
        if self.auth_data is None and self.init_data is None:
            raise ValueError("Передайте auth_data или init_data Telegram")
        return self


class TelegramMessageAuthStart(BaseModel):
    role: UserRole = UserRole.STUDENT


class TelegramMessageAuthStartOut(BaseModel):
    session_token: str
    confirmation_code: str
    bot_username: str
    bot_url: str
    expires_in_seconds: int


class TelegramMessageAuthStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    EXPIRED = "expired"


class TelegramMessageAuthStatusOut(BaseModel):
    status: TelegramMessageAuthStatus
    expires_at: datetime
    confirmed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    telegram_username: Optional[str] = None
    telegram_first_name: Optional[str] = None


class TelegramMessageAuthComplete(BaseModel):
    session_token: str


class UserOut(BaseModel):
    id: int
    email: Optional[EmailStr]
    phone: Optional[str]
    first_name: str
    last_name: Optional[str]
    role: UserRole
    is_email_verified: bool
    is_phone_verified: bool

    class Config:
        from_attributes = True  # orm_mode для Pydantic v2


class TokenPayload(BaseModel):
    sub: str
    exp: int
    type: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
