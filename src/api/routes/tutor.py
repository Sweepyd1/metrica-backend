import datetime as dt
import os
import shutil
from typing import List

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from src.api.dependencies import get_current_tutor, get_db_session, get_tutor_service
from src.core.service.tutor import TutorService
from src.schemas.group import GroupCreate, GroupDetailOut, GroupOut, GroupStudentsUpdate
from src.schemas.tutor import (
    StudentAdd,
    StudentOut,
    LessonCreate,
    LessonUpdate,
    StarTransactionCreate,
    StarTransactionOut,
    TutorLessonDetail,
    TutorLessonListOut,
    TutorLessonProgressTreeOut,
    TutorStudentStarsOut,
    LessonOut,
    SubmissionOut,
    SubmissionCheck,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User
from src.core.repositories.file import FileRepository

router = APIRouter(prefix="/tutor", tags=["tutor"])


def to_lesson_out(lesson) -> LessonOut:
    return LessonOut(
        id=lesson.id,
        tutor_student_id=lesson.tutor_student_id,
        date=lesson.l_date,
        time=lesson.l_time,
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
        full_name=f"{student.first_name} {student.last_name or ''}",
        subject=link.subject,
        class_info=link.student_inf,
        star_balance=link.star_balance,
        last_submission_id=None,
        last_submission_status="none",
    )


@router.get("/students", response_model=List[StudentOut])
async def list_students(
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.get_my_students(tutor.id)


@router.get(
    "/students/{tutor_student_id}/progress-tree",
    response_model=TutorLessonProgressTreeOut,
)
async def student_progress_tree(
    tutor_student_id: int,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.get_student_progress_tree(tutor.id, tutor_student_id)


@router.get(
    "/students/{tutor_student_id}/stars",
    response_model=TutorStudentStarsOut,
)
async def student_stars(
    tutor_student_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.get_student_stars(
        tutor.id, tutor_student_id=tutor_student_id, limit=limit
    )


@router.post(
    "/students/{tutor_student_id}/stars/accrue",
    response_model=StarTransactionOut,
    status_code=status.HTTP_201_CREATED,
)
async def accrue_student_stars(
    tutor_student_id: int,
    data: StarTransactionCreate,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.accrue_stars(tutor.id, tutor_student_id, data)


@router.post(
    "/students/{tutor_student_id}/stars/write-off",
    response_model=StarTransactionOut,
    status_code=status.HTTP_201_CREATED,
)
async def write_off_student_stars(
    tutor_student_id: int,
    data: StarTransactionCreate,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.write_off_stars(tutor.id, tutor_student_id, data)


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


@router.get("/submissions/pending", response_model=List[SubmissionOut])
async def pending_submissions(
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.get_pending_submissions(tutor.id)


@router.post("/submissions/{submission_id}/check", response_model=SubmissionOut)
async def check_submission(
    submission_id: int,
    check_data: SubmissionCheck,
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    sub = await service.check_submission(tutor.id, submission_id, check_data.comment)
    lesson = sub.lesson
    student = lesson.tutor_student.student
    return SubmissionOut(
        id=sub.id,
        student=f"{student.first_name} {student.last_name or ''}",
        lesson_date=lesson.l_date,
        lesson_topic=lesson.topic,
        file_url=sub.file.path if sub.file else None,
        status=sub.status.value,
        comment=sub.comment,
    )


# Загрузка файла (перед созданием занятия)
@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    tutor: User = Depends(get_current_tutor),
    db: AsyncSession = Depends(get_db_session),
):
    # Сохраняем файл на диск
    file_path = f"uploads/{tutor.id}_{file.filename}"
    os.makedirs("uploads", exist_ok=True)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    # Создаём запись в БД
    file_repo = FileRepository(db)
    db_file = await file_repo.create(
        path=file_path,
        filename=file.filename,
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
