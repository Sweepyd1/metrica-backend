from fastapi import APIRouter, Depends, Query

from api.dependencies import get_current_parent, get_parent_service
from core.service.parent import ParentService
from database.models import User
from schemas.parent import (
    ParentChildAdd,
    ParentChildOut,
    ParentLessonDetail,
    ParentLessonListOut,
)

router = APIRouter(prefix="/parent", tags=["parent"])


@router.post("/children", response_model=ParentChildOut)
async def add_child(
    data: ParentChildAdd,
    parent: User = Depends(get_current_parent),
    service: ParentService = Depends(get_parent_service),
):
    return await service.add_child(parent.id, data.email)


@router.get("/children", response_model=list[ParentChildOut])
async def list_children(
    parent: User = Depends(get_current_parent),
    service: ParentService = Depends(get_parent_service),
):
    return await service.get_children(parent.id)


@router.get("/lessons", response_model=ParentLessonListOut)
async def list_lessons(
    student_id: int | None = Query(default=None),
    parent: User = Depends(get_current_parent),
    service: ParentService = Depends(get_parent_service),
):
    return await service.get_lessons(parent.id, student_id)


@router.get("/lessons/{lesson_id}", response_model=ParentLessonDetail)
async def lesson_detail(
    lesson_id: int,
    parent: User = Depends(get_current_parent),
    service: ParentService = Depends(get_parent_service),
):
    return await service.get_lesson_detail(parent.id, lesson_id)
