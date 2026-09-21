import logging
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.db_manager import db_manager
from database.models import (
    AiHomeworkReview,
    AiHomeworkTask,
    AiProgressReportCache,
    AiReviewStatus,
    Lesson,
    LessonFile,
    LessonFileKind,
    TutorStudent,
    User,
)

from .provider import analyze_progress_openai_compat, review_homework_openai_compat
from .schemas import (
    AiHomeworkHistoryItemOut,
    AiHomeworkResult,
    AiProgressReportOut,
    AiReviewStateOut,
)
from .taxonomy import DAILY_TASK_LIMIT, PROGRESS_REPORT_THRESHOLD, TASK_TYPE_LABELS


logger = logging.getLogger(__name__)
MOSCOW_TIMEZONE = ZoneInfo("Europe/Moscow")
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif"}
MEDIA_TYPE_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".heic": "image/heic",
    ".heif": "image/heif",
}


def _now_utc_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _usage_date():
    return datetime.now(MOSCOW_TIMEZONE).date()


def _is_supported_image(lesson_file: LessonFile) -> bool:
    if not lesson_file.file:
        return False
    suffix = Path(lesson_file.file.filename or lesson_file.file.path or "").suffix.lower()
    media_type = (lesson_file.file.type or "").lower().split(";", 1)[0]
    return suffix in SUPPORTED_SUFFIXES or media_type in MEDIA_TYPE_BY_SUFFIX.values()


def _media_type(lesson_file: LessonFile) -> str:
    suffix = Path(lesson_file.file.filename or lesson_file.file.path or "").suffix.lower()
    if suffix in MEDIA_TYPE_BY_SUFFIX:
        return MEDIA_TYPE_BY_SUFFIX[suffix]
    guessed = mimetypes.guess_type(lesson_file.file.filename or "")[0]
    return guessed or lesson_file.file.type or "application/octet-stream"


def _read_image(lesson_file: LessonFile) -> tuple[bytes, str]:
    if not lesson_file.file or not lesson_file.file.path:
        raise ValueError("У файла отсутствует путь.")
    uploads_root = Path("uploads").resolve()
    file_path = Path(lesson_file.file.path).resolve()
    if not file_path.is_relative_to(uploads_root) or not file_path.is_file():
        raise ValueError("Файл решения недоступен.")
    return file_path.read_bytes(), _media_type(lesson_file)


async def _get_lesson_for_tutor(
    session: AsyncSession, tutor_id: int, lesson_id: int
) -> Lesson | None:
    result = await session.execute(
        select(Lesson)
        .join(TutorStudent, Lesson.tutor_student_id == TutorStudent.id)
        .where(Lesson.id == lesson_id, TutorStudent.tutor_id == tutor_id)
        .options(
            selectinload(Lesson.tutor_student),
            selectinload(Lesson.lesson_files).selectinload(LessonFile.file),
        )
    )
    return result.scalar_one_or_none()


async def _has_daily_review(session: AsyncSession, student_id: int) -> bool:
    result = await session.execute(
        select(func.count(AiHomeworkReview.id)).where(
            AiHomeworkReview.student_id == student_id,
            AiHomeworkReview.usage_date == _usage_date(),
            AiHomeworkReview.status.in_(
                [
                    AiReviewStatus.PENDING,
                    AiReviewStatus.RUNNING,
                    AiReviewStatus.COMPLETED,
                ]
            ),
        )
    )
    return int(result.scalar_one()) > 0


def _to_state(review: AiHomeworkReview, *, available: bool = True) -> AiReviewStateOut:
    result = (
        AiHomeworkResult.model_validate(review.result_json)
        if review.result_json is not None
        else None
    )
    return AiReviewStateOut(
        id=review.id,
        lesson_id=review.lesson_id,
        status=review.status.value,
        available=available,
        result=result,
        error_message=review.error_message,
    )


async def get_ai_review_state(
    session: AsyncSession, tutor_id: int, lesson_id: int
) -> AiReviewStateOut:
    lesson = await _get_lesson_for_tutor(session, tutor_id, lesson_id)
    if lesson is None:
        raise LookupError("Домашнее задание не найдено.")

    existing = await session.scalar(
        select(AiHomeworkReview).where(AiHomeworkReview.lesson_id == lesson_id)
    )
    if existing is not None:
        available = True
        if existing.status == AiReviewStatus.FAILED:
            available = not await _has_daily_review(
                session, lesson.tutor_student.student_id
            )
        return _to_state(existing, available=available)

    has_solution_image = any(
        item.kind == LessonFileKind.SUBMISSION and _is_supported_image(item)
        for item in lesson.lesson_files
    )
    daily_review_exists = await _has_daily_review(
        session, lesson.tutor_student.student_id
    )
    return AiReviewStateOut(
        lesson_id=lesson_id,
        status="not_started",
        available=has_solution_image and not daily_review_exists,
    )


async def _ordered_completed_reviews(
    session: AsyncSession, *, student_id: int, tutor_id: int
) -> list[AiHomeworkReview]:
    reviews_result = await session.execute(
        select(AiHomeworkReview)
        .where(
            AiHomeworkReview.student_id == student_id,
            AiHomeworkReview.tutor_id == tutor_id,
            AiHomeworkReview.status == AiReviewStatus.COMPLETED,
        )
        .options(selectinload(AiHomeworkReview.tasks))
        .order_by(AiHomeworkReview.completed_at, AiHomeworkReview.id)
    )
    return list(reviews_result.scalars().all())


def _compute_homework_label(index: int, tasks: list[AiHomeworkTask]) -> str:
    present = {task_type for task in tasks for task_type in (task.task_types or [])}
    ordered = [label for key, label in TASK_TYPE_LABELS.items() if key in present]
    if not ordered:
        ordered = [TASK_TYPE_LABELS["other"]]
    return f"дз{index}: {'+'.join(ordered)}"


async def get_ai_review_history(
    session: AsyncSession, tutor_id: int, lesson_id: int
) -> list[AiHomeworkHistoryItemOut]:
    lesson = await _get_lesson_for_tutor(session, tutor_id, lesson_id)
    if lesson is None:
        raise LookupError("Домашнее задание не найдено.")

    reviews = await _ordered_completed_reviews(
        session, student_id=lesson.tutor_student.student_id, tutor_id=tutor_id
    )
    return [
        AiHomeworkHistoryItemOut(
            homework_number=index,
            homework_label=_compute_homework_label(index, review.tasks),
            created_at=(review.completed_at or review.created_at).isoformat(),
        )
        for index, review in enumerate(reviews, start=1)
    ]


async def get_ai_review_progress(
    session: AsyncSession, tutor_id: int, lesson_id: int
) -> AiProgressReportOut:
    lesson = await _get_lesson_for_tutor(session, tutor_id, lesson_id)
    if lesson is None:
        raise LookupError("Домашнее задание не найдено.")

    student_id = lesson.tutor_student.student_id
    reviews = await _ordered_completed_reviews(
        session, student_id=student_id, tutor_id=tutor_id
    )
    if not reviews:
        raise LookupError("У этого ученика пока нет проверенных ИИ домашних заданий.")

    homework_count = len(reviews)
    threshold_reached = homework_count >= PROGRESS_REPORT_THRESHOLD

    cached = await session.scalar(
        select(AiProgressReportCache).where(
            AiProgressReportCache.student_id == student_id,
            AiProgressReportCache.up_to_homework_count == homework_count,
        )
    )
    if cached is not None:
        return AiProgressReportOut.model_validate(cached.report_json)

    errors: list[dict] = []
    for index, review in enumerate(reviews, start=1):
        homework_label = _compute_homework_label(index, review.tasks)
        for task in review.tasks:
            for error in task.errors or []:
                errors.append(
                    {
                        "topic": error.get("topic", ""),
                        "severity": error.get("severity", ""),
                        "explanation": error.get("explanation", ""),
                        "homework_label": homework_label,
                    }
                )

    llm_result = await analyze_progress_openai_compat(errors)
    report = AiProgressReportOut(
        homework_count=homework_count,
        threshold_reached=threshold_reached,
        **llm_result.model_dump(),
    )

    insert_stmt = pg_insert(AiProgressReportCache).values(
        student_id=student_id,
        up_to_homework_count=homework_count,
        report_json=report.model_dump(mode="json"),
    )
    upsert_stmt = insert_stmt.on_conflict_do_update(
        constraint="uq_ai_progress_student_upto",
        set_={"report_json": insert_stmt.excluded.report_json},
    )
    await session.execute(upsert_stmt)
    await session.commit()

    return report


async def start_ai_review(
    session: AsyncSession, tutor_id: int, lesson_id: int
) -> AiReviewStateOut:
    lesson = await _get_lesson_for_tutor(session, tutor_id, lesson_id)
    if lesson is None:
        raise LookupError("Домашнее задание не найдено.")

    student_id = lesson.tutor_student.student_id
    await session.execute(select(User).where(User.id == student_id).with_for_update())
    existing = await session.scalar(
        select(AiHomeworkReview).where(AiHomeworkReview.lesson_id == lesson_id)
    )
    if existing is not None and existing.status != AiReviewStatus.FAILED:
        return _to_state(existing)

    has_solution_image = any(
        item.kind == LessonFileKind.SUBMISSION and _is_supported_image(item)
        for item in lesson.lesson_files
    )
    if not has_solution_image:
        raise ValueError("В решении ученика нет изображения для ИИ-проверки.")

    if await _has_daily_review(session, student_id):
        raise PermissionError("ИИ-проверка для этого ученика сегодня недоступна.")

    provider = os.getenv("AI_PROVIDER", "openai_compat")
    model = os.getenv("AI_CHECKER_MODEL", "google/gemma-4-26b-a4b-it")
    if existing is None:
        existing = AiHomeworkReview(
            lesson_id=lesson_id,
            tutor_id=tutor_id,
            student_id=student_id,
            status=AiReviewStatus.PENDING,
            mode="school",
            provider=provider,
            model=model,
            usage_date=_usage_date(),
            reserved_task_count=DAILY_TASK_LIMIT,
        )
        session.add(existing)
    else:
        existing.status = AiReviewStatus.PENDING
        existing.error_message = None
        existing.usage_date = _usage_date()
        existing.reserved_task_count = DAILY_TASK_LIMIT
        existing.provider = provider
        existing.model = model

    await session.commit()
    await session.refresh(existing)
    return _to_state(existing)


async def run_ai_review(review_id: int) -> None:
    try:
        async with db_manager.get_session() as session:
            review = await session.get(AiHomeworkReview, review_id)
            if review is None or review.status != AiReviewStatus.PENDING:
                return
            review.status = AiReviewStatus.RUNNING
            review.started_at = _now_utc_naive()
            await session.commit()

            result = await session.execute(
                select(LessonFile)
                .where(LessonFile.lesson_id == review.lesson_id)
                .options(selectinload(LessonFile.file))
                .order_by(LessonFile.id)
            )
            lesson_files = list(result.scalars().all())
            task_limit = review.reserved_task_count

        solution_images = [
            _read_image(item)
            for item in lesson_files
            if item.kind == LessonFileKind.SUBMISSION and _is_supported_image(item)
        ]
        task_images = [
            _read_image(item)
            for item in lesson_files
            if item.kind == LessonFileKind.HOMEWORK_TASK and _is_supported_image(item)
        ]
        ai_result = await review_homework_openai_compat(
            solution_images,
            task_images=task_images,
            max_tasks=task_limit,
        )

        async with db_manager.get_session() as session:
            review = await session.get(AiHomeworkReview, review_id)
            if review is None:
                return
            review.status = AiReviewStatus.COMPLETED
            review.task_count = len(ai_result.tasks)
            review.reserved_task_count = DAILY_TASK_LIMIT
            review.result_json = ai_result.model_dump(mode="json")
            review.error_message = None
            review.completed_at = _now_utc_naive()

            for position, task in enumerate(ai_result.tasks, start=1):
                topic_groups = list(
                    dict.fromkeys(
                        [TASK_TYPE_LABELS.get(item, TASK_TYPE_LABELS["other"]) for item in task.task_types]
                        + [error.topic for error in task.errors]
                    )
                )
                session.add(
                    AiHomeworkTask(
                        review_id=review.id,
                        position=position,
                        task_label=task.task_label,
                        transcription=task.transcription,
                        is_correct=task.is_correct,
                        task_types=list(task.task_types),
                        topic_groups=topic_groups,
                        errors=[error.model_dump(mode="json") for error in task.errors],
                    )
                )
            await session.commit()
    except Exception:
        logger.exception("Не удалось выполнить ИИ-проверку %s", review_id)
        async with db_manager.get_session() as session:
            review = await session.get(AiHomeworkReview, review_id)
            if review is not None and review.status != AiReviewStatus.COMPLETED:
                review.status = AiReviewStatus.FAILED
                review.reserved_task_count = 0
                review.error_message = "Не удалось выполнить ИИ-проверку. Попробуйте позже."
                review.completed_at = _now_utc_naive()
                await session.commit()
