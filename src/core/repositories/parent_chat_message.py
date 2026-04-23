from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.repositories.base import BaseRepository
from src.database.models import ParentChatMessage


class ParentChatMessageRepository(BaseRepository[ParentChatMessage]):
    def __init__(self, session):
        super().__init__(ParentChatMessage, session)

    def _query_with_relations(self):
        return select(ParentChatMessage).options(
            selectinload(ParentChatMessage.sender)
        )

    async def get_by_id(self, message_id: int) -> ParentChatMessage | None:
        result = await self.session.execute(
            self._query_with_relations().where(ParentChatMessage.id == message_id)
        )
        return result.scalar_one_or_none()

    async def list_for_access(self, access_id: int) -> list[ParentChatMessage]:
        result = await self.session.execute(
            self._query_with_relations()
            .where(ParentChatMessage.parent_access_id == access_id)
            .order_by(ParentChatMessage.created_at.asc(), ParentChatMessage.id.asc())
        )
        return result.scalars().all()

    async def save(self, message: ParentChatMessage) -> ParentChatMessage:
        self.session.add(message)
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(message)
        return message
