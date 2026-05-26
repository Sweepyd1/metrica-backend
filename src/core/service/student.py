from datetime import date, datetime, time

from fastapi import HTTPException, status

from core.repositories.bonus_task import BonusTaskRepository
from core.repositories.file import FileRepository
from core.repositories.lesson import LessonRepository
from core.repositories.lesson_file import LessonFileRepository
from core.repositories.tutor_student import TutorStudentRepository
from database.models import Lesson, LessonFile, LessonFileKind, SubmissionStatus
from schemas.gamification import BonusTaskOut, GamificationOut
from schemas.student import (
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
        bonus_task_repo: BonusTaskRepository,
        tutor_student_repo: TutorStudentRepository,
    ):
        self.lesson_repo = lesson_repo
        self.lesson_file_repo = lesson_file_repo
        self.file_repo = file_repo
        self.bonus_task_repo = bonus_task_repo
        self.tutor_student_repo = tutor_student_repo

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

    async def get_gamification(self, student_id: int) -> list[GamificationOut]:
        links = await self.tutor_student_repo.get_by_student(student_id)
        result: list[GamificationOut] = []
        for link in links:
            result.append(await self._build_gamification(link))
        return result

    async def submit_homework(
        self,
        student_id: int,
        lesson_id: int,
        uploaded_files: list[tuple[str, str, str | None]],
        existing_file_ids: list[int] | None = None,
        student_comment: str | None = None,
    ) -> HomeworkSubmissionOut:
        lesson = await self.lesson_repo.get_student_lesson(student_id, lesson_id)
        if not lesson:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found"
            )

        existing_file_ids = existing_file_ids or []
        current_submissions = await self.lesson_file_repo.get_submissions_for_lesson(
            lesson.id
        )
        available_existing_ids = {
            submission.file_id
            for submission in current_submissions
            if submission.file_id is not None
        }

        for file_id in existing_file_ids:
            if file_id not in available_existing_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Submission file is not available",
                )

        if not uploaded_files and not existing_file_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one file is required",
            )

        saved_files = []
        for file_path, filename, content_type in uploaded_files:
            saved_files.append(
                await self.file_repo.create(
                    path=file_path,
                    filename=filename,
                    type=content_type,
                    uploaded_by=student_id,
                )
            )

        lesson.homework_done = True
        deadline_missed = (
            lesson.homework_deadline is not None
            and datetime.now().date() > lesson.homework_deadline
        )
        await self.lesson_file_repo.replace_submissions_for_lesson(
            lesson.id,
            [*existing_file_ids, *[file.id for file in saved_files]],
            deadline_missed=deadline_missed,
            student_comment=student_comment.strip() if student_comment else None,
        )
        saved_submissions = await self.lesson_file_repo.get_submissions_for_lesson(
            lesson.id
        )
        saved_submission = saved_submissions[0] if saved_submissions else None
        return HomeworkSubmissionOut(
            lesson_id=lesson.id,
            star_rewards_enabled=lesson.tutor_student.star_rewards_enabled,
            homework_status=self._submission_status(saved_submission),
            homework_deadline_missed=(
                saved_submission.deadline_missed if saved_submission else False
            ),
            submission_file=(
                self._file_to_schema(saved_submission.file)
                if saved_submission and saved_submission.file
                else None
            ),
            submission_files=[
                self._file_to_schema(item.file)
                for item in saved_submissions
                if item.file
            ],
            checked_file=None,
            checked_files=[],
            submission_comment=saved_submission.comment if saved_submission else None,
            student_comment=saved_submission.student_comment if saved_submission else None,
            submitted_at=saved_submission.created_at if saved_submission else None,
            homework_grade=saved_submission.grade if saved_submission else None,
            homework_stars=saved_submission.stars_awarded if saved_submission else 0,
        )

    def _build_lesson_summary(self, lesson: Lesson) -> StudentLessonSummary:
        materials, homework_task_files, submissions = self._split_lesson_files(lesson)
        submission = submissions[0] if submissions else None
        tutor = lesson.tutor_student.tutor
        tutor_name = f"{tutor.first_name} {tutor.last_name or ''}".strip()
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
        return StudentLessonSummary(
            id=lesson.id,
            star_rewards_enabled=lesson.tutor_student.star_rewards_enabled,
            date=lesson.l_date,
            time=lesson.l_time,
            subject=lesson.subject,
            topic=lesson.topic,
            tutor_name=tutor_name,
            meet_link=lesson.meet_link,
            materials=[self._file_to_schema(item.file) for item in materials],
            homework_task_files=[
                self._file_to_schema(item.file) for item in homework_task_files
            ],
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

    def _build_lesson_detail(self, lesson: Lesson) -> StudentLessonDetail:
        materials, homework_task_files, submissions = self._split_lesson_files(lesson)
        submission = submissions[0] if submissions else None
        tutor = lesson.tutor_student.tutor
        tutor_name = f"{tutor.first_name} {tutor.last_name or ''}".strip()
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
        return StudentLessonDetail(
            id=lesson.id,
            star_rewards_enabled=lesson.tutor_student.star_rewards_enabled,
            date=lesson.l_date,
            time=lesson.l_time,
            subject=lesson.subject,
            topic=lesson.topic,
            tutor_name=tutor_name,
            meet_link=lesson.meet_link,
            materials=[self._file_to_schema(item.file) for item in materials],
            homework_task_files=[
                self._file_to_schema(item.file) for item in homework_task_files
            ],
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

    async def _build_gamification(self, link) -> GamificationOut:
        homework_stars = await self._get_homework_stars_for_link(link.id)
        bonus_stars = await self._get_bonus_stars_for_link(link.id)
        tasks = await self.bonus_task_repo.get_for_tutor_student(link.id)
        tutor = link.tutor
        tutor_name = f"{tutor.first_name} {tutor.last_name or ''}".strip()
        student = link.student
        student_name = f"{student.first_name} {student.last_name or ''}".strip()
        return GamificationOut(
            tutor_student_id=link.id,
            student_id=link.student_id,
            student_name=student_name,
            tutor_name=tutor_name,
            star_rewards_enabled=link.star_rewards_enabled,
            star_goal=link.star_goal,
            star_reward_title=link.star_reward_title,
            homework_stars=homework_stars,
            bonus_stars=bonus_stars,
            earned_stars=homework_stars + bonus_stars,
            bonus_tasks=[self._bonus_task_to_schema(task) for task in tasks],
        )

    async def _get_homework_stars_for_link(self, tutor_student_id: int) -> float:
        lessons = await self.lesson_repo.get_by_tutor_student(tutor_student_id)
        total = 0.0
        for lesson in lessons:
            counted_lesson = False
            for lesson_file in lesson.lesson_files:
                if lesson_file.kind == LessonFileKind.SUBMISSION and not counted_lesson:
                    total += lesson_file.stars_awarded or 0
                    counted_lesson = True
        return total

    async def _get_bonus_stars_for_link(self, tutor_student_id: int) -> float:
        tasks = await self.bonus_task_repo.get_for_tutor_student(tutor_student_id)
        return sum(task.stars for task in tasks if task.is_completed)

    def _bonus_task_to_schema(self, task) -> BonusTaskOut:
        return BonusTaskOut(
            id=task.id,
            tutor_student_id=task.tutor_student_id,
            title=task.title,
            description=task.description,
            stars=task.stars,
            reward_title=task.reward_title,
            due_date=task.due_date,
            is_completed=task.is_completed,
            created_at=task.created_at,
            completed_at=task.completed_at,
        )

    def _split_lesson_files(
        self, lesson: Lesson
    ) -> tuple[list[LessonFile], list[LessonFile], list[LessonFile]]:
        materials: list[LessonFile] = []
        homework_task_files: list[LessonFile] = []
        submissions: list[LessonFile] = []

        for lesson_file in sorted(lesson.lesson_files, key=lambda item: item.id):
            if lesson_file.kind == LessonFileKind.MATERIAL:
                materials.append(lesson_file)
            elif lesson_file.kind == LessonFileKind.HOMEWORK_TASK:
                homework_task_files.append(lesson_file)
            elif lesson_file.kind == LessonFileKind.SUBMISSION:
                submissions.append(lesson_file)

        return materials, homework_task_files, submissions

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
