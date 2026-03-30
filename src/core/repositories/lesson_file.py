from sqlalchemy import select, and_, desc
from sqlalchemy.orm import selectinload
from database.models import (
    LessonFile,
    Lesson,
    TutorStudent,
    LessonFileKind,
    SubmissionStatus,
)
from core.repositories.base import BaseRepository


class LessonFileRepository(BaseRepository[LessonFile]):
    def __init__(self, session):
        super().__init__(LessonFile, session)  # Добавлено

    async def get_submission_for_tutor(self, tutor_id: int, submission_id: int):
        query = (
            select(LessonFile)
            .join(Lesson, LessonFile.lesson_id == Lesson.id)
            .join(TutorStudent, Lesson.tutor_student_id == TutorStudent.id)
            .where(
                and_(
                    TutorStudent.tutor_id == tutor_id,
                    LessonFile.id == submission_id,
                    LessonFile.kind == LessonFileKind.SUBMISSION,
                )
            )
            .options(
                selectinload(LessonFile.lesson)
                .selectinload(Lesson.tutor_student)
                .selectinload(TutorStudent.student),
                selectinload(LessonFile.file),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

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

    async def get_latest_submission_for_lesson(self, lesson_id: int):
        query = (
            select(LessonFile)
            .where(
                and_(
                    LessonFile.lesson_id == lesson_id,
                    LessonFile.kind == LessonFileKind.SUBMISSION,
                )
            )
            .options(selectinload(LessonFile.file))
            .order_by(desc(LessonFile.id))
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def save(self, lesson_file: LessonFile) -> LessonFile:
        self.session.add(lesson_file)
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(lesson_file)
        return lesson_file

    async def sync_lesson_files(
        self,
        lesson: Lesson,
        *,
        material_file_ids: list[int],
        homework_task_file_ids: list[int],
    ) -> None:
        desired_by_file_id: dict[int, LessonFileKind] = {}

        for file_id in material_file_ids:
            if file_id > 0 and file_id not in desired_by_file_id:
                desired_by_file_id[file_id] = LessonFileKind.MATERIAL

        for file_id in homework_task_file_ids:
            if file_id > 0 and file_id not in desired_by_file_id:
                desired_by_file_id[file_id] = LessonFileKind.HOMEWORK_TASK

        current_files = [
            lesson_file
            for lesson_file in lesson.lesson_files
            if lesson_file.kind != LessonFileKind.SUBMISSION
        ]

        for lesson_file in current_files:
            desired_kind = desired_by_file_id.pop(lesson_file.file_id, None)

            if desired_kind is None:
                await self.session.delete(lesson_file)
                continue

            if lesson_file.kind != desired_kind:
                lesson_file.kind = desired_kind
                self.session.add(lesson_file)

        for file_id, kind in desired_by_file_id.items():
            self.session.add(
                LessonFile(
                    lesson_id=lesson.id,
                    file_id=file_id,
                    kind=kind,
                )
            )

        await self.session.flush()
