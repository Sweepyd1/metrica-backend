from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from core.repositories.base import BaseRepository
from database.models import ParentStudent


class ParentStudentRepository(BaseRepository[ParentStudent]):
    def __init__(self, session):
        super().__init__(ParentStudent, session)

    async def get_by_parent(self, parent_id: int):
        query = (
            select(ParentStudent)
            .where(ParentStudent.parent_id == parent_id)
            .options(selectinload(ParentStudent.student))
            .order_by(ParentStudent.id)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_parent_and_student(self, parent_id: int, student_id: int):
        query = (
            select(ParentStudent)
            .where(
                and_(
                    ParentStudent.parent_id == parent_id,
                    ParentStudent.student_id == student_id,
                )
            )
            .options(selectinload(ParentStudent.student))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(self, parent_id: int, student_id: int):
        link = ParentStudent(parent_id=parent_id, student_id=student_id)
        self.session.add(link)
        await self.session.flush()
        await self.session.commit()

        result = await self.session.execute(
            select(ParentStudent)
            .where(ParentStudent.id == link.id)
            .options(selectinload(ParentStudent.student))
        )
        return result.scalar_one()
