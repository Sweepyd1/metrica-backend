from fastapi import HTTPException, status
from typing import List, Dict, Any

from core.repositories.tutor_student import TutorStudentRepository
from core.repositories.lesson import LessonRepository
from core.repositories.lesson_file import LessonFileRepository
from core.repositories.user import UserRepository
from database.models import (
    User,
    TutorStudent,
    Lesson,
    LessonFile,
    SubmissionStatus,
    LessonFileKind,
)
from schemas.tutor import LessonCreate, SubmissionOut


class TutorService:
    def __init__(
        self,
        tutor_student_repo: TutorStudentRepository,
        lesson_repo: LessonRepository,
        lesson_file_repo: LessonFileRepository,
        user_repo: UserRepository,
    ):
        self.tutor_student_repo = tutor_student_repo
        self.lesson_repo = lesson_repo
        self.lesson_file_repo = lesson_file_repo
        self.user_repo = user_repo

    async def add_student(self, tutor_id: int, email: str) -> TutorStudent:
        student = await self.user_repo.get_by_email(email)
        if not student or student.role != "student":
            raise HTTPException(
                status_code=404, detail="Не удалось найти ученика с таким email"
            )

        existing = await self.tutor_student_repo.get_by_tutor_and_student(
            tutor_id, student.id
        )
        if existing:
            raise HTTPException(status_code=400, detail="Ученик уже добавлен")

        # Создаём связь – студент уже загружен внутри репозитория
        link = await self.tutor_student_repo.create(
            tutor_id=tutor_id, student_id=student.id, subject=None, student_inf=None
        )
        return link

    async def get_my_students(self, tutor_id: int) -> List[Dict[str, Any]]:
        links = await self.tutor_student_repo.get_by_tutor(tutor_id)
        result = []
        for link in links:
            student = link.student
            # последняя отправленная работа (submission) этого ученика
            last_sub = await self.lesson_file_repo.get_last_submission_for_student(
                student.id
            )
            status_str = "none"
            sub_id = None
            if last_sub:
                sub_id = last_sub.id
                if last_sub.status == SubmissionStatus.SUBMITTED:
                    status_str = "pending"
                elif last_sub.status == SubmissionStatus.CHECKED:
                    status_str = "checked"
            result.append(
                {
                    "id": link.id,
                    "student_id": student.id,
                    "full_name": f"{student.first_name} {student.last_name or ''}",
                    "subject": link.subject,
                    "class_info": link.student_inf,
                    "last_submission_id": sub_id,
                    "last_submission_status": status_str,
                }
            )
        return result

    async def create_lesson(self, tutor_id: int, data: LessonCreate) -> Lesson:
        # проверяем, что связь принадлежит этому репетитору
        link = await self.tutor_student_repo.get(data.tutor_student_id)
        if not link or link.tutor_id != tutor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not your student"
            )
        lesson = await self.lesson_repo.create(
            tutor_student_id=data.tutor_student_id,
            l_date=data.date,
            l_time=data.time,
            topic=data.topic,
            meet_link=data.meet_link,
            homework_deadline=data.homework_deadline,
            homework_done=False,
        )
        # прикрепляем файлы
        for file_id in data.material_file_ids:
            await self.lesson_file_repo.create(
                lesson_id=lesson.id, file_id=file_id, kind=LessonFileKind.MATERIAL
            )
        for file_id in data.homework_task_file_ids:
            await self.lesson_file_repo.create(
                lesson_id=lesson.id, file_id=file_id, kind=LessonFileKind.HOMEWORK_TASK
            )
        return lesson

    async def get_pending_submissions(self, tutor_id: int) -> List[SubmissionOut]:
        submissions = await self.lesson_file_repo.get_pending_for_tutor(tutor_id)
        result = []
        for sub in submissions:
            lesson = sub.lesson
            student = lesson.tutor_student.student
            result.append(
                SubmissionOut(
                    id=sub.id,
                    student=f"{student.first_name} {student.last_name or ''}",
                    lesson_date=lesson.l_date,
                    lesson_topic=lesson.topic,
                    file_url=sub.file.path if sub.file else None,
                    status=sub.status.value if sub.status else "unknown",
                    comment=sub.comment,
                )
            )
        return result

    async def check_submission(
        self, tutor_id: int, submission_id: int, comment: str = None
    ) -> LessonFile:
        sub = await self.lesson_file_repo.get(submission_id)
        if not sub or sub.kind != LessonFileKind.SUBMISSION:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found"
            )
        # проверка доступа
        lesson = await self.lesson_repo.get(sub.lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")
        link = await self.tutor_student_repo.get(lesson.tutor_student_id)
        if link.tutor_id != tutor_id:
            raise HTTPException(status_code=403, detail="Not your student")
        sub.status = SubmissionStatus.CHECKED
        sub.comment = comment
        await self.lesson_file_repo.update(sub)
        return sub
