from datetime import date, datetime, time

from fastapi import HTTPException, status

from src.core.repositories.file import FileRepository
from src.core.repositories.lesson import LessonRepository
from src.core.repositories.lesson_file import LessonFileRepository
from src.database.models import Lesson, LessonFile, LessonFileKind, SubmissionStatus
from src.schemas.student import (
    HomeworkSubmissionOut,
    LessonAttachmentOut,
    StudentLessonDetail,
    StudentLessonListOut,
    StudentLessonSummary,
)


class StudentService:
    def __init__(
        self,
        lesson_repo: LessonRepository,
        lesson_file_repo: LessonFileRepository,
        file_repo: FileRepository,
    ):
        self.lesson_repo = lesson_repo
        self.lesson_file_repo = lesson_file_repo
        self.file_repo = file_repo

    async def get_my_lessons(self, student_id: int) -> StudentLessonListOut:
        lessons = await self.lesson_repo.get_by_student(student_id)
        now = datetime.now()
        upcoming: list[StudentLessonSummary] = []
        past: list[StudentLessonSummary] = []

        for lesson in lessons:
            lesson_out = self._build_lesson_summary(lesson)
            if self._is_upcoming(lesson, now):
                upcoming.append(lesson_out)
            else:
                past.append(lesson_out)

        upcoming.sort(key=self._lesson_sort_key)
        past.sort(key=self._lesson_sort_key, reverse=True)
        return StudentLessonListOut(upcoming=upcoming, past=past)

    async def get_lesson_detail(
        self, student_id: int, lesson_id: int
    ) -> StudentLessonDetail:
        lesson = await self.lesson_repo.get_student_lesson(student_id, lesson_id)
        if not lesson:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found"
            )
        return self._build_lesson_detail(lesson)

    async def submit_homework(
        self,
        student_id: int,
        lesson_id: int,
        file_path: str,
        filename: str,
        content_type: str | None,
    ) -> HomeworkSubmissionOut:
        lesson = await self.lesson_repo.get_student_lesson(student_id, lesson_id)
        if not lesson:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found"
            )

        saved_file = await self.file_repo.create(
            path=file_path,
            filename=filename,
            type=content_type,
            uploaded_by=student_id,
        )

        submission = await self.lesson_file_repo.get_latest_submission_for_lesson(
            lesson.id
        )
        if submission:
            submission.file_id = saved_file.id
            submission.status = SubmissionStatus.SUBMITTED
            submission.comment = None
        else:
            submission = LessonFile(
                lesson_id=lesson.id,
                file_id=saved_file.id,
                kind=LessonFileKind.SUBMISSION,
                status=SubmissionStatus.SUBMITTED,
                comment=None,
            )

        lesson.homework_done = True
        saved_submission = await self.lesson_file_repo.save(submission)
        return HomeworkSubmissionOut(
            lesson_id=lesson.id,
            homework_status=self._submission_status(saved_submission),
            submission_file=self._file_to_schema(saved_file),
            submission_comment=saved_submission.comment,
        )

    def _build_lesson_summary(self, lesson: Lesson) -> StudentLessonSummary:
        materials, homework_task_files, submission = self._split_lesson_files(lesson)
        tutor = lesson.tutor_student.tutor
        tutor_name = f"{tutor.first_name} {tutor.last_name or ''}".strip()
        return StudentLessonSummary(
            id=lesson.id,
            date=lesson.l_date,
            time=lesson.l_time,
            topic=lesson.topic,
            tutor_name=tutor_name,
            meet_link=lesson.meet_link,
            materials=[self._file_to_schema(item.file) for item in materials],
            homework_task_files=[
                self._file_to_schema(item.file) for item in homework_task_files
            ],
            homework_deadline=lesson.homework_deadline,
            homework_status=self._submission_status(submission),
        )

    def _build_lesson_detail(self, lesson: Lesson) -> StudentLessonDetail:
        materials, homework_task_files, submission = self._split_lesson_files(lesson)
        tutor = lesson.tutor_student.tutor
        tutor_name = f"{tutor.first_name} {tutor.last_name or ''}".strip()
        submission_file = self._file_to_schema(submission.file) if submission else None
        return StudentLessonDetail(
            id=lesson.id,
            date=lesson.l_date,
            time=lesson.l_time,
            topic=lesson.topic,
            tutor_name=tutor_name,
            meet_link=lesson.meet_link,
            materials=[self._file_to_schema(item.file) for item in materials],
            homework_task_files=[
                self._file_to_schema(item.file) for item in homework_task_files
            ],
            homework_deadline=lesson.homework_deadline,
            homework_status=self._submission_status(submission),
            submission_file=submission_file,
            submission_comment=submission.comment if submission else None,
        )

    def _split_lesson_files(
        self, lesson: Lesson
    ) -> tuple[list[LessonFile], list[LessonFile], LessonFile | None]:
        materials: list[LessonFile] = []
        homework_task_files: list[LessonFile] = []
        submission: LessonFile | None = None

        for lesson_file in sorted(lesson.lesson_files, key=lambda item: item.id):
            if lesson_file.kind == LessonFileKind.MATERIAL:
                materials.append(lesson_file)
            elif lesson_file.kind == LessonFileKind.HOMEWORK_TASK:
                homework_task_files.append(lesson_file)
            elif lesson_file.kind == LessonFileKind.SUBMISSION:
                submission = lesson_file

        return materials, homework_task_files, submission

    def _submission_status(self, submission: LessonFile | None) -> str:
        if not submission or not submission.status:
            return "not_submitted"
        return submission.status.value

    def _file_to_schema(self, file) -> LessonAttachmentOut:
        return LessonAttachmentOut(
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

    def _lesson_sort_key(self, lesson: StudentLessonSummary):
        return (
            lesson.date or date.min,
            lesson.time or time.min,
            lesson.id,
        )
