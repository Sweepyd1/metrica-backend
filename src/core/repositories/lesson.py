import datetime as dt

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import selectinload
from database.models import Lesson, LessonFile, TutorStudent
from core.repositories.base import BaseRepository


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
        await self.session.commit()  # ← добавить эту строку
        await self.session.refresh(lesson)  # опционально
        return lesson

    async def get_by_student(self, student_id: int):
        query = (
            select(Lesson)
            .join(TutorStudent, Lesson.tutor_student_id == TutorStudent.id)
            .where(TutorStudent.student_id == student_id)
            .options(
                selectinload(Lesson.tutor_student).selectinload(TutorStudent.tutor),
                selectinload(Lesson.lesson_files).selectinload(LessonFile.file),
            )
            .order_by(desc(Lesson.l_date), desc(Lesson.l_time), desc(Lesson.id))
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_student_lesson(self, student_id: int, lesson_id: int):
        query = (
            select(Lesson)
            .join(TutorStudent, Lesson.tutor_student_id == TutorStudent.id)
            .where(and_(TutorStudent.student_id == student_id, Lesson.id == lesson_id))
            .options(
                selectinload(Lesson.tutor_student).selectinload(TutorStudent.tutor),
                selectinload(Lesson.lesson_files).selectinload(LessonFile.file),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_tutor(
        self,
        tutor_id: int,
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
    ):
        query = (
            select(Lesson)
            .join(TutorStudent, Lesson.tutor_student_id == TutorStudent.id)
            .where(TutorStudent.tutor_id == tutor_id)
            .options(
                selectinload(Lesson.tutor_student).selectinload(TutorStudent.student),
                selectinload(Lesson.lesson_files).selectinload(LessonFile.file),
            )
        )
        if date_from is not None:
            query = query.where(Lesson.l_date >= date_from)
        if date_to is not None:
            query = query.where(Lesson.l_date <= date_to)
        query = query.order_by(
            desc(Lesson.l_date), desc(Lesson.l_time), desc(Lesson.id)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_tutor_lesson(self, tutor_id: int, lesson_id: int):
        query = (
            select(Lesson)
            .join(TutorStudent, Lesson.tutor_student_id == TutorStudent.id)
            .where(and_(TutorStudent.tutor_id == tutor_id, Lesson.id == lesson_id))
            .options(
                selectinload(Lesson.tutor_student).selectinload(TutorStudent.student),
                selectinload(Lesson.lesson_files).selectinload(LessonFile.file),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def save(self, lesson: Lesson) -> Lesson:
        self.session.add(lesson)
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(lesson)
        return lesson
