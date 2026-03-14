# src/api/dependencies.py
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.user import UserRepository
from core.service.auth import AuthService
from typing import AsyncIterator

from fastapi.security import OAuth2PasswordBearer


from database.db_manager import db_manager


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with db_manager.get_session() as session:
        yield session


async def get_auth_service(
    db: AsyncSession = Depends(get_db_session),
) -> AuthService:
    repo = UserRepository(db)
    return AuthService(repo)
