import os
import shutil
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from api.dependencies import get_current_student, get_student_service
from core.service.student import StudentService
from database.models import User
from schemas.student import (
    HomeworkSubmissionOut,
    StudentLessonDetail,
    StudentLessonListOut,
)

router = APIRouter(prefix="/student", tags=["student"])

ALLOWED_HOMEWORK_TYPES = {"application/pdf", "image/jpeg", "image/jpg"}


@router.get("/lessons", response_model=StudentLessonListOut)
async def list_lessons(
    student: User = Depends(get_current_student),
    service: StudentService = Depends(get_student_service),
):
    return await service.get_my_lessons(student.id)


@router.get("/lessons/{lesson_id}", response_model=StudentLessonDetail)
async def lesson_detail(
    lesson_id: int,
    student: User = Depends(get_current_student),
    service: StudentService = Depends(get_student_service),
):
    return await service.get_lesson_detail(student.id, lesson_id)


@router.post(
    "/lessons/{lesson_id}/submit-homework",
    response_model=HomeworkSubmissionOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit_homework(
    lesson_id: int,
    file: UploadFile = File(...),
    student: User = Depends(get_current_student),
    service: StudentService = Depends(get_student_service),
):
    if file.content_type not in ALLOWED_HOMEWORK_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and JPEG files are allowed",
        )

    await service.get_lesson_detail(student.id, lesson_id)

    os.makedirs("uploads", exist_ok=True)
    original_filename = os.path.basename(file.filename or "homework")
    saved_filename = f"{student.id}_{uuid4().hex}_{original_filename}"
    file_path = os.path.join("uploads", saved_filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return await service.submit_homework(
        student_id=student.id,
        lesson_id=lesson_id,
        file_path=file_path,
        filename=original_filename,
        content_type=file.content_type,
    )
