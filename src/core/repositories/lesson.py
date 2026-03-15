from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from database.models import Lesson
from .base import BaseRepository


class LessonRepository(BaseRepository[Lesson]):
    def __init__(self, session):
        super().__init__(Lesson, session)  # Добавлено

    async def get_last_for_tutor_student(self, tutor_student_id: int):
        query = (
            select(Lesson)
            .where(Lesson.tutor_student_id == tutor_student_id)
            .order_by(desc(Lesson.l_date), desc(Lesson.l_time))
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(self, **kwargs):
        lesson = Lesson(**kwargs)
        self.session.add(lesson)
        await self.session.flush()
        return lesson
