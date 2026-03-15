from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload
from database.models import (
    LessonFile,
    Lesson,
    TutorStudent,
    LessonFileKind,
    SubmissionStatus,
)
from .base import BaseRepository


class LessonFileRepository(BaseRepository[LessonFile]):
    def __init__(self, session):
        super().__init__(LessonFile, session)  # Добавлено

    async def get_pending_for_tutor(self, tutor_id: int):
        query = (
            select(LessonFile)
            .join(Lesson, LessonFile.lesson_id == Lesson.id)
            .join(TutorStudent, Lesson.tutor_student_id == TutorStudent.id)
            .where(
                and_(
                    TutorStudent.tutor_id == tutor_id,
                    LessonFile.kind == LessonFileKind.SUBMISSION,
                    LessonFile.status == SubmissionStatus.SUBMITTED,
                )
            )
            .options(
                selectinload(LessonFile.lesson)
                .selectinload(Lesson.tutor_student)
                .selectinload(TutorStudent.student),
                selectinload(LessonFile.file),
            )
            .order_by(desc(Lesson.l_date), desc(Lesson.l_time))
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_last_submission_for_student(self, student_id: int):
        query = (
            select(LessonFile)
            .join(Lesson, LessonFile.lesson_id == Lesson.id)
            .join(TutorStudent, Lesson.tutor_student_id == TutorStudent.id)
            .where(
                and_(
                    TutorStudent.student_id == student_id,
                    LessonFile.kind == LessonFileKind.SUBMISSION,
                )
            )
            .options(selectinload(LessonFile.file))
            .order_by(desc(Lesson.l_date), desc(Lesson.l_time), desc(LessonFile.id))
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
