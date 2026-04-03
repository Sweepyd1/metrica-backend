import datetime as dt
import os
import shutil
from typing import List

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from src.api.dependencies import get_current_tutor, get_db_session, get_tutor_service
from src.core.service.tutor import TutorService
from src.schemas.tutor import (
    StudentAdd,
    StudentOut,
    LessonCreate,
    LessonUpdate,
    TutorLessonDetail,
    TutorLessonListOut,
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
        last_submission_id=None,
        last_submission_status="none",
    )


@router.get("/students", response_model=List[StudentOut])
async def list_students(
    tutor: User = Depends(get_current_tutor),
    service: TutorService = Depends(get_tutor_service),
):
    return await service.get_my_students(tutor.id)


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
