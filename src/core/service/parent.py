from datetime import date, datetime, time

from fastapi import HTTPException, status

from src.core.repositories.lesson import LessonRepository
from src.core.repositories.parent_access import ParentAccessRepository
from src.core.repositories.parent_chat_message import ParentChatMessageRepository
from src.core.repositories.tutor_student import TutorStudentRepository
from src.core.repositories.user import UserRepository
from src.database.models import (
    Lesson,
    LessonFile,
    LessonFileKind,
    ParentAccess,
    ParentAccessStatus,
    ParentChatMessage,
    ParentChatSenderRole,
    SubmissionStatus,
    UserRole,
)
from src.schemas.parent import (
    ParentAccessOut,
    ParentAccessRequestCreate,
    ParentChatMessageCreate,
    ParentChatMessageOut,
    ParentLessonAttachmentOut,
    ParentLessonDetail,
    ParentLessonListOut,
    ParentLessonSummary,
)


class ParentService:
    def __init__(
        self,
        parent_access_repo: ParentAccessRepository,
        parent_chat_message_repo: ParentChatMessageRepository,
        tutor_student_repo: TutorStudentRepository,
        lesson_repo: LessonRepository,
        user_repo: UserRepository,
    ):
        self.parent_access_repo = parent_access_repo
        self.parent_chat_message_repo = parent_chat_message_repo
        self.tutor_student_repo = tutor_student_repo
        self.lesson_repo = lesson_repo
        self.user_repo = user_repo

    async def create_access_request(
        self,
        parent_id: int,
        data: ParentAccessRequestCreate,
    ) -> ParentAccessOut:
        tutor_email = self._normalize_email(str(data.tutor_email))
        student_email = self._normalize_email(str(data.student_email))

        tutor = await self.user_repo.get_by_email(tutor_email)
        if not tutor or tutor.role != UserRole.TUTOR:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Репетитор с таким email не найден",
            )

        student = await self.user_repo.get_by_email(student_email)
        if not student or student.role != UserRole.STUDENT:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ученик с таким email не найден",
            )

        tutor_student = await self.tutor_student_repo.get_by_tutor_and_student(
            tutor.id,
            student.id,
        )
        if not tutor_student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Связка репетитора и ученика не найдена",
            )

        access = await self.parent_access_repo.get_by_parent_and_tutor_student(
            parent_id,
            tutor_student.id,
        )
        request_message = self._clean_text(data.message)

        if access and access.status == ParentAccessStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Доступ уже одобрен",
            )

        if access and access.status == ParentAccessStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Запрос уже отправлен и ожидает ответа репетитора",
            )

        if access is None:
            access = ParentAccess(
                parent_id=parent_id,
                tutor_student_id=tutor_student.id,
                status=ParentAccessStatus.PENDING,
                request_message=request_message,
            )
        else:
            access.status = ParentAccessStatus.PENDING
            access.request_message = request_message
            access.review_comment = None
            access.reviewed_by = None
            access.responded_at = None

        await self.parent_access_repo.save(access)
        fresh_access = await self.parent_access_repo.get_for_parent(parent_id, access.id)
        if not fresh_access:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось получить созданный запрос доступа",
            )
        return self._build_access_out(fresh_access)

    async def get_my_accesses(
        self,
        parent_id: int,
        status_filter: ParentAccessStatus | str | None = None,
    ) -> list[ParentAccessOut]:
        if isinstance(status_filter, str):
            status_filter = ParentAccessStatus(status_filter)
        accesses = await self.parent_access_repo.list_for_parent(
            parent_id,
            status=status_filter,
        )
        return [self._build_access_out(access) for access in accesses]

    async def get_access_lessons(
        self,
        parent_id: int,
        access_id: int,
    ) -> ParentLessonListOut:
        access = await self._get_approved_access(parent_id, access_id)
        tutor_student = access.tutor_student
        lessons = await self.lesson_repo.get_by_tutor_student(
            tutor_student.tutor_id,
            tutor_student.id,
        )

        now = datetime.now()
        upcoming: list[ParentLessonSummary] = []
        past: list[ParentLessonSummary] = []
        for lesson in lessons:
            lesson_out = self._build_lesson_summary(access, lesson)
            if self._is_upcoming(lesson, now):
                upcoming.append(lesson_out)
            else:
                past.append(lesson_out)

        upcoming.sort(key=self._lesson_sort_key)
        past.sort(key=self._lesson_sort_key, reverse=True)
        return ParentLessonListOut(
            access=self._build_access_out(access),
            upcoming=upcoming,
            past=past,
        )

    async def get_lesson_detail(
        self,
        parent_id: int,
        access_id: int,
        lesson_id: int,
    ) -> ParentLessonDetail:
        access = await self._get_approved_access(parent_id, access_id)
        tutor_student = access.tutor_student
        lesson = await self.lesson_repo.get_tutor_student_lesson(
            tutor_student.tutor_id,
            tutor_student.id,
            lesson_id,
        )
        if not lesson:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Занятие не найдено",
            )
        return self._build_lesson_detail(access, lesson)

    async def get_chat_messages(
        self,
        parent_id: int,
        access_id: int,
    ) -> list[ParentChatMessageOut]:
        access = await self._get_approved_access(parent_id, access_id)
        messages = await self.parent_chat_message_repo.list_for_access(access.id)
        return [self._build_chat_message_out(message) for message in messages]

    async def send_chat_message(
        self,
        parent_id: int,
        access_id: int,
        data: ParentChatMessageCreate,
    ) -> ParentChatMessageOut:
        access = await self._get_approved_access(parent_id, access_id)
        text = self._clean_text(data.text)
        if not text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Сообщение не может быть пустым",
            )

        message = ParentChatMessage(
            parent_access_id=access.id,
            sender_id=parent_id,
            sender_role=ParentChatSenderRole.PARENT,
            text=text,
        )
        await self.parent_chat_message_repo.save(message)

        fresh_message = await self.parent_chat_message_repo.get_by_id(message.id)
        if not fresh_message:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось сохранить сообщение",
            )
        return self._build_chat_message_out(fresh_message)

    async def _get_approved_access(
        self,
        parent_id: int,
        access_id: int,
    ) -> ParentAccess:
        access = await self.parent_access_repo.get_for_parent(parent_id, access_id)
        if not access:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Доступ не найден",
            )
        if access.status != ParentAccessStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Доступ к истории занятий еще не одобрен репетитором",
            )
        return access

    def _build_access_out(self, access: ParentAccess) -> ParentAccessOut:
        tutor = access.tutor_student.tutor
        student = access.tutor_student.student
        return ParentAccessOut(
            id=access.id,
            tutor_student_id=access.tutor_student_id,
            status=access.status.value,
            tutor_id=tutor.id,
            tutor_name=self._user_full_name(tutor.first_name, tutor.last_name),
            tutor_email=tutor.email,
            student_id=student.id,
            student_name=self._user_full_name(student.first_name, student.last_name),
            student_email=student.email,
            subject=access.tutor_student.subject,
            class_info=access.tutor_student.student_inf,
            request_message=access.request_message,
            review_comment=access.review_comment,
            created_at=access.created_at,
            responded_at=access.responded_at,
            can_view_lessons=access.status == ParentAccessStatus.APPROVED,
        )

    def _build_lesson_summary(
        self,
        access: ParentAccess,
        lesson: Lesson,
    ) -> ParentLessonSummary:
        materials, homework_task_files, submission = self._split_lesson_files(lesson)
        tutor = access.tutor_student.tutor
        student = access.tutor_student.student
        return ParentLessonSummary(
            id=lesson.id,
            access_id=access.id,
            tutor_student_id=lesson.tutor_student_id,
            student_id=student.id,
            student_name=self._user_full_name(student.first_name, student.last_name),
            tutor_id=tutor.id,
            tutor_name=self._user_full_name(tutor.first_name, tutor.last_name),
            date=lesson.l_date,
            time=lesson.l_time,
            topic=lesson.topic,
            meet_link=lesson.meet_link,
            materials=[self._file_to_schema(item.file) for item in materials],
            homework_task_files=[
                self._file_to_schema(item.file) for item in homework_task_files
            ],
            homework_deadline=lesson.homework_deadline,
            homework_status=self._submission_status(submission),
        )

    def _build_lesson_detail(
        self,
        access: ParentAccess,
        lesson: Lesson,
    ) -> ParentLessonDetail:
        materials, homework_task_files, submission = self._split_lesson_files(lesson)
        tutor = access.tutor_student.tutor
        student = access.tutor_student.student
        submission_file = self._file_to_schema(submission.file) if submission else None
        return ParentLessonDetail(
            id=lesson.id,
            access_id=access.id,
            tutor_student_id=lesson.tutor_student_id,
            student_id=student.id,
            student_name=self._user_full_name(student.first_name, student.last_name),
            tutor_id=tutor.id,
            tutor_name=self._user_full_name(tutor.first_name, tutor.last_name),
            date=lesson.l_date,
            time=lesson.l_time,
            topic=lesson.topic,
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

    def _build_chat_message_out(
        self,
        message: ParentChatMessage,
    ) -> ParentChatMessageOut:
        sender = message.sender
        return ParentChatMessageOut(
            id=message.id,
            access_id=message.parent_access_id,
            sender_id=message.sender_id,
            sender_role=message.sender_role.value,
            sender_name=self._user_full_name(sender.first_name, sender.last_name),
            text=message.text,
            created_at=message.created_at,
        )

    def _split_lesson_files(
        self,
        lesson: Lesson,
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
        if submission.status == SubmissionStatus.SUBMITTED:
            return SubmissionStatus.SUBMITTED.value
        return SubmissionStatus.CHECKED.value

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

    def _user_full_name(self, first_name: str, last_name: str | None) -> str:
        return f"{first_name} {last_name or ''}".strip()

    def _normalize_email(self, email: str) -> str:
        return email.strip().lower()

    def _clean_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None
