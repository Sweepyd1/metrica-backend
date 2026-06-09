from datetime import date, datetime, time
from typing import Any, Dict, List

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.repositories.bonus_task import BonusTaskRepository
from src.core.repositories.file import FileRepository
from src.core.repositories.group import GroupRepository
from src.core.repositories.lesson import LessonRepository
from src.core.repositories.lesson_file import LessonFileRepository
from src.core.repositories.parent_access import ParentAccessRepository
from src.core.repositories.parent_chat_message import ParentChatMessageRepository
from src.core.repositories.star_transaction import StarTransactionRepository
from src.core.repositories.tutor_student import TutorStudentRepository
from src.core.repositories.user import UserRepository
from src.database.models import (
    BonusTask,
    Lesson,
    LessonFile,
    LessonFileKind,
    ParentAccess,
    ParentAccessStatus,
    ParentChatMessage,
    ParentChatSenderRole,
    StarTransaction,
    StarTransactionType,
    SubmissionStatus,
    TutorStudent,
    UserRole,
)
from src.schemas.group import GroupCreate, GroupDetailOut, GroupOut, StudentBasicOut
from src.schemas.parent import (
    ParentChatMessageCreate,
    ParentChatMessageOut,
    TutorParentAccessRequestOut,
)
from src.schemas.gamification import (
    BonusTaskCreate,
    BonusTaskOut,
    BonusTaskUpdate,
    GamificationOut,
    GamificationSettingsUpdate,
)
from src.schemas.tutor import (
    LessonCreate,
    LessonUpdate,
    StarTransactionCreate,
    StarTransactionOut,
    SubmissionOut,
    SubmissionCheck,
    TutorLessonAttachmentOut,
    TutorLessonDetail,
    TutorLessonListOut,
    TutorLessonProgressItem,
    TutorLessonProgressTreeOut,
    TutorStudentStarsOut,
    TutorLessonSummary,
    TutorStudentUpdate,
    ParentLessonMessageUpdate,
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
        file_repo: FileRepository,
        bonus_task_repo: BonusTaskRepository,
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
        self.file_repo = file_repo
        self.bonus_task_repo = bonus_task_repo

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

    async def _get_total_stars_for_link(self, tutor_student_id: int) -> float:
        return (
            await self._get_homework_stars_for_link(tutor_student_id)
            + await self._get_bonus_stars_for_link(tutor_student_id)
        )

    async def get_my_students(self, tutor_id: int) -> List[Dict[str, Any]]:
        links = await self.tutor_student_repo.get_by_tutor(tutor_id)
        return [await self._student_link_to_schema_data(link) for link in links]

    async def update_student(
        self, tutor_id: int, tutor_student_id: int, data: TutorStudentUpdate
    ) -> Dict[str, Any]:
        link = await self._get_owned_link(tutor_id, tutor_student_id)
        update_data = data.model_dump(exclude_unset=True)
        student = link.student

        if "email" in update_data:
            email = str(update_data["email"]).strip()
            existing_user = await self.user_repo.get_by_email(email)
            if existing_user and existing_user.id != student.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Пользователь с таким email уже существует",
                )
            student.email = email

        if "first_name" in update_data:
            first_name = update_data["first_name"].strip()
            if not first_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Имя ученика не может быть пустым",
                )
            student.first_name = first_name

        if "last_name" in update_data:
            last_name = update_data["last_name"]
            student.last_name = last_name.strip() if last_name else None

        if "subject" in update_data:
            subject = update_data["subject"]
            link.subject = subject.strip() if subject else None

        if "class_info" in update_data:
            class_info = update_data["class_info"]
            link.student_inf = class_info.strip() if class_info else None

        if "parent_contact_enabled" in update_data:
            link.parent_contact_enabled = bool(update_data["parent_contact_enabled"])

        self.tutor_student_repo.session.add(student)
        self.tutor_student_repo.session.add(link)
        await self.tutor_student_repo.session.commit()
        updated_link = await self.tutor_student_repo.get_with_student(link.id)
        if not updated_link:
            raise HTTPException(status_code=404, detail="Student link not found")
        return await self._student_link_to_schema_data(updated_link)

    async def delete_student(self, tutor_id: int, tutor_student_id: int) -> None:
        link = await self._get_owned_link(tutor_id, tutor_student_id)
        await self.tutor_student_repo.delete(link.id)

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
            subject=data.subject.strip() if data.subject else None,
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
        lesson.subject = data.subject.strip() if data.subject else None
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

    async def update_parent_lesson_message(
        self, tutor_id: int, lesson_id: int, data: ParentLessonMessageUpdate
    ) -> TutorLessonDetail:
        lesson = await self.lesson_repo.get_tutor_lesson(tutor_id, lesson_id)
        if not lesson:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found"
            )

        if not lesson.tutor_student.parent_contact_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent contact is disabled for this student",
            )

        files = []
        for file_id in list(dict.fromkeys(data.file_ids)):
            file = await self.file_repo.get_by_id(file_id)
            if not file or file.uploaded_by != tutor_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="File is not available",
                )
            files.append(file)

        lesson.parent_comment = data.comment.strip() if data.comment else None
        current_files = [
            lesson_file
            for lesson_file in lesson.lesson_files
            if lesson_file.kind == LessonFileKind.PARENT_MESSAGE
        ]
        for lesson_file in current_files:
            await self.lesson_file_repo.session.delete(lesson_file)
        await self.lesson_file_repo.session.flush()

        for file in files:
            self.lesson_file_repo.session.add(
                LessonFile(
                    lesson_id=lesson.id,
                    file_id=file.id,
                    kind=LessonFileKind.PARENT_MESSAGE,
                )
            )

        self.lesson_repo.session.add(lesson)
        await self.lesson_repo.session.commit()
        updated_lesson = await self.lesson_repo.get_tutor_lesson(tutor_id, lesson_id)
        if not updated_lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")
        return self._build_lesson_detail(updated_lesson)

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
        grouped_submissions: dict[int, LessonFile] = {}
        for submission in submissions:
            grouped_submissions.setdefault(submission.lesson_id, submission)
        return [self._submission_to_schema(sub) for sub in grouped_submissions.values()]

    async def get_submissions(
        self, tutor_id: int, status_filter: str | None = None
    ) -> List[SubmissionOut]:
        status_value: SubmissionStatus | None = None
        if status_filter:
            try:
                status_value = SubmissionStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unknown submission status",
                )
        submissions = await self.lesson_file_repo.get_for_tutor(tutor_id, status_value)
        grouped_submissions: dict[int, LessonFile] = {}
        for submission in submissions:
            grouped_submissions.setdefault(submission.lesson_id, submission)
        return [self._submission_to_schema(sub) for sub in grouped_submissions.values()]

    async def check_submission(
        self, tutor_id: int, submission_id: int, check_data: SubmissionCheck
    ) -> SubmissionOut:
        sub = await self.lesson_file_repo.get_submission_for_tutor(
            tutor_id, submission_id
        )
        if not sub or sub.kind != LessonFileKind.SUBMISSION:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found"
            )

        checked_file_ids = list(check_data.checked_file_ids)
        if check_data.checked_file_id is not None and not checked_file_ids:
            checked_file_ids.append(check_data.checked_file_id)

        checked_files = []
        for checked_file_id in checked_file_ids:
            checked_file = await self.file_repo.get_by_id(checked_file_id)
            if not checked_file or checked_file.uploaded_by != tutor_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Checked file is not available",
                )
            checked_files.append(checked_file)

        rewards_enabled = sub.lesson.tutor_student.star_rewards_enabled
        lesson_submissions = await self.lesson_file_repo.get_submissions_for_lesson(
            sub.lesson_id
        )

        for index, lesson_submission in enumerate(lesson_submissions):
            lesson_submission.status = SubmissionStatus.CHECKED
            lesson_submission.comment = check_data.comment
            lesson_submission.grade = check_data.grade
            lesson_submission.stars_awarded = (
                check_data.grade if rewards_enabled and check_data.grade else 0
            )
            lesson_submission.checked_file_id = (
                checked_files[index].id if index < len(checked_files) else None
            )

        await self.lesson_file_repo.save_many(lesson_submissions)
        checked_submission = await self.lesson_file_repo.get_submission_for_tutor(
            tutor_id, submission_id
        )
        if not checked_submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        return self._submission_to_schema(checked_submission)

    async def get_student_gamification(
        self, tutor_id: int, tutor_student_id: int
    ) -> GamificationOut:
        link = await self._get_owned_link(tutor_id, tutor_student_id)
        return await self._build_gamification(link)

    async def update_student_gamification(
        self,
        tutor_id: int,
        tutor_student_id: int,
        data: GamificationSettingsUpdate,
    ) -> GamificationOut:
        link = await self._get_owned_link(tutor_id, tutor_student_id)
        link.star_rewards_enabled = data.star_rewards_enabled
        link.star_goal = data.star_goal
        link.star_reward_title = data.star_reward_title
        lessons = await self.lesson_repo.get_by_tutor_student(link.id)
        for lesson in lessons:
            for lesson_file in lesson.lesson_files:
                if lesson_file.kind == LessonFileKind.SUBMISSION:
                    lesson_file.stars_awarded = (
                        lesson_file.grade
                        if data.star_rewards_enabled and lesson_file.grade
                        else 0
                    )
                    self.tutor_student_repo.session.add(lesson_file)
        self.tutor_student_repo.session.add(link)
        await self.tutor_student_repo.session.commit()
        await self.tutor_student_repo.session.refresh(link)
        return await self._build_gamification(link)

    async def create_bonus_task(
        self, tutor_id: int, tutor_student_id: int, data: BonusTaskCreate
    ) -> BonusTaskOut:
        link = await self._get_owned_link(tutor_id, tutor_student_id)
        if link.star_rewards_enabled and not link.star_goal:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Сначала укажите цель в звездах",
            )
        if link.star_rewards_enabled and not data.stars:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Укажите количество звезд за бонусное задание",
            )
        if not link.star_rewards_enabled and not (data.reward_title or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Укажите награду за бонусное задание",
            )

        task = await self.bonus_task_repo.create(
            tutor_student_id=tutor_student_id,
            title=data.title,
            description=data.description,
            stars=data.stars if link.star_rewards_enabled else 0,
            reward_title=(
                data.reward_title.strip()
                if data.reward_title and not link.star_rewards_enabled
                else None
            ),
            due_date=data.due_date,
            is_completed=False,
        )
        return self._bonus_task_to_schema(task)

    async def update_bonus_task(
        self, tutor_id: int, task_id: int, data: BonusTaskUpdate
    ) -> BonusTaskOut:
        task = await self.bonus_task_repo.get_for_tutor(tutor_id, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Bonus task not found")

        update_data = data.model_dump(exclude_unset=True)
        rewards_enabled = task.tutor_student.star_rewards_enabled
        if "is_completed" in update_data:
            is_completed = update_data["is_completed"]
            if is_completed and not task.is_completed:
                task.completed_at = datetime.now()
            if not is_completed:
                task.completed_at = None

        for key, value in update_data.items():
            if key == "stars" and not rewards_enabled:
                continue
            if key == "reward_title":
                value = value.strip() if value else None
            setattr(task, key, value)

        if rewards_enabled:
            task.reward_title = None
        else:
            task.stars = 0

        return self._bonus_task_to_schema(await self.bonus_task_repo.save(task))

    async def _get_owned_link(
        self, tutor_id: int, tutor_student_id: int
    ) -> TutorStudent:
        link = await self.tutor_student_repo.get_with_student(tutor_student_id)
        if not link or link.tutor_id != tutor_id:
            raise HTTPException(status_code=404, detail="Student link not found")
        return link

    async def _student_link_to_schema_data(self, link: TutorStudent) -> Dict[str, Any]:
        student = link.student
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
        earned_stars = await self._get_total_stars_for_link(link.id)
        return {
            "id": link.id,
            "student_id": student.id,
            "email": student.email,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "full_name": f"{student.first_name} {student.last_name or ''}".strip(),
            "subject": link.subject,
            "class_info": link.student_inf,
            "last_submission_id": sub_id,
            "last_submission_status": status_str,
            "star_rewards_enabled": link.star_rewards_enabled,
            "parent_contact_enabled": link.parent_contact_enabled,
            "star_goal": link.star_goal,
            "star_reward_title": link.star_reward_title,
            "earned_stars": earned_stars,
        }

    async def _build_gamification(self, link: TutorStudent) -> GamificationOut:
        homework_stars = await self._get_homework_stars_for_link(link.id)
        bonus_stars = await self._get_bonus_stars_for_link(link.id)
        tasks = await self.bonus_task_repo.get_for_tutor_student(link.id)
        student = link.student
        student_name = f"{student.first_name} {student.last_name or ''}".strip()
        return GamificationOut(
            tutor_student_id=link.id,
            student_id=student.id,
            student_name=student_name,
            star_rewards_enabled=link.star_rewards_enabled,
            star_goal=link.star_goal,
            star_reward_title=link.star_reward_title,
            homework_stars=homework_stars,
            bonus_stars=bonus_stars,
            earned_stars=homework_stars + bonus_stars,
            bonus_tasks=[self._bonus_task_to_schema(task) for task in tasks],
        )

    def _bonus_task_to_schema(self, task: BonusTask) -> BonusTaskOut:
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

    def _submission_to_schema(self, sub: LessonFile) -> SubmissionOut:
        lesson = sub.lesson
        student = lesson.tutor_student.student
        submissions = [
            item
            for item in sorted(lesson.lesson_files, key=lambda lesson_file: lesson_file.id)
            if item.kind == LessonFileKind.SUBMISSION
        ]
        submission_files = [
            self._file_to_schema(item.file) for item in submissions if item.file
        ]
        checked_files = [
            self._file_to_schema(item.checked_file)
            for item in submissions
            if item.checked_file
        ]
        return SubmissionOut(
            id=sub.id,
            student=f"{student.first_name} {student.last_name or ''}".strip(),
            star_rewards_enabled=lesson.tutor_student.star_rewards_enabled,
            lesson_date=lesson.l_date,
            lesson_topic=lesson.topic,
            file_url=sub.file.path if sub.file else None,
            file_name=sub.file.filename if sub.file else None,
            submission_files=submission_files,
            checked_file_url=sub.checked_file.path if sub.checked_file else None,
            checked_file_name=sub.checked_file.filename if sub.checked_file else None,
            checked_files=checked_files,
            status=sub.status.value if sub.status else "unknown",
            comment=sub.comment,
            student_comment=sub.student_comment,
            submitted_at=sub.created_at,
            homework_deadline=lesson.homework_deadline,
            homework_deadline_missed=sub.deadline_missed,
            grade=sub.grade,
            stars_awarded=sub.stars_awarded or 0,
        )


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
        materials, homework_task_files, submissions, parent_message_files = self._split_lesson_files(lesson)
        submission = submissions[0] if submissions else None
        student = lesson.tutor_student.student
        student_name = f"{student.first_name} {student.last_name or ''}".strip()
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
        return TutorLessonSummary(
            id=lesson.id,
            tutor_student_id=lesson.tutor_student_id,
            student_id=student.id,
            star_rewards_enabled=lesson.tutor_student.star_rewards_enabled,
            student_name=student_name,
            date=lesson.l_date,
            time=lesson.l_time,
            subject=lesson.subject,
            topic=lesson.topic,
            meet_link=lesson.meet_link,
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
            homework_done=lesson.homework_done,
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

    def _build_lesson_detail(self, lesson: Lesson) -> TutorLessonDetail:
        materials, homework_task_files, submissions, parent_message_files = self._split_lesson_files(lesson)
        submission = submissions[0] if submissions else None
        student = lesson.tutor_student.student
        student_name = f"{student.first_name} {student.last_name or ''}".strip()
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
        return TutorLessonDetail(
            id=lesson.id,
            tutor_student_id=lesson.tutor_student_id,
            student_id=student.id,
            star_rewards_enabled=lesson.tutor_student.star_rewards_enabled,
            student_name=student_name,
            date=lesson.l_date,
            time=lesson.l_time,
            subject=lesson.subject,
            topic=lesson.topic,
            meet_link=lesson.meet_link,
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
            homework_done=lesson.homework_done,
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

    def _build_lesson_progress_item(
        self,
        lesson: Lesson,
        *,
        sequence_number: int,
        progress_status: str,
    ) -> TutorLessonProgressItem:
        materials, homework_task_files, submissions, _ = self._split_lesson_files(lesson)
        submission = submissions[0] if submissions else None
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
