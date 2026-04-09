from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.repositories.base import BaseRepository
from src.database.models import AuthIdentity, AuthProvider


class AuthIdentityRepository(BaseRepository[AuthIdentity]):
    def __init__(self, session: AsyncSession):
        super().__init__(AuthIdentity, session)

    async def get_by_provider_identity(
        self, provider: AuthProvider, provider_user_id: str
    ) -> AuthIdentity | None:
        result = await self.session.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == provider,
                AuthIdentity.provider_user_id == provider_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_user_and_provider(
        self, user_id: int, provider: AuthProvider
    ) -> AuthIdentity | None:
        result = await self.session.execute(
            select(AuthIdentity).where(
                AuthIdentity.user_id == user_id,
                AuthIdentity.provider == provider,
            )
        )
        return result.scalar_one_or_none()
