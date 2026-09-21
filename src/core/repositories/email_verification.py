from sqlalchemy import select

from src.core.repositories.base import BaseRepository
from src.database.models import EmailVerificationToken


class EmailVerificationTokenRepository(BaseRepository[EmailVerificationToken]):
    def __init__(self, session):
        super().__init__(EmailVerificationToken, session)

    async def get_by_token(self, token: str) -> EmailVerificationToken | None:
        result = await self.session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token == token
            )
        )
        return result.scalar_one_or_none()
