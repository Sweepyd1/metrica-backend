from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from src.core.repositories.base import BaseRepository
from src.database.models import BonusTask, TutorStudent


class BonusTaskRepository(BaseRepository[BonusTask]):
    def __init__(self, session):
        super().__init__(BonusTask, session)

    async def get_for_tutor(self, tutor_id: int, task_id: int):
        query = (
            select(BonusTask)
            .join(TutorStudent, BonusTask.tutor_student_id == TutorStudent.id)
            .where(and_(TutorStudent.tutor_id == tutor_id, BonusTask.id == task_id))
            .options(selectinload(BonusTask.tutor_student))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_for_tutor_student(self, tutor_student_id: int):
        query = (
            select(BonusTask)
            .where(BonusTask.tutor_student_id == tutor_student_id)
            .order_by(BonusTask.is_completed, BonusTask.due_date, BonusTask.id)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_for_student(self, student_id: int):
        query = (
            select(BonusTask)
            .join(TutorStudent, BonusTask.tutor_student_id == TutorStudent.id)
            .where(TutorStudent.student_id == student_id)
            .order_by(BonusTask.is_completed, BonusTask.due_date, BonusTask.id)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def save(self, task: BonusTask) -> BonusTask:
        self.session.add(task)
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(task)
        return task
