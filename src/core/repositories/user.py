# src/core/repositories/user.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User
from src.core.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> User | None:
        result = await self.session.execute(select(User).where(User.phone == phone))
        return result.scalar_one_or_none()

    async def check_exists(self, email: str) -> bool:
        return await self.check_exists_by_email(email)

    async def check_exists_by_email(self, email: str) -> bool:
        result = await self.session.execute(
            select(User.id).where(User.email == email).limit(1)
        )
        return result.scalar() is not None

    async def check_exists_by_phone(self, phone: str) -> bool:
        result = await self.session.execute(
            select(User.id).where(User.phone == phone).limit(1)
        )
        return result.scalar() is not None
