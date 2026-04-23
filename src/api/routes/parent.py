from typing import List

from fastapi import APIRouter, Depends, Query, status

from src.api.dependencies import (
    get_current_parent,
    get_parent_service,
)
from src.core.service.parent import ParentService
from src.database.models import User
from src.schemas.parent import (
    ParentAccessOut,
    ParentAccessRequestCreate,
    ParentChatMessageCreate,
    ParentChatMessageOut,
    ParentAccessStatus,
    ParentLessonDetail,
    ParentLessonListOut,
)

router = APIRouter(prefix="/parent", tags=["parent"])


@router.post(
    "/access-requests",
    response_model=ParentAccessOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_access_request(
    data: ParentAccessRequestCreate,
    parent: User = Depends(get_current_parent),
    service: ParentService = Depends(get_parent_service),
):
    return await service.create_access_request(parent.id, data)


@router.get("/access-requests", response_model=List[ParentAccessOut])
async def list_access_requests(
    status_filter: ParentAccessStatus | None = Query(default=None, alias="status"),
    parent: User = Depends(get_current_parent),
    service: ParentService = Depends(get_parent_service),
):
    return await service.get_my_accesses(
        parent.id,
        status_filter=status_filter.value if status_filter else None,
    )


@router.get("/accesses/{access_id}/lessons", response_model=ParentLessonListOut)
async def list_access_lessons(
    access_id: int,
    parent: User = Depends(get_current_parent),
    service: ParentService = Depends(get_parent_service),
):
    return await service.get_access_lessons(parent.id, access_id)


@router.get(
    "/accesses/{access_id}/lessons/{lesson_id}",
    response_model=ParentLessonDetail,
)
async def access_lesson_detail(
    access_id: int,
    lesson_id: int,
    parent: User = Depends(get_current_parent),
    service: ParentService = Depends(get_parent_service),
):
    return await service.get_lesson_detail(parent.id, access_id, lesson_id)


@router.get(
    "/accesses/{access_id}/messages",
    response_model=List[ParentChatMessageOut],
)
async def list_chat_messages(
    access_id: int,
    parent: User = Depends(get_current_parent),
    service: ParentService = Depends(get_parent_service),
):
    return await service.get_chat_messages(parent.id, access_id)


@router.post(
    "/accesses/{access_id}/messages",
    response_model=ParentChatMessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_chat_message(
    access_id: int,
    data: ParentChatMessageCreate,
    parent: User = Depends(get_current_parent),
    service: ParentService = Depends(get_parent_service),
):
    return await service.send_chat_message(parent.id, access_id, data)
