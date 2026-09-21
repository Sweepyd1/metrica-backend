from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.repositories.base import BaseRepository
from src.database.models import TelegramAuthSession


class TelegramAuthSessionRepository(BaseRepository[TelegramAuthSession]):
    def __init__(self, session: AsyncSession):
        super().__init__(TelegramAuthSession, session)

    async def get_by_session_token(
        self, session_token: str
    ) -> TelegramAuthSession | None:
        result = await self.session.execute(
            select(TelegramAuthSession).where(
                TelegramAuthSession.session_token == session_token
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_session_token(
        self, session_token: str
    ) -> TelegramAuthSession | None:
        now = datetime.utcnow()
        result = await self.session.execute(
            select(TelegramAuthSession).where(
                TelegramAuthSession.session_token == session_token,
                TelegramAuthSession.expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_confirmation_code(
        self, confirmation_code: str
    ) -> TelegramAuthSession | None:
        now = datetime.utcnow()
        result = await self.session.execute(
            select(TelegramAuthSession)
            .where(
                TelegramAuthSession.confirmation_code == confirmation_code,
                TelegramAuthSession.expires_at > now,
                TelegramAuthSession.completed_at.is_(None),
            )
            .order_by(TelegramAuthSession.created_at.desc(), TelegramAuthSession.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
