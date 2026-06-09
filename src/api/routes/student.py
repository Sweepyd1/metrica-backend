import os
import shutil

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from src.api.dependencies import get_current_student, get_student_service
from src.core.files import build_upload_path, validate_upload_file
from src.core.service.student import StudentService
from src.database.models import User
from src.schemas.gamification import GamificationOut
from src.schemas.student import (
    HomeworkSubmissionOut,
    StudentLessonDetail,
    StudentLessonListOut,
)

router = APIRouter(prefix="/student", tags=["student"])


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


@router.get("/gamification", response_model=list[GamificationOut])
async def gamification(
    student: User = Depends(get_current_student),
    service: StudentService = Depends(get_student_service),
):
    return await service.get_gamification(student.id)


@router.post(
    "/lessons/{lesson_id}/submit-homework",
    response_model=HomeworkSubmissionOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit_homework(
    lesson_id: int,
    files: list[UploadFile] | None = File(default=None),
    file: UploadFile | None = File(default=None),
    existing_file_ids: list[int] | None = Form(default=None),
    comment: str | None = Form(default=None),
    student: User = Depends(get_current_student),
    service: StudentService = Depends(get_student_service),
):
    await service.get_lesson_detail(student.id, lesson_id)

    os.makedirs("uploads", exist_ok=True)
    uploaded_files = []
    if files:
        uploaded_files.extend(files)
    if file:
        uploaded_files.append(file)

    if not uploaded_files and not existing_file_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one file is required",
        )

    saved_files = []
    for uploaded_file in uploaded_files:
        original_filename = validate_upload_file(uploaded_file)
        file_path = build_upload_path(student.id, original_filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(uploaded_file.file, buffer)

        saved_files.append(
            (file_path, original_filename, uploaded_file.content_type)
        )

    return await service.submit_homework(
        student_id=student.id,
        lesson_id=lesson_id,
        uploaded_files=saved_files,
        existing_file_ids=existing_file_ids or [],
        student_comment=comment,
    )
