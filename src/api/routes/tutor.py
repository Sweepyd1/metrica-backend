import datetime as dt
import os
import shutil
from typing import List

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from api.dependencies import get_current_tutor, get_db_session, get_tutor_service
from core.files import build_upload_path, validate_upload_file
from core.service.tutor import TutorService
from schemas.gamification import (
    BonusTaskCreate,
    BonusTaskOut,
    BonusTaskUpdate,
    GamificationOut,
    GamificationSettingsUpdate,
)
from schemas.group import GroupCreate, GroupDetailOut, GroupOut, GroupStudentsUpdate
from schemas.tutor import (
    StudentAdd,
    StudentOut,
    TutorStudentUpdate,
    LessonCreate,
    LessonUpdate,
    TutorLessonDetail,
    TutorLessonListOut,
    LessonOut,
    SubmissionOut,
    SubmissionCheck,
    ParentLessonMessageUpdate,
)
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from core.repositories.file import FileRepository

router = APIRouter(prefix="/tutor", tags=["tutor"])


def to_lesson_out(lesson) -> LessonOut:
    return LessonOut(
        id=lesson.id,
        tutor_student_id=lesson.tutor_student_id,
        date=lesson.l_date,
        time=lesson.l_time,
        subject=lesson.subject,
        topic=lesson.topic,
        meet_link=lesson.meet_link,
        homework_done=lesson.homework_done,
        homework_deadline=lesson.homework_deadline,
    )


@router.post("/students", response_model=StudentOut)
async def add_student(
    data: StudentAdd,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    link = await service.add_student(tutor.id, data.email)
    student = link.student
    return StudentOut(
        id=link.id,
        student_id=student.id,
        email=student.email,
        first_name=student.first_name,
        last_name=student.last_name,
        full_name=f"{student.first_name} {student.last_name or ''}",
        subject=link.subject,
        class_info=link.student_inf,
        last_submission_id=None,
        last_submission_status="none",
        star_rewards_enabled=link.star_rewards_enabled,
        star_goal=link.star_goal,
        star_reward_title=link.star_reward_title,
        earned_stars=0,
    )


@router.get("/students", response_model=List[StudentOut])
async def list_students(
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.get_my_students(tutor.id)


@router.patch("/students/{tutor_student_id}", response_model=StudentOut)
async def update_student(
    tutor_student_id: int,
    data: TutorStudentUpdate,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.update_student(tutor.id, tutor_student_id, data)


@router.delete("/students/{tutor_student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student(
    tutor_student_id: int,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    await service.delete_student(tutor.id, tutor_student_id)


@router.post("/lessons", response_model=LessonOut)
async def create_lesson(
    data: LessonCreate,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    lesson = await service.create_lesson(tutor.id, data)
    return to_lesson_out(lesson)


@router.patch("/lessons/{lesson_id}", response_model=LessonOut)
@router.put("/lessons/{lesson_id}", response_model=LessonOut)
async def update_lesson(
    lesson_id: int,
    data: LessonUpdate,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    lesson = await service.update_lesson(tutor.id, lesson_id, data)
    return to_lesson_out(lesson)


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson(
    lesson_id: int,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    await service.delete_lesson(tutor.id, lesson_id)


@router.get("/lessons", response_model=TutorLessonListOut)
async def list_lessons(
    date_from: dt.date | None = Query(default=None),
    date_to: dt.date | None = Query(default=None),
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.get_my_lessons(
        tutor.id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/lessons/{lesson_id}", response_model=TutorLessonDetail)
async def lesson_detail(
    lesson_id: int,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.get_lesson_detail(tutor.id, lesson_id)


@router.post("/lessons/{lesson_id}/parent-message", response_model=TutorLessonDetail)
async def update_parent_lesson_message(
    lesson_id: int,
    data: ParentLessonMessageUpdate,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.update_parent_lesson_message(tutor.id, lesson_id, data)


@router.get("/submissions/pending", response_model=List[SubmissionOut])
async def pending_submissions(
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.get_pending_submissions(tutor.id)


@router.get("/submissions", response_model=List[SubmissionOut])
async def list_submissions(
    status_filter: str | None = Query(default=None, alias="status"),
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.get_submissions(tutor.id, status_filter)


@router.post("/submissions/{submission_id}/check", response_model=SubmissionOut)
async def check_submission(
    submission_id: int,
    check_data: SubmissionCheck,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.check_submission(tutor.id, submission_id, check_data)


@router.get(
    "/students/{tutor_student_id}/gamification",
    response_model=GamificationOut,
)
async def student_gamification(
    tutor_student_id: int,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.get_student_gamification(tutor.id, tutor_student_id)


@router.patch(
    "/students/{tutor_student_id}/gamification",
    response_model=GamificationOut,
)
async def update_student_gamification(
    tutor_student_id: int,
    data: GamificationSettingsUpdate,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.update_student_gamification(tutor.id, tutor_student_id, data)


@router.post(
    "/students/{tutor_student_id}/bonus-tasks",
    response_model=BonusTaskOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_bonus_task(
    tutor_student_id: int,
    data: BonusTaskCreate,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.create_bonus_task(tutor.id, tutor_student_id, data)


@router.patch("/bonus-tasks/{task_id}", response_model=BonusTaskOut)
async def update_bonus_task(
    task_id: int,
    data: BonusTaskUpdate,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.update_bonus_task(tutor.id, task_id, data)


# Загрузка файла (перед созданием занятия)
@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    tutor: User = Depends(get_current_tutor),
    db: AsyncSession = Depends(get_db_session),
):
    original_filename = validate_upload_file(file)
    file_path = build_upload_path(tutor.id, original_filename)
    os.makedirs("uploads", exist_ok=True)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    # Создаём запись в БД
    file_repo = FileRepository(db)
    db_file = await file_repo.create(
        path=file_path,
        filename=original_filename,
        type=file.content_type,
        uploaded_by=tutor.id,
    )
    return {"file_id": db_file.id}

@router.post("/groups", response_model=GroupOut)
async def create_group(
    data: GroupCreate,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.create_group(tutor.id, data)


@router.get("/groups", response_model=List[GroupOut])
async def list_groups(
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.get_my_groups(tutor.id)


@router.get("/groups/{group_id}", response_model=GroupDetailOut)
async def get_group(
    group_id: int,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.get_group_detail(tutor.id, group_id)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    await service.delete_group(tutor.id, group_id)


@router.post("/groups/{group_id}/students", response_model=GroupDetailOut)
async def add_students_to_group(
    group_id: int,
    data: GroupStudentsUpdate,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.add_students_to_group(tutor.id, group_id, data.student_ids)


@router.delete("/groups/{group_id}/students", response_model=GroupDetailOut)
async def remove_students_from_group(
    group_id: int,
    data: GroupStudentsUpdate,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.remove_students_from_group(tutor.id, group_id, data.student_ids)
