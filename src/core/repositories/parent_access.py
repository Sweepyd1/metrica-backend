from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from src.core.repositories.base import BaseRepository
from src.database.models import ParentAccess, ParentAccessStatus, TutorStudent


class ParentAccessRepository(BaseRepository[ParentAccess]):
    def __init__(self, session):
        super().__init__(ParentAccess, session)

    def _query_with_relations(self):
        return select(ParentAccess).options(
            selectinload(ParentAccess.parent),
            selectinload(ParentAccess.reviewer),
            selectinload(ParentAccess.tutor_student).selectinload(TutorStudent.student),
            selectinload(ParentAccess.tutor_student).selectinload(TutorStudent.tutor),
        )

    async def get_by_parent_and_tutor_student(
        self,
        parent_id: int,
        tutor_student_id: int,
    ) -> ParentAccess | None:
        result = await self.session.execute(
            self._query_with_relations().where(
                and_(
                    ParentAccess.parent_id == parent_id,
                    ParentAccess.tutor_student_id == tutor_student_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_for_parent(
        self,
        parent_id: int,
        access_id: int,
    ) -> ParentAccess | None:
        result = await self.session.execute(
            self._query_with_relations().where(
                and_(
                    ParentAccess.id == access_id,
                    ParentAccess.parent_id == parent_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_for_parent(
        self,
        parent_id: int,
        status: ParentAccessStatus | None = None,
    ) -> list[ParentAccess]:
        query = self._query_with_relations().where(ParentAccess.parent_id == parent_id)
        if status is not None:
            query = query.where(ParentAccess.status == status)
        query = query.order_by(ParentAccess.created_at.desc(), ParentAccess.id.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_for_tutor(
        self,
        tutor_id: int,
        access_id: int,
    ) -> ParentAccess | None:
        result = await self.session.execute(
            self._query_with_relations()
            .join(TutorStudent, ParentAccess.tutor_student_id == TutorStudent.id)
            .where(
                and_(
                    ParentAccess.id == access_id,
                    TutorStudent.tutor_id == tutor_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_for_tutor(
        self,
        tutor_id: int,
        status: ParentAccessStatus | None = None,
    ) -> list[ParentAccess]:
        query = (
            self._query_with_relations()
            .join(TutorStudent, ParentAccess.tutor_student_id == TutorStudent.id)
            .where(TutorStudent.tutor_id == tutor_id)
        )
        if status is not None:
            query = query.where(ParentAccess.status == status)
        query = query.order_by(ParentAccess.created_at.desc(), ParentAccess.id.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def save(self, access: ParentAccess) -> ParentAccess:
        self.session.add(access)
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(access)
        return access
