# src/schemas/user.py
from pydantic import BaseModel, EmailStr, Field
from enum import Enum
from typing import Optional


# Enums (должны совпадать с модельными)
class UserRole(str, Enum):
    TUTOR = "tutor"
    STUDENT = "student"


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


# ---------- Ответы ----------
class UserOut(BaseModel):
    id: int
    email: EmailStr
    first_name: str
    last_name: Optional[str]
    role: UserRole

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
