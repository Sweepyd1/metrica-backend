from datetime import date, datetime, time
from typing import Any, Dict, List

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.repositories.group import GroupRepository
from src.core.repositories.tutor_student import TutorStudentRepository
from src.core.repositories.lesson import LessonRepository
from src.core.repositories.lesson_file import LessonFileRepository
from src.core.repositories.parent_access import ParentAccessRepository
from src.core.repositories.parent_chat_message import ParentChatMessageRepository
from src.core.repositories.star_transaction import StarTransactionRepository
from src.core.repositories.user import UserRepository
from src.database.models import (
    TutorStudent,
    Lesson,
    LessonFile,
    ParentAccess,
    ParentAccessStatus,
    ParentChatMessage,
    ParentChatSenderRole,
    StarTransaction,
    StarTransactionType,
    SubmissionStatus,
    LessonFileKind,
    UserRole,
)
from src.schemas.group import GroupCreate, GroupDetailOut, GroupOut, StudentBasicOut
from src.schemas.parent import (
    ParentChatMessageCreate,
    ParentChatMessageOut,
    TutorParentAccessRequestOut,
)
from src.schemas.tutor import (
    LessonCreate,
    LessonUpdate,
    StarTransactionCreate,
    StarTransactionOut,
    SubmissionOut,
    TutorLessonAttachmentOut,
    TutorLessonDetail,
    TutorLessonListOut,
    TutorLessonProgressItem,
    TutorLessonProgressTreeOut,
    TutorStudentStarsOut,
    TutorLessonSummary,
)


class TutorService:
    def __init__(
        self,
        tutor_student_repo: TutorStudentRepository,
        lesson_repo: LessonRepository,
        lesson_file_repo: LessonFileRepository,
        parent_access_repo: ParentAccessRepository,
        parent_chat_message_repo: ParentChatMessageRepository,
        star_transaction_repo: StarTransactionRepository,
        user_repo: UserRepository,
        session: AsyncSession,
        group_repo: GroupRepository,
    ):
        self.tutor_student_repo = tutor_student_repo
        self.lesson_repo = lesson_repo
        self.lesson_file_repo = lesson_file_repo
        self.parent_access_repo = parent_access_repo
        self.parent_chat_message_repo = parent_chat_message_repo
        self.star_transaction_repo = star_transaction_repo
        self.user_repo = user_repo
        self.session = session
        self.group_repo = group_repo

    async def add_student(self, tutor_id: int, email: str) -> TutorStudent:
        student = await self.user_repo.get_by_email(email)
        if not student or student.role != UserRole.STUDENT:
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
                    "star_balance": link.star_balance,
                    "last_submission_id": sub_id,
                    "last_submission_status": status_str,
                }
            )
        return result

    async def get_parent_access_requests(
        self,
        tutor_id: int,
        status_filter: ParentAccessStatus | str | None = None,
    ) -> List[TutorParentAccessRequestOut]:
        if isinstance(status_filter, str):
            status_filter = ParentAccessStatus(status_filter)
        accesses = await self.parent_access_repo.list_for_tutor(
            tutor_id,
            status=status_filter,
        )
        return [self._build_parent_access_request_out(access) for access in accesses]

    async def approve_parent_access_request(
        self,
        tutor_id: int,
        request_id: int,
        comment: str | None = None,
    ) -> TutorParentAccessRequestOut:
        return await self._review_parent_access_request(
            tutor_id=tutor_id,
            request_id=request_id,
            target_status=ParentAccessStatus.APPROVED,
            comment=comment,
        )

    async def reject_parent_access_request(
        self,
        tutor_id: int,
        request_id: int,
        comment: str | None = None,
    ) -> TutorParentAccessRequestOut:
        return await self._review_parent_access_request(
            tutor_id=tutor_id,
            request_id=request_id,
            target_status=ParentAccessStatus.REJECTED,
            comment=comment,
        )

    async def get_parent_access_messages(
        self,
        tutor_id: int,
        access_id: int,
    ) -> List[ParentChatMessageOut]:
        access = await self._get_approved_parent_access_for_tutor(tutor_id, access_id)
        messages = await self.parent_chat_message_repo.list_for_access(access.id)
        return [self._build_parent_chat_message_out(message) for message in messages]

    async def send_parent_access_message(
        self,
        tutor_id: int,
        access_id: int,
        data: ParentChatMessageCreate,
    ) -> ParentChatMessageOut:
        access = await self._get_approved_parent_access_for_tutor(tutor_id, access_id)
        text = self._clean_text(data.text)
        if not text:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Сообщение не может быть пустым",
            )

        message = ParentChatMessage(
            parent_access_id=access.id,
            sender_id=tutor_id,
            sender_role=ParentChatSenderRole.TUTOR,
            text=text,
        )
        await self.parent_chat_message_repo.save(message)

        fresh_message = await self.parent_chat_message_repo.get_by_id(message.id)
        if not fresh_message:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Не удалось сохранить сообщение",
            )
        return self._build_parent_chat_message_out(fresh_message)

    async def get_student_stars(
        self, tutor_id: int, tutor_student_id: int, limit: int = 50
    ) -> TutorStudentStarsOut:
        link = await self.tutor_student_repo.get_for_tutor(tutor_id, tutor_student_id)
        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student link not found",
            )

        transactions = await self.star_transaction_repo.get_by_tutor_student(
            tutor_id, tutor_student_id, limit=limit
        )
        return self._build_student_stars_out(link, transactions)

    async def accrue_stars(
        self,
        tutor_id: int,
        tutor_student_id: int,
        data: StarTransactionCreate,
    ) -> StarTransactionOut:
        return await self._create_star_transaction(
            tutor_id=tutor_id,
            tutor_student_id=tutor_student_id,
            data=data,
            transaction_type=StarTransactionType.ACCRUAL,
        )

    async def write_off_stars(
        self,
        tutor_id: int,
        tutor_student_id: int,
        data: StarTransactionCreate,
    ) -> StarTransactionOut:
        return await self._create_star_transaction(
            tutor_id=tutor_id,
            tutor_student_id=tutor_student_id,
            data=data,
            transaction_type=StarTransactionType.WRITE_OFF,
        )

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

    async def get_student_progress_tree(
        self, tutor_id: int, tutor_student_id: int
    ) -> TutorLessonProgressTreeOut:
        link = await self.tutor_student_repo.get_for_tutor(tutor_id, tutor_student_id)
        if not link:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student link not found",
            )

        lessons = await self.lesson_repo.get_by_tutor_student(tutor_id, tutor_student_id)
        now = datetime.now()
        completed_lessons = 0
        upcoming_lessons = 0
        unscheduled_lessons = 0
        items: list[TutorLessonProgressItem] = []

        for sequence_number, lesson in enumerate(lessons, start=1):
            progress_status = self._progress_status(lesson, now)
            if progress_status == "completed":
                completed_lessons += 1
            elif progress_status == "upcoming":
                upcoming_lessons += 1
            else:
                unscheduled_lessons += 1

            items.append(
                self._build_lesson_progress_item(
                    lesson,
                    sequence_number=sequence_number,
                    progress_status=progress_status,
                )
            )

        student = link.student
        student_name = f"{student.first_name} {student.last_name or ''}".strip()
        return TutorLessonProgressTreeOut(
            tutor_student_id=link.id,
            student_id=student.id,
            student_name=student_name,
            subject=link.subject,
            class_info=link.student_inf,
            total_lessons=len(items),
            completed_lessons=completed_lessons,
            upcoming_lessons=upcoming_lessons,
            unscheduled_lessons=unscheduled_lessons,
            items=items,
        )

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
            valid_student_ids = await self._validate_students_ownership(
                tutor_id, data.student_ids
            )
            if set(valid_student_ids) != set(data.student_ids):
                raise HTTPException(
                    status_code=404,
                    detail="One or more students do not belong to you",
                )

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
            raise HTTPException(
                status_code=404, detail="Group not found or not owned by you"
            )

        students = await self.group_repo.get_students(group_id)
        student_out = [
            StudentBasicOut(id=s.id, full_name=f"{s.first_name} {s.last_name or ''}".strip())
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
            raise HTTPException(
                status_code=404, detail="Group not found or not owned by you"
            )
        await self.group_repo.delete(group_id)

    async def add_students_to_group(
        self, tutor_id: int, group_id: int, student_ids: List[int]
    ) -> GroupDetailOut:
        group = await self.group_repo.get_by_id(group_id, tutor_id)
        if not group:
            raise HTTPException(
                status_code=404, detail="Group not found or not owned by you"
            )

        valid_ids = await self._validate_students_ownership(tutor_id, student_ids)
        if not valid_ids:
            raise HTTPException(
                status_code=404, detail="None of the students belong to you"
            )

        await self.group_repo.add_students(group_id, valid_ids)

        return await self.get_group_detail(tutor_id, group_id)

    async def remove_students_from_group(
        self, tutor_id: int, group_id: int, student_ids: List[int]
    ) -> GroupDetailOut:
        group = await self.group_repo.get_by_id(group_id, tutor_id)
        if not group:
            raise HTTPException(
                status_code=404, detail="Group not found or not owned by you"
            )
        await self.group_repo.remove_students(group_id, student_ids)

        return await self.get_group_detail(tutor_id, group_id)

    async def _validate_students_ownership(
        self, tutor_id: int, student_ids: List[int]
    ) -> List[int]:
        # Этот метод может остаться в сервисе, но он использует репозиторий TutorStudentRepository
        return await self.tutor_student_repo.get_valid_student_ids(tutor_id, student_ids)

    async def _review_parent_access_request(
        self,
        *,
        tutor_id: int,
        request_id: int,
        target_status: ParentAccessStatus,
        comment: str | None,
    ) -> TutorParentAccessRequestOut:
        access = await self.parent_access_repo.get_for_tutor(tutor_id, request_id)
        if not access:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запрос родителя не найден",
            )

        if access.status != ParentAccessStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Запрос уже обработан",
            )

        access.status = target_status
        access.review_comment = self._clean_text(comment)
        access.reviewed_by = tutor_id
        access.responded_at = datetime.utcnow()
        await self.parent_access_repo.save(access)

        refreshed_access = await self.parent_access_repo.get_for_tutor(tutor_id, request_id)
        if not refreshed_access:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запрос родителя не найден",
            )
        return self._build_parent_access_request_out(refreshed_access)

    async def _get_approved_parent_access_for_tutor(
        self,
        tutor_id: int,
        access_id: int,
    ) -> ParentAccess:
        access = await self.parent_access_repo.get_for_tutor(tutor_id, access_id)
        if not access:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Доступ родителя не найден",
            )
        if access.status != ParentAccessStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Чат доступен только после одобрения доступа родителя",
            )
        return access

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

    def _build_lesson_progress_item(
        self,
        lesson: Lesson,
        *,
        sequence_number: int,
        progress_status: str,
    ) -> TutorLessonProgressItem:
        materials, homework_task_files, submission = self._split_lesson_files(lesson)
        submission_file = self._file_to_schema(submission.file) if submission else None
        return TutorLessonProgressItem(
            id=lesson.id,
            sequence_number=sequence_number,
            progress_status=progress_status,
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

    def _build_student_stars_out(
        self,
        link: TutorStudent,
        transactions: list[StarTransaction],
    ) -> TutorStudentStarsOut:
        student = link.student
        student_name = f"{student.first_name} {student.last_name or ''}".strip()
        return TutorStudentStarsOut(
            tutor_student_id=link.id,
            student_id=student.id,
            student_name=student_name,
            subject=link.subject,
            class_info=link.student_inf,
            star_balance=link.star_balance,
            transactions=[
                self._star_transaction_to_schema(link, transaction)
                for transaction in transactions
            ],
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

    def _star_transaction_to_schema(
        self,
        link: TutorStudent,
        transaction: StarTransaction,
        *,
        lesson: Lesson | None = None,
    ) -> StarTransactionOut:
        student = link.student
        student_name = f"{student.first_name} {student.last_name or ''}".strip()
        related_lesson = lesson or transaction.lesson
        return StarTransactionOut(
            id=transaction.id,
            tutor_student_id=link.id,
            student_id=student.id,
            student_name=student_name,
            lesson_id=related_lesson.id if related_lesson else None,
            lesson_topic=related_lesson.topic if related_lesson else None,
            lesson_date=related_lesson.l_date if related_lesson else None,
            delta=transaction.delta,
            balance_after=transaction.balance_after,
            transaction_type=transaction.transaction_type.value,
            reason=transaction.reason,
            created_at=transaction.created_at,
        )

    async def _create_star_transaction(
        self,
        *,
        tutor_id: int,
        tutor_student_id: int,
        data: StarTransactionCreate,
        transaction_type: StarTransactionType,
    ) -> StarTransactionOut:
        try:
            link = await self.tutor_student_repo.get_for_tutor(
                tutor_id, tutor_student_id, for_update=True
            )
            if not link:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Student link not found",
                )

            lesson = None
            if data.lesson_id is not None:
                lesson = await self.lesson_repo.get_tutor_student_lesson(
                    tutor_id, tutor_student_id, data.lesson_id
                )
                if not lesson:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Lesson not found",
                    )

            delta = data.amount
            if transaction_type == StarTransactionType.WRITE_OFF:
                delta = -delta

            new_balance = link.star_balance + delta
            if new_balance < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Insufficient stars",
                )

            link.star_balance = new_balance
            transaction = await self.star_transaction_repo.create_pending(
                tutor_student_id=link.id,
                lesson_id=lesson.id if lesson else None,
                created_by=tutor_id,
                delta=delta,
                balance_after=new_balance,
                transaction_type=transaction_type,
                reason=data.reason,
            )

            self.session.add(link)
            await self.session.commit()
            await self.session.refresh(transaction)
            return self._star_transaction_to_schema(link, transaction, lesson=lesson)
        except HTTPException:
            await self.session.rollback()
            raise
        except Exception:
            await self.session.rollback()
            raise

    def _progress_status(self, lesson: Lesson, now: datetime) -> str:
        if lesson.l_date is None:
            return "unscheduled"
        if self._is_upcoming(lesson, now):
            return "upcoming"
        return "completed"

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

    def _build_parent_access_request_out(
        self,
        access: ParentAccess,
    ) -> TutorParentAccessRequestOut:
        parent = access.parent
        student = access.tutor_student.student
        return TutorParentAccessRequestOut(
            id=access.id,
            tutor_student_id=access.tutor_student_id,
            status=access.status.value,
            parent_id=parent.id,
            parent_name=f"{parent.first_name} {parent.last_name or ''}".strip(),
            parent_email=parent.email,
            student_id=student.id,
            student_name=f"{student.first_name} {student.last_name or ''}".strip(),
            request_message=access.request_message,
            review_comment=access.review_comment,
            created_at=access.created_at,
            responded_at=access.responded_at,
        )

    def _build_parent_chat_message_out(
        self,
        message: ParentChatMessage,
    ) -> ParentChatMessageOut:
        sender = message.sender
        return ParentChatMessageOut(
            id=message.id,
            access_id=message.parent_access_id,
            sender_id=message.sender_id,
            sender_role=message.sender_role.value,
            sender_name=f"{sender.first_name} {sender.last_name or ''}".strip(),
            text=message.text,
            created_at=message.created_at,
        )

    def _clean_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None
