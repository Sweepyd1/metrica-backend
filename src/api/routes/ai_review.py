from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ai_checker.integration import (
    get_ai_review_history,
    get_ai_review_progress,
    get_ai_review_state,
    run_ai_review,
    start_ai_review,
)
from ai_checker.schemas import AiHomeworkHistoryItemOut, AiProgressReportOut, AiReviewStateOut
from api.dependencies import get_current_tutor, get_db_session
from database.models import User


router = APIRouter(prefix="/tutor", tags=["ai-homework-review"])


@router.get(
    "/lessons/{lesson_id}/ai-review",
    response_model=AiReviewStateOut,
)
async def ai_review_state(
    lesson_id: int,
    tutor: User = Depends(get_current_tutor),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await get_ai_review_state(session, tutor.id, lesson_id)
    except LookupError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error


@router.get(
    "/lessons/{lesson_id}/ai-history",
    response_model=list[AiHomeworkHistoryItemOut],
)
async def ai_review_history(
    lesson_id: int,
    tutor: User = Depends(get_current_tutor),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await get_ai_review_history(session, tutor.id, lesson_id)
    except LookupError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error


@router.get(
    "/lessons/{lesson_id}/ai-progress",
    response_model=AiProgressReportOut,
)
async def ai_review_progress(
    lesson_id: int,
    tutor: User = Depends(get_current_tutor),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await get_ai_review_progress(session, tutor.id, lesson_id)
    except LookupError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(error)) from error


@router.post(
    "/lessons/{lesson_id}/ai-review",
    response_model=AiReviewStateOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_ai_review(
    lesson_id: int,
    background_tasks: BackgroundTasks,
    tutor: User = Depends(get_current_tutor),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        review = await start_ai_review(session, tutor.id, lesson_id)
    except LookupError as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    except ValueError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    except PermissionError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error

    if review.status == "pending" and review.id is not None:
        background_tasks.add_task(run_ai_review, review.id)
    return review
