import datetime as dt
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class ParentAccessStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ParentChatSenderRole(str, Enum):
    PARENT = "parent"
    TUTOR = "tutor"


class ParentAccessRequestCreate(BaseModel):
    tutor_email: EmailStr
    student_email: EmailStr
    message: Optional[str] = None


class ParentAccessReview(BaseModel):
    comment: Optional[str] = None


class ParentAccessOut(BaseModel):
    id: int
    tutor_student_id: int
    status: ParentAccessStatus
    tutor_id: int
    tutor_name: str
    tutor_email: Optional[EmailStr] = None
    student_id: int
    student_name: str
    student_email: Optional[EmailStr] = None
    subject: Optional[str] = None
    class_info: Optional[str] = None
    request_message: Optional[str] = None
    review_comment: Optional[str] = None
    created_at: dt.datetime
    responded_at: Optional[dt.datetime] = None
    can_view_lessons: bool


class ParentLessonAttachmentOut(BaseModel):
    id: int
    filename: Optional[str] = None
    file_url: Optional[str] = None
    type: Optional[str] = None


class ParentLessonSummary(BaseModel):
    id: int
    access_id: int
    tutor_student_id: int
    student_id: int
    student_name: str
    tutor_id: int
    tutor_name: str
    date: Optional[dt.date] = None
    time: Optional[dt.time] = None
    topic: Optional[str] = None
    meet_link: Optional[str] = None
    materials: List[ParentLessonAttachmentOut] = Field(default_factory=list)
    homework_task_files: List[ParentLessonAttachmentOut] = Field(default_factory=list)
    homework_deadline: Optional[dt.date] = None
    homework_status: str


class ParentLessonListOut(BaseModel):
    access: ParentAccessOut
    upcoming: List[ParentLessonSummary] = Field(default_factory=list)
    past: List[ParentLessonSummary] = Field(default_factory=list)


class ParentLessonDetail(ParentLessonSummary):
    submission_file: Optional[ParentLessonAttachmentOut] = None
    submission_comment: Optional[str] = None


class TutorParentAccessRequestOut(BaseModel):
    id: int
    tutor_student_id: int
    status: ParentAccessStatus
    parent_id: int
    parent_name: str
    parent_email: Optional[EmailStr] = None
    student_id: int
    student_name: str
    request_message: Optional[str] = None
    review_comment: Optional[str] = None
    created_at: dt.datetime
    responded_at: Optional[dt.datetime] = None


class ParentChatMessageCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)


class ParentChatMessageOut(BaseModel):
    id: int
    access_id: int
    sender_id: int
    sender_role: ParentChatSenderRole
    sender_name: str
    text: str
    created_at: dt.datetime
