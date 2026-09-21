import datetime as dt

from sqlalchemy import and_, asc, desc, nullslast, select
from sqlalchemy.orm import selectinload
from src.database.models import Lesson, LessonFile, ParentStudent, TutorStudent
from src.core.repositories.base import BaseRepository


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

    async def get_by_tutor_student(self, tutor_student_id: int):
        query = (
            select(Lesson)
            .where(Lesson.tutor_student_id == tutor_student_id)
            .options(
                selectinload(Lesson.lesson_files).selectinload(LessonFile.file),
                selectinload(Lesson.lesson_files).selectinload(
                    LessonFile.checked_file
                ),
            )
        )
        result = await self.session.execute(query)
        return result.scalars().all()

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
                selectinload(Lesson.lesson_files).selectinload(
                    LessonFile.checked_file
                ),
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
                selectinload(Lesson.lesson_files).selectinload(
                    LessonFile.checked_file
                ),
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
                selectinload(Lesson.lesson_files).selectinload(
                    LessonFile.checked_file
                ),
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

    async def get_by_tutor_student(
        self, tutor_id: int, tutor_student_id: int | None = None
    ):
        if tutor_student_id is None:
            tutor_student_id = tutor_id
            query = select(Lesson).where(Lesson.tutor_student_id == tutor_student_id)
        else:
            query = (
                select(Lesson)
                .join(TutorStudent, Lesson.tutor_student_id == TutorStudent.id)
                .where(
                    and_(
                        TutorStudent.tutor_id == tutor_id,
                        Lesson.tutor_student_id == tutor_student_id,
                    )
                )
            )
        query = (
            query.options(
                selectinload(Lesson.tutor_student).selectinload(TutorStudent.student),
                selectinload(Lesson.tutor_student).selectinload(TutorStudent.tutor),
                selectinload(Lesson.lesson_files).selectinload(LessonFile.file),
                selectinload(Lesson.lesson_files).selectinload(
                    LessonFile.checked_file
                ),
            )
            .order_by(
                nullslast(asc(Lesson.l_date)),
                nullslast(asc(Lesson.l_time)),
                asc(Lesson.id),
            )
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_tutor_student_lesson(
        self, tutor_id: int, tutor_student_id: int, lesson_id: int
    ):
        query = (
            select(Lesson)
            .join(TutorStudent, Lesson.tutor_student_id == TutorStudent.id)
            .where(
                and_(
                    TutorStudent.tutor_id == tutor_id,
                    Lesson.tutor_student_id == tutor_student_id,
                    Lesson.id == lesson_id,
                )
            )
            .options(
                selectinload(Lesson.tutor_student).selectinload(TutorStudent.student),
                selectinload(Lesson.tutor_student).selectinload(TutorStudent.tutor),
                selectinload(Lesson.lesson_files).selectinload(LessonFile.file),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_tutor_lesson(self, tutor_id: int, lesson_id: int):
        query = (
            select(Lesson)
            .join(TutorStudent, Lesson.tutor_student_id == TutorStudent.id)
            .where(and_(TutorStudent.tutor_id == tutor_id, Lesson.id == lesson_id))
            .options(
                selectinload(Lesson.tutor_student).selectinload(TutorStudent.student),
                selectinload(Lesson.lesson_files).selectinload(LessonFile.file),
                selectinload(Lesson.lesson_files).selectinload(
                    LessonFile.checked_file
                ),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_parent(self, parent_id: int, student_id: int | None = None):
        query = (
            select(Lesson)
            .join(TutorStudent, Lesson.tutor_student_id == TutorStudent.id)
            .join(ParentStudent, ParentStudent.student_id == TutorStudent.student_id)
            .where(
                and_(
                    ParentStudent.parent_id == parent_id,
                    TutorStudent.parent_contact_enabled == True,
                )
            )
            .options(
                selectinload(Lesson.tutor_student).selectinload(TutorStudent.student),
                selectinload(Lesson.tutor_student).selectinload(TutorStudent.tutor),
                selectinload(Lesson.lesson_files).selectinload(LessonFile.file),
                selectinload(Lesson.lesson_files).selectinload(
                    LessonFile.checked_file
                ),
            )
        )
        if student_id is not None:
            query = query.where(TutorStudent.student_id == student_id)
        query = query.order_by(
            desc(Lesson.l_date), desc(Lesson.l_time), desc(Lesson.id)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_parent_lesson(self, parent_id: int, lesson_id: int):
        query = (
            select(Lesson)
            .join(TutorStudent, Lesson.tutor_student_id == TutorStudent.id)
            .join(ParentStudent, ParentStudent.student_id == TutorStudent.student_id)
            .where(
                and_(
                    ParentStudent.parent_id == parent_id,
                    Lesson.id == lesson_id,
                    TutorStudent.parent_contact_enabled == True,
                )
            )
            .options(
                selectinload(Lesson.tutor_student).selectinload(TutorStudent.student),
                selectinload(Lesson.tutor_student).selectinload(TutorStudent.tutor),
                selectinload(Lesson.lesson_files).selectinload(LessonFile.file),
                selectinload(Lesson.lesson_files).selectinload(
                    LessonFile.checked_file
                ),
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
