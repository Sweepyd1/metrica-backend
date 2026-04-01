from datetime import date, datetime, time
from typing import Any, Dict, List

from core.repositories.group import GroupRepository
from fastapi import HTTPException, status

from core.repositories.tutor_student import TutorStudentRepository
from core.repositories.lesson import LessonRepository
from core.repositories.lesson_file import LessonFileRepository
from core.repositories.user import UserRepository
from database.models import (
    TutorStudent,
    Lesson,
    LessonFile,
    SubmissionStatus,
    LessonFileKind,
)
from schemas.group import GroupCreate, GroupDetailOut, GroupOut, StudentBasicOut
from schemas.tutor import (
    LessonCreate,
    LessonUpdate,
    SubmissionOut,
    TutorLessonAttachmentOut,
    TutorLessonDetail,
    TutorLessonListOut,
    TutorLessonSummary,
)


class TutorService:
    def __init__(
        self,
        tutor_student_repo: TutorStudentRepository,
        lesson_repo: LessonRepository,
        lesson_file_repo: LessonFileRepository,
        user_repo: UserRepository,
        group_repo: GroupRepository
    ):
        self.tutor_student_repo = tutor_student_repo
        self.lesson_repo = lesson_repo
        self.lesson_file_repo = lesson_file_repo
        self.user_repo = user_repo
        self.group_repo = group_repo
        

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

    async def update_lesson(
        self, tutor_id: int, lesson_id: int, data: LessonUpdate
    ) -> Lesson:
        lesson = await self.lesson_repo.get_tutor_lesson(tutor_id, lesson_id)
        if not lesson:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found"
            )

        link = await self.tutor_student_repo.get(data.tutor_student_id)
        if not link or link.tutor_id != tutor_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not your student"
            )

        lesson.tutor_student_id = data.tutor_student_id
        lesson.l_date = data.date
        lesson.l_time = data.time
        lesson.topic = data.topic
        lesson.meet_link = data.meet_link
        lesson.homework_deadline = data.homework_deadline

        await self.lesson_file_repo.sync_lesson_files(
            lesson,
            material_file_ids=data.material_file_ids,
            homework_task_file_ids=data.homework_task_file_ids,
        )
        await self.lesson_repo.save(lesson)

        updated_lesson = await self.lesson_repo.get_tutor_lesson(tutor_id, lesson_id)
        if not updated_lesson:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found"
            )
        return updated_lesson

    async def delete_lesson(self, tutor_id: int, lesson_id: int) -> None:
        lesson = await self.lesson_repo.get_tutor_lesson(tutor_id, lesson_id)
        if not lesson:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found"
            )

        await self.lesson_repo.delete(lesson.id)

    async def get_my_lessons(
        self,
        tutor_id: int,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> TutorLessonListOut:
        lessons = await self.lesson_repo.get_by_tutor(
            tutor_id, date_from=date_from, date_to=date_to
        )
        now = datetime.now()
        upcoming: list[TutorLessonSummary] = []
        past: list[TutorLessonSummary] = []

        for lesson in lessons:
            lesson_out = self._build_lesson_summary(lesson)
            if self._is_upcoming(lesson, now):
                upcoming.append(lesson_out)
            else:
                past.append(lesson_out)

        upcoming.sort(key=self._lesson_sort_key)
        past.sort(key=self._lesson_sort_key, reverse=True)
        return TutorLessonListOut(upcoming=upcoming, past=past)

    async def get_lesson_detail(
        self, tutor_id: int, lesson_id: int
    ) -> TutorLessonDetail:
        lesson = await self.lesson_repo.get_tutor_lesson(tutor_id, lesson_id)
        if not lesson:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found"
            )
        return self._build_lesson_detail(lesson)

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
        sub = await self.lesson_file_repo.get_submission_for_tutor(
            tutor_id, submission_id
        )
        if not sub or sub.kind != LessonFileKind.SUBMISSION:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found"
            )
        # проверка доступа
        sub.status = SubmissionStatus.CHECKED
        sub.comment = comment
        await self.lesson_file_repo.save(sub)
        checked_submission = await self.lesson_file_repo.get_submission_for_tutor(
            tutor_id, submission_id
        )
        if not checked_submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        return checked_submission
    async def create_group(self, tutor_id: int, data: GroupCreate) -> GroupOut:
        if data.student_ids:
            valid_student_ids = await self._validate_students_ownership(tutor_id, data.student_ids)
            if set(valid_student_ids) != set(data.student_ids):
                raise HTTPException(status_code=404,detail="One or more students do not belong to you")

        group = await self.group_repo.create(
            tutor_id=tutor_id,
            name=data.name,
            description=data.description,
        )
        if data.student_ids:
            await self.group_repo.add_students(group.id, data.student_ids)

        

        # получаем количество студентов
        student_count = await self.group_repo.count_students(group.id)

        return GroupOut(
            id=group.id,
            name=group.name,
            description=group.description,
            student_count=student_count,
            created_at=group.created_at,
        )

    async def get_my_groups(self, tutor_id: int) -> List[GroupOut]:
        groups = await self.group_repo.get_by_tutor(tutor_id)
        result = []
        for g in groups:
            count = await self.group_repo.count_students(g.id)
            result.append(GroupOut(
                id=g.id,
                name=g.name,
                description=g.description,
                student_count=count,
                created_at=g.created_at,
            ))
        return result

    async def get_group_detail(self, tutor_id: int, group_id: int) -> GroupDetailOut:
        group = await self.group_repo.get_by_id(group_id, tutor_id)
        if not group:
            raise HTTPException(status_code=404,detail="Group not found or not owned by you")

        students = await self.group_repo.get_students(group_id)
        student_out = [
            StudentBasicOut(
                id=s.id,
                full_name=f"{s.first_name} {s.last_name or ''}".strip()
            )
            for s in students
        ]

        return GroupDetailOut(
            id=group.id,
            name=group.name,
            description=group.description,
            student_count=len(student_out),
            created_at=group.created_at,
            students=student_out,
        )

    async def delete_group(self, tutor_id: int, group_id: int) -> None:
        group = await self.group_repo.get_by_id(group_id, tutor_id)
        if not group:
            raise HTTPException(status_code=404,detail="Group not found or not owned by you")
        await self.group_repo.delete(group_id)
        

    async def add_students_to_group(
        self, tutor_id: int, group_id: int, student_ids: List[int]
    ) -> GroupDetailOut:
        group = await self.group_repo.get_by_id(group_id, tutor_id)
        if not group:
            raise HTTPException(status_code=404,detail="Group not found or not owned by you")

        valid_ids = await self._validate_students_ownership(tutor_id, student_ids)
        if not valid_ids:
            raise HTTPException(status_code=404,detail="None of the students belong to you")

        await self.group_repo.add_students(group_id, valid_ids)
        
        return await self.get_group_detail(tutor_id, group_id)

    async def remove_students_from_group(
        self, tutor_id: int, group_id: int, student_ids: List[int]
    ) -> GroupDetailOut:
        group = await self.group_repo.get_by_id(group_id, tutor_id)
        if not group:
            raise HTTPException(status_code=404,detail="Group not found or not owned by you")
        await self.group_repo.remove_students(group_id, student_ids)
        
        return await self.get_group_detail(tutor_id, group_id)

    async def _validate_students_ownership(self, tutor_id: int, student_ids: List[int]) -> List[int]:
        # Этот метод может остаться в сервисе, но он использует репозиторий TutorStudentRepository
        return await self.tutor_student_repo.get_valid_student_ids(tutor_id, student_ids)
    

    def _build_lesson_summary(self, lesson: Lesson) -> TutorLessonSummary:
        materials, homework_task_files, submission = self._split_lesson_files(lesson)
        student = lesson.tutor_student.student
        student_name = f"{student.first_name} {student.last_name or ''}".strip()
        return TutorLessonSummary(
            id=lesson.id,
            tutor_student_id=lesson.tutor_student_id,
            student_id=student.id,
            student_name=student_name,
            date=lesson.l_date,
            time=lesson.l_time,
            topic=lesson.topic,
            meet_link=lesson.meet_link,
            materials=[self._file_to_schema(item.file) for item in materials],
            homework_task_files=[
                self._file_to_schema(item.file) for item in homework_task_files
            ],
            homework_deadline=lesson.homework_deadline,
            homework_done=lesson.homework_done,
            homework_status=self._submission_status(submission),
        )

    def _build_lesson_detail(self, lesson: Lesson) -> TutorLessonDetail:
        materials, homework_task_files, submission = self._split_lesson_files(lesson)
        student = lesson.tutor_student.student
        student_name = f"{student.first_name} {student.last_name or ''}".strip()
        submission_file = self._file_to_schema(submission.file) if submission else None
        return TutorLessonDetail(
            id=lesson.id,
            tutor_student_id=lesson.tutor_student_id,
            student_id=student.id,
            student_name=student_name,
            date=lesson.l_date,
            time=lesson.l_time,
            topic=lesson.topic,
            meet_link=lesson.meet_link,
            materials=[self._file_to_schema(item.file) for item in materials],
            homework_task_files=[
                self._file_to_schema(item.file) for item in homework_task_files
            ],
            homework_deadline=lesson.homework_deadline,
            homework_done=lesson.homework_done,
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

    def _file_to_schema(self, file) -> TutorLessonAttachmentOut:
        return TutorLessonAttachmentOut(
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

    def _lesson_sort_key(self, lesson: TutorLessonSummary):
        return (
            lesson.date or date.min,
            lesson.time or time.min,
            lesson.id,
        )
