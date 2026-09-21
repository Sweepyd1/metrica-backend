from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.repositories.base import BaseRepository
from src.database.models import Invite, TutorStudent


class InviteRepository(BaseRepository[Invite]):
    def __init__(self, session):
        super().__init__(Invite, session)

    async def get_by_token(self, token: str) -> Invite | None:
        result = await self.session.execute(
            select(Invite)
            .where(Invite.token == token)
            .options(
                selectinload(Invite.tutor),
                selectinload(Invite.tutor_student).selectinload(TutorStudent.student),
            )
        )
        return result.scalar_one_or_none()
