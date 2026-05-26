from datetime import date, datetime, time

from fastapi import HTTPException, status

from core.repositories.lesson import LessonRepository
from core.repositories.parent_student import ParentStudentRepository
from core.repositories.user import UserRepository
from database.models import Lesson, LessonFile, LessonFileKind, ParentStudent, UserRole
from schemas.parent import (
    ParentChildOut,
    ParentLessonAttachmentOut,
    ParentLessonDetail,
    ParentLessonListOut,
    ParentLessonSummary,
)


class ParentService:
    def __init__(
        self,
        parent_student_repo: ParentStudentRepository,
        lesson_repo: LessonRepository,
        user_repo: UserRepository,
    ):
        self.parent_student_repo = parent_student_repo
        self.lesson_repo = lesson_repo
        self.user_repo = user_repo

    async def add_child(self, parent_id: int, email: str) -> ParentChildOut:
        student = await self.user_repo.get_by_email(email)
        if not student or student.role != UserRole.STUDENT:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Не удалось найти ученика с таким email",
            )

        existing = await self.parent_student_repo.get_by_parent_and_student(
            parent_id, student.id
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ученик уже добавлен в кабинет родителя",
            )

        link = await self.parent_student_repo.create(parent_id, student.id)
        return self._child_to_schema(link)

    async def get_children(self, parent_id: int) -> list[ParentChildOut]:
        links = await self.parent_student_repo.get_by_parent(parent_id)
        return [self._child_to_schema(link) for link in links]

    async def get_lessons(
        self, parent_id: int, student_id: int | None = None
    ) -> ParentLessonListOut:
        if student_id is not None:
            link = await self.parent_student_repo.get_by_parent_and_student(
                parent_id, student_id
            )
            if not link:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Child not found",
                )

        lessons = await self.lesson_repo.get_by_parent(parent_id, student_id)
        now = datetime.now()
        upcoming: list[ParentLessonSummary] = []
        past: list[ParentLessonSummary] = []

        for lesson in lessons:
            lesson_out = self._build_lesson_summary(lesson)
            if self._is_upcoming(lesson, now):
                upcoming.append(lesson_out)
            else:
                past.append(lesson_out)

        upcoming.sort(key=self._lesson_sort_key)
        past.sort(key=self._lesson_sort_key, reverse=True)
        return ParentLessonListOut(upcoming=upcoming, past=past)

    async def get_lesson_detail(
        self, parent_id: int, lesson_id: int
    ) -> ParentLessonDetail:
        lesson = await self.lesson_repo.get_parent_lesson(parent_id, lesson_id)
        if not lesson:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lesson not found",
            )
        return self._build_lesson_detail(lesson)

    def _child_to_schema(self, link: ParentStudent) -> ParentChildOut:
        student = link.student
        return ParentChildOut(
            id=link.id,
            student_id=student.id,
            full_name=f"{student.first_name} {student.last_name or ''}".strip(),
            created_at=link.created_at,
        )

    def _build_lesson_summary(self, lesson: Lesson) -> ParentLessonSummary:
        materials, homework_task_files, submissions, parent_message_files = self._split_lesson_files(lesson)
        submission = submissions[0] if submissions else None
        student = lesson.tutor_student.student
        tutor = lesson.tutor_student.tutor
        submission_file = self._file_to_schema(submission.file) if submission else None
        submission_files = [
            self._file_to_schema(item.file) for item in submissions if item.file
        ]
        checked_file = (
            self._file_to_schema(submission.checked_file)
            if submission and submission.checked_file
            else None
        )
        checked_files = [
            self._file_to_schema(item.checked_file)
            for item in submissions
            if item.checked_file
        ]
        return ParentLessonSummary(
            id=lesson.id,
            tutor_student_id=lesson.tutor_student_id,
            student_id=student.id,
            star_rewards_enabled=lesson.tutor_student.star_rewards_enabled,
            student_name=f"{student.first_name} {student.last_name or ''}".strip(),
            tutor_name=f"{tutor.first_name} {tutor.last_name or ''}".strip(),
            date=lesson.l_date,
            time=lesson.l_time,
            topic=lesson.topic,
            meet_link=lesson.meet_link,
            subject=lesson.subject,
            class_info=lesson.tutor_student.student_inf,
            materials=[self._file_to_schema(item.file) for item in materials],
            homework_task_files=[
                self._file_to_schema(item.file) for item in homework_task_files
            ],
            parent_message_files=[
                self._file_to_schema(item.file) for item in parent_message_files if item.file
            ],
            parent_comment=lesson.parent_comment,
            homework_deadline=lesson.homework_deadline,
            homework_deadline_missed=(
                submission.deadline_missed if submission else False
            ),
            homework_status=self._submission_status(submission),
            submission_file=submission_file,
            submission_files=submission_files,
            checked_file=checked_file,
            checked_files=checked_files,
            submission_comment=submission.comment if submission else None,
            student_comment=submission.student_comment if submission else None,
            submitted_at=submission.created_at if submission else None,
            homework_grade=submission.grade if submission else None,
            homework_stars=submission.stars_awarded if submission else 0,
        )

    def _build_lesson_detail(self, lesson: Lesson) -> ParentLessonDetail:
        return ParentLessonDetail(**self._build_lesson_summary(lesson).model_dump())

    def _split_lesson_files(
        self, lesson: Lesson
    ) -> tuple[list[LessonFile], list[LessonFile], list[LessonFile], list[LessonFile]]:
        materials: list[LessonFile] = []
        homework_task_files: list[LessonFile] = []
        submissions: list[LessonFile] = []
        parent_message_files: list[LessonFile] = []

        for lesson_file in sorted(lesson.lesson_files, key=lambda item: item.id):
            if lesson_file.kind == LessonFileKind.MATERIAL:
                materials.append(lesson_file)
            elif lesson_file.kind == LessonFileKind.HOMEWORK_TASK:
                homework_task_files.append(lesson_file)
            elif lesson_file.kind == LessonFileKind.SUBMISSION:
                submissions.append(lesson_file)
            elif lesson_file.kind == LessonFileKind.PARENT_MESSAGE:
                parent_message_files.append(lesson_file)

        return materials, homework_task_files, submissions, parent_message_files

    def _submission_status(self, submission: LessonFile | None) -> str:
        if not submission or not submission.status:
            return "not_submitted"
        return submission.status.value

    def _file_to_schema(self, file) -> ParentLessonAttachmentOut:
        return ParentLessonAttachmentOut(
            id=file.id,
            filename=file.filename,
            file_url=file.path,
            type=file.type,
        )

    def _is_upcoming(self, lesson: Lesson, now: datetime) -> bool:
        if lesson.l_date is None:
            return False
        lesson_time = lesson.l_time or time.min
        return datetime.combine(lesson.l_date, lesson_time) >= now

    def _lesson_sort_key(self, lesson: ParentLessonSummary):
        return (
            lesson.date or date.min,
            lesson.time or time.min,
            lesson.id,
        )
